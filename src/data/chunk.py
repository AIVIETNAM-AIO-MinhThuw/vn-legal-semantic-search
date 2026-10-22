"""Chunk theo SPEC 3.4: Điều -> Khoản -> câu -> cửa sổ token. Độ dài đo bằng tokenizer E5, gồm tiền tố."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .parse import KHOAN_RE
from .tokenizer import count_tokens

SENT_RE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ỸĐ“\"(])")


@dataclass
class Chunk:
    body: str
    text: str
    n_tokens: int
    kind: str  # whole | khoan | sentence | token_window


def make_prefix(doc_title: str, number: str, art_title: str) -> str:
    head = f"{doc_title} › Điều {number}. {art_title}".rstrip()
    return head + " › "


def _fits(tok, prefix: str, body: str, limit: int) -> int | None:
    n = count_tokens(tok, prefix + body)
    return n if n <= limit else None


def _khoan_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    for l in lines:
        if KHOAN_RE.match(l) or not blocks:
            blocks.append([l])
        else:
            blocks[-1].append(l)
    return blocks


def _sentences(lines: list[str]) -> list[tuple[str, str]]:
    """(câu, ký tự nối sau câu): newline cuối dòng, dấu cách giữa các câu cùng dòng."""
    out: list[tuple[str, str]] = []
    for l in lines:
        parts = SENT_RE.split(l)
        for j, p in enumerate(parts):
            out.append((p, " " if j < len(parts) - 1 else "\n"))
    return out


def _join(units: list[tuple[str, str]]) -> str:
    return "".join(t + sep for t, sep in units).strip()


def _token_windows(tok, prefix: str, text: str, limit: int, overlap: int) -> list[str]:
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    offs = enc["offset_mapping"]
    n = len(offs)
    budget = limit - count_tokens(tok, prefix)
    if budget <= overlap + 1:
        raise ValueError("Tiền tố quá dài so với giới hạn token.")
    out, start = [], 0
    while start < n:
        end = min(start + budget, n)
        while True:
            piece = text[offs[start][0]: offs[end - 1][1]].strip()
            if count_tokens(tok, prefix + piece) <= limit or end - start <= 1:
                break
            end -= 1
        out.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return out


def chunk_article(tok, prefix: str, lines: list[str], limit: int, token_overlap: int,
                  sentence_overlap: int = 1) -> tuple[list[Chunk], bool]:
    """Trả về (chunks, có_câu_dài_phải_cắt_theo_token)."""
    whole = "\n".join(lines)
    n = _fits(tok, prefix, whole, limit)
    if n is not None:
        return [Chunk(whole, prefix + whole, n, "whole")], False

    chunks: list[Chunk] = []
    long_sentence = False

    def emit(body: str, kind: str) -> None:
        text = prefix + body
        chunks.append(Chunk(body, text, count_tokens(tok, text), kind))

    cur: list[str] = []  # các Khoản đang gộp

    def flush() -> None:
        nonlocal cur
        if cur:
            emit("\n".join(cur), "khoan")
            cur = []

    for block in _khoan_blocks(lines):
        btxt = "\n".join(block)
        if _fits(tok, prefix, btxt, limit) is not None:
            if cur and _fits(tok, prefix, "\n".join(cur + [btxt]), limit) is None:
                flush()
            cur.append(btxt)
            continue
        flush()
        run: list[tuple[str, str]] = []

        def emit_run() -> None:
            i, m = 0, len(run)
            while i < m:
                j = i + 1
                while j < m and _fits(tok, prefix, _join(run[i:j + 1]), limit) is not None:
                    j += 1
                emit(_join(run[i:j]), "sentence")
                if j >= m:
                    break
                i = j - sentence_overlap if j - sentence_overlap > i else j

        for s in _sentences(block):
            if _fits(tok, prefix, s[0], limit) is None:
                emit_run()
                run = []
                long_sentence = True
                for w in _token_windows(tok, prefix, s[0], limit, token_overlap):
                    emit(w, "token_window")
            else:
                run.append(s)
        emit_run()
    flush()
    return chunks, long_sentence
