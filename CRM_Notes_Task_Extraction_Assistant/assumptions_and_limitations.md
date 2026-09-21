# Assumptions & Limitations

This tool is a **rule-based / regex extraction engine**, not a machine-learning
or LLM-based system. That choice was intentional: it needs no external API
key, no GPU, no internet access, and no live CRM connection, and every
decision it makes can be traced back to a specific pattern in `extractor/rules.py`.
The trade-off is that it will never be as flexible as an LLM at parsing truly
novel phrasing. This document is an honest account of where it does well and
where it doesn't.

## How it was evaluated

`evaluate.py` compares this tool's output against the dataset pack's own
`expected_actions_reference.csv` and `expected_summaries_reference.csv`,
using the checks the pack's README itself recommends (not exact-string
matching, which would be the wrong bar for a rule-based system to be judged
against a hand-authored reference — see below).

Results on the full 100-note dataset (see `outputs/evaluation_report.txt`):

| Check | Result |
|---|---|
| Follow-up action count within ±1 of reference | 92 / 100 notes (92%) |
| Owner presence (has-an-owner vs. correctly-blank) agreement | 192 / 221 actions (87%) |
| Correctly left `due_date_iso` blank when reference is vague | 114 / 128 actions (89%) |
| `manual_review_required` flag agreement at note level | 65 / 100 notes (65%) |

## Known limitations

1. **Owner IDs are approximate, not exact.** The reference file assigns
   specific hand-picked IDs (`AE-02`, `SE-02`, `RevOps-01`...) that are not
   always derivable from the note text alone — the dataset author appears to
   have used an internal numbering convention. This tool instead returns the
   **role** (`AE`, `SE`, `CSM`, `RevOps`, ...) when a specific ID isn't
   explicitly present in the note, and leaves the owner blank (flagging for
   manual review) when the note itself says ownership is unclear. We judged
   "right role, no fabricated number" to be safer for an operational tool
   than guessing a specific person.

2. **Compound sentences are sometimes captured as one action instead of two.**
   e.g. "They asked for customer references ... and want a simple ROI
   summary" may occasionally stay merged into a single action row rather than
   splitting cleanly, when the two halves don't each contain an unambiguous
   verb cue. The engine does attempt this split (see `_split_and_if_both_actionish`
   in `engine.py`) but it is conservative by design — it would rather under-split
   into one slightly longer action than fabricate a second action that wasn't
   clearly there.

3. **Some background/context sentences may still surface as low-confidence
   action rows.** The trigger patterns (`asked`, `requested`, `want(s)`, bare
   `need(s)`) are necessarily heuristic. Every action produced this way is
   still tagged with `confidence` and `manual_review_required`, so these are
   visible to a reviewer rather than silently treated as certain.

4. **Due-date grounding is deliberately conservative.** The tool computes a
   concrete `due_date_iso` only for unambiguous phrases (`today`, `tomorrow`,
   a specific weekday, `month-end`, `next week` without a vagueness qualifier).
   Phrases like "early next week," "soon," "ASAP," or "should work" are
   **never** converted into a specific date — `timing_reference` preserves the
   original phrase and `due_date_iso` is left blank, exactly as the project
   brief requires ("do not invent dates").

5. **`manual_review_required` agreement (65%) is the weakest metric.** This
   is the most subjective field in the whole schema — the reference dataset's
   review calls sometimes hinge on domain judgment ("is this deal at risk?")
   that a keyword list can't fully replicate. The engine flags for review
   whenever owner is missing/inferred, timing is vague/absent, or a
   context marker (e.g. "partner handover," "tentative," "messy") appears —
   it is tuned to **over-flag rather than under-flag**, since a sales-ops
   reviewer glancing at an extra flagged row costs far less than a missed
   one.

6. **Category classification is keyword-driven.** `follow_up_category` is
   assigned by counting keyword hits per category (see
   `rules.CATEGORY_KEYWORDS`) and picking the top match. Notes that
   genuinely straddle two categories (e.g. a renewal note that also raises a
   technical question) will have all of their actions tagged with whichever
   category "wins" the keyword count for that specific action's sentence —
   this is per-action, not per-note, which helps but doesn't eliminate the
   effect.

7. **Input assumptions.** The engine expects the same columns as
   `crm_notes_raw.csv` (see `data_dictionary.csv` in the original pack). Rows
   missing `note_body` entirely, or with a `note_body` that contains no
   recognizable action language, fall back to `existing_next_action_field` if
   present; if neither is present, the note will produce zero action rows.
   No note in the 100-record sample dataset actually hits this fallback path
   in a way that returns zero actions (verified via `processing_log.json`).

## What this tool intentionally does NOT do

Per the project brief, this tool never:
- Scores or coaches sales reps
- Recommends deal/sales strategy beyond structuring the operational follow-up
- Connects to a live CRM (it only reads files you give it)
- Sends emails or calendar invites
- Fabricates a date, owner, or fact that isn't reasonably grounded in the note

## Suggested next steps if extended

- Swap the rule-based `find_action_phrases()` for an LLM-based extractor
  (e.g. via Claude or a local Ollama model) behind the same
  `ExtractedAction` interface, and A/B the two against `evaluate.py`.
- Add a small manually-labeled "golden set" (20–30 notes) with exact
  human-agreed action counts, for a stricter precision/recall metric than
  the ±1 tolerance used here.
- Extend `category_owner_mapping.csv`-driven defaults into a small
  YAML/JSON config so sales-ops can retune keywords without touching code.
