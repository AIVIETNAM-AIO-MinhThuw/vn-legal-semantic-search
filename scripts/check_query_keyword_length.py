"""Flag keywords over four VNCoreNLP words without removing or rewriting queries.

Run from the repository root with --queries and a new --output directory.
Uses the same segmenter configuration and word_tokens as BM25 S1_0.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.retrieval.text import load_segmenter, word_tokens  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path('configs/bm25.yaml'))
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    cfg = yaml.safe_load(args.config.read_text(encoding='utf-8'))
    with args.queries.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not {'query_id', 'query_type', 'query'}.issubset(reader.fieldnames or []):
            raise ValueError('Required CSV columns: query_id, query_type, query')
        rows = [r for r in reader if r['query_type'] == 'keyword']
    segmenter = load_segmenter(cfg['segmenter'])
    results = []
    for row in rows:
        words = word_tokens(row['query'], segmenter)
        results.append(dict(query_id=row['query_id'], query=row['query'],
                            n_words=len(words), words=' '.join(words),
                            flag='keyword_over_4_words' if len(words) > 4 else ''))
    summary = dict(segmenter_revision=cfg['segmenter']['revision'], keywords=len(results),
                   n_words=dict(sorted(Counter(r['n_words'] for r in results).items())),
                   over_4_words=sum(bool(r['flag']) for r in results),
                   note='Flags only; no queries removed. Group must decide treatment of keywords over four words.')
    args.output.mkdir(parents=True)
    with (args.output/'keyword_word_count.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['query_id', 'query', 'n_words', 'words', 'flag'])
        writer.writeheader()
        writer.writerows(results)
    (args.output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
