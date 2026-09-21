#!/usr/bin/env python3
"""
evaluate.py
-----------
Lightweight evaluation harness that compares this tool's output against
the pack's reference files (expected_actions_reference.csv and
expected_summaries_reference.csv) at a *note* level -- not by demanding an
exact string match on wording or exact hand-assigned owner IDs (those were
authored by hand and are not fully derivable from note text alone), but on
the checks the pack's own README recommends:

  - Did we find a similar number of follow-up actions for each note?
  - Did we identify an owner (any owner) when the reference expected one?
  - Did we correctly leave the owner blank when the reference says unclear?
  - Did we avoid inventing a due date when the reference has none?
  - Did our manual_review_required flag agree with the reference summary?

Usage:
    python evaluate.py --actions outputs/extracted_actions.csv \
                        --summaries outputs/extracted_summaries.csv \
                        --ref-actions sample_data/expected_actions_reference.csv \
                        --ref-summaries sample_data/expected_summaries_reference.csv
"""

import argparse
import csv
from collections import defaultdict


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group_by_note(rows, key="note_id"):
    grouped = defaultdict(list)
    for r in rows:
        grouped[r[key]].append(r)
    return grouped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actions", required=True)
    parser.add_argument("--summaries", required=True)
    parser.add_argument("--ref-actions", required=True)
    parser.add_argument("--ref-summaries", required=True)
    args = parser.parse_args()

    actions = load_csv(args.actions)
    summaries = load_csv(args.summaries)
    ref_actions = load_csv(args.ref_actions)
    ref_summaries = load_csv(args.ref_summaries)

    my_actions_by_note = group_by_note(actions)
    ref_actions_by_note = group_by_note(ref_actions)
    my_summary_by_note = {r["note_id"]: r for r in summaries}
    ref_summary_by_note = {r["note_id"]: r for r in ref_summaries}

    note_ids = sorted(ref_summary_by_note.keys())

    action_count_within_1 = 0
    owner_presence_agree = 0
    owner_presence_total = 0
    due_date_no_invent = 0
    due_date_total_ref_blank = 0
    review_flag_agree = 0

    for nid in note_ids:
        my_acts = my_actions_by_note.get(nid, [])
        ref_acts = ref_actions_by_note.get(nid, [])
        if abs(len(my_acts) - len(ref_acts)) <= 1:
            action_count_within_1 += 1

        for ra in ref_acts:
            ref_has_owner = bool(ra.get("suggested_owner", "").strip())
            # crude alignment: same note, compare against whichever of our
            # rows has the closest action index (order-based, best-effort)
            idx = ref_acts.index(ra)
            if idx < len(my_acts):
                my_has_owner = bool(my_acts[idx].get("suggested_owner", "").strip())
                owner_presence_total += 1
                if my_has_owner == ref_has_owner:
                    owner_presence_agree += 1

            ref_due = ra.get("due_date_iso", "").strip()
            if not ref_due:
                due_date_total_ref_blank += 1
                if idx < len(my_acts) and not my_acts[idx].get("due_date_iso", "").strip():
                    due_date_no_invent += 1

        my_s = my_summary_by_note.get(nid)
        ref_s = ref_summary_by_note.get(nid)
        if my_s and ref_s and my_s.get("manual_review_required") == ref_s.get("manual_review_required"):
            review_flag_agree += 1

    n = len(note_ids)
    print("=== Evaluation vs. reference dataset ===")
    print(f"Notes evaluated: {n}")
    print(f"Action count within +/-1 of reference: {action_count_within_1}/{n} "
          f"({100*action_count_within_1/n:.0f}%)")
    if owner_presence_total:
        print(f"Owner presence (has-owner vs blank) agreement: "
              f"{owner_presence_agree}/{owner_presence_total} "
              f"({100*owner_presence_agree/owner_presence_total:.0f}%)")
    if due_date_total_ref_blank:
        print(f"Correctly left due_date blank when reference is vague: "
              f"{due_date_no_invent}/{due_date_total_ref_blank} "
              f"({100*due_date_no_invent/due_date_total_ref_blank:.0f}%)")
    print(f"manual_review_required flag agreement (note level): "
          f"{review_flag_agree}/{n} ({100*review_flag_agree/n:.0f}%)")
    print()
    print("Note: exact wording, exact owner IDs (e.g. 'AE-02' vs 'AE'), and")
    print("exact due-date-to-the-day matches are NOT scored here -- the")
    print("reference file's specific owner numbering was hand-authored and")
    print("is not fully derivable from note text alone. See")
    print("assumptions_and_limitations.md for details.")


if __name__ == "__main__":
    main()
