"""Configured startup must fail closed; fixture-only processes never load real artifacts."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("failure", [FileNotFoundError, ValueError])
def test_configured_startup_propagates_load_errors(monkeypatch, failure):
    from src.api.app import _app_from_env
    from src.app import service

    monkeypatch.setenv("APP_CONFIG", "fixture.yaml")
    def fail(_):
        raise failure("fixture startup failure")
    monkeypatch.setattr(service, "SearchService", fail)
    with pytest.raises(failure, match="fixture startup failure"):
        _app_from_env()


@pytest.mark.parametrize("state", ["valid", "missing", "mismatch"])
def test_process_startup_exit_and_health(tmp_path, state):
    manifest = tmp_path / "manifest.json"
    if state != "missing":
        manifest.write_text('{"valid":' + ("true" if state == "valid" else "false") + '}')
    script = """
import json
from pathlib import Path
from src.app import service
calls = []
def load(config):
    calls.append(config)
    if not json.loads(Path(config).read_text())["valid"]:
        raise ValueError("fixture manifest mismatch")
    return object()
service.SearchService = load
from src.api.app import app
print('IMPORTED', flush=True)
from fastapi.testclient import TestClient
assert len(calls) == 1
assert TestClient(app).get('/health').status_code == 200
print('HEALTHY')
"""
    env = {**os.environ, "APP_CONFIG": str(manifest), "PYTHONPATH": os.pathsep.join(
        [str(ROOT), os.environ.get("PYTHONPATH", "")])}
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=60)
    if state == "valid":
        assert result.returncode == 0, result.stderr
        assert "HEALTHY" in result.stdout
    else:
        assert result.returncode != 0
        assert "IMPORTED" not in result.stdout
        assert "HEALTHY" not in result.stdout
        assert ("FileNotFoundError" if state == "missing" else "fixture manifest mismatch") in result.stderr
