"""JSONL ghi tăng dần, resume không tạo bản ghi trùng (SPEC 5.1)."""
from __future__ import annotations

import json
from pathlib import Path


class JsonlStore:
    """Mỗi bản ghi có `article_id` duy nhất. Mở lại file thì nạp các article_id đã có; dòng cuối bị ngắt giữa chừng
    (không có ký tự xuống dòng) được cắt bỏ để lần chạy sau ghi lại, không để lại bản ghi hỏng."""

    def __init__(self, path: Path | str, key: str = "article_id"):
        self.path, self.key = Path(path), key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.seen: set[str] = set()
        self.truncated_partial_line = False
        if self.path.exists():
            raw = self.path.read_bytes()
            if raw and not raw.endswith(b"\n"):
                cut = raw.rfind(b"\n") + 1
                self.path.write_bytes(raw[:cut])
                self.truncated_partial_line = True
                raw = raw[:cut]
            for line in raw.decode("utf-8").splitlines():
                if line.strip():
                    self.seen.add(json.loads(line)[key])

    def __contains__(self, article_id: str) -> bool:
        return article_id in self.seen

    def append(self, record: dict) -> bool:
        """Ghi bản ghi nếu chưa có; trả về False (không ghi) nếu trùng."""
        k = record[self.key]
        if k in self.seen:
            return False
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        self.seen.add(k)
        return True

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]


def write_meta_once(path: Path | str, meta: dict) -> bool:
    """Ghi metadata (model, temperature, prompt, ngày sinh…) đúng một lần; không ghi đè."""
    p = Path(path)
    if p.exists():
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    return True
