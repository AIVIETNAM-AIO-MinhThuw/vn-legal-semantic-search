"""SearchService: nạp BM25 S1₀ + một hệ thống semantic, lọc metadata, hybrid RRF, highlight, feedback SQLite."""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
import sqlite3
import subprocess
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from src.api.errors import ApiError
from src.app.artifacts import artifact_path, bm25_index_files, sha_file as _sha, verify_artifacts
from src.contracts import (
    ErrorCode, FeedbackAck, FeedbackRequest, FilterValues, Highlight, InfoLimits, InfoResponse,
    ResultItem, ResultList, SearchRequest, SearchResponse, SearchWarning, WarningCode,
)
from src.retrieval.common import read_jsonl, rank_articles

import logging
LOG = logging.getLogger("search_service")

ROOT = Path(__file__).resolve().parents[2]
WORD = re.compile(r"\w+")


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"_script_{name}", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def normalize(q: str) -> str:
    return " ".join(unicodedata.normalize("NFC", q).split())


STOPWORDS = set("""được gì nào thì là và của có các những cho với để khi bao nhiêu không phải như thế này đó ra sao hay
hoặc trong theo về một mà nếu đã đang sẽ bị từ tại do vì nên cũng chỉ còn rồi ai đâu chúng tôi mình họ hãy cần muốn""".split())


def keyword_spans(content: str, query: str) -> list[Highlight]:
    """BM25: tô các từ (âm tiết) của query xuất hiện trong Điều; gộp các từ liền kề thành cụm."""
    qs = {w for w in WORD.findall(query.lower()) if len(w) > 1 and w not in STOPWORDS}
    spans = []
    for m in WORD.finditer(content):
        if m.group().lower() in qs:
            if spans and content[spans[-1][1]:m.start()].strip() == "":
                spans[-1][1] = m.end()
            else:
                spans.append([m.start(), m.end()])
    return [Highlight(start=a, end=b) for a, b in spans]


def segments(content: str, max_len: int = 400) -> list[tuple[int, int]]:
    """Tách Điều thành câu/dòng (theo xuống dòng, dấu chấm, chấm phẩy) để chọn đoạn liên quan."""
    out = []
    for m in re.finditer(r"[^\n.;]+[.;]?", content):
        a, b = m.start(), m.end()
        while a < b and content[a].isspace(): a += 1
        while b > a and content[b - 1].isspace(): b -= 1
        if b - a >= 15:
            out.append((a, min(b, a + max_len)))
    return out


class SearchService:
    def __init__(self, config_path: Path):
        import torch
        self.cfg = yaml.safe_load((ROOT / config_path).read_text(encoding="utf-8"))
        dev = self.cfg["device"]
        self.device = ("cuda" if torch.cuda.is_available() else "cpu") if dev == "auto" else dev
        self.lock = threading.Lock()
        self._prepare_artifacts()
        self._load_corpus()
        self._load_bm25()
        self._load_semantic()
        self._init_db()
        self._fv = self.info().filter_values
        # Khởi động JVM (VNCoreNLP) và encoder ngay trên luồng chính để lượt tìm đầu không chậm.
        t = time.perf_counter(); self._bm25("khởi động hệ thống", None, 1); self._semantic("khởi động", None, 1)
        LOG.info("Warm-up %.1fs", time.perf_counter() - t)

    # ---------- nạp ----------
    def _prepare_artifacts(self):
        self.artifact_root = (ROOT / self.cfg.get("artifact_root", ".")).resolve()
        feedback = (ROOT / self.cfg["feedback_db"]).resolve()
        if "artifact_root" in self.cfg and feedback.is_relative_to(self.artifact_root):
            raise ValueError("feedback_db phải nằm ngoài artifact_root chỉ đọc")
        covered = verify_artifacts(self.artifact_root) if "artifact_root" in self.cfg else None
        self.bcfg = yaml.safe_load((ROOT / self.cfg["bm25_config"]).read_text(encoding="utf-8"))
        self.bpaths = {k: artifact_path(self.artifact_root, self.bcfg["paths"][k])
                       for k in ("chunks", "articles", "docs", "index")}
        self.segmenter_settings = {**self.bcfg["segmenter"], "model_dir": str(
            artifact_path(self.artifact_root, self.bcfg["segmenter"]["model_dir"]))}
        s = self.cfg["systems"][self.cfg["semantic_system"]]
        self.scfg = yaml.safe_load((ROOT / s["config"]).read_text(encoding="utf-8"))
        model = s.get("model", self.scfg["paths"]["model"])
        if "{lr}" in model:
            selection = json.loads((ROOT / "models/lr_selection.json").read_text(encoding="utf-8-sig"))
            model = model.replace("{lr}", selection["selected_lr"])
        self.spaths = {
            "model": artifact_path(self.artifact_root, model),
            "index": artifact_path(self.artifact_root, s.get("index", self.scfg["paths"]["index"])),
            "chunks": artifact_path(self.artifact_root, self.scfg["paths"]["chunks"]),
        }
        if s["kind"] == "e5":
            self.spaths.update({k: artifact_path(self.artifact_root, self.scfg["paths"][k])
                                for k in ("articles", "docs")})
        required = [self.bpaths[k] for k in ("chunks", "articles", "docs")]
        required += [self.bpaths["index"] / "manifest.json", self.spaths["index"] / "manifest.json",
                     self.spaths["chunks"], self.spaths["index"] / "vectors.npy"]
        required += [self.spaths["index"] / ("chunks.jsonl" if s["kind"] == "e5" else "chunk_ids.json")]
        if s["kind"] == "e5":
            required += [self.spaths[k] for k in ("articles", "docs")]
        required += [self.spaths["model"] / name for name in (
            "config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json")]
        required += [Path(self.segmenter_settings["model_dir"]) / name
                     for name in [*self.bcfg["segmenter"]["files"], "revision.txt"]]
        bm25_manifest = json.loads((self.bpaths["index"] / "manifest.json").read_text(encoding="utf-8"))
        required += [self.bpaths["index"] / name for name in bm25_index_files(bm25_manifest)]
        for path in required:
            if not path.is_file():
                raise FileNotFoundError(f"Thiếu file runtime: {path}")
            if covered is not None and path.relative_to(self.artifact_root).as_posix() not in covered:
                raise ValueError(f"File runtime không có trong MANIFEST.json: {path}")

    def _load_corpus(self):
        p = self.bpaths
        self.arts = {a["article_id"]: a for a in read_jsonl(p["articles"])}
        self.docs = {d["doc_id"]: d for d in read_jsonl(p["docs"])}

    def _load_bm25(self):
        from src.retrieval.bm25 import BM25Retriever, provenance
        from src.retrieval.text import load_segmenter
        paths = dict(self.bpaths)
        source = provenance(self.bcfg, paths, model_dir=Path(self.segmenter_settings["model_dir"]))
        # Reject invalid persisted state before starting the JVM.
        self.bm25 = BM25Retriever.load(paths["index"], self.bcfg["bm25"], None, source)
        self.segmenter = load_segmenter(self.segmenter_settings)
        self.bm25.segmenter = self.segmenter
        self.manifests = {"bm25_s10": _sha(paths["index"] / "manifest.json")}

    def _load_semantic(self):
        name = self.cfg["semantic_system"]
        s = self.cfg["systems"][name]
        cfg = self.scfg
        self.sem_name, self.sem_label = name, s["label"]
        if s["kind"] == "e5":
            from src.retrieval.e5 import E5Encoder, E5Retriever
            mod = _load_script("run_e5")
            paths = dict(self.spaths)
            paths["queries"] = paths["chunks"]
            source = mod.provenance(cfg, paths)
            enc = E5Encoder.load(paths["model"], cfg["encoding"], self.device)
            r = E5Retriever.load(paths["index"], enc, {"chunk_top_k": cfg["retrieval"]["chunk_top_k"]}, source)
            self.sem_chunks, self.sem_vectors = r.chunks, r.vectors
            self.sem_encode = lambda q: enc.encode([q], "query")[0]
            self.sem_encode_passages = lambda ts: enc.encode(ts, "passage")
            self.tokenizer = enc.tokenizer
            self.model_name, self.model_rev = cfg["model"]["name"], cfg["model"]["revision"]
            index = paths["index"]
        else:
            from src.retrieval.dense import DenseEncoder, DenseRetriever
            model, index = self.spaths["model"], self.spaths["index"]
            enc = DenseEncoder(model, cfg["encoding"], self.device)
            r = DenseRetriever.load(index, read_jsonl(self.spaths["chunks"]), enc,
                                    cfg["retrieval"]["chunk_top_k"], chunks_path=self.spaths["chunks"])
            self.sem_chunks, self.sem_vectors = r.chunks, r.vectors
            self.sem_encode = lambda q: enc.encode([q], "query")[0]
            self.sem_encode_passages = lambda ts: enc.encode(ts, "passage")
            self.tokenizer = enc.tok
            self.model_name = model.relative_to(self.artifact_root).as_posix()
            mf = model / "model.safetensors"
            self.model_rev = _sha(mf)[:12] if mf.exists() else "unknown"
        self.manifests[name] = _sha(index / "manifest.json")

    def _init_db(self):
        p = ROOT / self.cfg["feedback_db"]; p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, check_same_thread=False)
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS searches(search_id TEXT PRIMARY KEY, created TEXT, query TEXT, mode TEXT,
                                              top_k INTEGER, filters TEXT, results TEXT);
          CREATE TABLE IF NOT EXISTS feedback(search_id TEXT, system TEXT, article_id TEXT, label TEXT, rank INTEGER,
                                              created TEXT, PRIMARY KEY(search_id, system, article_id));""")
        self.db.commit()

    # ---------- info ----------
    def info(self) -> InfoResponse:
        years = [d["year"] for d in self.docs.values() if isinstance(d.get("year"), int)]
        vals = lambda k: sorted({d[k] for d in self.docs.values() if d.get(k)})
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5).stdout.strip() or "unknown"
        except Exception:
            commit = "unknown"
        return InfoResponse(semantic_system=f"{self.sem_name} — {self.sem_label}", model_name=self.model_name,
                            model_revision=self.model_rev, manifest_hashes=self.manifests, git_commit=commit,
                            limits=InfoLimits(query_max_tokens=self.cfg["query_max_tokens"]),
                            filter_values=FilterValues(doc_types=vals("loai_van_ban"), domains=vals("linh_vuc"),
                                                       issuers=vals("co_quan_ban_hanh"),
                                                       year_min=min(years) if years else None, year_max=max(years) if years else None),
                            modes=["bm25", "semantic", "hybrid", "compare"])

    # ---------- search ----------
    def _allowed(self, f) -> set | None:
        fv = self._fv
        for vals, opts in ((f.doc_types, fv.doc_types), (f.domains, fv.domains), (f.issuers, fv.issuers)):
            if any(v not in opts for v in vals):
                raise ApiError(ErrorCode.INVALID_FILTER, "Giá trị lọc không hợp lệ.")
        if f.year_min is not None and f.year_max is not None and f.year_min > f.year_max:
            raise ApiError(ErrorCode.INVALID_FILTER, "year_min lớn hơn year_max.")
        if not (f.doc_types or f.domains or f.issuers or f.year_min is not None or f.year_max is not None):
            return None
        ok = set()
        for aid, a in self.arts.items():
            d = self.docs[a["doc_id"]]
            if f.doc_types and d.get("loai_van_ban") not in f.doc_types: continue
            if f.domains and d.get("linh_vuc") not in f.domains: continue
            if f.issuers and d.get("co_quan_ban_hanh") not in f.issuers: continue
            y = d.get("year")
            if f.year_min is not None and (y is None or y < f.year_min): continue
            if f.year_max is not None and (y is None or y > f.year_max): continue
            ok.add(aid)
        return ok

    def _rank(self, chunks, scores, allowed, k):
        if allowed is not None:
            mask = np.fromiter((c["article_id"] in allowed for c in chunks), bool, len(chunks))
            if not mask.any():
                return []
            scores = np.where(mask, scores, -np.inf)
            depth = int(mask.sum())
        else:
            depth = 200
        res = rank_articles(chunks, np.nan_to_num(scores, neginf=-1e9), max(depth, k), k)
        return [(a, s) for a, s in res if allowed is None or a in allowed]

    def _bm25(self, q, allowed, k):
        from src.retrieval.text import word_tokens
        toks = word_tokens(q, self.segmenter)
        if not toks:
            return []
        scores = np.asarray(self.bm25.index.get_scores(toks), dtype=np.float64)
        return [(a, s) for a, s in self._rank(self.bm25.chunks, scores, allowed, k) if s > 0]

    def _semantic(self, q, allowed, k):
        v = self.sem_encode(q)
        return self._rank(self.sem_chunks, (self.sem_vectors @ v).astype(np.float64), allowed, k)

    def _passage_spans(self, contents: list[str], query: str) -> list[list[Highlight]]:
        """Semantic/hybrid: chọn câu gần nghĩa nhất với query bằng chính encoder semantic (cosine)."""
        segs = [segments(c)[:40] for c in contents]
        texts = [c[a:b] for c, ss in zip(contents, segs) for a, b in ss]
        if not texts:
            return [[] for _ in contents]
        qv = self.sem_encode(query)
        pv = self.sem_encode_passages(texts)
        sims = pv @ qv
        out, k = [], 0
        for ss in segs:
            if not ss:
                out.append([]); continue
            best = int(np.argmax(sims[k:k + len(ss)])); k += len(ss)
            out.append([Highlight(start=ss[best][0], end=ss[best][1])])
        return out

    def _items(self, res, query, highlight, other=None, kind="keyword"):
        contents = [unicodedata.normalize("NFC", self.arts[aid]["body"]) for aid, _ in res]
        if not highlight:
            spans = [[] for _ in res]
        elif kind == "keyword":
            spans = [keyword_spans(c, query) for c in contents]
        else:
            spans = self._passage_spans(contents, query)
        items = []
        for i, ((aid, score), content, hl) in enumerate(zip(res, contents, spans), 1):
            a = self.arts[aid]; d = self.docs[a["doc_id"]]
            items.append(ResultItem(rank=i, article_id=aid, doc_title=d.get("title", ""), article_number=str(a.get("number", "")),
                                    article_title=a.get("title") or "", effect_status=d.get("tinh_trang_hieu_luc") or "",
                                    content=content, score=float(score), in_both=bool(other and aid in other),
                                    highlights=hl))
        return items

    def search(self, req: SearchRequest) -> SearchResponse:
        t0 = time.perf_counter()
        q = normalize(req.query)
        if not WORD.search(q):
            raise ApiError(ErrorCode.EMPTY_QUERY, "Câu hỏi rỗng hoặc không có chữ.")
        warnings = []
        ids = self.tokenizer(q, add_special_tokens=False)["input_ids"]
        if len(ids) > self.cfg["query_max_tokens"]:
            q = self.tokenizer.decode(ids[: self.cfg["query_max_tokens"]], skip_special_tokens=True).strip()
            warnings.append(SearchWarning(code=WarningCode.QUERY_TRUNCATED,
                                          message=f"Câu hỏi dài hơn {self.cfg['query_max_tokens']} token nên đã được cắt bớt."))
        allowed = self._allowed(req.filters)
        k = req.top_k
        with self.lock:
            lists = []
            if req.mode in ("bm25", "compare"):
                b = self._bm25(q, allowed, k)
            if req.mode in ("semantic", "compare"):
                s = self._semantic(q, allowed, k)
            if req.mode == "bm25":
                lists = [ResultList(system="bm25", score_type="bm25", items=self._items(b, q, req.highlight))]
            elif req.mode == "semantic":
                lists = [ResultList(system="semantic", score_type="cosine", items=self._items(s, q, req.highlight, kind="passage"))]
            elif req.mode == "compare":
                sb, ss = {a for a, _ in b}, {a for a, _ in s}
                lists = [ResultList(system="bm25", score_type="bm25", items=self._items(b, q, req.highlight, ss)),
                         ResultList(system="semantic", score_type="cosine", items=self._items(s, q, req.highlight, sb, kind="passage"))]
            else:  # hybrid: Reciprocal Rank Fusion trên top-50 mỗi hệ thống
                depth, rk = 50, self.cfg["rrf_k"]
                fused = {}
                for res in (self._bm25(q, allowed, depth), self._semantic(q, allowed, depth)):
                    for r, (a, _) in enumerate(res, 1):
                        fused[a] = fused.get(a, 0.0) + 1.0 / (rk + r)
                h = sorted(fused.items(), key=lambda x: (-x[1], x[0]))[:k]
                lists = [ResultList(system="hybrid", score_type="rrf", items=self._items(h, q, req.highlight, kind="passage"))]
        LOG.info("search mode=%s %.1f ms", req.mode, (time.perf_counter() - t0) * 1000)
        sid = uuid.uuid4()
        results = {l.system: [i.article_id for i in l.items] for l in lists}
        self.db.execute("INSERT INTO searches VALUES (?,?,?,?,?,?,?)",
                        (str(sid), datetime.now(timezone.utc).isoformat(), req.query, req.mode, k,
                         req.filters.model_dump_json(), json.dumps(results)))
        self.db.commit()
        return SearchResponse(search_id=sid, query_normalized=q, warnings=warnings,
                              timing_ms=(time.perf_counter() - t0) * 1000, lists=lists)

    # ---------- feedback ----------
    def feedback(self, req: FeedbackRequest) -> FeedbackAck:
        row = self.db.execute("SELECT results FROM searches WHERE search_id=?", (str(req.search_id),)).fetchone()
        if not row:
            raise ApiError(ErrorCode.INVALID_REQUEST, "search_id không tồn tại.")
        ids = json.loads(row[0]).get(req.system)
        if not ids or req.article_id not in ids:
            raise ApiError(ErrorCode.INVALID_REQUEST, "(system, article_id) không thuộc lượt tìm này.")
        self.db.execute("INSERT OR REPLACE INTO feedback VALUES (?,?,?,?,?,?)",
                        (str(req.search_id), req.system, req.article_id, req.label, ids.index(req.article_id) + 1,
                         datetime.now(timezone.utc).isoformat()))
        self.db.commit()
        return FeedbackAck(**req.model_dump())

    def export_csv(self) -> bytes:
        out = io.StringIO(newline="")
        w = csv.writer(out)
        w.writerow(["search_id", "created", "query", "mode", "system", "article_id", "rank", "label"])
        for r in self.db.execute("""SELECT f.search_id, f.created, s.query, s.mode, f.system, f.article_id, f.rank, f.label
                                    FROM feedback f JOIN searches s USING(search_id) ORDER BY f.created"""):
            w.writerow(r)
        return out.getvalue().encode("utf-8-sig")
