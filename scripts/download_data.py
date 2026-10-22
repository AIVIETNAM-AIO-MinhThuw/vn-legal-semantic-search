"""Tải các file parquet của dataset đúng revision ghim trong config (SPEC 3.1)."""
from __future__ import annotations

import argparse

import yaml
from huggingface_hub import hf_hub_download


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/data.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    ds = cfg["dataset"]
    if not ds.get("revision") or ds["revision"] == "main":
        raise SystemExit("dataset.revision phải là commit hash cố định, không được để trống hoặc 'main'.")
    for key, rel in ds["files"].items():
        path = hf_hub_download(ds["name"], rel, repo_type="dataset", revision=ds["revision"],
                               local_dir=cfg["paths"]["raw_dir"])
        print(key, path)


if __name__ == "__main__":
    main()
