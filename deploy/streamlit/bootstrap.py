"""Community Cloud packaging only: verified main snapshot + original frozen ZIP."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_name('source_manifest.json')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(root: Path, name: str) -> Path:
    parts = PurePosixPath(name)
    if parts.is_absolute() or '..' in parts.parts or '\\' in name:
        raise ValueError(f'Unsafe source path: {name}')
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f'Unsafe source path: {name}')
    return target


def extract_source(stream, target: Path, expected: dict[str, str]) -> None:
    for name in expected:
        safe_path(target, name)
    seen = set()
    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        for member in archive:
            name = member.name.partition('/')[2]
            if name not in expected:
                continue
            if not member.isfile() or name in seen or member.size > 4 * 1024 * 1024:
                raise ValueError(f'Unsafe source member: {name}')
            with archive.extractfile(member) as item:
                data = item.read()
            if hashlib.sha256(data).hexdigest() != expected[name]:
                raise ValueError(f'Source hash mismatch: {name}')
            path = safe_path(target, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            seen.add(name)
    if seen != set(expected):
        raise ValueError('Missing source files: ' + ', '.join(sorted(set(expected) - seen)))


def download(url: str, path: Path) -> None:
    partial = path.with_suffix('.part')
    try:
        with urlopen(Request(url, headers={'User-Agent': 'vnlegal-demo'}), timeout=120) as response:
            with partial.open('wb') as output:
                shutil.copyfileobj(response, output, length=4 * 1024 * 1024)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def artifacts_valid(folder: Path, manifest_hash: str) -> bool:
    manifest = folder / 'MANIFEST.json'
    if not manifest.is_file() or digest(manifest) != manifest_hash:
        return False
    files = json.loads(manifest.read_text())['files']
    return all((p := safe_path(folder, name)).is_file()
               and p.stat().st_size == meta['bytes'] and digest(p) == meta['sha256']
               for name, meta in files.items())


def prepare_runtime() -> Path:
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    runtime = Path(os.environ.get('VNLEGAL_RUNTIME_DIR', Path(tempfile.gettempdir()) / 'vnlegal-streamlit')) / spec['source_commit']
    source, artifacts = runtime / 'source', runtime / 'artifacts'
    runtime.mkdir(parents=True, exist_ok=True)
    expected = spec['source_files_sha256']
    if not all((p := safe_path(source, name)).is_file() and digest(p) == checksum for name, checksum in expected.items()):
        url = f"https://codeload.github.com/{spec['repository']}/tar.gz/{spec['source_commit']}"
        with urlopen(Request(url, headers={'User-Agent': 'vnlegal-demo'}), timeout=120) as response:
            extract_source(response, source, expected)
    if not artifacts_valid(artifacts, spec['artifact_manifest_sha256']):
        package = runtime / 'artifacts.zip'
        local_zip = os.environ.get('VNLEGAL_ARTIFACT_ZIP')
        if local_zip:
            package = Path(local_zip).resolve()
        elif not package.is_file():
            download(spec['artifact_url'], package)
        if digest(package) != spec['artifact_zip_sha256']:
            if not local_zip:
                package.unlink(missing_ok=True)
            raise ValueError('Artifact ZIP SHA-256 mismatch; check Drive download/quota')
        subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts/fetch_artifacts.py'),
                        '--zip', str(package), '--sha256', spec['artifact_zip_sha256'],
                        '--output-dir', str(artifacts)], check=True, cwd=ROOT)
        if not artifacts_valid(artifacts, spec['artifact_manifest_sha256']):
            raise ValueError('Incomplete or invalid runtime artifacts')
        if not local_zip:
            package.unlink()
    # Source uses its original paths; only the generated runtime gets symlinks.
    selection = json.loads((source / 'models/lr_selection.json').read_text(encoding='utf-8-sig'))
    model = f"models/e5_ft_B_lr{selection['selected_lr']}"
    for name in ['data/processed', 'data/raw', 'indexes', model]:
        dest = safe_path(artifacts, name)
        # resolve() follows existing links, so construct the leaf without resolving it.
        link = source / name
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() and link.resolve() == dest:
            continue
        if link.exists() or link.is_symlink():
            raise ValueError(f'Runtime path conflict: {name}')
        link.symlink_to(dest, target_is_directory=True)
    if os.access(artifacts, os.W_OK):
        for item in artifacts.rglob('*'):
            item.chmod(0o555 if item.is_dir() else 0o444)
        artifacts.chmod(0o555)
    return source


def start_backend(source: Path):
    java = shutil.which('java')
    if not java:
        raise RuntimeError('Java is missing; Community Cloud must install packages.txt')
    env = dict(os.environ, APP_CONFIG='configs/app.yaml', JAVA_HOME=str(Path(java).resolve().parents[1]),
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', TOKENIZERS_PARALLELISM='false')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = source.parent / 'api.log'
    with log.open('a', encoding='utf-8') as output:
        process = subprocess.Popen([sys.executable, '-B', '-m', 'uvicorn', 'src.api.app:app',
                                    '--host', '127.0.0.1', '--port', str(port), '--workers', '1'],
                                   cwd=source, env=env, stdout=output, stderr=subprocess.STDOUT)
    url = f'http://127.0.0.1:{port}'
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('API startup failed:\n' + log.read_text(encoding='utf-8')[-6000:])
        try:
            with urlopen(url + '/health', timeout=5) as response:
                if response.status == 200:
                    return process, url
        except OSError:
            pass
        time.sleep(2)
    process.terminate()
    raise TimeoutError('API did not become healthy within 900 seconds; inspect api.log')
