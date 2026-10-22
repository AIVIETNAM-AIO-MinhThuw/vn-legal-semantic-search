"""Tokenizer E5 dùng chung cho chunking và validate_data (SPEC 3.4, 7.3)."""
from __future__ import annotations

from pathlib import Path

from transformers import AutoTokenizer


def load_tokenizer(cfg: dict):
    tok_dir = Path(cfg["tokenizer"]["local_dir"])
    if not (tok_dir / "tokenizer.json").exists():
        raise SystemExit(f"Thiếu tokenizer ở {tok_dir}; chạy scripts/download_data.py trước.")
    return AutoTokenizer.from_pretrained(str(tok_dir))


def count_tokens(tok, text: str) -> int:
    """Số token không tính special token. Tiền tố 'passage: ' chưa gắn (SPEC 3.4)."""
    return len(tok(text, add_special_tokens=False)["input_ids"])
