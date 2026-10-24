"""Duyệt query val/test OFFLINE (SPEC 5.4): xuất phiếu CSV cho người điền, áp dụng phiếu đã điền, chốt tập.
Công cụ không điền tên người duyệt hay quyết định thay người. Xem docstring của src/querygen/review.py.

  init      tạo trạng thái từ tập ứng viên (kết quả `generate_queries.py build-sets` với --plan)
  export    xuất phiếu các slot đang chờ duyệt
  apply     áp dụng phiếu người đã điền (atomic; sửa câu chữ test ghi vào logs/test_query_edits.jsonl, kiểm tra lại N=8)
  finalize  chốt tập khi mọi slot đã được người chấp nhận (không ghi hash vào FROZEN.md)
  typo-apply  áp dụng kết quả người đọc mẫu 30 biến thể typo (loại biến thể bị đổi nghĩa; không gán nhãn lại)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.querygen import review as R  # noqa: E402
from src.querygen import select as sel  # noqa: E402
from src.querygen import variants as V  # noqa: E402
from src.querygen.io import JsonlStore  # noqa: E402


def load_articles(qcfg: dict) -> dict[str, dict]:
    return {a["article_id"]: a for a in sel.read_jsonl(qcfg["paths"]["articles"])}


def paths(qcfg: dict, split: str):
    out, rev = Path(qcfg["paths"]["out_dir"]), Path(qcfg["paths"]["review_dir"])
    return out / f"queries_{split}.raw.jsonl", rev / f"review_state_{split}.json", rev


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query-config", default="configs/querygen.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nm in ("init", "export", "apply", "finalize"):
        p = sub.add_parser(nm)
        p.add_argument("--split", required=True, choices=("val", "test"))
    sub.choices["init"].add_argument("--candidates", required=True)
    sub.choices["init"].add_argument("--plan", required=True)
    sub.choices["apply"].add_argument("--sheet", required=True)
    ta = sub.add_parser("typo-apply")
    ta.add_argument("--variants", required=True)
    ta.add_argument("--sheet", required=True)
    ta.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    q = yaml.safe_load(open(args.query_config, encoding="utf-8"))
    if args.cmd == "typo-apply":
        kept, report = V.apply_typo_review(sel.read_jsonl(args.variants), R.read_sheet(args.sheet))
        store = JsonlStore(args.out, key="query_id")
        for v in kept:
            store.append(v)
        print(json.dumps(report, ensure_ascii=False))
        return
    raw, state_path, rev = paths(q, args.split)
    rev.mkdir(parents=True, exist_ok=True)
    records = JsonlStore(raw).read_all()
    arts = load_articles(q)
    if args.cmd == "init":
        cands = sel.read_jsonl(args.candidates)
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        state_path.write_text(json.dumps(R.init_state(args.split, cands, plan), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã tạo {state_path} với {len(cands)} slot")
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if args.cmd == "export":
        sheet = rev / f"review_{args.split}_round{state['round']}.csv"
        print(f"đã xuất {R.export_sheet(state, arts, sheet)} dòng cần duyệt: {sheet} (người điền decision/reason/edited_text/reviewer/date)")
    elif args.cmd == "apply":
        new = R.apply_sheet(state, R.read_sheet(args.sheet), records, arts, verbatim_n=q["lexical"]["verbatim_n"], edit_log=q["paths"]["test_edit_log"] if args.split == "test" else None)
        state_path.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"đã áp dụng; còn {sum(1 for s in new['slots'] if s['status'] == 'pending')} slot chờ duyệt (vòng {new['round']})")
    elif args.cmd == "finalize":
        final = R.finalize(state, records, q["selection"]["eval_articles_per_type"])
        out = Path(q["paths"]["out_dir"]) / f"queries_{args.split}.jsonl"
        store = JsonlStore(out, key="query_id")
        for x in final:
            store.append(x)
        print(f"đã chốt {len(final)} query: {out} (chưa ghi hash vào data/FROZEN.md)")


if __name__ == "__main__":
    main()
