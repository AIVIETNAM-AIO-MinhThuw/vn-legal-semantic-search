"""Tải paraphrase-multilingual-MiniLM-L12-v2 (safetensors) và ghi commit hash vào download.json."""
import hashlib, json
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
target = Path("data/raw/paraphrase-multilingual-MiniLM-L12-v2")
# token=False: model công khai; tránh lỗi 401 khi máy còn lưu token HF đã hết hạn
info = HfApi(token=False).model_info(REPO)
snapshot_download(REPO, revision=info.sha, local_dir=target, token=False,
                  allow_patterns=["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
                                  "special_tokens_map.json", "sentencepiece.bpe.model", "unigram.json"])
files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in target.iterdir() if p.is_file() and p.name != "download.json"}
(target / "download.json").write_text(json.dumps({"repo": REPO, "revision": info.sha, "files": files}, indent=2), encoding="utf-8")
print(REPO, info.sha)
