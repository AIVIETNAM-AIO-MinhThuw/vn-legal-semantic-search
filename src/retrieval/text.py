"""Shared text normalization and BM25-only Vietnamese word segmentation."""

from __future__ import annotations

import os
import subprocess
import unicodedata
from pathlib import Path


def normalize_query(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("Text must be a string")
    return " ".join(unicodedata.normalize("NFC", text).split())


def word_tokens(text: str, segmenter) -> list[str]:
    text = normalize_query(text)
    if not text:
        return []
    return [
        token.lower()
        for sentence in segmenter.word_segment(text)
        for token in sentence.split()
        if not all(unicodedata.category(ch).startswith("P") for ch in token)
    ]


def load_segmenter(settings: dict):
    """The wrapper changes cwd during init; restore it even when Java fails."""
    import py_vncorenlp

    cwd = Path.cwd()
    try:
        return py_vncorenlp.VnCoreNLP(
            annotators=settings["annotators"],
            save_dir=str(Path(settings["model_dir"]).resolve()),
            max_heap_size=settings["max_heap_size"],
        )
    finally:
        os.chdir(cwd)


def java_version(settings: dict) -> str:
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        raise ValueError("Set JAVA_HOME to the Java runtime used by pyjnius")
    java = Path(java_home) / "bin" / settings["java_executable"]
    result = subprocess.run(
        [str(java), "-version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=settings["java_timeout_seconds"],
    )
    return (result.stderr + result.stdout).strip()
