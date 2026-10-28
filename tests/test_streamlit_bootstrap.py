import hashlib
import io
import tarfile

import pytest

from deploy.streamlit import bootstrap
from deploy.streamlit.bootstrap import extract_source


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name, data in entries.items():
            item = tarfile.TarInfo(name)
            item.size = len(data)
            tar.addfile(item, io.BytesIO(data))
    stream.seek(0)
    return stream


def test_extracts_only_verified_source(tmp_path):
    data = b'original source'
    expected = {'src/app.py': hashlib.sha256(data).hexdigest()}
    extract_source(archive({'repo/src/app.py': data, 'repo/unrelated.txt': b'ignored'}), tmp_path, expected)
    assert (tmp_path / 'src/app.py').read_bytes() == data
    assert not (tmp_path / 'unrelated.txt').exists()


def test_changed_source_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='hash'):
        extract_source(archive({'repo/src/app.py': b'changed'}), tmp_path, {'src/app.py': '0' * 64})
    assert not (tmp_path / 'src/app.py').exists()


def test_missing_source_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='Missing'):
        extract_source(archive({}), tmp_path, {'src/app.py': '0' * 64})


def test_manifest_cannot_escape_runtime(tmp_path):
    with pytest.raises(ValueError, match='Unsafe'):
        extract_source(archive({'repo/../outside.py': b'x'}), tmp_path, {'../outside.py': hashlib.sha256(b'x').hexdigest()})
    assert not (tmp_path.parent / 'outside.py').exists()


def test_backend_requires_java(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, 'which', lambda name: None)
    with pytest.raises(RuntimeError, match='Java is missing'):
        bootstrap.start_backend(tmp_path)


def test_failed_backend_does_not_report_healthy(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap.shutil, 'which', lambda name: '/usr/bin/java')
    class FailedProcess:
        def poll(self):
            return 1
    monkeypatch.setattr(bootstrap.subprocess, 'Popen', lambda *args, **kwargs: FailedProcess())
    with pytest.raises(RuntimeError, match='API startup failed'):
        bootstrap.start_backend(tmp_path)
