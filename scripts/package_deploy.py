"""Package the committed main application, unchanged, with CPU Docker files and verified artifacts.

python scripts/package_deploy.py --zip ../vnlegal-demo-v1.zip --checksum ../vnlegal-demo-v1.sha256
Output: release/deploy-cpu (ignored by Git); refuses to overwrite an existing bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PINNED_ZIP_SHA256 = "059a6a1101721ec497fb22d82d33a4194e8f1158150037897fd2ef0b43783096"
SOURCE_PATHS = ["src/__init__.py", "src/api", "src/app", "src/contracts", "src/retrieval",
                "src/ui", "configs", "scripts/run_e5.py", "models/lr_selection.json", ".streamlit"]
PACKAGING_PATHS = ["Dockerfile.api", "Dockerfile.ui", "docker-compose.yml", ".dockerignore",
                   "requirements-api.txt", "requirements-ui.txt", "scripts/smoke_demo.py"]


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--checksum", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "release/deploy-cpu")
    args = parser.parse_args()
    checksum = args.checksum.read_text(encoding="utf-8-sig").split()[0].lower()
    if not re.fullmatch(r"[a-f0-9]{64}", checksum) or checksum != PINNED_ZIP_SHA256:
        raise ValueError("Checksum file does not match the published vnlegal-demo-v1 SHA-256")
    if sha(args.zip) != checksum:
        raise ValueError("ZIP SHA-256 mismatch")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "rev-parse", "main^{commit}"], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(["git", "archive", commit, *SOURCE_PATHS], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source:
            target = (output / member.name).resolve()
            if not target.is_relative_to(output) or not (member.isdir() or member.isfile()):
                raise ValueError(f"Unexpected source member: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    source_hashes = {p.relative_to(output).as_posix(): sha(p)
                     for p in output.rglob("*") if p.is_file()}
    for name in PACKAGING_PATHS:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    # The main app uses its original paths. Resolve them through image symlinks to a read-only mount.
    selection = json.loads((output / "models/lr_selection.json").read_text(encoding="utf-8-sig"))
    model = f"e5_ft_B_lr{selection['selected_lr']}"
    if not re.fullmatch(r"e5_ft_B_lr[0-9.e+-]+", model):
        raise ValueError("Invalid selected model path")
    dockerfile = output / "Dockerfile.api"
    docker = dockerfile.read_text(encoding="utf-8")
    links = ("RUN ln -s /app/artifacts/data/processed /app/data/processed \\\n"
             "    && ln -s /app/artifacts/data/raw /app/data/raw \\\n"
             "    && ln -s /app/artifacts/indexes /app/indexes \\\n"
             f"    && ln -s /app/artifacts/models/{model} /app/models/{model}\n\n")
    if docker.count("USER 10001:10001") != 1:
        raise ValueError("Unexpected Dockerfile USER anchor")
    dockerfile.write_text(docker.replace("USER 10001:10001", links + "USER 10001:10001"), encoding="utf-8")
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/fetch_artifacts.py"), "--zip", str(args.zip.resolve()),
                    "--sha256", checksum, "--output-dir", str(output / "artifacts")], cwd=ROOT, check=True)
    for name, digest in source_hashes.items():
        if sha(output / name) != digest:
            raise ValueError(f"Main source changed during packaging: {name}")
    release = {"source_commit": commit, "source_ref": "main", "runtime": "CPU/Linux/amd64",
               "artifact_zip_sha256": checksum, "source_files_sha256": source_hashes,
               "packaging_files_sha256": {name: sha(output / name) for name in PACKAGING_PATHS},
               "limitations": ["Application uses the existing main manifest validation and startup behavior; D3 compliance is not claimed.",
                               "No source code, model, corpus or index rebuilt or modified."]}
    (output / "RELEASE.json").write_text(json.dumps(release, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(ROOT / "docs/deploy_cpu.md", output / "DEPLOY.md")
    print(f"CPU bundle: {output}\nUnchanged main source: {commit}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
