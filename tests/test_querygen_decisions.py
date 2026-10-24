"""Test cho các quyết định Q5/Q6/Q7 (người dùng xác nhận 2026-10-23): adapter Gemini qua httpx (MockTransport), tham số query đã chốt,
thứ tự phân tầng, dự phòng 75/25, thống kê trước/sau lọc, công cụ duyệt val/test offline. Không gọi mạng; "người duyệt" trong test là dữ liệu giả."""
from __future__ import annotations

import csv
import json
import socket
import sys
from pathlib import Path

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import test_querygen as base  # noqa: E402
from src.querygen import review as R  # noqa: E402
from src.querygen import select as sel  # noqa: E402
from src.querygen import sets, variants as V  # noqa: E402
from src.querygen.client import ENDPOINT, GeminiClient, GeminiRequestError, MissingApiKeyError  # noqa: E402
from src.querygen.generator import build_meta  # noqa: E402
from src.querygen.io import JsonlStore  # noqa: E402
from src.querygen.limits import RateLimitError, RetryableError  # noqa: E402

KEY = "TEST-KEY-NOT-REAL-123"
KWR = {"keyword_min_syllables": base.KW["keyword_min"], "keyword_max_syllables": base.KW["keyword_max"]}  # giới hạn keyword từ config


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("test không được gọi mạng")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


# ---------------- Gemini qua httpx ----------------
def ok_body(text="{}"):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_gemini_request_shape_and_key_in_header_only():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"], seen["body"] = str(request.url), request.headers.get("x-goog-api-key"), json.loads(request.content)
        return httpx.Response(200, json=ok_body('{"results": []}'))

    c = GeminiClient("gemini-3.5-flash-lite", 0.7, api_key=KEY, transport=httpx.MockTransport(handler))
    assert c.generate("PROMPT") == '{"results": []}'
    assert seen["url"] == ENDPOINT.format(model="gemini-3.5-flash-lite") and KEY not in seen["url"]
    assert seen["key"] == KEY
    assert seen["body"]["generationConfig"] == {"temperature": 0.7, "responseMimeType": "application/json"}
    assert seen["body"]["contents"][0]["parts"][0]["text"] == "PROMPT"
    assert KEY not in repr(c) and KEY not in str(c)


def test_gemini_reads_key_from_environment_and_reports_missing_key_without_leaking(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError) as e:
        GeminiClient("gemini-3.5-flash-lite", 0.7)
    assert "GEMINI_API_KEY" in str(e.value)
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    c = GeminiClient("gemini-3.5-flash-lite", 0.7, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=ok_body("x"))))
    assert c.generate("p") == "x"


def test_gemini_error_mapping_and_no_key_in_messages():
    def client(handler):
        return GeminiClient("m", 0.7, api_key=KEY, transport=httpx.MockTransport(handler))

    with pytest.raises(RateLimitError) as e:
        client(lambda r: httpx.Response(429, headers={"retry-after": "3"})).generate("p")
    assert e.value.retry_after == 3.0
    with pytest.raises(RateLimitError) as e:
        client(lambda r: httpx.Response(429)).generate("p")
    assert e.value.retry_after is None
    with pytest.raises(RetryableError):
        client(lambda r: httpx.Response(503)).generate("p")
    with pytest.raises(GeminiRequestError) as e:
        client(lambda r: httpx.Response(400, text=f"bad request {KEY}")).generate("p")
    assert KEY not in str(e.value)

    def boom(request):
        raise httpx.ConnectError("không kết nối được", request=request)

    with pytest.raises(RetryableError) as e:
        client(boom).generate("p")
    assert KEY not in str(e.value)
    with pytest.raises(RetryableError):
        client(lambda r: httpx.Response(200, json={"candidates": []})).generate("p")
    with pytest.raises(RetryableError):
        client(lambda r: httpx.Response(200, text="không phải JSON")).generate("p")


def test_generator_with_gemini_client_retries_using_retry_after_with_fake_sleep(tmp_path):
    ft = base.FakeTime()
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "4"})
        prompt =json.loads(request.content)["contents"][0]["parts"][0]["text"]
        arts = json.loads(prompt[prompt.rindex("[\n"):])
        results = [{"article_id": a["article_id"], "skip": False, "skip_reason": None,
                    "queries": {"natural": "câu một", "scenario": "câu hai", "keyword": "từ khóa"}} for a in arts]
        return httpx.Response(200, json=ok_body(json.dumps({"results": results}, ensure_ascii=False)))

    client = GeminiClient("gemini-3.5-flash-lite", 0.7, api_key=KEY, transport=httpx.MockTransport(handler))
    g, store, _ = base.make_gen(tmp_path, client, ft=ft)
    g.run(base.make_articles(10))
    assert ft.sleeps == [4.0] and len(store.read_all()) == 10 and len(calls) == 2


# ---------------- cấu hình đã chốt ----------------
def test_config_reflects_confirmed_decisions_and_never_guesses_quota():
    raw = (ROOT / "configs" / "querygen.yaml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(raw)
    assert cfg["llm"]["model"] == "gemini-3.5-flash-lite" and cfg["llm"]["temperature"] == 0.7 and cfg["llm"]["batch_size"] == 15
    assert cfg["llm"]["api_key_env"] == "GEMINI_API_KEY"
    assert cfg["llm"]["rate_limit_calls"] == 5 and cfg["llm"]["generation_date"] is None  # quota người dùng điền từ AI Studio; ngày ghi khi chạy
    assert cfg["lexical"] == {"verbatim_n": 8, "train_overlap_threshold": 0.8, "train_overlap_inclusive": True,
                              "keyword_min_syllables": 1, "keyword_max_syllables": 6}  # nhóm duyệt 2026-10-24
    s = cfg["selection"]
    assert s["train_target_pairs_after_filter"] == 5000 and s["eval_articles_per_type"] == 50 and s["eval_reserve_per_type"] == 25
    assert s["eval_selection"] == "stratified_by_domain"
    assert "AIza" not in raw and "api_key:" not in raw.lower()


def test_dotenv_is_gitignored():
    lines = [l.strip() for l in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()]
    assert ".env" in lines


def test_build_meta_records_runtime_date_and_requires_pinned_model():
    cfg = yaml.safe_load((ROOT / "configs" / "querygen.yaml").read_text(encoding="utf-8"))
    m = build_meta(cfg, "h", "train", 42)
    import datetime
    assert m["generation_date"] == datetime.date.today().isoformat() and m["model"] == "gemini-3.5-flash-lite" and m["mock"] is False
    assert build_meta(cfg, "h", "train", 42, generation_date="2001-02-03")["generation_date"] == "2001-02-03"
    cfg["llm"]["model"] = None
    with pytest.raises(ValueError):
        build_meta(cfg, "h", "train", 42)


# ---------------- thứ tự phân tầng, dự phòng ----------------
def pool(n_a=60, n_b=40, n_c=0):
    items = [{"article_id": f"a{i:03d}", "domain": "A"} for i in range(n_a)] + [{"article_id": f"b{i:03d}", "domain": "B"} for i in range(n_b)]
    return items + [{"article_id": f"c{i:03d}", "domain": "C"} for i in range(n_c)]


def test_stratified_order_prefixes_are_proportional_deterministic_and_complete():
    items = pool()
    o = sel.stratified_order(items, 42)
    assert len(o) == 100 and len({a["article_id"] for a in o}) == 100
    for k, expected_a in ((10, 6), (20, 12), (50, 30)):
        assert sum(1 for a in o[:k] if a["domain"] == "A") == expected_a
    assert o == sel.stratified_order(list(reversed(items)), 42) and o != sel.stratified_order(items, 43)


def test_stratified_order_tie_prefers_smaller_domain_name():
    o = sel.stratified_order(pool(5, 5), 1)
    assert o[0]["domain"] == "A"


def test_plan_eval_main_plus_reserve_with_balanced_types_and_no_overlap():
    items = pool(90, 90, 45)
    plan = sel.plan_eval(items, 10, 5, 42)  # thu nhỏ từ 50/25
    from collections import Counter
    assert len(plan["article_ids"]) == 30 and len(plan["reserve_ids"]) == 15
    assert set(plan["article_ids"]).isdisjoint(plan["reserve_ids"])
    assert Counter(plan["types"].values()) == Counter({"natural": 10, "scenario": 10, "keyword": 10})
    assert Counter(plan["reserve_types"].values()) == Counter({"natural": 5, "scenario": 5, "keyword": 5})
    assert plan == sel.plan_eval(items, 10, 5, 42)
    dom = Counter(a["domain"] for a in items if a["article_id"] in set(plan["article_ids"]))
    assert dom == Counter({"A": 12, "B": 12, "C": 6})  # tỷ lệ 90:90:45


def test_plan_eval_with_full_sizes_is_225_articles_per_split():
    items = pool(400, 300, 100)
    plan = sel.plan_eval(items, 50, 25, 42)
    assert len(plan["article_ids"]) == 150 and len(plan["reserve_ids"]) == 75


def test_plan_eval_insufficient_source_raises_without_changing_seed():
    with pytest.raises(sel.InsufficientSourceError) as e:
        sel.plan_eval(pool(70, 70), 50, 25, 42)  # 140 Điều < 225 cần có
    assert "225" in str(e.value)


def test_assemble_eval_replaces_with_reserve_of_same_assigned_type_only():
    ok = {"natural": (0.1, False, False), "scenario": (0.1, False, False), "keyword": (0.1, False, False)}
    bad_nat = {"natural": (0.1, True, False), "scenario": (0.1, False, False), "keyword": (0.1, False, False)}
    recs = [base.rec("a_001", "val", ok), base.rec("b_001", "val", bad_nat), base.rec("r1_001", "val", ok), base.rec("r2_001", "val", bad_nat), base.rec("r3_001", "val", ok)]
    types = {"a_001": "keyword", "b_001": "natural"}
    out, replaced = sets.assemble_eval(recs, ["a_001", "b_001"], types, ["r1_001", "r2_001", "r3_001"], {"r1_001": "keyword", "r2_001": "natural", "r3_001": "natural"})
    # r1 là dự phòng kiểu keyword nên không dùng thay query natural; r2 kiểu natural nhưng vi phạm; r3 đạt
    assert replaced == [{"replaced_article_id": "b_001", "by_article_id": "r3_001", "type": "natural"}]
    assert [q["type"] for q in out] == ["keyword", "natural"] and out[1]["article_id"] == "r3_001"
    with pytest.raises(ValueError):
        sets.assemble_eval(recs, ["a_001", "b_001"], types, ["r1_001"], {"r1_001": "keyword"})


def test_filter_stats_report_generated_and_kept_by_type_for_keyword_measurement():
    recs = [base.rec(f"t{i}_001", "train", {"natural": (0.5, False, False), "scenario": (0.85, False, False), "keyword": (1.0, False, False)}) for i in range(4)]
    recs.append(base.rec("t9_001", "train", {}, skip=True))
    st = sets.filter_stats(recs, "train", 0.8, True)
    assert st["by_type"]["keyword"] == {"generated": 4, "kept": 0, "rejected": {"high_overlap_train": 4}}
    assert st["by_type"]["natural"]["kept"] == 4 and st["by_type"]["scenario"]["kept"] == 0
    assert st["kept_total"] == 4 and st["generated_total"] == 12 and st["articles_skipped"] == 1
    # val: overlap không lọc (chỉ dùng để phân nhóm)
    vrecs = [dict(r, split="val") for r in recs[:4]]
    assert sets.filter_stats(vrecs, "val", 0.8, True)["by_type"]["keyword"]["kept"] == 4


# ---------------- run_until: bổ sung đến mục tiêu ----------------
def test_run_until_stops_after_the_batch_that_reaches_target_and_keeps_all_pairs(tmp_path):
    client = base.FakeClient()
    g, store, _ = base.make_gen(tmp_path, client)
    arts = base.make_articles(40)
    lex = (0.8, True)
    count = lambda: len(sets.filter_split(store.read_all(), "train", *lex)[0]) if store.read_all() else 0
    for a in arts:
        a["split"] = "train"
    stats = g.run_until(arts, count, 20)
    assert client.calls == 1 and stats["pairs_after_filter"] == 30 and stats["target_reached"]  # vượt nhẹ ở lượt cuối, giữ mọi query hợp lệ
    assert len(store.read_all()) == 10
    stats2 = g.run_until(arts, count, 20)  # chạy lại: đã đủ, không gọi thêm
    assert client.calls == 1 and stats2["target_reached"]
    stats3 = g.run_until(arts, count, 55)  # cần thêm
    assert stats3["pairs_after_filter"] == 60 and client.calls == 2


def test_run_until_reports_shortfall_instead_of_borrowing(tmp_path):
    client = base.FakeClient()
    g, store, _ = base.make_gen(tmp_path, client)
    arts = base.make_articles(20)
    for a in arts:
        a["split"] = "train"
    count = lambda: len(sets.filter_split(store.read_all(), "train", 0.8, True)[0]) if store.read_all() else 0
    stats = g.run_until(arts, count, 1000)
    assert stats["target_reached"] is False and stats["pairs_after_filter"] == 60 and client.calls == 2
    assert stats["stop_reason"] == "plan_exhausted"


# ---------------- CLI plan / generate / build-sets ----------------
def test_cli_plan_train_pilot_and_errors(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    plan = gq.cmd_plan(dcfg, qcfg, "train")
    assert plan["target_pairs"] == 5000 and len(plan["ordered_article_ids"]) == base.N_CLI and plan == gq.cmd_plan(dcfg, qcfg, "train")
    pilot = gq.cmd_plan(dcfg, qcfg, "train", pilot=5)
    assert pilot["ordered_article_ids"] == plan["ordered_article_ids"][:5] and pilot["target_pairs"] is None and pilot["pilot"] is True
    with pytest.raises(SystemExit):
        gq.cmd_plan(dcfg, qcfg, "val", pilot=5)
    (tmp_path / "nosplit").mkdir()
    d2, q2 = base._tmp_cfgs(tmp_path / "nosplit", with_split=False)
    with pytest.raises(SystemExit) as e:
        gq.cmd_plan(d2, q2, "train")
    assert "Chưa có split" in str(e.value) and not (tmp_path / "nosplit" / "data").exists()


def test_cli_plan_eval_insufficient_source_stops_without_borrowing(tmp_path):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    base.write_split(Path(dcfg["split"]["output"]), {f"d{i:02d}": ("val" if i < 8 else "train") for i in range(base.N_CLI)})
    with pytest.raises(SystemExit) as e:  # 8 Điều val < 225
        gq.cmd_plan(dcfg, qcfg, "val")
    assert "không lấy bù từ split khác" in str(e.value) and "không đổi seed" in str(e.value)


def test_cli_generate_requires_quota_and_api_key_and_never_prints_key(tmp_path, monkeypatch):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path, pinned=False)
    qcfg["llm"]["rate_limit_calls"] = None
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    with pytest.raises(SystemExit) as e:  # rate_limit_calls vẫn null: không đoán quota
        gq.cmd_generate(dcfg, qcfg, "train", {"split": "train", "article_ids": []})
    assert "rate_limit_calls" in str(e.value) and KEY not in str(e.value)
    qcfg["llm"]["rate_limit_calls"] = 10
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(SystemExit) as e:
        gq.cmd_generate(dcfg, qcfg, "train", {"split": "train", "article_ids": []})
    assert "GEMINI_API_KEY" in str(e.value)


def _eval_env(tmp_path, n_docs=base.N_CLI):
    gq = base._script()
    dcfg, qcfg = base._tmp_cfgs(tmp_path)
    base.write_split(Path(dcfg["split"]["output"]), {f"d{i:02d}": "val" for i in range(n_docs)})
    qcfg["selection"].update(eval_articles_per_type=4, eval_reserve_per_type=1)  # 12 + 3 = 15 Điều = 1 batch đầy đủ
    qcfg["paths"]["review_dir"] = str(tmp_path / "review")
    qcfg["paths"]["test_edit_log"] = str(tmp_path / "logs" / "test_query_edits.jsonl")
    return gq, dcfg, qcfg


def test_end_to_end_plan_generate_build_sets_and_review_with_simulated_human(tmp_path):
    gq, dcfg, qcfg = _eval_env(tmp_path)
    plan = gq.cmd_plan(dcfg, qcfg, "val")
    assert len(plan["article_ids"]) == 12 and len(plan["reserve_ids"]) == 3
    ft = base.FakeTime()
    gq.cmd_generate(dcfg, qcfg, "val", plan, client=base.FakeClient(), mock=True, sleep=ft.sleep, clock=ft.clock)
    res = gq.cmd_build_sets(qcfg, "val", plan)
    assert res["candidates"] == 12 and res["replaced"] == 0
    stats = json.loads((tmp_path / "runs" / "queries_val.filter_stats.json").read_text(encoding="utf-8"))
    assert set(stats["by_type"]) == {"natural", "scenario", "keyword"} and stats["generated_total"] == 45
    # duyệt offline
    cands = sel.read_jsonl(tmp_path / "runs" / "queries_val.candidates.jsonl")
    state = R.init_state("val", cands, plan)
    arts = {a["article_id"]: a for a in sel.read_jsonl(qcfg["paths"]["articles"])}
    records = JsonlStore(tmp_path / "runs" / "queries_val.raw.jsonl").read_all()
    sheet = tmp_path / "sheet.csv"
    assert R.export_sheet(state, arts, sheet) == 12
    rows = R.read_sheet(sheet)
    assert all(r["decision"] == "" and r["reviewer"] == "" and r["date"] == "" for r in rows)  # công cụ không điền thay người
    with pytest.raises(R.ReviewError):  # phiếu chưa điền
        R.apply_sheet(state, rows, records, arts, **KWR)
    for i, r in enumerate(rows):  # "người duyệt" giả: loại một query, chấp nhận còn lại
        r.update(reviewer="Người Giả", date="2000-01-01", decision="reject" if i == 0 else "accept", reason="khó hiểu" if i == 0 else "")
    state2 = R.apply_sheet(state, rows, records, arts, **KWR)
    assert sum(1 for s in state2["slots"] if s["status"] == "pending") == 1 and len(state2["reserve_used"]) == 1
    rows2 = [dict(r, decision="accept", reviewer="Người Giả", date="2000-01-02") for r in R.read_sheet(_export(state2, arts, tmp_path / "s2.csv"))]
    final = R.finalize(R.apply_sheet(state2, rows2, records, arts, **KWR), records, 4)
    assert len(final) == 12 and all(x["split"] == "val" for x in final)


def _export(state, arts, path):
    R.export_sheet(state, arts, path)
    return path


# ---------------- công cụ duyệt ----------------
def _review_fixture(split="test", n_main=3, with_bad_reserve=False):
    ok = {"natural": (0.1, False, False), "scenario": (0.1, False, False), "keyword": (0.1, False, False)}
    main = [f"m{i}_001" for i in range(n_main)]
    reserve = ["r0_001", "r1_001"]
    recs = [base.rec(a, split, ok) for a in main + reserve]
    arts = {a: {"article_id": a, "title": f"Tiêu đề {a}", "body": "người nộp thuế phải kê khai đầy đủ thông tin theo quy định của pháp luật"} for a in main + reserve}
    types = {main[0]: "natural", main[1]: "scenario", main[2]: "keyword"}
    cands = []
    for a in main:
        q = next(x for x in next(r for r in recs if r["article_id"] == a)["queries"] if x["type"] == types[a])
        cands.append({**q, "article_id": a, "doc_id": a.split("_")[0], "split": split})
    plan = {"reserve_ids": reserve, "reserve_types": {"r0_001": "natural", "r1_001": "keyword"}}
    return R.init_state(split, cands, plan), recs, arts


def row(slot_state, **kw):
    s = slot_state
    r = {"slot": str(s["slot"]), "query_id": s["query_id"], "decision": "accept", "reason": "", "edited_text": "", "reviewer": "Người Giả", "date": "2000-01-01", "note": ""}
    r.update(kw)
    return r


def test_review_val_allows_only_accept_or_reject_and_requires_human_fields():
    st, recs, arts = _review_fixture("val")
    s0 = st["slots"][0]
    with pytest.raises(R.ReviewError) as e:
        R.apply_sheet(st, [row(s0, decision="edit", edited_text="câu khác")], recs, arts, **KWR)
    assert "không hợp lệ cho val" in str(e.value)
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [row(s0, reviewer="")], recs, arts, **KWR)
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [row(s0, date="")], recs, arts, **KWR)
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [row(s0, decision="")], recs, arts, **KWR)
    assert all(s["status"] == "pending" for s in st["slots"])  # trạng thái gốc không đổi


def test_review_apply_is_atomic_when_any_row_is_invalid():
    st, recs, arts = _review_fixture("val")
    good, bad = row(st["slots"][0]), row(st["slots"][1], decision="reject", reason="lý do tự bịa")
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [good, bad], recs, arts, **KWR)
    assert all(s["status"] == "pending" for s in st["slots"])


def test_review_reject_requires_listed_reason_and_replaces_with_same_type_reserve():
    st, recs, arts = _review_fixture("test")
    new = R.apply_sheet(st, [row(st["slots"][0], decision="reject", reason="chứa số hiệu Điều hoặc văn bản")], recs, arts, **KWR)
    s0 = new["slots"][0]
    assert s0["article_id"] == "r0_001" and s0["type"] == "natural" and s0["status"] == "pending"
    assert s0["history"][0]["decision"] == "reject" and new["reserve_used"] == ["r0_001"]
    with pytest.raises(R.ReviewError):  # kiểu keyword còn r1; loại tiếp slot natural: hết dự phòng natural
        R.apply_sheet(new, [row(new["slots"][0], decision="reject", reason="khó hiểu")], recs, arts, **KWR)


def test_review_test_edit_logs_history_and_rechecks_verbatim_n8(tmp_path):
    st, recs, arts = _review_fixture("test")
    log = tmp_path / "logs" / "test_query_edits.jsonl"
    s = st["slots"][0]
    verbatim = "ai cũng biết người nộp thuế phải kê khai đầy đủ thông tin"  # chứa 8+ âm tiết liên tiếp của Điều
    with pytest.raises(R.ReviewError) as e:
        R.apply_sheet(st, [row(s, decision="edit", edited_text=verbatim)], recs, arts, verbatim_n=8, edit_log=log, **KWR)
    assert "chép nguyên văn" in str(e.value) and not log.exists()
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [row(s, decision="edit", edited_text="theo Điều 5 thì sao")], recs, arts, edit_log=log, **KWR)
    with pytest.raises(R.ReviewError):
        R.apply_sheet(st, [row(s, decision="edit", edited_text=s["text"])], recs, arts, edit_log=log, **KWR)
    new = R.apply_sheet(st, [row(s, decision="edit", edited_text="hỏi lại bằng lời khác hẳn", reviewer="Thư Giả")], recs, arts, edit_log=log, **KWR)
    assert new["slots"][0]["status"] == "accepted" and new["slots"][0]["edited"] and new["slots"][0]["text"] == "hỏi lại bằng lời khác hẳn"
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert entry["original"] == s["text"] and entry["edited"] == "hỏi lại bằng lời khác hẳn" and entry["editor"] == "Thư Giả" and entry["split"] == "test"
    assert new["slots"][0]["history"][0]["original_text"] == s["text"]


def test_review_edit_of_keyword_must_stay_within_configured_syllables():
    st, recs, arts = _review_fixture("test")
    kw = st["slots"][2]
    with pytest.raises(R.ReviewError) as e:
        R.apply_sheet(st, [row(kw, decision="edit", edited_text="một hai ba bốn năm sáu bảy")], recs, arts, **KWR)
    assert "1-6 âm tiết" in str(e.value)
    assert R.apply_sheet(st, [row(kw, decision="edit", edited_text="một hai ba bốn năm sáu")], recs, arts, **KWR)["slots"][2]["status"] == "accepted"


def test_review_accept_refused_for_query_failing_automatic_filter():
    st, recs, arts = _review_fixture("val")
    next(q for q in recs[0]["queries"] if q["type"] == "natural")["verbatim_copy"] = True
    with pytest.raises(R.ReviewError) as e:
        R.apply_sheet(st, [row(st["slots"][0])], recs, arts, **KWR)
    assert "không thể accept" in str(e.value)


def test_review_finalize_needs_every_slot_accepted_and_balanced_types():
    st, recs, arts = _review_fixture("val")
    with pytest.raises(R.ReviewError):
        R.finalize(st, recs, 1)
    done = R.apply_sheet(st, [row(s) for s in st["slots"]], recs, arts, **KWR)
    out = R.finalize(done, recs, 1)
    assert [q["type"] for q in out] == ["natural", "scenario", "keyword"] and all(q["review_history"] for q in out)
    with pytest.raises(R.ReviewError):
        R.finalize(done, recs, 2)  # sai quy mô mỗi kiểu


# ---------------- mẫu typo cho người đọc ----------------
def test_typo_review_removes_changed_meaning_only_after_human_fields_and_reports_count(tmp_path):
    tq = [{"query_id": f"a{i:03d}_001::natural", "text": f"học phí đại học số {i}", "split": "test", "article_id": f"a{i:03d}_001"} for i in range(40)]
    vs = V.make_variants(tq, 42)
    p = tmp_path / "sample.csv"
    V.export_typo_sample(vs, {q["query_id"]: q["text"] for q in tq}, 30, 42, p)
    rows = R.read_sheet(p)
    assert len(rows) == 30 and all(r["meaning_changed(reviewer)"] == "" for r in rows)
    with pytest.raises(ValueError):
        V.apply_typo_review(vs, rows)  # chưa có người đọc: không đoán
    for i, r in enumerate(rows):
        r.update({"meaning_changed(reviewer)": "yes" if i < 3 else "no", "reviewer": "Người Giả", "date": "2000-01-01"})
    kept, rep = V.apply_typo_review(vs, rows)
    assert rep["removed"] == 3 and rep["sample_size"] == 30 and len(kept) == len(vs) - 3
    assert all(v["query_id"] not in set(rep["removed_ids"]) for v in kept)
    with pytest.raises(ValueError):
        V.apply_typo_review(vs, [dict(rows[0], **{"meaning_changed(reviewer)": "có lẽ"})])
