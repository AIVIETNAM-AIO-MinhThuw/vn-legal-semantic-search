"""Mở nguồn và output parser của một văn bản để người duyệt đối chiếu.

Quy ước số dòng: dòng văn bản đã chuẩn hóa do `html_to_lines` trả về, đánh số từ 1 (cùng quy ước với các bảng đối chiếu).
Mỗi dòng có nhãn `[Đn]` = Điều parser gán (`*` = Điều sau chữ ký), `[đầu]` = đầu văn bản, `[chương]` = dòng Chương/Mục bị bỏ,
`[ký]` = chữ ký/nơi nhận/lời dẫn sau chữ ký bị bỏ, `[cắt]` = phụ lục/biểu mẫu bị cắt. `▶` = tiêu đề Điều parser nhận.

Ví dụ:
  python -X utf8 scripts/show_source.py --doc 110137 --lines 36-48
  python -X utf8 scripts/show_source.py --doc 110137 --lines 40-40 --html      # kèm đoạn HTML gốc quanh dòng
  python -X utf8 scripts/show_source.py --doc 110137 --articles                 # danh sách Điều parser nhận
  python -X utf8 scripts/show_source.py --doc 110137 --article-id 110137_005    # nội dung Điều trong output
"""
from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data import parse as P  # noqa: E402
from src.data.html_text import html_to_lines  # noqa: E402

TAGS = {P.OWNER_NONE: "đầu", P.OWNER_SECTION: "chương", P.OWNER_TRAILER: "ký", P.OWNER_CUT: "cắt"}


def load_html(cfg: dict, doc_id: str) -> str:
    cached = Path(cfg["processed"]["dir"]) / "review_cache" / f"{doc_id}.html"
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    pf = pq.ParquetFile(Path(cfg["paths"]["raw_dir"]) / cfg["dataset"]["files"]["content"])
    for batch in pf.iter_batches(batch_size=500, columns=["id", "content_html"]):
        for i, h in zip(batch.column("id").to_pylist(), batch.column("content_html").to_pylist()):
            if i == doc_id:
                return h
    raise SystemExit(f"Không thấy doc_id {doc_id} trong {cfg['dataset']['files']['content']}")


def html_trace(raw: str, line: str, width: int = 140) -> str:
    probe = line.strip().lstrip("“\"‘ ")[:24]
    if len(probe) < 6:
        return "(dòng quá ngắn để định vị tự động)"
    for label, text in (("HTML gốc", raw), ("HTML đã unescape", htmllib.unescape(raw))):
        k = text.find(probe)
        if k >= 0:
            snippet = text[max(0, k - width // 2): k + width].replace("\n", "\\n")
            return f"{label}, vị trí ký tự {k}: …{snippet}…"
    return "(không tìm thấy nguyên văn đầu dòng trong HTML: văn bản có thể bị tách bởi thẻ; tìm theo từ khóa trong file cache)"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/data.yaml")
    ap.add_argument("--doc", required=True)
    ap.add_argument("--lines", help="khoảng dòng 1-based, ví dụ 36-48")
    ap.add_argument("--html", action="store_true", help="kèm đoạn HTML gốc quanh mỗi dòng")
    ap.add_argument("--articles", action="store_true", help="liệt kê các Điều parser nhận")
    ap.add_argument("--article-id", help="in nội dung Điều trong output (articles_index.jsonl)")
    ap.add_argument("--width", type=int, default=400, help="độ rộng tối đa mỗi dòng khi in")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    raw = load_html(cfg, args.doc)
    lines = html_to_lines(raw)
    parsed = P.parse_articles(lines)
    print(f"# {args.doc}: {len(lines)} dòng văn bản chuẩn hóa, {len(parsed.articles)} Điều parser nhận")

    if args.articles:
        for k, a in enumerate(parsed.articles):
            hi = max(a.src_lines) if a.src_lines else a.heading_line
            print(f"{args.doc}_{k + 1:03d}  Điều {a.number}{'*' if a.after_signature else ''}  tiêu đề L{a.heading_line + 1}, nội dung tới L{hi + 1}"
                  f"  {(a.title or '<nội dung>')[:70]}  {P.article_reject_reason(a) or ''}")
    if args.lines:
        m = re.fullmatch(r"(\d+)-(\d+)", args.lines)
        if not m:
            raise SystemExit("--lines phải có dạng a-b")
        a, b = int(m.group(1)), int(m.group(2))
        for i in range(max(1, a) - 1, min(len(lines), b)):
            o = parsed.line_owner[i]
            tag = TAGS[o] if o < 0 else f"Đ{parsed.articles[o].number}{'*' if parsed.articles[o].after_signature else ''}"
            head = "▶" if o >= 0 and parsed.articles[o].heading_line == i else " "
            text = lines[i] if len(lines[i]) <= args.width else lines[i][: args.width] + "…"
            print(f"{head}L{i + 1} [{tag}] {text}")
            if args.html:
                print("      " + html_trace(raw, lines[i]))
    if args.article_id:
        p = Path(cfg["processed"]["dir"]) / "articles_index.jsonl"
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            if r["article_id"] == args.article_id:
                print(f"--- {r['article_id']} Điều {r['number']} — {r['title']} (display_label: {r.get('display_label')})\n{r['body']}")
                break
        else:
            print(f"{args.article_id} không có trong articles_index.jsonl (bị loại hoặc là bản trùng); xem logs/rejected.jsonl và duplicate_groups.json")


if __name__ == "__main__":
    main()
