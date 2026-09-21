#!/usr/bin/env python3
"""
CRM Notes -> Follow-Up Task Extraction: Python CLI workflow.

Usage:
    python cli.py --input sample_data/crm_notes_raw.csv --outdir outputs
    python cli.py --input sample_data/sample_input_10_records.json --outdir outputs

Reads CRM notes (CSV or JSON), runs the rule-based extraction engine,
and writes:
    outputs/extracted_actions.csv / .json
    outputs/extracted_summaries.csv / .json
    outputs/processing_log.json

No live CRM connection, external API, or internet access is required.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from extractor import process_notes


def load_notes(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "records" in data:
            data = data["records"]
        return data
    elif path.suffix.lower() == ".csv":
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    else:
        raise ValueError(f"Unsupported input file type: {path.suffix}")


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text("")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="CRM Notes follow-up task extraction CLI")
    parser.add_argument("--input", required=True, help="Path to CRM notes CSV or JSON file")
    parser.add_argument("--outdir", default="outputs", help="Directory to write output files")
    args = parser.parse_args()

    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1

    notes = load_notes(input_path)
    print(f"Loaded {len(notes)} CRM note record(s) from {input_path.name}")

    actions, summaries, log = process_notes(notes)

    action_rows = [a.as_row() for a in actions]
    summary_rows = [s.as_row() for s in summaries]

    write_csv(action_rows, outdir / "extracted_actions.csv")
    write_json(action_rows, outdir / "extracted_actions.json")
    write_csv(summary_rows, outdir / "extracted_summaries.csv")
    write_json(summary_rows, outdir / "extracted_summaries.json")
    write_json(log, outdir / "processing_log.json")

    review_count = sum(1 for s in summaries if s.manual_review_required == "Yes")
    print(f"Extracted {len(action_rows)} follow-up action(s) across {len(summary_rows)} note(s)")
    print(f"Notes flagged for manual review: {review_count} / {len(summary_rows)}")
    print(f"Output written to: {outdir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
