"""Bộ sinh query (SPEC 5.1–5.3). Chạy với client được truyền vào; không gọi mạng ở đây.

Xử lý lỗi theo từng Điều:
- JSON hỏng (không parse được, thiếu `results`) hoặc không có Điều hợp lệ nào -> retry cả batch.
- Batch có cả Điều hợp lệ và Điều lỗi -> ghi Điều hợp lệ; Điều lỗi không ghi query nào, chỉ ghi log (article_id, trường, lý do)
  và không được đánh dấu đã xử lý, nên lần resume sau gửi lại. Chưa có bộ đếm retry riêng theo Điều.
- Kết quả không gán được cho Điều nào (thiếu article_id, article_id không được yêu cầu) -> log cấp batch.
- Hết retry vì 429 -> log và dừng cả lượt chạy, không gửi batch khác.
- Mọi request có 10–20 Điều (SPEC 5.1), chia cân bằng bằng `next_batch_size`; chỉ dừng và báo khi tổng số Điều còn chờ
  dưới 10. Còn Điều lỗi sau khi gửi hết thì lượt chạy báo `completed_with_unprocessed` kèm danh sách article_id.
- Lỗi của từng lần thử (kể cả lần bị retry) đều được ghi log kèm `attempt`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .io import AppendLog, JsonlStore
from .limits import RateLimiter, RateLimitError, RetryableError, call_with_retry
from .text import (article_text, has_verbatim_copy, overlap, refers_to_article_or_document_number, syllables)

QUERY_TYPES = ("natural", "scenario", "keyword")
MIN_BATCH, MAX_BATCH = 10, 20  # SPEC 5.1: 10–20 Điều mỗi request

STOP_COMPLETED = "completed"
STOP_TARGET_REACHED = "target_reached"
STOP_PLAN_EXHAUSTED = "plan_exhausted"
STOP_RATE_LIMIT = "rate_limit_exhausted"
STOP_BELOW_MIN_BATCH = "pending_below_min_batch"
STOP_INCOMPLETE = "completed_with_unprocessed"  # đã gửi hết nhưng còn Điều lỗi chưa ghi: cần resume hoặc xin quyết định


def next_batch_size(left: int, batch_size: int) -> int:
    """Cỡ batch kế tiếp khi còn `left` >= 10 Điều chờ. Lấy `batch_size` nếu phần còn lại vẫn đủ 10 (hoặc hết); nếu không,
    để lại đúng 10 cho batch sau khi được (vd. 24 Điều, batch 15 -> 14 + 10; 20 -> 10 + 10). Chỉ khi không tách được thành
    hai batch >= 10 (16–19 Điều với batch 15) mới gửi một batch lớn hơn `batch_size`, vẫn <= 20 (SPEC 5.1)."""
    if left < MIN_BATCH:
        raise ValueError(f"còn {left} Điều, ít hơn {MIN_BATCH}")
    if left <= batch_size or left - batch_size >= MIN_BATCH:
        return min(left, batch_size)
    return left - MIN_BATCH if left >= 2 * MIN_BATCH else left


class InvalidResponse(RetryableError):
    """Phản hồi không đúng schema ở cấp batch (JSON hỏng, thiếu `results`): retry cả batch."""


class NoValidArticles(InvalidResponse):
    """Phản hồi parse được nhưng không có Điều hợp lệ nào: retry cả batch. Giữ kết quả parse của lần thử cuối để ghi log."""

    def __init__(self, message: str, parsed: "Parsed"):
        super().__init__(message)
        self.parsed = parsed


@dataclass
class Parsed:
    valid: dict[str, dict]
    article_errors: list[dict] = field(default_factory=list)  # {article_id, field, reason}
    batch_errors: list[dict] = field(default_factory=list)    # {field, reason}: không gán được cho Điều nào


def load_prompt(path: Path | str) -> tuple[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def keyword_rule_phrase(keyword_min: int, keyword_max: int) -> str:
    return f"từ {keyword_min} đến {keyword_max} âm tiết"


def check_prompt_keyword_rule(template: str, keyword_min: int, keyword_max: int) -> None:
    """Prompt phải ghi đúng giới hạn keyword của config; lệch thì dừng (không sinh với prompt và bộ lọc khác nhau)."""
    phrase = keyword_rule_phrase(keyword_min, keyword_max)
    if phrase not in template:
        raise ValueError(f"prompt không ghi giới hạn keyword {phrase!r} như configs/querygen.yaml (lexical.keyword_*_syllables); "
                         "tạo prompt version mới hoặc sửa config, không sinh với hai quy tắc khác nhau")


def render_prompt(template: str, articles: list[dict]) -> str:
    payload = [{"article_id": a["article_id"], "title": a.get("title", ""), "content": a["body"]} for a in articles]
    return template.replace("{{ARTICLES_JSON}}", json.dumps(payload, ensure_ascii=False, indent=1))


def _check_result(r: dict, keyword_min: int, keyword_max: int) -> list[tuple[str, str]]:
    if r.get("skip"):
        return []
    q = r.get("queries")
    if not isinstance(q, dict):
        return [("queries", "thiếu queries hoặc không phải object")]
    if set(q) != set(QUERY_TYPES):
        return [("queries", f"cần đúng ba khóa natural/scenario/keyword, nhận {sorted(q)}")]
    problems = [(f"queries.{t}", "rỗng hoặc không phải chuỗi") for t in QUERY_TYPES if not (isinstance(q[t], str) and q[t].strip())]
    if not problems:
        n = len(syllables(q["keyword"]))
        if not keyword_min <= n <= keyword_max:
            problems.append(("queries.keyword", f"keyword có {n} âm tiết, cần {keyword_min}-{keyword_max} âm tiết"))
    return problems


def parse_response(raw: str, requested: list[str], *, keyword_min: int, keyword_max: int) -> Parsed:
    """Kiểm tra schema. Raise InvalidResponse chỉ khi lỗi cấp batch (JSON hỏng, thiếu `results`); lỗi của từng Điều trả về
    trong `article_errors`, kết quả không gán được cho Điều nào trong `batch_errors`."""
    try:
        results = json.loads(raw)["results"]
    except (ValueError, KeyError, TypeError) as e:
        raise InvalidResponse(f"JSON không đúng schema: {e!r}")
    if not isinstance(results, list):
        raise InvalidResponse("`results` không phải danh sách")
    want = set(requested)
    out = Parsed(valid={})
    problems: dict[str, list[tuple[str, str]]] = {}
    seen: set[str] = set()
    dup: set[str] = set()
    for i, r in enumerate(results):
        if not isinstance(r, dict) or not isinstance(r.get("article_id"), str):
            out.batch_errors.append({"field": "article_id", "reason": f"kết quả thứ {i} thiếu article_id"})
            continue
        aid = r["article_id"]
        if aid not in want:
            out.batch_errors.append({"field": "article_id", "reason": f"article_id không được yêu cầu: {aid}"})
            continue
        if aid in seen:
            dup.add(aid)
            continue
        seen.add(aid)
        p = _check_result(r, keyword_min, keyword_max)
        if p:
            problems[aid] = p
        elif r.get("skip"):
            out.valid[aid] = {"skip": True, "skip_reason": r.get("skip_reason"), "queries": None}
        else:
            out.valid[aid] = {"skip": False, "skip_reason": None, "queries": {t: r["queries"][t].strip() for t in QUERY_TYPES}}
    for aid in dup:
        out.valid.pop(aid, None)
        problems.setdefault(aid, []).append(("article_id", "lặp trong phản hồi"))
    for aid in requested:
        if aid not in seen:
            problems[aid] = [("article_id", "thiếu trong phản hồi")]
    out.article_errors = [{"article_id": a, "field": f, "reason": why} for a in requested if a in problems for f, why in problems[a]]
    return out


def _retry_kind(e: Exception) -> str:
    if isinstance(e, RateLimitError):
        return "rate_limit"
    if isinstance(e, NoValidArticles):
        return "no_valid_article"
    if isinstance(e, InvalidResponse):
        return "invalid_response"
    return "transient"


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class QueryGenerator:
    def __init__(self, client, store: JsonlStore, *, prompt_template: str, batch_size: int, max_attempts: int,
                 base_delay: float, max_delay: float, verbatim_n: int, keyword_min: int, keyword_max: int,
                 limiter: RateLimiter | None = None, sleep: Callable[[float], None] = time.sleep,
                 errors_path: Path | str | None = None, split: str | None = None, run_id: str | None = None):
        if not MIN_BATCH <= batch_size <= MAX_BATCH:
            raise ValueError(f"batch_size phải từ {MIN_BATCH} đến {MAX_BATCH} Điều (SPEC 5.1)")
        self.client, self.store, self.template = client, store, prompt_template
        self.batch_size, self.max_attempts, self.base_delay, self.max_delay = batch_size, max_attempts, base_delay, max_delay
        self.verbatim_n, self.keyword_min, self.keyword_max = verbatim_n, keyword_min, keyword_max
        self.limiter, self.sleep, self.split = limiter, sleep, split
        self.run_id = run_id or f"{_now()}-{uuid.uuid4().hex[:8]}"
        self.errors = AppendLog(errors_path) if errors_path else None
        self.stats = {"requests": 0, "retries": Counter(), "written": 0, "skipped_existing": 0, "failed_batches": 0,
                      "batch_errors": 0, "invalid_articles": Counter(), "invalid_article_ids": set()}
        self.stop_reason: str | None = None
        self.pending_article_ids: list[str] = []      # chưa gửi trong lượt này
        self.unprocessed_article_ids: list[str] = []  # đã gửi nhưng chưa ghi được (Điều lỗi, batch hỏng)

    # ---------- log ----------
    def _log(self, entry: dict) -> None:
        if self.errors is not None:
            self.errors.append({"run_id": self.run_id, "time": _now(), "split": self.split, **entry})

    def _log_parsed(self, parsed: Parsed, batch_ids: list[str], attempt: int) -> None:
        """Ghi lỗi của MỘT lần thử (kể cả lần bị retry), kèm số thứ tự lần thử."""
        for e in parsed.article_errors:
            self.stats["invalid_articles"][e["field"]] += 1
            self.stats["invalid_article_ids"].add(e["article_id"])
            self._log({"level": "article", **e, "attempt": attempt})
        for e in parsed.batch_errors:
            self.stats["batch_errors"] += 1
            self._log({"level": "batch", "error_type": "unassignable", **e, "article_ids": batch_ids, "attempt": attempt})

    # ---------- request ----------
    def _request(self, batch: list[dict]) -> Parsed:
        ids = [a["article_id"] for a in batch]
        prompt = render_prompt(self.template, batch)
        attempt = 0

        def once():
            nonlocal attempt
            attempt += 1
            if self.limiter:
                self.limiter.acquire()
            self.stats["requests"] += 1
            parsed = parse_response(self.client.generate(prompt), ids, keyword_min=self.keyword_min, keyword_max=self.keyword_max)
            self._log_parsed(parsed, ids, attempt)
            if not parsed.valid:
                raise NoValidArticles(f"không có Điều hợp lệ nào trong phản hồi ({len(parsed.article_errors)} lỗi Điều)", parsed)
            return parsed

        def on_retry(attempt, e, delay):
            self.stats["retries"][_retry_kind(e)] += 1

        return call_with_retry(once, max_attempts=self.max_attempts, base_delay=self.base_delay, max_delay=self.max_delay,
                               sleep=self.sleep, on_retry=on_retry)

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

    def _process(self, batch: list[dict]) -> bool:
        """Gửi một batch. Trả về False khi phải dừng cả lượt chạy (hết retry vì 429)."""
        ids = [a["article_id"] for a in batch]
        try:
            parsed = self._request(batch)
        except RetryableError as e:
            self.stats["failed_batches"] += 1
            self.unprocessed_article_ids += ids
            self._log({"level": "batch", "error_type": _retry_kind(e), "reason": str(e) or repr(e), "article_ids": ids,
                       "attempts": self.max_attempts})
            return not isinstance(e, RateLimitError)
        for art in batch:
            res = parsed.valid.get(art["article_id"])
            if res is None:
                self.unprocessed_article_ids.append(art["article_id"])
            elif self.store.append(self._record(art, res)):
                self.stats["written"] += 1
        return True

    # ---------- vòng chạy ----------
    def run(self, articles: list[dict], count_pairs: Callable[[], int] | None = None, target: int | None = None) -> dict:
        """Xử lý các Điều chưa có trong file (resume), theo thứ tự đã cho, chia batch bằng `next_batch_size`.

        Mỗi Điều được gửi tối đa một lần trong một lượt chạy; Điều lỗi để lại cho lần resume sau và được liệt kê trong
        `unprocessed_article_ids` (khi đó lượt chạy không báo `completed`). Có `target` thì dừng sau batch làm
        `count_pairs()` >= target (giữ mọi query hợp lệ của batch cuối). Dừng khi: hết Điều, hết retry 429, hoặc tổng số Điều
        còn chờ nhỏ hơn 10 (không tự đổi quy tắc 10–20 Điều/request)."""
        pending = []
        for a in articles:
            if a["article_id"] in self.store:
                self.stats["skipped_existing"] += 1
            else:
                pending.append(a)
        self.stop_reason, self.pending_article_ids, self.unprocessed_article_ids = None, [], []
        i = 0
        while True:
            if target is not None and count_pairs() >= target:
                self.stop_reason = STOP_TARGET_REACHED
                break
            left = len(pending) - i
            if left == 0:
                self.stop_reason = STOP_COMPLETED if target is None else STOP_PLAN_EXHAUSTED
                if self.unprocessed_article_ids and target is None:
                    self.stop_reason = STOP_INCOMPLETE
                break
            if left < MIN_BATCH:
                self.stop_reason = STOP_BELOW_MIN_BATCH
                self.pending_article_ids = [a["article_id"] for a in pending[i:]]
                break
            size = next_batch_size(left, self.batch_size)
            batch = pending[i:i + size]
            i += size
            if not self._process(batch):
                self.stop_reason = STOP_RATE_LIMIT
                self.pending_article_ids = [a["article_id"] for a in batch + pending[i:]]
                self.unprocessed_article_ids = [a for a in self.unprocessed_article_ids if a not in set(self.pending_article_ids)]
                break
        return self.summary()

    def run_until(self, ordered_articles: list[dict], count_pairs, target: int) -> dict:
        """Train: bổ sung theo thứ tự phân tầng đến khi `count_pairs()` >= target. Hết danh sách mà chưa đủ thì dừng và báo
        thiếu (không lấy bù từ nơi khác)."""
        out = self.run(ordered_articles, count_pairs, target)
        pairs = count_pairs()
        return {**out, "pairs_after_filter": pairs, "target_reached": pairs >= target}

    def summary(self) -> dict:
        s = self.stats
        return {"requests": s["requests"], "retries": dict(s["retries"]), "written": s["written"], "skipped_existing": s["skipped_existing"],
                "failed_batches": s["failed_batches"], "batch_errors": s["batch_errors"], "invalid_articles": dict(s["invalid_articles"]),
                "invalid_article_count": len(s["invalid_article_ids"]), "stop_reason": self.stop_reason,
                "pending_article_ids": list(self.pending_article_ids), "unprocessed_article_ids": list(self.unprocessed_article_ids)}


def build_meta(cfg: dict, prompt_hash: str, split: str, seed, *, mock: bool = False, generation_date: str | None = None) -> dict:
    """Metadata ghi cạnh file đầu ra (SPEC 5.1). Sinh thật yêu cầu model/temperature đã chốt trong config; ngày sinh ghi
    khi chạy thực tế (không lấy từ config)."""
    llm, lex = cfg["llm"], cfg["lexical"]
    if not mock:
        missing = [k for k in ("model", "temperature") if llm.get(k) is None]
        if missing:
            raise ValueError(f"configs/querygen.yaml: llm.{missing} chưa được chốt; không thể sinh query thật. "
                             "Điền giá trị vào configs/querygen.yaml theo chú thích cạnh khóa, không tự chọn")
    return {"provider": llm["provider"], "model": llm.get("model"), "temperature": llm.get("temperature"),
            "generation_date": generation_date or datetime.date.today().isoformat(), "prompt_path": cfg["prompt"]["path"],
            "prompt_version": cfg["prompt"]["version"], "prompt_sha256": prompt_hash, "split": split, "seed": seed,
            "batch_size": llm["batch_size"], "verbatim_n": lex["verbatim_n"], "keyword_min_syllables": lex["keyword_min_syllables"],
            "keyword_max_syllables": lex["keyword_max_syllables"], "mock": mock}
