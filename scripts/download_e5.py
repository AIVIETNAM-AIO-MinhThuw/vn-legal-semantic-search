"""Explicit pinned E5 download; inference never calls the network."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval.common import file_hash  # noqa: E402


def download(cfg: dict) -> None:
    settings = cfg["model"]
    revision = settings["revision"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Model revision must be an immutable commit SHA")
    target = Path(cfg["paths"]["model"])
    if target.exists():
        raise FileExistsError(target)
    os.environ["HF_HUB_DISABLE_XET"] = str(int(cfg["download"]["disable_xet"]))
    from huggingface_hub import snapshot_download

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=target.name + ".", dir=target.parent))
    try:
        snapshot_download(
            settings["name"],
            revision=revision,
            allow_patterns=settings["files"],
            local_dir=staging,
            cache_dir=cfg["download"]["cache_dir"],
            max_workers=cfg["download"]["max_workers"],
        )
        hashes = {}
        for name in settings["files"]:
            if Path(name).name != name:
                raise ValueError(f"Expected top-level model file: {name}")
            hashes[name] = file_hash(staging / name)
        (staging / "download.json").write_text(
            json.dumps({"model": settings, "files": hashes}, indent=2), encoding="utf-8"
        )
        os.rename(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    download(yaml.safe_load(args.config.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
