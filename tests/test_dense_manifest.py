"""Small offline index fixtures protect the shared dense loader, never frozen artifacts."""
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from src.retrieval.common import file_hash, read_jsonl, write_jsonl
from src.retrieval.dense import DenseRetriever


@pytest.mark.parametrize("package", ["transformers", "tokenizers", "sentence-transformers", "torch"])
def test_missing_runtime_dependency_rejected(monkeypatch, package):
    import importlib.metadata
    from src.retrieval.dense import runtime_versions
    installed = importlib.metadata.version
    def version(name):
        if name == package:
            raise importlib.metadata.PackageNotFoundError(name)
        return installed(name)
    monkeypatch.setattr(importlib.metadata, "version", version)
    with pytest.raises(ValueError, match=package):
        runtime_versions()


class Tokenizer:
    pass


class Encoder:
    def __init__(self, path):
        self.path = path
        self.s = dict(max_length=512, batch_size=32, fp16_inference=False,
                      query_prefix="query: ", passage_prefix="passage: ")
        self.model = SimpleNamespace(config=SimpleNamespace(hidden_size=2))
        self.tok = Tokenizer()

    def encode(self, texts, kind):
        return np.asarray([[1., 0.] for _ in texts], dtype=np.float32)


@pytest.fixture
def index(tmp_path):
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text('{"_name_or_path":"fixture/model","hidden_size":2}')
    (model / "model.safetensors").write_bytes(b"fixture weights, not a real model")
    (model / "tokenizer.json").write_text('{"fixture":true}')
    chunks = [dict(chunk_id=f"a#{i}", article_id="a", doc_id="d", chunk_index=i, text=f"text {i}")
              for i in range(2)]
    source = tmp_path / "chunks.jsonl"
    write_jsonl(source, chunks)
    enc = Encoder(model)
    target = tmp_path / "index"
    DenseRetriever.build(chunks, enc, 200).save(target, {
        "config": {"encoding": enc.s, "retrieval": {"chunk_top_k": 200}},
        "chunks_sha256": file_hash(source), "model_files": {},
    })
    return target, source, enc


def rewrite(target, mutate):
    path = target / "manifest.json"
    meta = json.loads(path.read_text())
    mutate(meta)
    path.write_text(json.dumps(meta))


def load(index):
    target, source, enc = index
    return DenseRetriever.load(target, read_jsonl(source), enc, 200, chunks_path=source)


def test_complete_manifest_roundtrip(index):
    target, source, enc = index
    meta = json.loads((target / "manifest.json").read_text())
    assert set(meta["versions"]) == {"transformers", "tokenizers", "sentence-transformers", "torch"}
    assert meta["encoder"]["model_name"] == "fixture/model"
    assert meta["encoder"]["model_revision"] == file_hash(enc.path / "model.safetensors")
    result = load(index)
    assert [c["chunk_id"] for c in result.chunks] == ["a#0", "a#1"]
    np.testing.assert_array_equal(result.vectors, [[1., 0.], [1., 0.]])


@pytest.mark.parametrize("field", ["versions", "encoder", "chunks_sha256", "model_files", "config"])
def test_missing_required_metadata_rejected(index, field):
    rewrite(index[0], lambda meta: meta.pop(field, None))
    with pytest.raises(ValueError, match="manifest"):
        load(index)


@pytest.mark.parametrize("package", ["transformers", "tokenizers", "sentence-transformers", "torch"])
def test_dependency_version_mismatch_rejected(index, package):
    rewrite(index[0], lambda meta: meta["versions"].update({package: "0.0.0"}))
    with pytest.raises(ValueError, match=package):
        load(index)


def test_torch_build_suffix_allowed(index):
    rewrite(index[0], lambda meta: meta["versions"].update({"torch": meta["versions"]["torch"] + "+cu121"}))
    assert len(load(index).chunks) == 2


@pytest.mark.parametrize("change", ["prefix", "depth", "weights", "chunks", "count", "ids", "shape", "dtype"])
def test_incompatible_config_or_payload_rejected(index, change):
    target, source, enc = index
    if change == "prefix":
        enc.s["query_prefix"] = "wrong: "
    elif change == "depth":
        rewrite(target, lambda meta: meta["config"]["retrieval"].update(chunk_top_k=10))
    elif change == "weights":
        (enc.path / "model.safetensors").write_bytes(b"changed")
    elif change == "chunks":
        source.write_text(source.read_text().replace("text 0", "changed"))
    elif change == "count":
        rewrite(target, lambda meta: meta.update(n_chunks=99))
    elif change == "ids":
        (target / "chunk_ids.json").write_text('["a#1","a#0"]')
    else:
        vectors = np.ones((2, 3) if change == "shape" else (2, 2),
                          dtype=np.float64 if change == "dtype" else np.float32)
        np.save(target / "vectors.npy", vectors)
        rewrite(target, lambda meta: meta.update(vectors_sha256=file_hash(target / "vectors.npy")))
    with pytest.raises(ValueError):
        load(index)


def test_missing_vectors_rejected(index):
    (index[0] / "vectors.npy").unlink()
    with pytest.raises(FileNotFoundError):
        load(index)


def test_real_encoder_loads_after_model_relocation(tmp_path):
    from transformers import BertConfig, BertModel, BertTokenizerFast
    from src.app.service import SearchService
    from src.retrieval.dense import DenseEncoder

    model = tmp_path / "original"
    model.mkdir()
    (model / "vocab.txt").write_text("[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\ntext\nquery\npassage\n")
    BertTokenizerFast(vocab_file=str(model / "vocab.txt")).save_pretrained(model)
    BertModel(BertConfig(vocab_size=8, hidden_size=8, num_hidden_layers=1,
                         num_attention_heads=2, intermediate_size=16)).save_pretrained(model)
    settings = dict(max_length=512, batch_size=32, fp16_inference=False,
                    query_prefix="query: ", passage_prefix="passage: ")
    enc = DenseEncoder(model, settings, "cpu")
    source = tmp_path / "chunks.jsonl"
    chunks = [dict(chunk_id="a#0", article_id="a", doc_id="d", chunk_index=0, text="text")]
    write_jsonl(source, chunks)
    target = tmp_path / "index"
    DenseRetriever.build(chunks, enc).save(target, {
        "config": {"encoding": settings, "retrieval": {"chunk_top_k": 200}},
        "chunks_sha256": file_hash(source),
    })
    relocated = tmp_path / "mounted-model"
    shutil.copytree(model, relocated)
    service = SearchService.__new__(SearchService)
    service.cfg = {"semantic_system": "fixture", "systems": {"fixture": {"kind": "dense", "label": "fixture"}}}
    service.scfg = {"encoding": settings, "retrieval": {"chunk_top_k": 200}}
    service.spaths = {"model": relocated, "index": target, "chunks": source}
    service.artifact_root, service.device, service.manifests = tmp_path, "cpu", {}
    service._load_semantic()
    assert service.sem_vectors.shape == (1, 8)
    assert service.sem_encode("query").shape == (8,)
