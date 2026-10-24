"""Test chuẩn bị pilot (P0, nhóm duyệt 2026-10-24): keyword 1–6 âm tiết đọc từ config, lỗi theo từng Điều trong batch, dừng khi
hết retry 429, log lỗi chỉ ghi thêm, tóm tắt lượt chạy, báo cáo build-sets, dừng khi resume còn dưới 10 Điều.
Hoàn toàn offline: client giả, sleep giả, không gọi Gemini."""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import test_querygen as base  # noqa: E402
from src.querygen import review as R  # noqa: E402
from src.querygen import sets  # noqa: E402
from src.querygen.generator import check_prompt_keyword_rule, keyword_rule_phrase, parse_response  # noqa: E402
from src.querygen.io import AppendLog, JsonlStore  # noqa: E402
from src.querygen.limits import RateLimitError  # noqa: E402

KW = base.KW
SIX, SEVEN = "một hai ba bốn năm sáu", "một hai ba bốn năm sáu bảy"
LONG_KW = {"natural": "câu hỏi", "scenario": "tình huống", "keyword": SEVEN}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("test không được gọi mạng")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


def ok(aid, keyword="từ khóa"):
    return {"article_id": aid, "skip": False, "skip_reason": None, "queries": {"natural": "câu hỏi", "scenario": "tình huống", "keyword": keyword}}


# ---------------- keyword 1–6 âm tiết từ config ----------------
def test_config_keyword_limits_are_one_to_six():
    assert (KW["keyword_min"], KW["keyword_max"]) == (1, 6)


def test_keyword_six_syllables_accepted_seven_rejected_by_parser():
    p = parse_response(json.dumps({"results": [ok("a", SIX), ok("b", SEVEN), ok("c", "thuế")]}), ["a", "b", "c"], **KW)
    assert set(p.valid) == {"a", "c"} and p.valid["a"]["queries"]["keyword"] == SIX
    assert p.article_errors == [{"article_id": "b", "field": "queries.keyword", "reason": "keyword có 7 âm tiết, cần 1-6 âm tiết"}]
    # dấu câu không tính là âm tiết (SPEC 5.3): 6 âm tiết có dấu phẩy vẫn đạt
    assert parse_response(json.dumps({"results": [ok("a", "một, hai - ba bốn (năm) sáu")]}), ["a"], **KW).valid


def test_keyword_limits_come_from_arguments_not_hard_coded():
    p = parse_response(json.dumps({"results": [ok("a", SEVEN)]}), ["a"], keyword_min=1, keyword_max=7)
    assert set(p.valid) == {"a"}


def test_review_edit_keyword_six_ok_seven_rejected():
    st, recs, arts = base_review()
    kw = st["slots"][2]
    lim = {"keyword_min_syllables": KW["keyword_min"], "keyword_max_syllables": KW["keyword_max"]}
    row = lambda text: {"slot": str(kw["slot"]), "query_id": kw["query_id"], "decision": "edit", "reason": "", "edited_text": text,
                        "reviewer": "Người Giả", "date": "2000-01-01", "note": ""}
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [row(SEVEN)], recs, arts, **lim)
    assert R.apply_sheet(st, [row(SIX)], recs, arts, **lim)["slots"][2]["status"] == "accepted"


def base_review():
    import test_querygen_decisions as dec
    return dec._review_fixture("test")


def test_prompt_matches_config_keyword_limit_and_old_prompt_is_kept_as_history():
    phrase = keyword_rule_phrase(KW["keyword_min"], KW["keyword_max"])
    assert phrase == "từ 1 đến 6 âm tiết" and phrase in base.TEMPLATE
    check_prompt_keyword_rule(base.TEMPLATE, KW["keyword_min"], KW["keyword_max"])
    assert base.QCFG["prompt"]["version"] == "v0.1-draft" and base.PROMPT_PATH.name == "query_generation.v0.1.draft.md"
    old = (ROOT / "prompts" / "query_generation.v0.draft.md").read_text(encoding="utf-8")
    assert "1 đến 4 từ" in old  # v0 giữ nguyên làm lịch sử
    with pytest.raises(ValueError):
        check_prompt_keyword_rule(old, KW["keyword_min"], KW["keyword_max"])


def test_generate_refuses_prompt_that_disagrees_with_config(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    qcfg["prompt"]["path"] = str(ROOT / "prompts" / "query_generation.v0.draft.md")
    c = base.FakeClient()
    with pytest.raises(SystemExit) as e:
        gq.cmd_generate(dcfg, qcfg, "train", {"split": "train", "article_ids": []}, client=c, mock=True)
    assert "từ 1 đến 6 âm tiết" in str(e.value) and c.calls == 0 and not (tmp_path / "runs").exists()


def test_generate_refuses_resume_when_metadata_differs(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    plan = {"split": "train", "article_ids": [f"d{i:02d}_001" for i in range(base.N_CLI)]}
    ft = base.FakeTime()
    gq.cmd_generate(dcfg, qcfg, "train", plan, client=base.FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock)
    qcfg["llm"]["temperature"] = 0.9
    with pytest.raises(SystemExit) as e:
        gq.cmd_generate(dcfg, qcfg, "train", plan, client=base.FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock)
    assert "temperature" in str(e.value)


# ---------------- batch có Điều lỗi ----------------
def test_batch_with_one_invalid_article_keeps_others_and_logs_article_field_reason(tmp_path):
    arts = base.make_articles(10)
    bad = arts[3]["article_id"]
    c = base.FakeClient(overrides={bad: LONG_KW})
    g, store, _ = base.make_gen(tmp_path, c)
    st = g.run(arts)
    assert c.calls == 1 and st["written"] == 9 and st["failed_batches"] == 0  # không retry cả batch
    assert bad not in store and {r["article_id"] for r in store.read_all()} == {a["article_id"] for a in arts} - {bad}
    assert st["invalid_articles"] == {"queries.keyword": 1} and st["invalid_article_count"] == 1
    err = AppendLog(tmp_path / "err.jsonl").read_all()
    assert len(err) == 1 and err[0]["level"] == "article" and err[0]["article_id"] == bad and err[0]["field"] == "queries.keyword"
    assert "7 âm tiết" in err[0]["reason"] and err[0]["run_id"] == g.run_id


def test_resume_resends_only_invalid_articles(tmp_path):
    arts = base.make_articles(30)
    bad_ids = [a["article_id"] for a in arts[:20:2]]  # 10 Điều lỗi trong 20 Điều đầu
    c = base.FakeClient(overrides={a: LONG_KW for a in bad_ids}, override_calls=2)
    g, store, _ = base.make_gen(tmp_path, c)
    g.run(arts[:20])
    assert c.calls == 2 and len(store.read_all()) == 10
    c2 = base.FakeClient()
    g2, store2, _ = base.make_gen(tmp_path, c2)  # resume: mở lại cùng file
    st = g2.run(arts[:20])
    assert c2.requested == [bad_ids] and st["written"] == 10 and st["skipped_existing"] == 10
    assert len(store2.read_all()) == 20


def test_resume_below_ten_pending_articles_stops_and_reports(tmp_path):
    arts = base.make_articles(10)
    bad = arts[0]["article_id"]
    c = base.FakeClient(overrides={bad: LONG_KW}, override_calls=99)
    g, store, _ = base.make_gen(tmp_path, c)
    g.run(arts)
    st = g.run(arts)  # resume: chỉ còn 1 Điều lỗi < 10
    assert c.calls == 1 and st["stop_reason"] == "pending_below_min_batch" and st["pending_article_ids"] == [bad]
    # có Điều mới bổ sung đủ 10 thì Điều lỗi được gửi lại cùng Điều mới
    more = arts + base.make_articles(9, prefix="e")
    st2 = g.run(more)
    assert c.requested[-1] == [bad] + [a["article_id"] for a in more[10:]]
    assert st2["stop_reason"] == "completed_with_unprocessed" and st2["unprocessed_article_ids"] == [bad]  # bad vẫn lỗi


def test_cli_generate_exits_with_message_when_pending_below_ten(tmp_path):
    gq, cfg_d, cfg_q, plan_path = _cli_env(tmp_path, n_plan=9)
    c = base.FakeClient()
    with pytest.raises(SystemExit) as e:
        gq.main(["--data-config", str(cfg_d), "--query-config", str(cfg_q), "generate", "--split", "train", "--plan", str(plan_path)], client=c)
    msg = str(e.value)
    assert c.calls == 0 and "còn 9 Điều" in msg and "10" in msg and "Không tự đổi quy tắc" in msg
    last = AppendLog(tmp_path / "runs" / "queries_train.runs.jsonl").read_all()[-1]
    assert last["stop_reason"] == "pending_below_min_batch" and len(last["pending_article_ids"]) == 9


def test_no_valid_article_retries_whole_batch(tmp_path):
    arts = base.make_articles(10)
    c = base.FakeClient(overrides={a["article_id"]: LONG_KW for a in arts}, override_calls=1)
    g, store, ft = base.make_gen(tmp_path, c)
    st = g.run(arts)
    assert c.calls == 2 and st["retries"] == {"no_valid_article": 1} and st["written"] == 10 and ft.sleeps == [2]
    assert st["stop_reason"] == "completed" and st["unprocessed_article_ids"] == []
    # lỗi của lần thử bị retry vẫn được ghi đủ: article_id, trường, lý do, số lần thử
    err = AppendLog(tmp_path / "err.jsonl").read_all()
    assert [e["article_id"] for e in err] == [a["article_id"] for a in arts]
    assert all(e["level"] == "article" and e["field"] == "queries.keyword" and "7 âm tiết" in e["reason"] and e["attempt"] == 1 for e in err)
    # Điều đã thành công ở lần thử sau không bị coi là chưa xử lý
    assert sets.error_report(err, {r["article_id"] for r in store.read_all()})["unresolved_article_ids"] == []


def test_no_valid_article_after_all_attempts_logs_and_continues_with_next_batch(tmp_path):
    arts = base.make_articles(20)
    c = base.FakeClient(overrides={a["article_id"]: LONG_KW for a in arts[:10]}, override_calls=3)
    g, store, _ = base.make_gen(tmp_path, c, max_attempts=3)
    st = g.run(arts)
    assert c.calls == 4 and st["failed_batches"] == 1 and st["written"] == 10 and st["stop_reason"] == "completed_with_unprocessed"
    assert st["unprocessed_article_ids"] == [a["article_id"] for a in arts[:10]]
    err = AppendLog(tmp_path / "err.jsonl").read_all()
    art_err = [e for e in err if e["level"] == "article"]
    assert len(art_err) == 30 and sorted({e["attempt"] for e in art_err}) == [1, 2, 3]  # 10 Điều x 3 lần thử
    assert [(e["error_type"], e["attempts"]) for e in err if e["level"] == "batch"] == [("no_valid_article", 3)]


def test_unassignable_result_logged_at_batch_level(tmp_path):
    arts = base.make_articles(10)
    raw = json.dumps({"results": [ok(a["article_id"]) for a in arts] + [ok("khong_yeu_cau")]}, ensure_ascii=False)
    g, store, _ = base.make_gen(tmp_path, base.FakeClient(script=[raw]))
    st = g.run(arts)
    assert st["written"] == 10 and st["batch_errors"] == 1
    err = AppendLog(tmp_path / "err.jsonl").read_all()
    assert err[0]["level"] == "batch" and err[0]["error_type"] == "unassignable" and "khong_yeu_cau" in err[0]["reason"]
    assert err[0]["article_ids"] == [a["article_id"] for a in arts]


@pytest.mark.parametrize("n,bs,sizes", [
    (24, 15, [14, 10]), (25, 15, [15, 10]), (30, 15, [15, 15]), (16, 15, [16]), (19, 15, [19]), (20, 15, [10, 10]),
    (21, 15, [11, 10]), (35, 15, [15, 10, 10]), (10, 15, [10]), (19, 10, [19]), (29, 20, [19, 10]), (45, 20, [20, 15, 10]),
])
def test_next_batch_size_uses_every_valid_group_of_10_to_20(n, bs, sizes):
    from src.querygen.generator import next_batch_size
    got, left = [], n
    while left >= 10:
        got.append(next_batch_size(left, bs))
        left -= got[-1]
    assert got == sizes and left == 0 and all(10 <= x <= 20 for x in got)


def test_next_batch_size_every_split_stays_within_10_to_20():
    from src.querygen.generator import next_batch_size
    for bs in range(10, 21):
        for n in range(10, 200):
            left = n
            while left >= 10:
                k = next_batch_size(left, bs)
                assert 10 <= k <= 20 and (left - k == 0 or left - k >= 10), (n, bs, k)
                left -= k
            assert left == 0


def test_run_24_articles_batch_15_sends_14_then_10(tmp_path):
    arts = base.make_articles(24)
    c = base.FakeClient()
    g, store, _ = base.make_gen(tmp_path, c, batch_size=15)
    st = g.run(arts)
    assert [len(r) for r in c.requested] == [14, 10] and st["written"] == 24 and st["stop_reason"] == "completed"


def test_cli_batch_has_invalid_article_reports_unprocessed_ids_and_exits(tmp_path):
    gq, cfg_d, cfg_q, plan_path = _cli_env(tmp_path, n_plan=24)
    bad = "d07_001"
    c = base.FakeClient(overrides={bad: LONG_KW})
    with pytest.raises(SystemExit) as e:
        gq.main(["--data-config", str(cfg_d), "--query-config", str(cfg_q), "generate", "--split", "train", "--plan", str(plan_path)], client=c)
    assert [len(r) for r in c.requested] == [14, 10] and "Chưa hoàn tất" in str(e.value) and bad in str(e.value)
    last = AppendLog(tmp_path / "runs" / "queries_train.runs.jsonl").read_all()[-1]
    assert last["stop_reason"] == "completed_with_unprocessed" and last["unprocessed_article_ids"] == [bad] and last["written"] == 23


def test_metadata_records_verbatim_n_and_resume_refuses_different_n(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    plan = {"split": "train", "article_ids": [f"d{i:02d}_001" for i in range(base.N_CLI)]}
    ft = base.FakeTime()
    gq.cmd_generate(dcfg, qcfg, "train", plan, client=base.FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock)
    meta = json.loads((tmp_path / "runs" / "queries_train.raw.meta.json").read_text(encoding="utf-8"))
    assert meta["verbatim_n"] == qcfg["lexical"]["verbatim_n"] == 8
    qcfg["lexical"]["verbatim_n"] = 9
    c = base.FakeClient()
    with pytest.raises(SystemExit) as e:
        gq.cmd_generate(dcfg, qcfg, "train", plan, client=c, mock=True, sleep=ft.sleep, clock=ft.clock)
    assert "verbatim_n" in str(e.value) and c.calls == 0


# ---------------- 429 hết retry: dừng cả lượt ----------------
def test_rate_limit_exhausted_stops_run_without_calling_next_batch(tmp_path):
    arts = base.make_articles(30)
    c = base.FakeClient(script=[RateLimitError("429")] * 3)
    g, store, _ = base.make_gen(tmp_path, c, max_attempts=3)
    st = g.run(arts)
    assert c.calls == 3 and len(c.requested) == 3 and all(r == c.requested[0] for r in c.requested)  # chỉ batch đầu
    assert st["stop_reason"] == "rate_limit_exhausted" and st["retries"] == {"rate_limit": 2} and st["failed_batches"] == 1
    assert st["pending_article_ids"] == [a["article_id"] for a in arts] and store.read_all() == []
    err = AppendLog(tmp_path / "err.jsonl").read_all()
    assert len(err) == 1 and err[0]["error_type"] == "rate_limit" and len(err[0]["article_ids"]) == 10


def test_cli_rate_limit_exhausted_exits_with_resume_instructions(tmp_path):
    gq, cfg_d, cfg_q, plan_path = _cli_env(tmp_path, n_plan=30)
    c = base.FakeClient(script=[None, RateLimitError("429"), RateLimitError("429")])  # batch 1 ổn, batch 2 hết retry
    with pytest.raises(SystemExit) as e:
        gq.main(["--data-config", str(cfg_d), "--query-config", str(cfg_q), "generate", "--split", "train", "--plan", str(plan_path)], client=c)
    msg = str(e.value)
    assert c.calls == 3 and "429" in msg and "resume" in msg and "generate --split train" in msg
    runs = AppendLog(tmp_path / "runs" / "queries_train.runs.jsonl").read_all()
    assert runs[-1]["stop_reason"] == "rate_limit_exhausted" and runs[-1]["written"] == 15 and len(runs[-1]["pending_article_ids"]) == 15
    # resume sau khi hạn mức phục hồi: chỉ gửi 15 Điều còn lại
    c2 = base.FakeClient()
    gq.main(["--data-config", str(cfg_d), "--query-config", str(cfg_q), "generate", "--split", "train", "--plan", str(plan_path)], client=c2)
    assert c2.calls == 1 and len(c2.requested[0]) == 15
    assert len(JsonlStore(tmp_path / "runs" / "queries_train.raw.jsonl").read_all()) == 30


# ---------------- log chỉ ghi thêm ----------------
def test_error_log_keeps_every_repeated_failure(tmp_path):
    arts = base.make_articles(10)
    for _ in range(3):  # cùng một batch hỏng ba lần, ba lượt chạy
        g, store, _ = base.make_gen(tmp_path, base.FakeClient(script=["không phải JSON"]), max_attempts=1)
        g.run(arts)
    bad = arts[0]["article_id"]
    for _ in range(2):  # cùng một Điều lỗi hai lần
        g, store, _ = base.make_gen(tmp_path, base.FakeClient(overrides={bad: LONG_KW}), max_attempts=1)
        g.run(arts)
        store.path.write_text("", encoding="utf-8")  # xóa bản ghi để Điều được gửi lại
    err = AppendLog(tmp_path / "err.jsonl").read_all()
    assert [e["level"] for e in err] == ["batch"] * 3 + ["article"] * 2
    assert len({e["run_id"] for e in err}) == 5


def test_append_log_truncates_partial_last_line(tmp_path):
    p = tmp_path / "e.jsonl"
    log = AppendLog(p)
    log.append({"a": 1})
    p.write_bytes(p.read_bytes() + b'{"a": 2, "tr')
    log2 = AppendLog(p)
    log2.append({"a": 3})
    assert log2.truncated_partial_line and [r["a"] for r in log2.read_all()] == [1, 3]


# ---------------- tóm tắt từng lượt generate ----------------
def test_each_generate_appends_one_run_summary(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    plan = {"split": "train", "article_ids": [f"d{i:02d}_001" for i in range(base.N_CLI)]}
    ft = base.FakeTime()
    bad = "d02_001"
    gq.cmd_generate(dcfg, qcfg, "train", plan, client=base.FakeClient(overrides={bad: LONG_KW}), mock=True, sleep=ft.sleep, clock=ft.clock, tag="pilot")
    gq.cmd_generate(dcfg, qcfg, "train", plan, client=base.FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock, tag="pilot")
    runs = AppendLog(tmp_path / "runs" / "queries_train.pilot.runs.jsonl").read_all()
    assert len(runs) == 2
    r1, r2 = runs
    for k in ("run_id", "requests", "retries", "failed_batches", "invalid_articles", "written", "stop_reason",
              "keyword_min_syllables", "keyword_max_syllables", "prompt_version"):
        assert k in r1
    assert r1["requests"] == 2 and r1["written"] == 29 and r1["invalid_articles"] == {"queries.keyword": 1}
    assert r1["stop_reason"] == "completed_with_unprocessed" and r1["unprocessed_article_ids"] == [bad]
    assert r2["stop_reason"] == "pending_below_min_batch" and r2["pending_article_ids"] == [bad] and r2["requests"] == 0


# ---------------- báo cáo build-sets ----------------
def test_kept_count_distribution_separates_copy_filter_and_train_overlap_layers():
    recs = [
        base.rec("a_001", "train", {"natural": (0.1, False, False), "scenario": (0.2, False, False), "keyword": (0.3, False, False)}),  # 3 / 3
        base.rec("b_001", "train", {"natural": (0.1, True, False), "scenario": (0.9, False, False), "keyword": (1.0, False, False)}),   # 2 / 0
        base.rec("c_001", "train", {"natural": (0.1, False, True), "scenario": (0.2, False, False), "keyword": (0.85, False, False)}),  # 2 / 1
        base.rec("d_001", "train", {"natural": (0.1, True, False), "scenario": (0.2, True, False), "keyword": (0.3, False, False)}),   # 1 / 1
        base.rec("e_001", "train", {}, skip=True),                                                                                      # 0 / 0
    ]
    d = sets.kept_count_distribution(recs, "train", 0.8, True)
    assert d["after_copy_filters"] == {"0": 1, "1": 1, "2": 2, "3": 1}
    assert d["after_train_overlap"] == {"0": 2, "1": 2, "2": 0, "3": 1}
    assert d["articles_total"] == 5 and d["articles_skipped"] == 1
    v = sets.kept_count_distribution([dict(r, split="val") for r in recs], "val", 0.8, True)
    assert v["after_train_overlap"] is None and v["after_copy_filters"] == d["after_copy_filters"]


def test_error_report_groups_by_article_field_batch_and_unresolved():
    entries = [
        {"level": "article", "article_id": "a", "field": "queries.keyword", "reason": "r1", "run_id": "1"},
        {"level": "article", "article_id": "a", "field": "queries.keyword", "reason": "r1", "run_id": "2"},
        {"level": "article", "article_id": "b", "field": "article_id", "reason": "thiếu trong phản hồi", "run_id": "1"},
        {"level": "batch", "error_type": "invalid_response", "reason": "x", "article_ids": ["c", "d"], "run_id": "1"},
        {"level": "batch", "error_type": "unassignable", "field": "article_id", "reason": "y", "article_ids": ["a", "b"], "run_id": "1"},
    ]
    rep = sets.error_report(entries, processed_ids={"b", "d"}, planned_ids=["a", "b", "c", "d", "e"])
    assert rep["article_errors_by_field"] == {"queries.keyword": 2, "article_id": 1}
    assert [x["run_id"] for x in rep["article_errors"]["a"]] == ["1", "2"]
    assert rep["batch_errors_by_type"] == {"invalid_response": 1, "unassignable": 1} and len(rep["batch_errors"]) == 2
    assert rep["unresolved_article_ids"] == ["a", "c"] and rep["planned_not_processed"] == ["a", "c", "e"]


def test_cli_build_sets_writes_report_with_distribution_and_errors(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    plan = {"split": "train", "ordered_article_ids": [f"d{i:02d}_001" for i in range(base.N_CLI)], "target_pairs": None, "pilot": True}
    ft = base.FakeTime()
    bad = "d05_001"
    gq.cmd_generate(dcfg, qcfg, "train", plan, client=base.FakeClient(overrides={bad: LONG_KW}), mock=True, sleep=ft.sleep, clock=ft.clock, tag="pilot")
    res = gq.cmd_build_sets(qcfg, "train", plan, tag="pilot")
    rep = json.loads((tmp_path / "runs" / "queries_train.pilot.build_report.json").read_text(encoding="utf-8"))
    assert rep == json.loads(json.dumps(res["report"], ensure_ascii=False))
    d = rep["kept_count_distribution"]
    assert d["articles_total"] == 29 and sum(d["after_copy_filters"].values()) == 29 and sum(d["after_train_overlap"].values()) == 29
    e = rep["errors"]
    assert e["article_errors_by_field"] == {"queries.keyword": 1} and list(e["article_errors"]) == [bad]
    assert e["unresolved_article_ids"] == [bad] and e["planned_not_processed"] == [bad] and e["batch_errors"] == []


# ---------------- tham chiếu cũ ----------------
def test_no_reference_to_questions_for_team_in_tooling():
    for p in list((ROOT / "src" / "querygen").glob("*.py")) + [ROOT / "scripts" / "generate_queries.py", ROOT / "scripts" / "review_queries.py",
                                                                ROOT / "configs" / "querygen.yaml"]:
        assert "QUESTIONS_FOR_TEAM" not in p.read_text(encoding="utf-8"), p


def test_missing_config_value_points_to_querygen_yaml(tmp_path):
    gq = base._script()
    with pytest.raises(SystemExit) as e:
        gq.require({"rate_limit_calls": None}, ["rate_limit_calls"], "configs/querygen.yaml: llm")
    assert "configs/querygen.yaml" in str(e.value) and "Điền" in str(e.value)


# ---------------- tiện ích ----------------
def _cli_env(tmp_path, n_plan):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    qcfg["llm"].update(retry_base_delay_seconds=0, retry_max_delay_seconds=0, max_attempts=2)  # không chờ thật
    cfg_d, cfg_q = tmp_path / "d.yaml", tmp_path / "q.yaml"
    cfg_d.write_text(yaml.safe_dump(dcfg), encoding="utf-8")
    cfg_q.write_text(yaml.safe_dump(qcfg, allow_unicode=True), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({"split": "train", "ordered_article_ids": [f"d{i:02d}_001" for i in range(n_plan)], "target_pairs": None}), encoding="utf-8")
    return gq, cfg_d, cfg_q, plan_path
