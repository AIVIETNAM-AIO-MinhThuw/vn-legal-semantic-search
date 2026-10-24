"""One resumable labeling pipeline for pilot and approved bulk dataset construction."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.annotation.api import label, validated_rows  # noqa: E402
from src.annotation.pipeline import new_directory, prepare, write_json  # noqa: E402
from src.annotation.review import (  # noqa: E402
    export_review,
    finalize,
    import_examples,
    import_review,
)
from src.retrieval.common import write_jsonl  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "examples-import",
            "label",
            "validate",
            "review-export",
            "review-import",
            "finalize",
        ],
    )
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-dir", type=Path)
    parser.add_argument("--human-dir", type=Path)
    parser.add_argument("--draft", action="store_true")
    args = parser.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    csv.field_size_limit(cfg["csv_field_size_limit"])
    try:
        if args.command == "prepare":
            print(prepare(cfg, args.queries))
        elif args.command == "label":
            print(json.dumps(label(cfg)))
        elif args.command == "examples-import":
            if not args.input:
                raise ValueError("--input calibration CSV required")
            print(import_examples(cfg, args.input, Path(cfg["paths"]["examples"])))
        else:
            if not args.output:
                raise ValueError("--output new directory required")
            if args.command == "validate":
                rows, info = validated_rows(cfg)
                with new_directory(args.output) as folder:
                    write_jsonl(folder / "accepted.jsonl", rows)
                    write_jsonl(folder / "pending.jsonl", info["pending"])
                    write_json(
                        folder / "report.json",
                        {
                            "accepted": len(rows),
                            "pending": len(info["pending"]),
                            "protocol_hash": info["protocol_hash"],
                        },
                    )
            elif args.command == "review-export":
                print(json.dumps(export_review(cfg, args.output)))
            elif args.command == "review-import":
                if not args.input or not args.review_dir:
                    raise ValueError("--input and --review-dir required")
                print(
                    json.dumps(
                        import_review(cfg, args.input, args.review_dir, args.output)
                    )
                )
            elif args.command == "finalize":
                print(
                    json.dumps(finalize(cfg, args.output, args.human_dir, args.draft))
                )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Labeling failed: {exc}\n")


if __name__ == "__main__":
    main()
