"""Test split (SPEC 4.1, phương án B) và check_leakage (SPEC 4.3) chỉ bằng dữ liệu giả trong thư mục tạm.
Không đọc dữ liệu thật, không tạo/sửa data/splits.json. Test đạt không có nghĩa corpus đã được duyệt."""
from __future__ import annotations

import importlib.util
import json
import random
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import splitting as S  # noqa: E402


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


R = {"train": 0.8, "val": 0.1, "test": 0.1}


def fams(spec):
    """spec: [(group_id, n_articles, domain)]"""
    return [{"group_id": g, "n_articles": a, "domain": d} for g, a, d in spec]


# ---------------- gom họ ----------------
def test_family_through_filtered_doc_and_dangling_node():
    edges = [("A", "X"), ("X", "B"),            # X là văn bản đã bị lọc (có trong metadata, không có trong corpus)
             ("C", "9999"), ("E", "9999"),      # 9999 là ID thiếu metadata: nút trung gian
             ("F", "G")]                        # G ngoài corpus; F là họ riêng với một văn bản corpus
    groups = S.build_families(edges, {"A", "B", "C", "E", "F", "H"})
    assert groups == {"A": ["A", "B"], "C": ["C", "E"], "F": ["F"], "H": ["H"]}


def test_family_group_id_is_min_doc_id_and_independent_of_edge_order():
    edges = [("b", "c"), ("c", "a"), ("a", "z9")]
    g1 = S.build_families(edges, {"a", "b", "c"})
    g2 = S.build_families(list(reversed(edges)), ["c", "b", "a"])
    assert g1 == g2 == {"a": ["a", "b", "c"]}


def test_family_without_corpus_member_is_dropped_and_null_id_is_error():
    assert S.build_families([("X", "Y")], {"Z"}) == {"Z": ["Z"]}
    with pytest.raises(ValueError):
        S.build_families([("A", None)], {"A"})
    with pytest.raises(ValueError):
        S.build_families([("A", "  ")], {"A"})
    with pytest.raises(ValueError):
        S.build_families([("A", float("nan"))], {"A"})


def test_family_unicode_order_for_group_id():
    # so sánh theo code point: "Z" (0x5A) < "a" (0x61)
    assert list(S.build_families([("a1", "Z1")], {"a1", "Z1"})) == ["Z1"]


# ---------------- chỉ tiêu ----------------
@pytest.mark.parametrize("n,expected", [(569, (455, 57, 57)), (10, (8, 1, 1)), (5, (4, 1, 0)), (3, (3, 0, 0)), (1, (1, 0, 0)), (0, (0, 0, 0))])
def test_quotas_largest_remainder_with_train_val_test_tie_order(n, expected):
    q = S.compute_quotas(n, {s: S.to_fraction(R[s]) for s in S.SPLITS})
    assert (q["train"], q["val"], q["test"]) == expected and sum(q.values()) == n


def test_ratio_must_sum_to_one():
    with pytest.raises(ValueError):
        S.compute_quotas(10, {"train": Fraction(1, 2), "val": Fraction(1, 5), "test": Fraction(1, 5)})


def test_threshold_is_exact_fraction_not_float():
    assert S.to_fraction(0.05) == Fraction(1, 20)


# ---------------- ngưỡng > 5% ----------------
def _spec_with_shares(shares, total=1000, domain="d"):
    out = [(f"g{i:02d}", int(total * s), domain) for i, s in enumerate(shares)]
    out.append(("rest", total - sum(a for _, a, _ in out), domain))
    return out


def test_threshold_exactly_five_percent_is_not_forced_but_above_is():
    n_other = 19
    spec = [("g00", 50, "d")] + [(f"h{i:02d}", 50, "d") for i in range(n_other)] + [("tail", 1000 - 50 * 20, "d")]
    assign, rep = S.allocate(fams(spec), R, 0.05, 42)
    assert rep["F"] == 0  # 50/1000 == 5% đúng bằng ngưỡng: không buộc
    spec[0] = ("g00", 51, "d")
    spec[-1] = ("tail", 1000 - 51 - 50 * 19, "d")
    assign, rep = S.allocate(fams(spec), R, 0.05, 42)
    assert rep["F"] == 1 and [f["group_id"] for f in rep["forced"]] == ["g00"] and assign["g00"] == "train"


def test_forced_family_counts_in_train_quota_and_rest_is_not_resplit():
    spec = [("big", 400, "d1")] + [(f"s{i:02d}", 10, "d1" if i % 2 else "d2") for i in range(29)]
    assign, rep = S.allocate(fams(spec), R, 0.05, 7)
    N = 30
    assert rep["Q"] == {"train": 24, "val": 3, "test": 3} and rep["F"] >= 1
    assert Counter(assign.values()) == Counter({"train": 24, "val": 3, "test": 3})
    assert rep["q"]["train"] == 24 - rep["F"] and rep["R"] == N - rep["F"]
    assert sum(rep["q"].values()) == rep["R"]


# ---------------- phân tầng và điều chỉnh tổng cột ----------------
def test_column_adjustment_tie_is_broken_by_domain_name_then_source_then_target():
    # q = (4,1,1), hai lĩnh vực mỗi nơi 3 họ: khởi tạo cho (2,1,0) ở cả hai, cột val thừa 1 / test thiếu 1;
    # hai phép chuyển cùng delta = 0 -> hòa, chọn lĩnh vực đứng trước theo Unicode ("d1"). Kết quả để d1 thiếu val nên
    # dừng (đúng luật); chẩn đoán vẫn ghi lại phép chuyển.
    spec = [(f"a{i}", 1, "d1") for i in range(3)] + [(f"b{i}", 1, "d2") for i in range(3)]
    with pytest.raises(S.StopSplit) as e:
        S.allocate(fams(spec), {"train": Fraction(2, 3), "val": Fraction(1, 6), "test": Fraction(1, 6)}, 1, 1)
    d = e.value.diag
    assert d["q"] == {"train": 4, "val": 1, "test": 1}
    assert d["x"]["d1"] == {"train": 2, "val": 0, "test": 1} and d["x"]["d2"] == {"train": 2, "val": 1, "test": 0}
    assert d["column_moves"] == [{"domain": "d1", "from": "val", "to": "test", "delta_sse": "0"}]
    assert d["domains_missing_in"] == {"val": ["d1"], "test": ["d2"]}


def test_column_adjustment_chooses_move_with_smallest_increase_of_squared_deviation():
    # 3 lĩnh vực (8, 8, 13 họ), N = 29 -> Q = (23, 3, 3). Tính tay: A, B khởi tạo (6,1,1); C (13 họ) khởi tạo (10,2,1);
    # cột (22, 4, 3): val thừa 1, train thiếu 1. Chuyển val->train: A/B tăng SSE ~0.98, C tăng ~0.06 -> chọn C.
    spec = [(f"{d}{i:02d}", 1, d) for d, n in zip("ABC", (8, 8, 13)) for i in range(n)]
    assign, rep = S.allocate(fams(spec), R, 1, 42)
    assert rep["Q"] == {"train": 23, "val": 3, "test": 3}
    assert rep["column_moves"] == [{"domain": "C", "from": "val", "to": "train", "delta_sse": rep["column_moves"][0]["delta_sse"]}]
    assert rep["x"] == {"A": {"train": 6, "val": 1, "test": 1}, "B": {"train": 6, "val": 1, "test": 1}, "C": {"train": 11, "val": 1, "test": 1}}
    assert Counter(assign.values()) == Counter({"train": 23, "val": 3, "test": 3})


def test_every_domain_row_and_column_sums_match():
    rnd = random.Random(1)
    spec = [(f"g{i:03d}", rnd.randint(1, 5), rnd.choice(["Ngân sách", "Thuế", "Lao động", "Đất đai"])) for i in range(200)]
    assign, rep = S.allocate(fams(spec), R, 0.05, 42)
    for d, row in rep["x"].items():
        assert sum(row.values()) == sum(1 for g, _, dd in spec if dd == d and g not in {f["group_id"] for f in rep["forced"]})
    for s in S.SPLITS:
        assert sum(row[s] for row in rep["x"].values()) == rep["q"][s]
    assert Counter(assign.values()) == Counter(rep["Q"])


# ---------------- tính xác định ----------------
def test_deterministic_for_same_seed_and_independent_of_input_order():
    rnd = random.Random(3)
    spec = [(f"g{i:03d}", rnd.randint(1, 9), rnd.choice(["a", "b", "c"])) for i in range(150)]
    a1, _ = S.allocate(fams(spec), R, 0.05, 42)
    shuffled = spec[:]
    random.Random(99).shuffle(shuffled)
    a2, _ = S.allocate(fams(shuffled), R, 0.05, 42)
    a3, _ = S.allocate(fams(spec), R, 0.05, 43)
    assert a1 == a2 and a1 != a3


def test_per_domain_rng_means_other_domain_changes_do_not_move_this_domain():
    base = [(f"a{i:02d}", 1, "A") for i in range(40)] + [(f"b{i:02d}", 1, "B") for i in range(40)]
    a1, r1 = S.allocate(fams(base), R, 1, 42)
    assert r1["x"]["A"] == r1["x"]["B"]  # cùng kích thước -> cùng phân bổ
    shuffled_a = {g: s for g, s in a1.items() if g.startswith("a")}
    a2, _ = S.allocate(fams([f for f in base]), R, 1, 42)
    assert {g: s for g, s in a2.items() if g.startswith("a")} == shuffled_a


# ---------------- điều kiện dừng ----------------
def test_stop_when_forced_exceeds_train_quota():
    spec = [(f"g{i}", 200, "d") for i in range(5)]  # mỗi họ 20% -> cả 5 họ bị buộc; Q_train = 4
    with pytest.raises(S.StopSplit) as e:
        S.allocate(fams(spec), R, 0.05, 42)
    assert e.value.diag["F"] == 5 and e.value.diag["Q"]["train"] == 4


def test_stop_when_domain_absent_from_val_or_test_and_never_merges_domains():
    spec = [(f"a{i:02d}", 10, "A") for i in range(9)] + [("b00", 10, "B")]
    with pytest.raises(S.StopSplit) as e:
        S.allocate(fams(spec), R, 0.5, 42)
    miss = e.value.diag["domains_missing_in"]
    assert "B" in miss["val"] + miss["test"] and set(e.value.diag["x"]) == {"A", "B"}


def test_stop_when_no_articles():
    with pytest.raises(S.StopSplit):
        S.allocate(fams([("g", 0, "d")]), R, 0.05, 42)


def test_dominant_domain_ties_use_unicode_order():
    assert S.dominant_domain(["Thuế", "Đất", "Thuế", "Đất"]) == "Thuế"  # "T" (0x54) < "Đ" (0x110)
    assert S.dominant_domain(["b", "a", "b"]) == "b"


# ---------------- CLI trên corpus giả ----------------
def _fake_corpus(tmp_path, n_docs=60):
    proc, raw = tmp_path / "proc", tmp_path / "raw"
    (raw / "data").mkdir(parents=True)
    proc.mkdir()
    domains = ["Thuế", "Ngân sách", "Lao động"]
    docs, arts, edges = [], [], []
    for i in range(n_docs):
        d = f"{i:03d}"
        docs.append({"doc_id": d, "linh_vuc": domains[i % 3]})
        for k in range(2 + (i % 3)):
            arts.append({"article_id": f"{d}_{k + 1:03d}", "doc_id": d, "body": f"nội dung {i} {k}", "content_sha1": f"h{i}-{k}",
                         "duplicate_article_ids": []})
    for i in range(0, n_docs - 1, 6):  # các cặp nối qua nút ID thiếu metadata
        edges.append((f"{i:03d}", f"missing-{i}"))
        edges.append((f"{i + 1:03d}", f"missing-{i}"))
    for name, rows in (("docs_index", docs), ("articles_index", arts)):
        (proc / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    labels = ["Thay thế"] * len(edges)
    pd.DataFrame({"doc_id": [a for a, _ in edges] + ["000"], "other_doc_id": [b for _, b in edges] + ["005"],
                  "relationship": labels + ["Căn cứ"]}).to_parquet(raw / "data" / "relationships.parquet")
    cfg = {"seed": 42, "dataset": {"files": {"relationships": "data/relationships.parquet"}},
           "paths": {"raw_dir": str(raw)}, "relations": {"mapping": {"Thay thế": "thay_the"}},
           "processed": {"dir": str(proc), "after_filter_dir": str(tmp_path / "reports")},
           "split": {"ratios": R, "output": str(tmp_path / "out" / "splits.json"), "force_train_article_share_gt": 0.05}}
    return cfg, docs, arts


def test_cli_refuses_without_approval_and_never_overwrites(tmp_path, monkeypatch):
    sp = _script("split")
    monkeypatch.setattr(sys, "argv", ["split.py", "--config", "x"])
    with pytest.raises(SystemExit) as e:
        sp.main()
    assert "Chưa chạy" in str(e.value)
    cfg, _, _ = _fake_corpus(tmp_path)
    sp.run(cfg, "người thử nghiệm")
    with pytest.raises(SystemExit):
        sp.run(cfg, "người thử nghiệm")  # không ghi đè splits.json


def test_cli_writes_valid_split_that_passes_leakage_check(tmp_path):
    sp, lk = _script("split"), _script("check_leakage")
    cfg, docs, arts = _fake_corpus(tmp_path)
    report = sp.run(cfg, "người thử nghiệm")
    obj, dups = lk.load_splits(Path(cfg["split"]["output"]))
    assert obj["meta"]["approved_by_corpus"] == "người thử nghiệm" and obj["meta"]["N"] == report["N"]
    # các cặp nối qua nút thiếu metadata nằm cùng họ -> cùng split
    gid = {d: g for g, ms in obj["members"].items() for d in ms}
    assert gid["000"] == gid["001"] and obj["splits"][gid["000"]] in S.SPLITS
    res = lk.check_leakage(obj, dups, docs, arts, [])
    assert res["ok"], res["errors"]
    assert sum(res["docs_per_split"].values()) == len(docs)
    # lặp lại -> cùng kết quả (tính xác định)
    cfg2, _, _ = _fake_corpus(tmp_path / "again")
    sp.run(cfg2, "người thử nghiệm")
    again = json.loads(Path(cfg2["split"]["output"]).read_text(encoding="utf-8"))
    assert again["splits"] == obj["splits"] and again["members"] == obj["members"]


def test_cli_stop_writes_only_diagnostic_report(tmp_path, monkeypatch):
    sp = _script("split")
    cfg, _, _ = _fake_corpus(tmp_path, n_docs=6)
    cfg["split"]["force_train_article_share_gt"] = 0.01  # buộc gần như mọi họ vào train
    cfgfile = tmp_path / "cfg.yaml"
    import yaml
    cfgfile.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["split.py", "--config", str(cfgfile), "--approved-by", "x"])
    with pytest.raises(SystemExit) as e:
        sp.main()
    assert e.value.code == 2
    assert not Path(cfg["split"]["output"]).exists()
    assert (tmp_path / "reports" / "split_stop_report.json").exists()


# ---------------- leakage ----------------
def _split_obj(assign, members):
    return {"splits": assign, "members": members}


def test_leakage_hash_check_is_on_index_articles_and_duplicates_spanning_splits_are_only_reported():
    # Quyết định Q2 (SPEC 4.3): chỉ kiểm tra chính trên Điều bản đại diện trong index; nhóm trùng bắt chéo split được báo riêng.
    lk = _script("check_leakage")
    docs = [{"doc_id": d} for d in ("a", "b", "c")]
    arts = [{"article_id": "a_001", "doc_id": "a", "body": "x", "content_sha1": "H1", "duplicate_article_ids": []},
            {"article_id": "b_001", "doc_id": "b", "body": "y", "content_sha1": "H2", "duplicate_article_ids": ["c_001"]},
            {"article_id": "c_002", "doc_id": "c", "body": "z", "content_sha1": "H3", "duplicate_article_ids": []}]
    obj = _split_obj({"a": "train", "b": "train", "c": "test"}, {"a": ["a"], "b": ["b"], "c": ["c"]})
    res = lk.check_leakage(obj, [], docs, arts, [])
    # bản đại diện b_001 (train) trùng nội dung với c_001 (test, đã bị loại khỏi index): không phải lỗi, nhưng được báo riêng
    assert res["ok"] and res["hash_overlap_index_only"]["train_test"] == 0
    assert res["duplicate_groups_spanning_splits"]["count"] == 1
    assert res["hash_overlap_including_removed_duplicates_info_only"]["train_test"] == 1
    clean = _split_obj({"a": "train", "b": "train", "c": "train"}, {"a": ["a"], "b": ["b"], "c": ["c"]})
    assert lk.check_leakage(clean, [], docs, arts, [])["ok"]
    assert lk.check_leakage(clean, [], docs, arts, [])["duplicate_groups_spanning_splits"]["count"] == 0


def test_leakage_fails_when_two_index_articles_in_train_and_test_share_a_hash():
    lk = _script("check_leakage")
    docs = [{"doc_id": d} for d in ("a", "b", "c")]
    arts = [{"article_id": "a_001", "doc_id": "a", "body": "x", "content_sha1": "SAME", "duplicate_article_ids": []},
            {"article_id": "b_001", "doc_id": "b", "body": "x", "content_sha1": "SAME", "duplicate_article_ids": []},
            {"article_id": "c_001", "doc_id": "c", "body": "w", "content_sha1": "OTHER", "duplicate_article_ids": []}]
    obj = _split_obj({"a": "train", "b": "val", "c": "test"}, {"a": ["a"], "b": ["b"], "c": ["c"]})
    res = lk.check_leakage(obj, [], docs, arts, [])
    assert not res["ok"] and res["hash_overlap_index_only"]["train_val"] == 1 and any("train∩val=1" in e for e in res["errors"])


def test_leakage_group_in_more_than_one_split_via_duplicate_json_keys(tmp_path):
    lk = _script("check_leakage")
    p = tmp_path / "s.json"
    p.write_text('{"splits": {"g1": "train", "g1": "val"}, "members": {"g1": ["a"]}}', encoding="utf-8")
    obj, dups = lk.load_splits(p)
    res = lk.check_leakage(obj, dups, [{"doc_id": "a"}], [], [])
    assert not res["ok"] and any("khóa lặp" in e for e in res["errors"])


def test_leakage_doc_in_two_groups_missing_and_invalid_split():
    lk = _script("check_leakage")
    docs = [{"doc_id": d} for d in ("a", "b")]
    obj = _split_obj({"g1": "train", "g2": "oops"}, {"g1": ["a"], "g2": ["a", "z"]})
    res = lk.check_leakage(obj, [], docs, [], [])
    msgs = " ".join(res["errors"])
    assert not res["ok"] and "hơn một họ" in msgs and "không hợp lệ" in msgs and "không thuộc họ nào" in msgs and "không có trong corpus" in msgs


def test_leakage_query_source_in_other_split_is_detected():
    lk = _script("check_leakage")
    docs = [{"doc_id": "a"}, {"doc_id": "b"}]
    arts = [{"article_id": "a_001", "doc_id": "a", "body": "x", "content_sha1": "H1"}, {"article_id": "b_001", "doc_id": "b", "body": "y", "content_sha1": "H2"}]
    obj = _split_obj({"a": "train", "b": "val"}, {"a": ["a"], "b": ["b"]})
    queries = [{"query_id": "q1", "split": "train", "source_article_id": "b_001"},
               {"query_id": "q2", "split": "val", "source_article_id": "b_001"},
               {"query_id": "q3", "split": "val", "source_article_id": "zzz_001"}]
    res = lk.check_leakage(obj, [], docs, arts, queries)
    assert not res["ok"] and [q["query_id"] for q in res["queries_with_other_split_source"]] == ["q1"] and res["queries_unknown_source"] == ["q3"]


def test_leakage_cli_reports_missing_split_clearly(tmp_path, monkeypatch):
    lk = _script("check_leakage")
    cfg, _, _ = _fake_corpus(tmp_path)
    import yaml
    cfgfile = tmp_path / "cfg.yaml"
    cfgfile.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_leakage.py", "--config", str(cfgfile)])
    with pytest.raises(SystemExit) as e:
        lk.main()
    assert "chưa chạy split" in str(e.value)
