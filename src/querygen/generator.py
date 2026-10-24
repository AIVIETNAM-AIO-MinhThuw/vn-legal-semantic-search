"""Bộ sinh query (SPEC 5.1–5.3). Chạy với client được truyền vào; không gọi mạng ở đây."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Callable

from .io import JsonlStore, write_meta_once
from .limits import RateLimiter, RetryableError, call_with_retry
from .text import (article_text, has_verbatim_copy, overlap, refers_to_article_or_document_number, syllables)

QUERY_TYPES = ("natural", "scenario", "keyword")


class InvalidResponse(RetryableError):
    """Phản hồi không đúng schema: được retry như lỗi tạm thời."""


def load_prompt(path: Path | str) -> tuple[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_prompt(template: str, articles: list[dict]) -> str:
    payload = [{"article_id": a["article_id"], "title": a.get("title", ""), "content": a["body"]} for a in articles]
    return template.replace("{{ARTICLES_JSON}}", json.dumps(payload, ensure_ascii=False, indent=1))


def parse_response(raw: str, requested: list[str]) -> dict[str, dict]:
    """Kiểm tra schema. Raise InvalidResponse nếu sai; chỉ nhận article_id đã yêu cầu và mỗi id một lần."""
    try:
        data = json.loads(raw)
        results = data["results"]
    except (ValueError, KeyError, TypeError) as e:
        raise InvalidResponse(f"JSON không đúng schema: {e!r}")
    out: dict[str, dict] = {}
    for r in results:
        if not isinstance(r, dict) or "article_id" not in r:
            raise InvalidResponse("kết quả thiếu article_id")
        aid = r["article_id"]
        if aid not in requested:
            raise InvalidResponse(f"article_id không được yêu cầu: {aid}")
        if aid in out:
            raise InvalidResponse(f"article_id lặp trong phản hồi: {aid}")
        if r.get("skip"):
            out[aid] = {"skip": True, "skip_reason": r.get("skip_reason"), "queries": None}
            continue
        q = r.get("queries")
        if not isinstance(q, dict) or set(q) != set(QUERY_TYPES) or not all(isinstance(q[t], str) and q[t].strip() for t in QUERY_TYPES):
            raise InvalidResponse(f"{aid}: cần đúng ba query natural/scenario/keyword không rỗng")
        if not 1 <= len(syllables(q["keyword"])) <= 4:
            raise InvalidResponse(f"{aid}: query keyword phải có 1-4 từ")
        out[aid] = {"skip": False, "skip_reason": None, "queries": {t: q[t].strip() for t in QUERY_TYPES}}
    missing = [a for a in requested if a not in out]
    if missing:
        raise InvalidResponse(f"phản hồi thiếu {len(missing)} article_id")
    return out


class QueryGenerator:
    def __init__(self, client, store: JsonlStore, *, prompt_template: str, batch_size: int, max_attempts: int,
                 base_delay: float, max_delay: float, verbatim_n: int, limiter: RateLimiter | None = None,
                 sleep: Callable[[float], None] = time.sleep, errors_path: Path | str | None = None, split: str | None = None):
        if not 10 <= batch_size <= 20:
            raise ValueError("batch_size phải từ 10 đến 20 Điều (SPEC 5.1)")
        self.client, self.store, self.template = client, store, prompt_template
        self.batch_size, self.max_attempts, self.base_delay, self.max_delay = batch_size, max_attempts, base_delay, max_delay
        self.verbatim_n, self.limiter, self.sleep, self.split = verbatim_n, limiter, sleep, split
        self.errors = JsonlStore(errors_path, key="batch_key") if errors_path else None
        self.stats = {"requests": 0, "written": 0, "skipped_existing": 0, "failed_batches": 0}

    def _request(self, batch: list[dict]) -> dict[str, dict]:
        ids = [a["article_id"] for a in batch]
        prompt = render_prompt(self.template, batch)

        def once():
            if self.limiter:
                self.limiter.acquire()
            self.stats["requests"] += 1
            return parse_response(self.client.generate(prompt), ids)

        return call_with_retry(once, max_attempts=self.max_attempts, base_delay=self.base_delay, max_delay=self.max_delay, sleep=self.sleep)

    def _record(self, art: dict, res: dict) -> dict:
        text = article_text(art.get("title", ""), art["body"])
        rec = {"article_id": art["article_id"], "doc_id": art.get("doc_id"), "split": art.get("split", self.split),
               "domain": art.get("domain"), "skip": res["skip"], "skip_reason": res["skip_reason"], "queries": []}
        if not res["skip"]:
            for t in QUERY_TYPES:
                q = res["queries"][t]
                rec["queries"].append({
                    "query_id": f"{art['article_id']}::{t}", "type": t, "text": q, "n_syllables": len(syllables(q)),
                    "overlap": round(overlap(q, text), 6),
                    "verbatim_copy": has_verbatim_copy(q, text, self.verbatim_n),
                    "refers_to_article_or_document": refers_to_article_or_document_number(q)})
        return rec

    def run_until(self, ordered_articles: list[dict], count_pairs, target: int) -> dict:
        """Bổ sung theo thứ tự đã cho, từng lượt `batch_size` Điều, đến khi `count_pairs()` >= target. Giữ mọi query hợp lệ của các
        Điều đã chọn: lượt cuối được phép vượt nhẹ. Hết danh sách mà chưa đủ thì dừng và báo thiếu (không lấy bù từ nơi khác)."""
        for i in range(0, len(ordered_articles), self.batch_size):
            if count_pairs() >= target:
                break
            self.run(ordered_articles[i:i + self.batch_size])
        pairs = count_pairs()
        return {**self.stats, "pairs_after_filter": pairs, "target_reached": pairs >= target}

    def run(self, articles: list[dict]) -> dict:
        """Xử lý các Điều chưa có trong file (resume). Batch lỗi sau khi hết số lần retry được ghi vào file lỗi và để lại
        chưa xử lý (lần chạy sau sẽ thử lại); không ghi bản ghi nào cho batch đó."""
        pending = []
        for a in articles:
            if a["article_id"] in self.store:
                self.stats["skipped_existing"] += 1
            else:
                pending.append(a)
        for i in range(0, len(pending), self.batch_size):
            batch = pending[i:i + self.batch_size]
            try:
                results = self._request(batch)
            except RetryableError as e:
                self.stats["failed_batches"] += 1
                if self.errors is not None:
                    self.errors.append({"batch_key": batch[0]["article_id"], "article_ids": [a["article_id"] for a in batch], "error": repr(e)})
                continue
            for art in batch:
                if self.store.append(self._record(art, results[art["article_id"]])):
                    self.stats["written"] += 1
        return dict(self.stats)


def build_meta(cfg: dict, prompt_hash: str, split: str, seed, *, mock: bool = False, generation_date: str | None = None) -> dict:
    """Metadata ghi cạnh file đầu ra (SPEC 5.1). Sinh thật yêu cầu model/temperature đã chốt trong config; ngày sinh ghi
    khi chạy thực tế (không lấy từ config)."""
    import datetime
    llm = cfg["llm"]
    if not mock:
        missing = [k for k in ("model", "temperature") if llm.get(k) is None]
        if missing:
            raise ValueError(f"configs/querygen.yaml: {missing} chưa được chốt; không thể sinh query thật (xem QUESTIONS_FOR_TEAM.md)")
    return {"provider": llm["provider"], "model": llm.get("model"), "temperature": llm.get("temperature"),
            "generation_date": generation_date or datetime.date.today().isoformat(), "prompt_path": cfg["prompt"]["path"],
            "prompt_version": cfg["prompt"]["version"], "prompt_sha256": prompt_hash, "split": split, "seed": seed,
            "batch_size": llm["batch_size"], "mock": mock}
