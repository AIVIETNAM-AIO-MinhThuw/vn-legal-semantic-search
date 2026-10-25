"""Gemini REST calls, durable attempts and resume. Credentials never enter artifacts."""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx

from src.annotation.pipeline import (
    Response,
    blind_payload,
    fingerprint,
    load_pool,
    validate_response,
    write_json,
)
from src.retrieval.common import file_hash, read_jsonl, write_jsonl


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_examples(cfg: dict) -> tuple[list[dict], set[str]]:
    path = Path(cfg["paths"]["examples"])
    examples = read_jsonl(path) if path.exists() else []
    counts = {label: 0 for label in (0, 1, 2)}
    public, ids = [], set()
    for row in examples:
        if (
            type(row.get("label")) is not int
            or row["label"] not in counts
            or row.get("review_status") not in {"unverified", "verified"}
        ):
            raise ValueError("Invalid calibration example label/review_status")
        root = Path(row["source_run"])
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        if file_hash(root / "pool.jsonl") != manifest["files"]["pool.jsonl"]:
            raise ValueError("Calibration source checksum mismatch")
        matches = [
            (q, c)
            for q in read_jsonl(root / "pool.jsonl")
            for c in q["candidates"]
            if c["candidate_id"] == row["candidate_id"]
        ]
        if len(matches) != 1 or row["candidate_id"] in ids:
            raise ValueError("Invalid/duplicate calibration candidate")
        q, candidate = matches[0]
        if (
            not row.get("reason", "").strip()
            or (row["evidence"] and row["evidence"] not in candidate["body"])
            or (row["label"] > 0 and not row["evidence"])
        ):
            raise ValueError("Calibration example lacks valid reason/evidence")
        public.append(
            {
                "query": q["query"],
                "candidate": blind_payload({**q, "candidates": [candidate]})[
                    "candidates"
                ][0],
                "label": row["label"],
                "reason": row["reason"],
                "evidence": row["evidence"],
            }
        )
        ids.add(row["candidate_id"])
        counts[row["label"]] += 1
    if any(n < cfg["review"]["examples_per_label"] for n in counts.values()):
        raise ValueError(
            "SPEC 10.1: at least two pilot examples per label required; fill calibration.csv then examples-import"
        )
    return public, ids


def protocol(cfg: dict) -> tuple[str, str, set[str]]:
    prompt = Path(cfg["paths"]["prompt"]).read_text(encoding="utf-8")
    guideline = Path(cfg["paths"]["guideline"]).read_text(encoding="utf-8")
    examples, example_ids = load_examples(cfg)
    system = (
        prompt
        + "\n\n"
        + guideline
        + "\n\nVí dụ hiệu chỉnh:\n"
        + json.dumps(examples, ensure_ascii=False)
    )
    signature = fingerprint(
        {
            "schema": Response.model_json_schema(),
            "system": system,
            "model": cfg["api"]["model"],
            "generation": cfg["api"]["generation"],
            "version": cfg["schema_version"],
        }
    )
    return system, signature, example_ids


def require_bulk_approval(cfg: dict, signature: str) -> None:
    if cfg["selection"]["mode"] == "pilot":
        return
    if cfg["selection"]["mode"] != "bulk" or not cfg["selection"]["approval"]:
        raise ValueError("Bulk labeling requires explicit pilot approval")
    approval = json.loads(
        Path(cfg["selection"]["approval"]).read_text(encoding="utf-8")
    )
    if (
        approval.get("approved") is not True
        or not approval.get("approver")
        or not approval.get("criteria")
        or approval.get("protocol_hash") != signature
    ):
        raise ValueError("Invalid bulk approval or changed labeling protocol")
    for field in ("pilot_report", "pilot_manifest"):
        if file_hash(Path(approval[field]["path"])) != approval[field]["sha256"]:
            raise ValueError(f"Bulk approval checksum mismatch: {field}")


class ApiFailure(Exception):
    def __init__(self, code: int | None, retryable: bool):
        self.code, self.retryable = code, retryable
        super().__init__(f"Gemini API failure code={code}; no model fallback")


class Gemini:
    def __init__(self, settings: dict, client: httpx.Client | None = None):
        self.settings = settings
        self.key = os.environ.get(settings["key_env"])
        if not self.key:
            raise ValueError(f"Missing environment variable {settings['key_env']}")
        if not settings["base_url"].startswith("https://"):
            raise ValueError("Gemini API requires HTTPS")
        self.client = client or httpx.Client(timeout=settings["timeout_seconds"])

    def close(self) -> None:
        self.client.close()

    def post(self, action: str, body: dict) -> dict:
        url = f"{self.settings['base_url'].rstrip('/')}/models/{self.settings['model']}:{action}"
        try:
            response = self.client.post(
                url, json=body, headers={"x-goog-api-key": self.key}
            )
        except httpx.TransportError as exc:
            raise ApiFailure(None, True) from exc
        if response.is_error:
            raise ApiFailure(
                response.status_code,
                response.status_code in self.settings["retry_statuses"],
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiFailure(response.status_code, True) from exc
        # No URL query credential or header is logged. Also redact any unexpected echo.
        return json.loads(
            json.dumps(data, ensure_ascii=False).replace(self.key, "[REDACTED]")
        )


def response_text(raw: dict, model: str) -> str:
    version = raw.get("modelVersion", "")
    if not version or not (version == model or version.startswith(model + "-")):
        raise ValueError("Missing/unexpected reported model version")
    candidates = raw.get("candidates", [])
    if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
        raise ValueError("Incomplete/blocked model response")
    return "".join(
        p.get("text", "")
        for p in candidates[0]["content"]["parts"]
        if not p.get("thought")
    )


@contextmanager
def run_lock(root: Path):
    path = root / ".label.lock"
    with path.open("x", encoding="utf-8") as f:
        f.write(json.dumps({"pid": os.getpid(), "started": now()}))
        f.flush()
        os.fsync(f.fileno())
    try:
        yield
    finally:
        path.unlink()


def request_for(cfg: dict, row: dict, system: str, signature: str) -> tuple[dict, str]:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": json.dumps(blind_payload(row), ensure_ascii=False)}],
            }
        ],
        "generationConfig": {
            **cfg["api"]["generation"],
            "responseMimeType": "application/json",
            "responseJsonSchema": Response.model_json_schema(),
        },
    }
    return body, fingerprint({"protocol": signature, "body": body})


def completed(root: Path, request_hash: str) -> bool:
    for path in (root / "attempts").glob("*/record.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("request_hash") == request_hash and record.get("status") in {
            "complete",
            "context_incomplete",
        }:
            return True
    return False


def label(cfg: dict, provider: Gemini | None = None, sleeper=time.sleep) -> dict:
    rows = load_pool(cfg)
    system, signature, _ = protocol(cfg)
    require_bulk_approval(cfg, signature)
    root = Path(cfg["paths"]["run"])
    owned = provider is None
    provider = provider or Gemini(cfg["api"])
    report = {"completed": 0, "skipped": 0, "errors": 0}
    try:
        with run_lock(root):
            for row in rows:
                body, key = request_for(cfg, row, system, signature)
                if completed(root, key):
                    report["skipped"] += 1
                    continue
                for attempt in range(cfg["api"]["attempts"]):
                    run_id = uuid.uuid4().hex
                    folder = root / "attempts" / run_id
                    folder.mkdir(parents=True)
                    record = {
                        "query_id": row["query_id"],
                        "request_hash": key,
                        "protocol_hash": signature,
                        "label_run_id": run_id,
                        "attempt": attempt + 1,
                        "started": now(),
                        "requested_model": cfg["api"]["model"],
                        "status": "started",
                    }
                    write_json(folder / "request.json", body)
                    write_json(folder / "started.json", record)
                    retryable = True
                    try:
                        counted = provider.post(
                            "countTokens",
                            {
                                "generateContentRequest": {
                                    "model": "models/" + cfg["api"]["model"],
                                    **body,
                                }
                            },
                        )
                        write_json(folder / "tokens.json", counted)
                        tokens = counted.get("totalTokens")
                        if type(tokens) is not int or tokens < 0:
                            raise ValueError("Invalid token count")
                        if tokens > cfg["api"]["max_input_tokens"]:
                            record.update(status="context_incomplete", tokens=tokens)
                            write_json(
                                folder / "record.json", {**record, "ended": now()}
                            )
                            break
                        raw = provider.post("generateContent", body)
                        write_json(folder / "response.json", raw)
                        parsed = json.loads(response_text(raw, cfg["api"]["model"]))
                        judgments = validate_response(row, parsed, run_id)
                        write_json(folder / "parsed.json", parsed)
                        write_jsonl(folder / "judgments.jsonl", judgments)
                        record.update(
                            status="complete",
                            reported_model=raw["modelVersion"],
                            response_sha256=file_hash(folder / "response.json"),
                        )
                        report["completed"] += 1
                    except ApiFailure as exc:
                        retryable = exc.retryable
                        record.update(status="error", error="api", api_code=exc.code)
                    except (ValueError, KeyError, TypeError) as exc:
                        record.update(status="error", error=type(exc).__name__)
                    record["ended"] = now()
                    write_json(folder / "record.json", record)
                    if record["status"] == "complete":
                        break
                    if not retryable:
                        raise ValueError(
                            f"API rejected request (code={record.get('api_code')}); inspect attempt record, no fallback"
                        )
                    if attempt + 1 < cfg["api"]["attempts"]:
                        sleeper(cfg["api"]["backoff_seconds"] * (attempt + 1))
                    else:
                        report["errors"] += 1
                sleeper(cfg["api"]["interval_seconds"])
    finally:
        if owned:
            provider.close()
    return report


def validated_rows(cfg: dict) -> tuple[list[dict], dict]:
    pool = load_pool(cfg)
    system, signature, _ = protocol(cfg)
    root = Path(cfg["paths"]["run"])
    records = []
    for path in (root / "attempts").glob("*/record.json"):
        records.append((json.loads(path.read_text(encoding="utf-8")), path.parent))
    result, pending = [], []
    for row in pool:
        _, key = request_for(cfg, row, system, signature)
        matches = [
            (record, folder)
            for record, folder in records
            if record["request_hash"] == key
            and record["status"] in {"complete", "context_incomplete"}
        ]
        if not matches:
            pending.extend(
                {
                    "query_id": row["query_id"],
                    "candidate_id": c["candidate_id"],
                    "article_id": c["article_id"],
                    "status": "error",
                    "reason": "No complete matching response",
                }
                for c in row["candidates"]
            )
            continue
        record, folder = max(matches, key=lambda item: item[0]["started"])
        if record["status"] == "context_incomplete":
            pending.extend(
                {
                    "query_id": row["query_id"],
                    "candidate_id": c["candidate_id"],
                    "article_id": c["article_id"],
                    "status": "needs_review",
                    "context_incomplete": True,
                    "reason": "Input budget exceeded",
                }
                for c in row["candidates"]
            )
            continue
        if file_hash(folder / "response.json") != record["response_sha256"]:
            raise ValueError("Saved API response checksum mismatch")
        raw = json.loads((folder / "response.json").read_text(encoding="utf-8"))
        judged = validate_response(
            row,
            json.loads(response_text(raw, cfg["api"]["model"])),
            record["label_run_id"],
        )
        result.extend(r for r in judged if r["status"] == "labeled")
        pending.extend(r for r in judged if r["status"] != "labeled")
    return result, {"protocol_hash": signature, "pending": pending}
