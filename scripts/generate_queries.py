"""Công cụ sinh query (SPEC mục 5). Prompt vẫn là bản nháp; chưa dùng để sinh query thật trong repo này.

Lệnh con:
  plan        chọn Điều theo split đã duyệt (đọc split từ config; không tạo/đổi split). `--pilot N` tạo kế hoạch thử nhỏ trên Điều train
  generate    sinh query thô cho một kế hoạch; gọi Gemini qua httpx. Key chỉ lấy từ biến môi trường GEMINI_API_KEY
  build-sets  lọc query thô, ghi thống kê trước/sau lọc theo từng kiểu; với val/test ghép tập ứng viên (thay thế cùng kiểu, cùng split)
  variants    biến thể no_diacritic/typo CHỈ cho query test, xác định theo seed
  typo-sample xuất file mẫu 30 biến thể typo cho người đọc (không điền kết quả)

Duyệt val/test offline: scripts/review_queries.py. Test dùng client giả: tests/test_querygen.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.querygen import select as sel  # noqa: E402
from src.querygen import sets, variants  # noqa: E402
from src.querygen.client import GeminiClient, MissingApiKeyError  # noqa: E402
from src.querygen.generator import QueryGenerator, build_meta, load_prompt  # noqa: E402
from src.querygen.io import JsonlStore, write_meta_once  # noqa: E402
from src.querygen.limits import RateLimiter  # noqa: E402


def load_cfgs(data_cfg: str, qcfg: str) -> tuple[dict, dict]:
    return (yaml.safe_load(open(data_cfg, encoding="utf-8")), yaml.safe_load(open(qcfg, encoding="utf-8")))


def require(cfg_section: dict, keys: list[str], where: str) -> None:
    missing = [k for k in keys if cfg_section.get(k) is None]
    if missing:
        raise SystemExit(f"{where}: {missing} chưa có giá trị (null). Xem reports/QUESTIONS_FOR_TEAM.md. Không tự chọn giá trị.")


def name(split: str, kind: str, tag: str = "") -> str:
    return f"queries_{split}{'.' + tag if tag else ''}.{kind}"


def cmd_plan(dcfg: dict, qcfg: dict, split: str, pilot: int | None = None) -> dict:
    s = qcfg["selection"]
    doc_split = sel.load_doc_splits(dcfg["split"]["output"])  # báo lỗi rõ nếu split chưa tồn tại
    pool = sel.eligible_articles(sel.read_jsonl(qcfg["paths"]["articles"]), sel.read_jsonl(qcfg["paths"]["docs"]), doc_split, split, s["excluded_titles"])
    seed = dcfg["seed"]
    if pilot is not None and split != "train":
        raise SystemExit("--pilot chỉ dành cho Điều train (chạy thử nhỏ trước khi freeze prompt)")
    if split == "train":
        ordered = [a["article_id"] for a in sel.stratified_order(pool, seed)]
        if pilot is not None:
            return {"split": split, "ordered_article_ids": ordered[:pilot], "target_pairs": None, "pilot": True}
        require(s, ["train_target_pairs_after_filter"], "configs/querygen.yaml: selection")
        return {"split": split, "ordered_article_ids": ordered, "target_pairs": s["train_target_pairs_after_filter"], "pool_size": len(pool)}
    require(s, ["eval_articles_per_type", "eval_reserve_per_type", "eval_selection"], "configs/querygen.yaml: selection")
    if s["eval_selection"] != "stratified_by_domain":
        raise SystemExit("eval_selection đã chốt là stratified_by_domain; giá trị khác chưa được phép")
    try:
        plan = sel.plan_eval(pool, s["eval_articles_per_type"], s["eval_reserve_per_type"], seed)
    except sel.InsufficientSourceError as e:
        raise SystemExit(f"Nguồn không đủ cho split {split}: {e}. Báo nhóm; không lấy bù từ split khác, không đổi seed.")
    return {"split": split, **plan}


def _count_pairs(store: JsonlStore, qcfg: dict, split: str):
    lex = qcfg["lexical"]

    def count() -> int:
        return len(sets.filter_split(store.read_all(), split, lex["train_overlap_threshold"], lex["train_overlap_inclusive"])[0])

    return count


def cmd_generate(dcfg: dict, qcfg: dict, split: str, plan: dict, *, client=None, mock: bool = False, sleep=None, clock=None, tag: str = "") -> dict:
    out_dir = Path(qcfg["paths"]["out_dir"])
    llm = qcfg["llm"]
    if client is None:
        require(llm, ["model", "temperature", "rate_limit_calls"], "configs/querygen.yaml: llm")
        try:
            client = GeminiClient(llm["model"], llm["temperature"], api_key_env=llm["api_key_env"])
        except MissingApiKeyError as e:
            raise SystemExit(str(e))
    template, phash = load_prompt(qcfg["prompt"]["path"])
    meta = build_meta(qcfg, phash, split, dcfg["seed"], mock=mock)
    write_meta_once(out_dir / name(split, "raw.meta.json", tag), meta)
    doc_split = sel.load_doc_splits(dcfg["split"]["output"])
    arts = sel.read_jsonl(qcfg["paths"]["articles"])
    pool = {a["article_id"]: a for a in sel.eligible_articles(arts, sel.read_jsonl(qcfg["paths"]["docs"]), doc_split, split, qcfg["selection"]["excluded_titles"])}
    ids = plan.get("ordered_article_ids") or (plan["article_ids"] + plan.get("reserve_ids", []))
    articles = [pool[i] for i in ids]  # KeyError nếu kế hoạch chứa Điều ngoài split / bị loại
    limiter = None
    if llm.get("rate_limit_calls") is not None:
        limiter = RateLimiter(llm["rate_limit_calls"], llm["rate_limit_window_seconds"], **({"clock": clock, "sleep": sleep} if clock and sleep else {}))
    store = JsonlStore(out_dir / name(split, "raw.jsonl", tag))
    gen = QueryGenerator(client, store, prompt_template=template, batch_size=llm["batch_size"], max_attempts=llm["max_attempts"],
                         base_delay=llm["retry_base_delay_seconds"], max_delay=llm["retry_max_delay_seconds"], verbatim_n=qcfg["lexical"]["verbatim_n"],
                         limiter=limiter, errors_path=out_dir / name(split, "errors.jsonl", tag), split=split, **({"sleep": sleep} if sleep else {}))
    if plan.get("target_pairs"):
        return gen.run_until(articles, _count_pairs(store, qcfg, split), plan["target_pairs"])
    return gen.run(articles)


def cmd_build_sets(qcfg: dict, split: str, plan: dict | None = None, tag: str = "") -> dict:
    out_dir, lex = Path(qcfg["paths"]["out_dir"]), qcfg["lexical"]
    recs = JsonlStore(out_dir / name(split, "raw.jsonl", tag)).read_all()
    thr, inc = lex["train_overlap_threshold"], lex["train_overlap_inclusive"]
    stats = sets.filter_stats(recs, split, thr, inc)
    (out_dir / name(split, "filter_stats.json", tag)).write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    if split == "train":
        kept, _ = sets.filter_split(recs, split, thr, inc)
        store = JsonlStore(out_dir / name(split, "filtered.jsonl", tag), key="query_id")
        for q in kept:
            store.append(q)
        return {"kept": len(kept), "stats": stats}
    if plan is None:
        raise SystemExit("val/test cần --plan để ghép tập ứng viên")
    out, replaced = sets.assemble_eval(recs, plan["article_ids"], plan["types"], plan["reserve_ids"], plan["reserve_types"])
    store = JsonlStore(out_dir / name(split, "candidates.jsonl", tag), key="query_id")
    for q in out:
        store.append(q)
    (out_dir / name(split, "replacements.json", tag)).write_text(json.dumps(replaced, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"candidates": len(out), "replaced": len(replaced), "stats": stats}


def main(argv=None, *, client=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-config", default="configs/data.yaml")
    ap.add_argument("--query-config", default="configs/querygen.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("plan", "generate", "build-sets"):
        p = sub.add_parser(nm)
        p.add_argument("--split", required=True, choices=sel.SPLITS)
        p.add_argument("--tag", default="", help="hậu tố tên file (vd. pilot)")
    sub.choices["plan"].add_argument("--pilot", type=int, help="chỉ train: kế hoạch thử nhỏ N Điều đầu danh sách phân tầng")
    sub.choices["generate"].add_argument("--plan")
    sub.choices["build-sets"].add_argument("--plan")
    vp = sub.add_parser("variants")
    vp.add_argument("--queries", required=True, help="JSONL query TEST đã duyệt (split = test)")
    vp.add_argument("--out", required=True)
    ts = sub.add_parser("typo-sample")
    ts.add_argument("--variants", required=True)
    ts.add_argument("--queries", required=True)
    ts.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    dcfg, qcfg = load_cfgs(args.data_config, args.query_config)
    out_dir = Path(qcfg["paths"]["out_dir"])
    if args.cmd == "plan":
        plan = cmd_plan(dcfg, qcfg, args.split, args.pilot)
        out = out_dir / name(args.split, "plan.json", args.tag or ("pilot" if args.pilot else ""))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã ghi kế hoạch: {out}")
    elif args.cmd == "generate":
        plan = json.loads(Path(args.plan or out_dir / name(args.split, "plan.json", args.tag)).read_text(encoding="utf-8"))
        print(json.dumps(cmd_generate(dcfg, qcfg, args.split, plan, client=client, tag=args.tag), ensure_ascii=False))
    elif args.cmd == "build-sets":
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8")) if args.plan else None
        print(json.dumps(cmd_build_sets(qcfg, args.split, plan, args.tag), ensure_ascii=False))
    elif args.cmd == "variants":
        vcfg = qcfg["variants"]
        qs = sel.read_jsonl(args.queries)
        vs = variants.make_variants(qs, dcfg["seed"], short_max=vcfg["typo_short_max_syllables"],
                                    errors_short=vcfg["typo_errors_short"], errors_long=vcfg["typo_errors_long"])
        store = JsonlStore(args.out, key="query_id")
        for v in vs:
            store.append(v)
        print(f"đã ghi {len(vs)} biến thể: {args.out}")
    elif args.cmd == "typo-sample":
        vs = sel.read_jsonl(args.variants)
        originals = {q["query_id"]: q["text"] for q in sel.read_jsonl(args.queries)}
        k = variants.export_typo_sample(vs, originals, qcfg["variants"]["typo_sample_size"], dcfg["seed"], args.out)
        print(f"đã xuất {k} biến thể typo cho người đọc: {args.out} (cột kết quả để trống)")


if __name__ == "__main__":
    main()
