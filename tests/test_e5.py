"""Offline encoder/index tests; no model download and no quality assertions."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.e5 import E5Encoder, E5Retriever, mean_pool


def settings():
    return dict(
        preprocessing_version="e5-natural-v1",
        max_length=8,
        batch_size=2,
        dimension=3,
        pooling="mean",
        normalize=True,
        dtype="float32",
        attention="eager",
        norm_atol=1e-5,
        log_every_batches=1,
    )


class Tokenizer:
    def __init__(self):
        self.seen = []

    def __call__(self, texts, **kwargs):
        assert kwargs["truncation"] is False
        self.seen.extend(texts)
        lengths = [len(t.split()) + 2 for t in texts]
        ids = torch.zeros((len(texts), max(lengths)), dtype=torch.long)
        mask = torch.zeros_like(ids)
        for i, n in enumerate(lengths):
            ids[i, :n] = torch.arange(1, n + 1)
            mask[i, :n] = 1
        return {"input_ids": ids, "attention_mask": mask}


class Model(torch.nn.Module):
    config = SimpleNamespace(hidden_size=3)

    def forward(self, input_ids, attention_mask):
        x = input_ids.float()
        return SimpleNamespace(
            last_hidden_state=torch.stack([x, x * x, torch.ones_like(x)], dim=-1)
        )


def encoder():
    return E5Encoder(Tokenizer(), Model(), settings(), "cpu")


def chunks():
    return [
        dict(
            chunk_id="b#0", article_id="b", doc_id="d", chunk_index=0, text="Luật thuế"
        ),
        dict(
            chunk_id="a#0", article_id="a", doc_id="d", chunk_index=0, text="Luật thuế"
        ),
        dict(
            chunk_id="a#1",
            article_id="a",
            doc_id="d",
            chunk_index=1,
            text="Luật thuế khác",
        ),
    ]


def test_mean_pool_masks_padding():
    hidden = torch.tensor([[[1.0, 0.0], [3.0, 4.0], [999.0, 999.0]]])
    mask = torch.tensor([[1, 1, 0]])
    assert torch.equal(mean_pool(hidden, mask), torch.tensor([[2.0, 2.0]]))


def test_encoder_prefix_normalization_repeat_and_no_segmentation():
    e = encoder()
    first = e.encode(["  Công ty\ntrả lương  "], "query")
    assert e.tokenizer.seen == ["query: Công ty trả lương"]
    assert np.allclose(np.linalg.norm(first, axis=1), 1)
    assert first.dtype == np.float32
    assert np.array_equal(first, e.encode(["Công ty trả lương"], "query"))
    e.encode(["Luật thuế"], "passage")
    assert e.tokenizer.seen[-1] == "passage: Luật thuế"
    e.encode(["Luật\n  thuế"], "passage")
    assert e.tokenizer.seen[-1] == "passage: Luật\n  thuế"
    with pytest.raises(ValueError):
        e.encode(["query: thuế"], "query")
    with pytest.raises(ValueError, match="length"):
        e.encode(["thuế " * 10], "passage")


def test_exact_maxp_ties_and_save_load(tmp_path):
    e = encoder()
    retriever = E5Retriever.build(chunks(), e, {"chunk_top_k": 200})
    result = retriever.search("thuế", 2, None)
    assert {a for a, _ in result} == {"a", "b"}
    vectors = retriever.vectors
    query = e.encode(["thuế"], "query")[0]
    scores = vectors @ query
    assert result[0][1] == pytest.approx(float(max(scores)))
    retriever.vectors[:] = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    tied = retriever.search("thuế", 2, None)
    assert [a for a, _ in tied] == ["a", "b"]
    target = tmp_path / "index"
    provenance = {"test": True}
    retriever.save(target, provenance)
    loaded = E5Retriever.load(target, e, {"chunk_top_k": 200}, provenance)
    assert loaded.search("thuế", 2, None) == tied
    with pytest.raises(ValueError, match="manifest"):
        E5Retriever.load(target, e, {"chunk_top_k": 10}, provenance)
    with pytest.raises(FileExistsError):
        retriever.save(target, provenance)
    with (target / "vectors.npy").open("ab") as f:
        f.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        E5Retriever.load(target, e, {"chunk_top_k": 200}, provenance)


def test_invalid_input_and_nonfinite_vectors():
    e = encoder()
    with pytest.raises(ValueError):
        E5Retriever.build([], e, {"chunk_top_k": 200})
    r = E5Retriever.build(chunks(), e, {"chunk_top_k": 200})
    assert r.search("  ", 2, None) == []
    with pytest.raises(ValueError):
        r.search("thuế", 0, None)
    r.vectors[0, 0] = np.nan
    with pytest.raises(ValueError):
        r.search("thuế", 2, None)


def test_model_loader_never_uses_network(monkeypatch, tmp_path):
    from src.retrieval import e5

    calls = []

    def tokenizer_loader(path, **kwargs):
        calls.append(kwargs)
        return Tokenizer()

    def model_loader(path, **kwargs):
        calls.append(kwargs)
        return Model()

    monkeypatch.setattr(e5.AutoTokenizer, "from_pretrained", tokenizer_loader)
    monkeypatch.setattr(e5.AutoModel, "from_pretrained", model_loader)
    E5Encoder.load(tmp_path, settings(), "cpu")
    assert all(c["local_files_only"] and not c["trust_remote_code"] for c in calls)
    assert calls[1]["use_safetensors"] is True
    assert calls[1]["torch_dtype"] == torch.float32


def test_shared_loader_checks_current_packages(tmp_path, monkeypatch):
    from src.retrieval import e5

    e = encoder()
    retriever = E5Retriever.build(chunks(), e, {"chunk_top_k": 200})
    target = tmp_path / "index"
    retriever.save(target, {"test": True})
    monkeypatch.setattr(e5, "dependency_versions", lambda: {"torch": "incompatible"})
    with pytest.raises(ValueError, match="dependency"):
        E5Retriever.load(target, e, {"chunk_top_k": 200}, {"test": True})


def test_e5_cli_exports_and_replays(tmp_path, monkeypatch):
    import json

    from scripts import run_e5

    paths = {
        name: tmp_path / name
        for name in [
            "chunks",
            "articles",
            "docs",
            "queries",
            "model",
            "index",
            "output",
        ]
    }
    paths["chunks"].write_text(
        "".join(json.dumps(c) + "\n" for c in chunks()), encoding="utf-8"
    )
    paths["articles"].write_text(
        "".join(
            json.dumps(dict(article_id=a, doc_id="d", body="nội dung")) + "\n"
            for a in ["a", "b"]
        ),
        encoding="utf-8",
    )
    paths["docs"].write_text(json.dumps(dict(doc_id="d")) + "\n", encoding="utf-8")
    paths["queries"].write_text(
        "query_id,query,source_article_id\nQ1,thuế,b\n", encoding="utf-8"
    )
    cfg = {
        "paths": {k: str(v) for k, v in paths.items()},
        "encoding": settings(),
        "retrieval": {"top_k": 2, "chunk_top_k": 200, "run_tag": "e5_fixture"},
        "runtime": {"device": "cpu"},
        "seed": 42,
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(run_e5, "provenance", lambda *_: {"test": True})
    monkeypatch.setattr(run_e5, "prepare_runtime", lambda *_: {"device": "cpu"})
    monkeypatch.setattr(E5Encoder, "load", lambda *_: encoder())
    summary = run_e5.run(cfg, config_path, True, None)
    assert summary["n_candidates"] == 2
    records = [
        json.loads(line)
        for line in (paths["output"] / "candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert all(not {"rank", "score", "source_article_id"} & r.keys() for r in records)
    run_e5.run(cfg, config_path, False, None, tmp_path / "replay")
    assert (tmp_path / "replay" / "run.trec").read_bytes() == (
        paths["output"] / "run.trec"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        run_e5.run(cfg, config_path, False, None)


def test_model_download_manifest_and_corruption(tmp_path, monkeypatch):
    import json

    from scripts.download_e5 import download
    from scripts.run_e5 import provenance

    cfg = {
        "model": {"name": "fixture", "revision": "a" * 40, "files": ["config.json"]},
        "paths": {"model": str(tmp_path / "model")},
        "download": {
            "disable_xet": True,
            "cache_dir": str(tmp_path / "cache"),
            "max_workers": 1,
        },
        "versions": {},
    }

    def fetch(name, **kwargs):
        assert kwargs["revision"] == "a" * 40
        (kwargs["local_dir"] / "config.json").write_text("{}")

    monkeypatch.setattr("huggingface_hub.snapshot_download", fetch)
    download(cfg)
    manifest = json.loads((tmp_path / "model" / "download.json").read_text())
    assert manifest["model"] == cfg["model"]
    (tmp_path / "model" / "config.json").write_text("corrupt")
    with pytest.raises(ValueError, match="checksum"):
        provenance(cfg, {"model": tmp_path / "model"})
