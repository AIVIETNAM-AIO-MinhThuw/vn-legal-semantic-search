"""Fetch only the configured VNCoreNLP files from a pinned revision."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

import yaml


def download(settings: dict, url_template: str, timeout: float) -> None:
    target = Path(settings["model_dir"])
    if target.exists():
        raise FileExistsError(target)
    if timeout <= 0 or "{revision}" not in url_template or "{file}" not in url_template:
        raise ValueError(
            "Positive timeout and URL template with {revision}/{file} required"
        )
    if not url_template.startswith("https://"):
        raise ValueError("HTTPS source required")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        for name in settings["files"]:
            destination = staging / name
            if destination.resolve().is_relative_to(staging.resolve()) is False:
                raise ValueError(f"Invalid model path: {name}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            url = url_template.format(revision=settings["revision"], file=name)
            with urllib.request.urlopen(url, timeout=timeout) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
            if destination.stat().st_size == 0:
                raise ValueError(f"Empty model file: {name}")
        (staging / "revision.txt").write_text(settings["revision"], encoding="utf-8")
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--url-template", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    download(cfg["segmenter"], args.url_template, args.timeout)


if __name__ == "__main__":
    main()
