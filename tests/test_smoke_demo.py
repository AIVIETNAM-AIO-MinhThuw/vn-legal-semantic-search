"""Smoke must reject incomplete results and preserve feedback on cleanup."""
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from scripts import smoke_demo as smoke


def stub_response(systems, *, empty=False):
    item = dict(rank=1, article_id="fixture-1", doc_title="", article_number="1",
                article_title="", effect_status="", content="fixture", score=1., in_both=False)
    return dict(search_id=str(uuid4()), query_normalized="fixture", timing_ms=1., lists=[
        dict(system=system, score_type={"bm25": "bm25", "semantic": "cosine", "hybrid": "rrf"}[system],
             items=[] if empty else [item]) for system in systems])


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps(self.payload).encode()


def test_smoke_checks_four_modes(monkeypatch):
    modes = []

    def request(req, timeout):
        mode = json.loads(req.data)["mode"]
        modes.append(mode)
        return Response(stub_response(["bm25", "semantic"] if mode == "compare" else [mode]))

    monkeypatch.setattr(smoke, "urlopen", request)
    smoke.send_smoke_query()
    assert modes == ["bm25", "semantic", "hybrid", "compare"]


@pytest.mark.parametrize("systems,empty", [(["bm25"], False), (["semantic"], True)])
def test_smoke_rejects_wrong_or_empty_results(monkeypatch, systems, empty):
    monkeypatch.setattr(smoke, "urlopen", lambda *a, **k: Response(stub_response(systems, empty=empty)))
    with pytest.raises(RuntimeError):
        smoke.send_query(smoke.SearchRequest(query="fixture", mode="semantic", top_k=1), ["semantic"])


def test_failed_startup_logs_and_cleans_only_own_project(monkeypatch):
    calls = []
    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))

    def compose(project, *args, **kwargs):
        calls.append((project, args))
        return SimpleNamespace(returncode=1 if args[0] == "up" else 0)

    monkeypatch.setattr(smoke, "compose", compose)
    assert smoke.main() == 1
    assert len({project for project, _ in calls}) == 1
    assert calls[0][0].startswith("vnlegal-smoke-")
    assert any(args[0] == "logs" for _, args in calls)
    assert calls[-1][1] == ("down", "--remove-orphans")
    assert all("-v" not in args and "--volumes" not in args for _, args in calls)
