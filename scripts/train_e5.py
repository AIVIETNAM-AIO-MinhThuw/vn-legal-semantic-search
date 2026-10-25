"""Fine-tune E5 bi-encoder (SPEC 8). Chạy trên GPU.

python -X utf8 scripts/train_e5.py --config configs/train_e5.yaml --variant A --lr 3e-5
python -X utf8 scripts/train_e5.py --config configs/train_e5.yaml --variant B --lr <lr chọn từ A>

Đầu ra models/e5_ft_<variant>_lr<lr>/: model/ (checkpoint tốt nhất theo val), val_metrics.json, train_log.jsonl, manifest.json.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, math, os, platform, random, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
import yaml
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.eval.metrics import evaluate  # noqa: E402
from src.retrieval.common import rank_articles, read_jsonl  # noqa: E402
from src.retrieval.dense import mean_pool  # noqa: E402

QP, PP = "query: ", "passage: "


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_csv(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_run(p):
    out = defaultdict(list)
    with open(p, encoding="utf-8") as f:
        for l in f:
            q, _, a, r, _, _ = l.split()
            out[q].append((int(r), a))
    return out


def set_seed(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(True, warn_only=True)


def encode(model, tok, texts, max_len, bs, device):
    model.eval(); out = []
    with torch.inference_mode(), torch.autocast(device.type, dtype=torch.float16, enabled=device.type == "cuda"):
        for i in range(0, len(texts), bs):
            enc = tok(texts[i:i + bs], padding=True, truncation=True, max_length=max_len, return_tensors="pt").to(device)
            h = model(**enc).last_hidden_state
            out.append(F.normalize(mean_pool(h.float(), enc["attention_mask"]), dim=1).cpu().numpy())
    return np.concatenate(out)


def val_eval(model, tok, chunks, val_q, qrels, ecfg, device):
    vec = encode(model, tok, [PP + c["text"] for c in chunks], ecfg["max_length"], ecfg["batch_size"], device)
    qv = encode(model, tok, [QP + q["query"] for q in val_q], 64, ecfg["batch_size"], device)
    run = {}
    for q, v in zip(val_q, qv):
        run[q["query_id"]] = [a for a, _ in rank_articles(chunks, vec @ v, ecfg["chunk_top_k"], ecfg["top_k"])]
    mean, _ = evaluate(run, qrels, [q["query_id"] for q in val_q])
    return mean


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--variant", required=True, choices=["A", "B"])
    ap.add_argument("--lr", required=True, type=float)
    ap.add_argument("--device", default="cuda", help="cpu chỉ dùng cho smoke test")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    P, T, E = cfg["paths"], cfg["train"], cfg["eval"]
    out = Path(P["output_root"]) / f"e5_ft_{a.variant}_lr{a.lr:g}"
    if out.exists():
        sys.exit(f"Output đã tồn tại: {out}")
    if a.device == "cuda" and not torch.cuda.is_available():
        sys.exit("Cần CUDA để fine-tune")
    device = torch.device(a.device)
    set_seed(cfg["seed"])

    arts = {r["article_id"]: r for r in read_jsonl(Path(P["articles"]))}
    chunks = sorted(read_jsonl(Path(P["chunks"])), key=lambda c: (c["article_id"], c["chunk_index"]))
    art_chunks = defaultdict(list)
    for c in chunks:
        art_chunks[c["article_id"]].append(c["text"])
    members = json.loads(Path(P["families"]).read_text(encoding="utf-8"))["members"]
    group = {d: g for g, ds in members.items() for d in ds}
    qrels = defaultdict(dict)
    for r in read_jsonl(Path(P["qrels"])):
        qrels[r["query_id"]][r["article_id"]] = r["label"]
    train_q = read_csv(P["train_queries"]); val_q = read_csv(P["val_queries"])

    # Hard negative (SPEC 8.3): rank trong cửa sổ, khác văn bản/họ/hash với positive; chọn 1 theo seed.
    lo, hi = T["hard_negative_window"]
    runs = [read_run(p) for p in P["hard_negative_runs"]]
    rng = random.Random(cfg["seed"])
    examples, no_hn = [], 0
    for q in train_q:
        pos = [x for x, g in qrels[q["query_id"]].items() if g >= 1]
        pos_docs = {arts[x]["doc_id"] for x in pos}; pos_groups = {group[d] for d in pos_docs}
        pos_hash = {arts[x]["content_sha1"] for x in pos}
        cands = sorted({aid for run in runs for r, aid in run.get(q["query_id"], []) if lo <= r <= hi
                        and aid not in pos and arts[aid]["doc_id"] not in pos_docs
                        and group[arts[aid]["doc_id"]] not in pos_groups and arts[aid]["content_sha1"] not in pos_hash})
        hn = rng.choice(cands) if cands else None
        no_hn += hn is None
        for p in pos:
            examples.append({"query_id": q["query_id"], "query": q["query"], "pos": p, "hn": hn,
                             "doc": arts[p]["doc_id"]})

    tok = AutoTokenizer.from_pretrained(P["base_model"], local_files_only=True)
    model = AutoModel.from_pretrained(P["base_model"], local_files_only=True, use_safetensors=True).to(device)
    if T["freeze_embeddings"]:
        for p in model.embeddings.parameters():
            p.requires_grad = False
    if T["gradient_checkpointing"]:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=T["weight_decay"])
    bs = T["batch_size"]
    steps = T["epochs"] * math.ceil(len(examples) / bs)
    sched = get_linear_schedule_with_warmup(opt, int(T["warmup_ratio"] * steps), steps)
    cuda = device.type == "cuda"
    bf16 = cuda and torch.cuda.is_bf16_supported()
    scaler = torch.amp.GradScaler("cuda", enabled=cuda and not bf16)
    amp_dtype = torch.bfloat16 if bf16 else torch.float16

    out.mkdir(parents=True)
    log = open(out / "train_log.jsonl", "w", encoding="utf-8")
    base_val = val_eval(model, tok, chunks, val_q, qrels, E, device)
    log.write(json.dumps({"epoch": 0, "val": base_val}, ensure_ascii=False) + "\n"); log.flush()
    print("epoch 0 val", base_val)
    best, best_epoch, history = -1.0, None, [{"epoch": 0, "val": base_val}]
    t_start = time.time(); step = 0
    for ep in range(1, T["epochs"] + 1):
        model.train()
        order = list(range(len(examples))); random.Random(cfg["seed"] * 1000 + ep).shuffle(order)
        crng = random.Random(cfg["seed"] * 7 + ep)
        for b in range(0, len(order), bs):
            batch = [examples[i] for i in order[b:b + bs]]
            qs = [QP + e["query"] for e in batch]
            ps = [PP + crng.choice(art_chunks[e["pos"]]) for e in batch]
            if a.variant == "B":
                ps += [PP + crng.choice(art_chunks[e["hn"]]) for e in batch if e["hn"]]
            qe = tok(qs, padding=True, truncation=True, max_length=T["max_query_length"], return_tensors="pt").to(device)
            pe = tok(ps, padding=True, truncation=True, max_length=T["max_passage_length"], return_tensors="pt").to(device)
            with torch.autocast(device.type, dtype=amp_dtype, enabled=cuda):
                qv = F.normalize(mean_pool(model(**qe).last_hidden_state.float(), qe["attention_mask"]), dim=1)
                pv = F.normalize(mean_pool(model(**pe).last_hidden_state.float(), pe["attention_mask"]), dim=1)
            logits = qv @ pv.T / T["temperature"]
            # Che false negative trong batch: passage của cùng Điều/cùng văn bản với positive của query.
            n = len(batch)
            pdocs = [e["doc"] for e in batch] + [arts[e["hn"]]["doc_id"] for e in batch if a.variant == "B" and e["hn"]]
            mask = torch.zeros_like(logits, dtype=torch.bool)
            for i, e in enumerate(batch):
                for j, d in enumerate(pdocs):
                    if j != i and (d == e["doc"] or (j < n and batch[j]["pos"] == e["pos"])):
                        mask[i, j] = True
            logits = logits.masked_fill(mask, -1e4)
            loss = F.cross_entropy(logits, torch.arange(n, device=device))
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward(); scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            scaler.step(opt); scaler.update(); sched.step(); step += 1
            if step % 20 == 0:
                print(f"ep {ep} step {step}/{steps} loss {loss.item():.4f} {time.time() - t_start:.0f}s", flush=True)
                log.write(json.dumps({"epoch": ep, "step": step, "loss": loss.item()}) + "\n"); log.flush()
        val = val_eval(model, tok, chunks, val_q, qrels, E, device)
        history.append({"epoch": ep, "val": val})
        log.write(json.dumps({"epoch": ep, "val": val}, ensure_ascii=False) + "\n"); log.flush()
        print(f"epoch {ep} val", val)
        if val[E["select_metric"]] > best:
            best, best_epoch = val[E["select_metric"]], ep
            model.save_pretrained(out / "model", safe_serialization=True)
            tok.save_pretrained(out / "model")
    log.close()
    (out / "val_metrics.json").write_text(json.dumps({"variant": a.variant, "lr": a.lr, "best_epoch": best_epoch,
        "select_metric": E["select_metric"], "best": best, "history": history}, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"variant": a.variant, "lr": a.lr, "config": cfg, "n_train_queries": len(train_q),
                "n_examples": len(examples), "queries_without_hard_negative": no_hn,
                "hard_negatives_sha256": hashlib.sha256(json.dumps([(e["query_id"], e["hn"]) for e in examples]).encode()).hexdigest(),
                "inputs": {k: sha(P[k]) for k in ("train_queries", "val_queries", "qrels", "chunks", "articles", "families")},
                "base_model": {p.name: sha(p) for p in sorted(Path(P["base_model"]).iterdir()) if p.suffix in {".json", ".safetensors", ".model"}},
                "gpu": torch.cuda.get_device_name(0) if cuda else "cpu", "torch": torch.__version__, "python": platform.python_version(),
                "bf16": bf16, "train_seconds": time.time() - t_start}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("best epoch", best_epoch, E["select_metric"], best, "->", out)


if __name__ == "__main__":
    main()
