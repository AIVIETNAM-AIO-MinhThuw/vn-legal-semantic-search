"""Test công cụ sinh query (SPEC mục 5) hoàn toàn offline: client giả, đồng hồ/sleep giả, split giả trong thư mục tạm.
Không gọi mạng (socket bị chặn), không đọc dữ liệu thật, không tạo split, không ghi API key."""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.querygen import select as sel  # noqa: E402
from src.querygen import sets, variants as V  # noqa: E402
from src.querygen import text as T  # noqa: E402
from src.querygen.client import GeminiClient, GeminiRequestError, MissingApiKeyError  # noqa: E402
from src.querygen.generator import InvalidResponse, QueryGenerator, build_meta, load_prompt, parse_response, render_prompt  # noqa: E402
from src.querygen.io import JsonlStore, write_meta_once  # noqa: E402
from src.querygen.limits import RateLimiter, RateLimitError, RetryableError, call_with_retry  # noqa: E402

TEMPLATE = (ROOT / "prompts" / "query_generation.v0.draft.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("test không được gọi mạng")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


def _script():
    spec = importlib.util.spec_from_file_location("generate_queries", ROOT / "scripts" / "generate_queries.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_queries"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------- text ----------------
def test_syllables_nfc_lowercase_and_punctuation():
    import unicodedata
    s = unicodedata.normalize("NFD", "Mức PHẠT, vi-phạm (giao thông)!")
    assert T.syllables(s) == ["mức", "phạt", "vi", "phạm", "giao", "thông"]


def test_overlap_counts_distinct_query_syllables_present_in_article():
    # query có 6 âm tiết khác nhau, 4 có trong Điều -> 4/6; lặp âm tiết không tăng mẫu số
    assert T.overlap("mức phạt vi phạm giao thông mức", "Mức phạt đối với vi phạm hành chính") == pytest.approx(4 / 6)
    assert T.overlap("", "x") == 0.0


def test_article_text_excludes_document_name():
    assert T.article_text("Tiêu đề", "Nội dung") == "Tiêu đề\nNội dung"


def test_verbatim_copy_threshold_is_eight_syllables():
    art = "người nộp thuế phải kê khai đầy đủ thông tin theo quy định của pháp luật"
    eight = "người nộp thuế phải kê khai đầy đủ"  # 8 âm tiết liên tiếp
    assert len(T.syllables(eight)) == 8 and T.has_verbatim_copy(eight, art, 8)
    seven = "người nộp thuế phải kê khai đầy"
    assert len(T.syllables(seven)) == 7 and not T.has_verbatim_copy(seven, art, 8)
    assert T.has_verbatim_copy("hỏi: " + eight + " không", art, 8)
    assert not T.has_verbatim_copy("kê khai thuế", art, 8)


def test_reference_to_article_or_document_number_detected():
    assert T.refers_to_article_or_document_number("quy định tại Điều 5 là gì")
    assert T.refers_to_article_or_document_number("theo thông tư 05/2020/TT-BTC")
    assert T.refers_to_article_or_document_number("nghị định 12/NĐ-CP")
    assert not T.refers_to_article_or_document_number("mức phạt khi đi xe máy vượt đèn đỏ")


def test_excluded_titles_match_whole_phrase_ignoring_case_and_punctuation():
    ex = ["Hiệu lực thi hành", "Trách nhiệm thi hành", "Điều khoản thi hành", "Tổ chức thực hiện"]
    assert T.is_excluded_title("HIỆU LỰC THI HÀNH.", ex) and T.is_excluded_title("Tổ chức thực hiện", ex)
    assert not T.is_excluded_title("Hiệu lực của giấy phép", ex)


# ---------------- rate limit / retry (đồng hồ giả) ----------------
class FakeTime:
    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def clock(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


def test_rate_limiter_sliding_window_uses_fake_clock():
    ft = FakeTime()
    rl = RateLimiter(2, 10, clock=ft.clock, sleep=ft.sleep)
    assert rl.acquire() == 0 and rl.acquire() == 0
    ft.t = 3.0
    assert rl.acquire() == pytest.approx(7.0)  # chờ tới khi cuộc gọi đầu (t=0) rời cửa sổ 10 s
    assert ft.sleeps == [pytest.approx(7.0)] and ft.t == pytest.approx(10.0)
    with pytest.raises(ValueError):
        RateLimiter(0, 10)


def test_retry_exponential_backoff_and_retry_after_with_fake_sleep():
    ft, calls = FakeTime(), []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RateLimitError("429")
        if len(calls) == 2:
            raise RateLimitError("429", retry_after=7.5)
        if len(calls) == 3:
            raise RetryableError("lỗi tạm")
        return "ok"

    assert call_with_retry(flaky, max_attempts=5, base_delay=2, max_delay=60, sleep=ft.sleep) == "ok"
    assert ft.sleeps == [2, 7.5, 8]  # 2*2^0, retry_after, 2*2^2


def test_retry_caps_delay_stops_after_max_attempts_and_does_not_retry_other_errors():
    ft = FakeTime()
    n = []

    def always():
        n.append(1)
        raise RetryableError("x")

    with pytest.raises(RetryableError):
        call_with_retry(always, max_attempts=4, base_delay=10, max_delay=15, sleep=ft.sleep)
    assert len(n) == 4 and ft.sleeps == [10, 15, 15]
    with pytest.raises(KeyError):
        call_with_retry(lambda: (_ for _ in ()).throw(KeyError("k")), max_attempts=3, base_delay=1, max_delay=2, sleep=ft.sleep)


# ---------------- JSONL / resume ----------------
def test_jsonl_store_append_dedup_resume_and_partial_line(tmp_path):
    p = tmp_path / "o" / "q.jsonl"
    s = JsonlStore(p)
    assert s.append({"article_id": "a", "x": 1}) and not s.append({"article_id": "a", "x": 2})
    p.write_bytes(p.read_bytes() + b'{"article_id": "b", "tr')  # bị ngắt giữa chừng
    s2 = JsonlStore(p)
    assert s2.truncated_partial_line and "a" in s2 and "b" not in s2
    assert s2.append({"article_id": "b", "x": 3})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["article_id"] for l in lines] == ["a", "b"]


def test_meta_written_once(tmp_path):
    p = tmp_path / "m.json"
    assert write_meta_once(p, {"model": "m1"}) and not write_meta_once(p, {"model": "m2"})
    assert json.loads(p.read_text(encoding="utf-8"))["model"] == "m1"


# ---------------- generator với client giả ----------------
class FakeClient:
    """Trả về JSON hợp lệ cho các article_id trong prompt; có thể kịch bản hóa lỗi."""

    def __init__(self, script=None, skip_ids=()):
        self.script, self.calls, self.skip_ids = list(script or []), 0, set(skip_ids)

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.script:
            step = self.script.pop(0)
            if isinstance(step, Exception):
                raise step
            if step is not None:
                return step
        ids = [a["article_id"] for a in json.loads(prompt[prompt.rindex("[\n"):])]
        results = []
        for i in ids:
            if i in self.skip_ids:
                results.append({"article_id": i, "skip": True, "skip_reason": "không đặt được câu hỏi", "queries": None})
            else:
                results.append({"article_id": i, "skip": False, "skip_reason": None,
                                "queries": {"natural": f"câu hỏi đời thường về {i}", "scenario": f"tình huống liên quan {i}", "keyword": "từ khóa"}})
        return json.dumps({"results": results}, ensure_ascii=False)


def make_articles(n, prefix="d"):
    return [{"article_id": f"{prefix}{i:03d}_001", "doc_id": f"{prefix}{i:03d}", "title": f"Tiêu đề {i}", "body": f"nội dung điều số {i} về thuế", "domain": "Thuế"}
            for i in range(n)]


def make_gen(tmp_path, client, **kw):
    ft = kw.pop("ft", FakeTime())
    store = JsonlStore(tmp_path / "raw.jsonl")
    g = QueryGenerator(client, store, prompt_template=TEMPLATE, batch_size=kw.pop("batch_size", 10), max_attempts=kw.pop("max_attempts", 3),
                       base_delay=2, max_delay=30, verbatim_n=8, sleep=ft.sleep, errors_path=tmp_path / "err.jsonl", split="train", **kw)
    return g, store, ft


def test_batches_of_requested_size_and_records_have_three_types(tmp_path):
    c = FakeClient(skip_ids={"d003_001"})
    g, store, _ = make_gen(tmp_path, c)
    stats = g.run(make_articles(25))
    assert c.calls == 3 and stats["written"] == 25 and stats["requests"] == 3
    recs = store.read_all()
    r3 = next(r for r in recs if r["article_id"] == "d003_001")
    assert r3["skip"] and r3["queries"] == [] and r3["skip_reason"]
    ok = next(r for r in recs if r["article_id"] == "d004_001")
    assert [q["type"] for q in ok["queries"]] == ["natural", "scenario", "keyword"]
    q = ok["queries"][0]
    assert q["query_id"] == "d004_001::natural" and 0 <= q["overlap"] <= 1 and q["verbatim_copy"] is False


def test_batch_size_must_be_between_10_and_20(tmp_path):
    for bad in (9, 21):
        with pytest.raises(ValueError):
            make_gen(tmp_path, FakeClient(), batch_size=bad)


def test_rate_limit_then_success_uses_fake_sleep_and_no_real_wait(tmp_path):
    c = FakeClient(script=[RateLimitError("429"), RateLimitError("429", retry_after=5)])
    g, store, ft = make_gen(tmp_path, c)
    g.run(make_articles(10))
    assert ft.sleeps == [2, 5] and len(store.read_all()) == 10


def test_invalid_json_is_retried_and_recovers(tmp_path):
    c = FakeClient(script=["không phải JSON", json.dumps({"results": []}), None])
    g, store, ft = make_gen(tmp_path, c, max_attempts=4)
    g.run(make_articles(10))
    assert c.calls == 3 and len(store.read_all()) == 10


def test_batch_failing_all_attempts_writes_error_not_records_and_resumes_later(tmp_path):
    c = FakeClient(script=[RateLimitError("429")] * 3)
    g, store, _ = make_gen(tmp_path, c, max_attempts=3)
    stats = g.run(make_articles(10))
    assert stats["failed_batches"] == 1 and store.read_all() == []
    assert len(JsonlStore(tmp_path / "err.jsonl", key="batch_key").read_all()) == 1
    stats2 = g.run(make_articles(10))  # lần sau thử lại và thành công
    assert stats2["written"] == 10 and len(store.read_all()) == 10


def test_resume_does_not_request_or_duplicate_processed_articles(tmp_path):
    arts = make_articles(30)
    c1 = FakeClient()
    g1, store1, _ = make_gen(tmp_path, c1)
    g1.run(arts[:15])
    c2 = FakeClient()
    g2, store2, _ = make_gen(tmp_path, c2)  # mở lại cùng file
    stats = g2.run(arts)
    assert stats["skipped_existing"] == 15 and stats["written"] == 15 and c2.calls == 2
    ids = [r["article_id"] for r in JsonlStore(tmp_path / "raw.jsonl").read_all()]
    assert len(ids) == 30 == len(set(ids))
    g2.run(arts)
    assert c2.calls <= 2  # lần chạy thứ ba không gọi client
    assert len(JsonlStore(tmp_path / "raw.jsonl").read_all()) == 30


def test_limiter_is_called_per_request(tmp_path):
    ft = FakeTime()
    lim = RateLimiter(1, 60, clock=ft.clock, sleep=ft.sleep)
    g, _, _ = make_gen(tmp_path, FakeClient(), limiter=lim, ft=ft)
    g.run(make_articles(20))
    assert ft.sleeps == [60]  # yêu cầu thứ hai phải chờ hết cửa sổ (đồng hồ giả)


def test_flags_verbatim_overlap_and_reference_are_recorded(tmp_path):
    art = {"article_id": "x_001", "doc_id": "x", "title": "Kê khai", "body": "người nộp thuế phải kê khai đầy đủ thông tin theo quy định của pháp luật"}
    raw = json.dumps({"results": [{"article_id": "x_001", "skip": False, "skip_reason": None, "queries": {
        "natural": "người nộp thuế phải kê khai đầy đủ thông tin thì sao", "scenario": "theo Điều 5 tôi phải làm gì", "keyword": "kê khai"}}]})
    g, store, _ = make_gen(tmp_path, FakeClient(script=[raw]))
    g.run([art])
    r = next(r for r in store.read_all() if r["article_id"] == "x_001")
    nat, sc, kw = r["queries"]
    assert nat["verbatim_copy"] and sc["refers_to_article_or_document"] and not kw["verbatim_copy"]
    assert nat["overlap"] > 0.8 and kw["overlap"] == 1.0


@pytest.mark.parametrize("payload,msg", [
    ({"results": [{"article_id": "zzz", "skip": True}]}, "không được yêu cầu"),
    ({"results": []}, "thiếu"),
    ({"results": [{"article_id": "a", "skip": True}, {"article_id": "a", "skip": True}]}, "lặp"),
    ({"results": [{"article_id": "a", "queries": {"natural": "x", "scenario": "y"}}]}, "ba query"),
    ({"results": [{"article_id": "a", "queries": {"natural": "x", "scenario": "y", "keyword": "một hai ba bốn năm"}}]}, "1-4 từ"),
])
def test_parse_response_rejects_bad_schema(payload, msg):
    with pytest.raises(InvalidResponse) as e:
        parse_response(json.dumps(payload), ["a"])
    assert msg in str(e.value)


def test_prompt_is_draft_and_has_no_examples_or_ood_content():
    assert "BẢN NHÁP" in TEMPLATE and "CHƯA FREEZE" in TEMPLATE and "{{ARTICLES_JSON}}" in TEMPLATE
    assert "OOD" not in TEMPLATE and "ví dụ query" not in TEMPLATE.lower()
    rendered = render_prompt(TEMPLATE, make_articles(2))
    assert "{{ARTICLES_JSON}}" not in rendered and "d000_001" in rendered
    text, h = load_prompt(ROOT / "prompts" / "query_generation.v0.draft.md")
    assert len(h) == 64 and text == TEMPLATE


# ---------------- chọn Điều / split ----------------
def write_split(path, assign):
    members = {g: [g] for g in assign}
    path.write_text(json.dumps({"meta": {}, "splits": assign, "members": members}), encoding="utf-8")


def test_missing_split_gives_clear_error_and_creates_nothing(tmp_path):
    p = tmp_path / "data" / "splits.json"
    with pytest.raises(SystemExit) as e:
        sel.load_doc_splits(p)
    assert "Chưa có split" in str(e.value) and not p.exists() and not p.parent.exists()


def test_eligible_articles_respect_split_and_excluded_titles(tmp_path):
    p = tmp_path / "splits.json"
    write_split(p, {"d1": "train", "d2": "val"})
    arts = [{"article_id": "d1_001", "doc_id": "d1", "title": "Mức phạt", "body": "x"},
            {"article_id": "d1_002", "doc_id": "d1", "title": "Hiệu lực thi hành", "body": "x"},
            {"article_id": "d2_001", "doc_id": "d2", "title": "Mức phạt", "body": "x"}]
    docs = [{"doc_id": "d1", "linh_vuc": "Thuế"}, {"doc_id": "d2", "linh_vuc": "Thuế"}]
    ex = ["Hiệu lực thi hành"]
    got = sel.eligible_articles(arts, docs, sel.load_doc_splits(p), "train", ex)
    assert [a["article_id"] for a in got] == ["d1_001"] and got[0]["domain"] == "Thuế"


def test_stratified_sample_is_proportional_deterministic_and_exact():
    items = [{"article_id": f"a{i:03d}", "domain": "A"} for i in range(60)] + [{"article_id": f"b{i:03d}", "domain": "B"} for i in range(40)]
    s1, s2 = sel.stratified_sample(items, 10, 42), sel.stratified_sample(list(reversed(items)), 10, 42)
    assert s1 == s2 and len(s1) == 10
    assert sum(1 for a in s1 if a["domain"] == "A") == 6 and sum(1 for a in s1 if a["domain"] == "B") == 4
    assert sel.stratified_sample(items, 10, 43) != s1
    with pytest.raises(ValueError):
        sel.stratified_sample(items, 101, 1)


def test_assign_eval_types_exact_counts_and_seeded():
    ids = [f"a{i:03d}" for i in range(150)]
    t = sel.assign_eval_types(ids, 50, 42)
    from collections import Counter
    assert Counter(t.values()) == Counter({"natural": 50, "scenario": 50, "keyword": 50})
    assert t == sel.assign_eval_types(ids, 50, 42) and t != sel.assign_eval_types(ids, 50, 43)
    with pytest.raises(ValueError):
        sel.assign_eval_types(ids[:149], 50, 42)


# ---------------- lọc / ghép tập ----------------
def rec(aid, split, queries, skip=False):
    return {"article_id": aid, "doc_id": aid.split("_")[0], "split": split, "skip": skip, "skip_reason": None,
            "queries": [{"query_id": f"{aid}::{t}", "type": t, "text": t, "overlap": ov, "verbatim_copy": vb, "refers_to_article_or_document": rf}
                        for t, (ov, vb, rf) in queries.items()]}


def test_train_overlap_filter_boundary_and_undecided_operator():
    r = [rec("a_001", "train", {"natural": (0.8, False, False), "scenario": (0.81, False, False), "keyword": (0.79, False, False)})]
    kept_inc, why_inc = sets.filter_split(r, "train", 0.8, True)
    kept_exc, why_exc = sets.filter_split(r, "train", 0.8, False)
    assert {q["type"] for q in kept_inc} == {"keyword"} and {q["type"] for q in kept_exc} == {"natural", "keyword"}
    assert why_inc["high_overlap_train"] == 2 and why_exc["high_overlap_train"] == 1
    with pytest.raises(ValueError):
        sets.filter_split(r, "train", 0.8, None)  # chưa chốt "> hay >=": không tự đoán


def test_val_test_not_filtered_by_overlap_but_verbatim_and_refs_removed_everywhere():
    r = [rec("b_001", "val", {"natural": (0.95, False, False), "scenario": (0.2, True, False), "keyword": (0.3, False, True)})]
    kept, why = sets.filter_split(r, "val", 0.8, True)
    assert [q["type"] for q in kept] == ["natural"] and why["verbatim_copy"] == 1 and why["refers_to_article_or_document_number"] == 1
    with pytest.raises(ValueError):
        sets.filter_split(r, "test", 0.8, True)  # query val không thể vào tập test


# ---------------- biến thể (chỉ test) ----------------
def test_no_diacritic_removes_tone_marks_and_maps_d():
    assert V.strip_diacritics("Đường bộ: học tập, quản lý") == "Duong bo: hoc tap, quan ly"


def test_telex_keystrokes_matches_documented_example():
    assert "h" + V.telex_keystrokes("ọ") + "c" == "hojc"  # học -> hojc
    assert V.telex_keystrokes("ô") == "oo" and V.telex_keystrokes("ơ") == "ow" and V.telex_keystrokes("ộ") == "ooj" and V.telex_keystrokes("đ") == "dd"
    assert V.telex_keystrokes("a") is None


def test_typo_error_count_depends_on_length_and_is_deterministic():
    short, long_ = "học phí đại học", "hồ sơ xin cấp giấy phép lái xe mới nhất"
    t1, a1 = V.make_typo(short, "q1", 42)
    t1b, a1b = V.make_typo(short, "q1", 42)
    t2, a2 = V.make_typo(long_, "q2", 42)
    assert (t1, a1) == (t1b, a1b) and len(a1) == 1 and len(a2) == 2
    assert t1 != short and t2 != long_
    assert V.make_typo(short, "q1", 43)[0] != t1 or V.make_typo(short, "q1", 44)[0] != t1
    assert set(a1 + a2) <= set(V.ERROR_TYPES)


def test_typo_all_four_types_are_reachable_and_each_changes_text():
    seen = set()
    for i in range(300):
        _, applied = V.make_typo("học phí đại học", f"q{i}", 42)
        seen.update(applied)
    assert seen == set(V.ERROR_TYPES)


def test_typo_telex_falls_back_when_no_diacritics():
    for i in range(50):
        out, applied = V.make_typo("thue", f"q{i}", 1)
        assert "telex" not in applied and out != "thue"


def test_variants_only_for_test_and_share_qrels_but_never_training_or_pooling():
    tq = [{"query_id": "a_001::natural", "text": "học phí đại học bao nhiêu", "split": "test", "article_id": "a_001", "doc_id": "a"}]
    vs = V.make_variants(tq, 42)
    assert [v["variant_type"] for v in vs] == ["no_diacritic", "typo"]
    for v in vs:
        assert v["variant_of"] == "a_001::natural" and v["qrels_from"] == "a_001::natural"
        assert v["use_for_training"] is False and v["use_for_pooling"] is False and v["query_id"].startswith("a_001::natural::")
    assert vs[0]["text"] == "hoc phi dai hoc bao nhieu"
    for bad_split in ("train", "val", "ood"):
        with pytest.raises(ValueError):
            V.make_variants([{**tq[0], "split": bad_split}], 42)
    with pytest.raises(ValueError):
        V.make_variants([{**tq[0], "variant_of": "x"}], 42)  # không tạo biến thể từ biến thể
    assert V.make_variants(tq, 42) == vs  # xác định theo seed


def test_typo_sample_export_has_blank_reviewer_columns(tmp_path):
    tq = [{"query_id": f"a{i:03d}_001::natural", "text": f"học phí đại học số {i}", "split": "test", "article_id": f"a{i:03d}_001"} for i in range(40)]
    vs = V.make_variants(tq, 42)
    p = tmp_path / "sample.csv"
    n = V.export_typo_sample(vs, {q["query_id"]: q["text"] for q in tq}, 30, 42, p)
    import csv
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    assert n == 30 == len(rows) and all(r["meaning_changed(reviewer)"] == "" and r["reviewer"] == "" and r["date"] == "" for r in rows)
    assert {r["query_id"].split("::")[-1] for r in rows} == {"typo"}


# ---------------- CLI offline ----------------
def _tmp_cfgs(tmp_path, *, with_split=True, pinned=True):
    qcfg = yaml.safe_load((ROOT / "configs" / "querygen.yaml").read_text(encoding="utf-8"))
    dcfg = {"seed": 42, "split": {"output": str(tmp_path / "data" / "splits.json")}}
    arts = [{"article_id": f"d{i:02d}_001", "doc_id": f"d{i:02d}", "title": f"Tiêu đề {i}", "body": f"nội dung {i}"} for i in range(24)]
    docs = [{"doc_id": f"d{i:02d}", "linh_vuc": "Thuế"} for i in range(24)]
    (tmp_path / "arts.jsonl").write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in arts), encoding="utf-8")
    (tmp_path / "docs.jsonl").write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for d in docs), encoding="utf-8")
    qcfg["paths"].update(articles=str(tmp_path / "arts.jsonl"), docs=str(tmp_path / "docs.jsonl"), out_dir=str(tmp_path / "runs"))
    qcfg["prompt"]["path"] = str(ROOT / "prompts" / "query_generation.v0.draft.md")
    if pinned:
        qcfg["llm"].update(model="fake-model", temperature=0.2, generation_date="2000-01-01", rate_limit_calls=100)
    if with_split:
        (tmp_path / "data").mkdir()
        write_split(Path(dcfg["split"]["output"]), {f"d{i:02d}": "train" for i in range(24)})
    return dcfg, qcfg


def test_cli_generate_with_injected_fake_client_end_to_end(tmp_path):
    gq = _script()
    dcfg, qcfg = _tmp_cfgs(tmp_path)
    plan = {"split": "train", "article_ids": [f"d{i:02d}_001" for i in range(24)]}
    ft = FakeTime()
    stats = gq.cmd_generate(dcfg, qcfg, "train", plan, client=FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock)
    assert stats["written"] == 24 and stats["requests"] == 2
    out = tmp_path / "runs"
    assert json.loads((out / "queries_train.raw.meta.json").read_text(encoding="utf-8"))["mock"] is True
    assert len(JsonlStore(out / "queries_train.raw.jsonl").read_all()) == 24
    again = gq.cmd_generate(dcfg, qcfg, "train", plan, client=FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock)
    assert again["written"] == 0 and again["skipped_existing"] == 24


def test_cli_variants_subcommand_refuses_non_test_input(tmp_path):
    gq = _script()
    dcfg, qcfg = _tmp_cfgs(tmp_path)
    qpath = tmp_path / "q.jsonl"
    qpath.write_text(json.dumps({"query_id": "a::natural", "text": "x y", "split": "val", "article_id": "a"}) + "\n", encoding="utf-8")
    cfg_d, cfg_q = tmp_path / "d.yaml", tmp_path / "q.yaml"
    cfg_d.write_text(yaml.safe_dump(dcfg), encoding="utf-8")
    cfg_q.write_text(yaml.safe_dump(qcfg, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError):
        gq.main(["--data-config", str(cfg_d), "--query-config", str(cfg_q), "variants", "--queries", str(qpath), "--out", str(tmp_path / "v.jsonl")])
