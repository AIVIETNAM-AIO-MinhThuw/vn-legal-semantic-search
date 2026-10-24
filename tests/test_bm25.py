import math
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.bm25 import BM25Retriever, validate_chunks
from src.retrieval.text import word_tokens


class Segmenter:
    def word_segment(self, text):
        assert text == unicodedata.normalize("NFC", text)
        return [
            text.replace("Công ty", "Công_ty").replace(
                "người lao động", "người_lao_động"
            )
        ]


def chunks():
    return [
        dict(
            chunk_id="b#0", article_id="b", doc_id="d", chunk_index=0, text="thuế thuế"
        ),
        dict(
            chunk_id="a#0", article_id="a", doc_id="d", chunk_index=0, text="thuế lương"
        ),
        dict(chunk_id="a#1", article_id="a", doc_id="d", chunk_index=1, text="lương"),
    ]


def config():
    return dict(
        k1=1.2,
        b=0.75,
        method="lucene",
        chunk_top_k=200,
        ngram_range=[1, 1],
        log_every_chunks=500,
    )


def test_tokens_preserve_words_numbers_negation_and_nfc():
    text = unicodedata.normalize(
        "NFD", " Công ty không trả người lao động 12/2020/NĐ-CP ! "
    )
    assert word_tokens(text, Segmenter()) == [
        "công_ty",
        "không",
        "trả",
        "người_lao_động",
        "12/2020/nđ-cp",
    ]


def test_symbols_are_not_punctuation():
    assert word_tokens("+ = ≤ ≥ × ₫ ! ,", Segmenter()) == ["+", "=", "≤", "≥", "×", "₫"]


def test_lucene_scores_against_independent_formula_and_maxp():
    r = BM25Retriever.build(chunks(), config(), Segmenter())
    # N=3 chunks, df(thuế)=2, lengths 2/2/1, avgdl=5/3.
    idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
    expected = idf * 2 / (2 + 1.2 * (1 - 0.75 + 0.75 * 2 / (5 / 3)))
    result = r.search("thuế", 2, None)
    assert [a for a, _ in result] == ["b", "a"]
    assert result[0][1] == pytest.approx(expected, rel=1e-6)
    assert r.search("thuế thuế", 2, None)[0][1] == pytest.approx(2 * expected, rel=1e-6)


def test_ties_cutoff_oov_and_rebuild_order():
    data = [
        dict(
            chunk_id=f"{i:03}#0",
            article_id=f"{i:03}",
            doc_id="d",
            chunk_index=0,
            text="thuế",
        )
        for i in range(205)
    ]
    r = BM25Retriever.build(list(reversed(data)), config(), Segmenter())
    assert r.search("thuế", 3, None) == BM25Retriever.build(
        data, config(), Segmenter()
    ).search("thuế", 3, None)
    assert [a for a, _ in r.search("xyz", 2, None)] == ["000", "001"]
    assert r.search("!!!", 2, None) == []
    with pytest.raises(ValueError):
        r.search("thuế", 0, None)


def test_save_load_and_reject_mismatch_or_corruption(tmp_path):
    r = BM25Retriever.build(chunks(), config(), Segmenter())
    target = tmp_path / "index"
    provenance = {"source": "fixture", "segmenter": "test"}
    r.save(target, provenance)
    loaded = BM25Retriever.load(target, config(), Segmenter(), provenance)
    assert loaded.search("thuế", 2, None) == r.search("thuế", 2, None)
    with pytest.raises(ValueError, match="manifest"):
        BM25Retriever.load(target, {**config(), "b": 0.4}, Segmenter(), provenance)
    with pytest.raises(FileExistsError):
        r.save(target, provenance)
    with (target / "chunks.jsonl").open("a", encoding="utf-8") as f:
        f.write("{}\n")
    with pytest.raises(ValueError, match="checksum"):
        BM25Retriever.load(target, config(), Segmenter(), provenance)


def test_invalid_chunks_and_config():
    for data in [
        [],
        chunks() + [chunks()[0]],
        [{**chunks()[0], "text": " "}],
        [{**chunks()[0], "chunk_index": -1}],
    ]:
        with pytest.raises(ValueError):
            validate_chunks(data)
    with pytest.raises(ValueError):
        BM25Retriever.build(chunks(), {**config(), "b": float("nan")}, Segmenter())
    with pytest.raises(ValueError):
        BM25Retriever.build(chunks(), {**config(), "ngram_range": [1, 2]}, Segmenter())


def test_csv_and_mapping_validation(tmp_path):
    from scripts.run_bm25 import read_queries, validate_corpus

    p = tmp_path / "q.csv"
    p.write_text("query_id,query\nQ01,thuế\n", encoding="utf-8-sig")
    assert read_queries(p) == [{"query_id": "Q01", "query": "thuế"}]
    p.write_text("query_id,query\nQ01,thuế\nQ01,lương\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_queries(p)
    with pytest.raises(ValueError):
        validate_corpus(chunks(), [], [])


def test_nan_scores_rejected():
    r = BM25Retriever.build(chunks(), config(), Segmenter())
    r.index.get_scores = lambda _: np.array([np.nan, 0, 0])
    with pytest.raises(ValueError):
        r.search("thuế", 2, None)


def test_cli_exports_blind_candidates_and_refuses_overwrite(tmp_path, monkeypatch):
    import json

    from scripts import run_bm25

    paths = {
        name: tmp_path / name
        for name in ["chunks", "articles", "docs", "queries", "index", "output"]
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
    paths["docs"].write_text(
        json.dumps(dict(doc_id="d", title="Luật")) + "\n", encoding="utf-8"
    )
    paths["queries"].write_text(
        "query_id,query,source_article_id\nQ1,thuế,a\n", encoding="utf-8"
    )
    cfg = {
        "paths": {k: str(v) for k, v in paths.items()},
        "bm25": config(),
        "retrieval": {"top_k": 2, "run_tag": "fixture"},
        "segmenter": {},
        "seed": 42,
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(run_bm25, "provenance", lambda *_: {"test": True})
    monkeypatch.setattr(run_bm25, "load_segmenter", lambda *_: Segmenter())
    summary = run_bm25.run(cfg, config_file, True, None)
    assert summary["n_candidates"] == 2
    candidates = [
        json.loads(line)
        for line in (paths["output"] / "candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert {c["article_id"] for c in candidates} == {"a", "b"}
    assert all(
        not {"score", "rank", "source_article_id"} & c.keys() for c in candidates
    )
    assert (
        candidates[0]["article_id"]
        != (paths["output"] / "run.trec").read_text().splitlines()[0].split()[2]
    )
    run_bm25.run(cfg, config_file, False, None, tmp_path / "replay")
    assert (tmp_path / "replay" / "run.trec").read_bytes() == (
        paths["output"] / "run.trec"
    ).read_bytes()
    with pytest.raises(FileExistsError):
        run_bm25.run(cfg, config_file, False, None)


def test_download_is_atomic_and_uses_configured_revision(tmp_path, monkeypatch):
    import io

    from scripts.download_vncorenlp import download

    requested = []

    def fetch(url, timeout):
        requested.append((url, timeout))
        return io.BytesIO(b"model")

    monkeypatch.setattr("urllib.request.urlopen", fetch)
    settings = {
        "model_dir": str(tmp_path / "model"),
        "revision": "fixture-rev",
        "files": ["a.jar", "models/wseg"],
    }
    download(settings, "https://example.test/{revision}/{file}", 10)
    assert requested[1][0] == "https://example.test/fixture-rev/models/wseg"
    assert (tmp_path / "model" / "revision.txt").read_text() == "fixture-rev"
    with pytest.raises(FileExistsError):
        download(settings, "https://example.test/{revision}/{file}", 10)
