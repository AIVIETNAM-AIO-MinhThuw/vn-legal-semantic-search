"""Sinh `openapi.json` từ code (SPEC 14.5). Chạy: python -X utf8 scripts/export_openapi.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.app import create_app  # noqa: E402


def render() -> str:
    return json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    out = ROOT / "openapi.json"
    out.write_text(render(), encoding="utf-8", newline="\n")
    print(f"Đã ghi {out}")
