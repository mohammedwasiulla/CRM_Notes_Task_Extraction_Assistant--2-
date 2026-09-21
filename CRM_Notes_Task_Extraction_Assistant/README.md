# CRM Notes → Follow-Up Task Extraction Workflow (Sales Operations)

A lightweight, local workflow assistant that reads CRM-style notes and
extracts structured follow-up tasks: **owners, due dates, blockers, priority,
follow-up category, confidence, and a CRM-ready summary** — so sales
operations doesn't have to comb through unstructured notes by hand after
every call, demo, renewal discussion, or pipeline review.

Built for the *CRM Notes to Follow-Up Task Extraction Workflow for Sales
Operations* project brief, against the bundled synthetic dataset pack
(100 CRM notes from "First Quadrant Labs").

**Runs entirely locally.** No live CRM connection, no external API key, no
GPU, no internet access required. Pure Python + pandas + regex/rule-based
extraction, with a Streamlit UI or a CLI as the two ways to run it.

**Theme:** the Streamlit UI uses a dark "case file / audit dossier" theme
(ink sidebar, teal accent, Space Grotesk headings, IBM Plex Mono for
tags/labels, a rotated review-status stamp, and a 3-step pipeline tracker) —
the same visual system used across this team's other review tooling, reused
here since the shape of the problem is the same: an automated first-pass
extraction that stays source-linked and pending manual sign-off.

---

## What it does

For each CRM note, the tool produces:

| Field | Description |
|---|---|
| `action_text` | Short, normalized follow-up action |
| `suggested_owner` | Owner mentioned/inferable (AE, SE, CSM, RevOps, LegalOps, InfoSec, Billing, Sales Manager) — blank if genuinely unclear |
| `timing_reference` | The timing phrase as written ("by Wednesday", "next week", "ASAP"...) |
| `due_date_iso` | A concrete date **only** when it can be safely grounded — never invented |
| `priority` | High / Medium / Low |
| `follow_up_category` | pricing_quote, technical_clarification, renewal_commercial, demo_pilot, procurement_vendor_setup, legal_security_review, account_research, proposal_collateral, internal_approval, meeting_scheduling, crm_update, or billing_clarification |
| `blocker_dependency` | Blocker/dependency tied to the action, if any |
| `confidence` | High / Medium / Low extraction confidence |
| `manual_review_required` | Yes/No — flagged whenever owner, timing, or context is ambiguous |
| `supporting_text` | The original sentence the action was extracted from |

Plus one **CRM-ready summary** per note (account, action count, primary
category, blocker, overall priority, review flag).

## What it intentionally does NOT do

Per the project brief's scope boundaries, this tool never:
- Scores or coaches sales reps
- Recommends deal/sales strategy
- Connects to a live CRM system
- Sends emails or calendar invites automatically
- Invents a date/owner/fact that isn't reasonably grounded in the note text

See [`assumptions_and_limitations.md`](assumptions_and_limitations.md) for a
full, honest account of extraction accuracy and known edge cases.

---

## Project structure

```
CRM_Notes_Task_Extraction_Assistant/
├── app.py                          # Streamlit UI (dark case-file theme)
├── .streamlit/
│   └── config.toml                 # Streamlit theme config (dark, teal accent)
├── cli.py                          # Python CLI workflow
├── evaluate.py                     # Compares output to the reference dataset
├── extractor/
│   ├── __init__.py
│   ├── engine.py                   # Core extraction logic
│   └── rules.py                    # Keyword tables, owner roles, timing/priority rules
├── data/
│   └── category_owner_mapping.csv  # Category → default owner guidance (from the source pack)
├── sample_data/
│   ├── sample_input_10_records.csv       # Quick-test sample (also .json)
│   ├── crm_notes_raw.csv                 # Full 100-note dataset
│   ├── expected_actions_reference.csv    # Reference labels, for evaluate.py
│   └── expected_summaries_reference.csv  # Reference summaries, for evaluate.py
├── outputs/                        # Generated output from running the full dataset
│   ├── extracted_actions.csv / .json
│   ├── extracted_summaries.csv / .json
│   ├── processing_log.json
│   └── evaluation_report.txt
├── screenshots/                    # Real screenshots of the running app (see below)
├── assumptions_and_limitations.md
├── requirements.txt
└── README.md
```

---

## Running it

### Option A — Streamlit app

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then in the browser: check "Use bundled 10-record sample" (or upload your own
CSV/JSON), click **Extract follow-up tasks**, filter the results table by
category / priority / manual-review status, and download the CSV/JSON
exports.

### Option B — Python CLI

```bash
pip install -r requirements.txt

# Quick test on the 10-record sample
python cli.py --input sample_data/sample_input_10_records.csv --outdir outputs

# Full 100-note dataset
python cli.py --input sample_data/crm_notes_raw.csv --outdir outputs
```

This writes `extracted_actions.csv/json`, `extracted_summaries.csv/json`, and
`processing_log.json` to the output directory.

### Evaluating against the reference dataset

```bash
python evaluate.py \
  --actions outputs/extracted_actions.csv \
  --summaries outputs/extracted_summaries.csv \
  --ref-actions sample_data/expected_actions_reference.csv \
  --ref-summaries sample_data/expected_summaries_reference.csv
```

Current results on the full 100-note dataset:

```
Notes evaluated: 100
Action count within +/-1 of reference: 92/100 (92%)
Owner presence (has-owner vs blank) agreement: 192/221 (87%)
Correctly left due_date blank when reference is vague: 114/128 (89%)
manual_review_required flag agreement (note level): 65/100 (65%)
```

---

## Expected input format

CSV or JSON with these columns (matching `crm_notes_raw.csv`):

```
note_id, account_alias, industry_segment, region, interaction_date,
interaction_type, opportunity_stage, note_author_role, crm_owner,
product_interest_area, estimated_deal_band, source_channel, note_body,
current_blocker_tag, existing_next_action_field
```

Only `note_id`, `account_alias`, and `note_body` are strictly required — the
rest improve extraction quality (owner defaults, timing anchoring, category
context) but are optional.

---

## How extraction works (short version)

1. Split each `note_body` into sentences.
2. For each sentence, look for a small set of precise triggers — an
   imperative verb start ("Send the recap..."), a modal + verb ("needs to
   confirm..."), or request language ("asked if/for...", "requested...",
   "wanted..."). This is deliberately narrower than "any sentence with a
   business-y word," to avoid mistaking background narrative for a task.
3. Pull owner, timing, category, priority, blocker, and confidence from the
   surrounding sentence context — never inventing an owner or a hard date
   the note doesn't support.
4. Flag `manual_review_required = Yes` whenever ownership or timing is
   genuinely unclear, or the note contains a context marker like "partner
   handover," "tentative," or "owner unclear."
5. Roll per-note actions up into one CRM-ready summary sentence.

Full detail and known edge cases are in
[`assumptions_and_limitations.md`](assumptions_and_limitations.md).

---

## Screenshots

See the `screenshots/` folder for real captures of the running Streamlit app
(dark case-file theme):

1. `01_upload_and_preview.png` — sidebar case-file scope + load-notes controls, input preview, pipeline stepper
2. `02_kpis_and_stamp.png` — KPI metrics + rotated review-status stamp + CRM-ready summaries
3. `03_full_results_page.png` — full results page (stepper, summaries, priority/review chip legend, actions table, export)
