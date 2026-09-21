# Running This Project in VS Code

Copy-paste guide for opening this project in VS Code and generating every
output (CLI results, evaluation report, and the Streamlit app) from the
integrated terminal.

---

## 0. Open the project

1. Unzip `CRM_Notes_Task_Extraction_Assistant.zip`.
2. In VS Code: **File → Open Folder...** → select the unzipped
   `CRM_Notes_Task_Extraction_Assistant` folder.
3. Open a terminal: **Terminal → New Terminal** (or `` Ctrl+` ``).

Make sure the terminal's working directory is the project root (it should
show the `CRM_Notes_Task_Extraction_Assistant>` prompt).

---

## 1. Set up a virtual environment

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If VS Code shows a popup asking "Select Interpreter", pick the one inside
`.venv` so the editor and terminal use the same environment.

---

## 2. Run the CLI to produce all output files

**Quick test — 10-record sample:**
```bash
python cli.py --input sample_data/sample_input_10_records.csv --outdir outputs
```

**Full 100-note dataset (this is what generated the outputs already in the zip):**
```bash
python cli.py --input sample_data/crm_notes_raw.csv --outdir outputs
```

This writes to `outputs/`:
- `extracted_actions.csv` / `extracted_actions.json`
- `extracted_summaries.csv` / `extracted_summaries.json`
- `processing_log.json`

Open any of these directly in VS Code (`code outputs/extracted_actions.csv`
or just click it in the file explorer) — CSVs render as a spreadsheet-style
table if you have the built-in or a CSV extension enabled.

---

## 3. Run the evaluation report

```bash
python evaluate.py --actions outputs/extracted_actions.csv --summaries outputs/extracted_summaries.csv --ref-actions sample_data/expected_actions_reference.csv --ref-summaries sample_data/expected_summaries_reference.csv
```

To save it to a file instead of just printing it:

**macOS / Linux:**
```bash
python evaluate.py --actions outputs/extracted_actions.csv --summaries outputs/extracted_summaries.csv --ref-actions sample_data/expected_actions_reference.csv --ref-summaries sample_data/expected_summaries_reference.csv | tee outputs/evaluation_report.txt
```

**Windows (PowerShell):**
```powershell
python evaluate.py --actions outputs/extracted_actions.csv --summaries outputs/extracted_summaries.csv --ref-actions sample_data/expected_actions_reference.csv --ref-summaries sample_data/expected_summaries_reference.csv | Tee-Object -FilePath outputs/evaluation_report.txt
```

---

## 4. Run the Streamlit app (live demo)

```bash
streamlit run app.py
```

This opens the app at `http://localhost:8501` in your browser. In the app:
1. Check "Use bundled 10-record sample" (or upload your own CSV/JSON).
2. Click **Extract follow-up tasks**.
3. Filter the results table by category / priority / manual-review status.
4. Use the download buttons to export CSV/JSON directly from the browser.

Stop the app with `Ctrl+C` in the terminal when you're done.

---

## 5. Everything in one go (optional convenience block)

**macOS / Linux — paste all at once:**
```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt \
  && python cli.py --input sample_data/crm_notes_raw.csv --outdir outputs \
  && python evaluate.py --actions outputs/extracted_actions.csv --summaries outputs/extracted_summaries.csv --ref-actions sample_data/expected_actions_reference.csv --ref-summaries sample_data/expected_summaries_reference.csv | tee outputs/evaluation_report.txt
```

Then separately, to launch the live demo:
```bash
streamlit run app.py
```

**Windows (PowerShell) — paste all at once:**
```powershell
py -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; `
python cli.py --input sample_data/crm_notes_raw.csv --outdir outputs; `
python evaluate.py --actions outputs/extracted_actions.csv --summaries outputs/extracted_summaries.csv --ref-actions sample_data/expected_actions_reference.csv --ref-summaries sample_data/expected_summaries_reference.csv | Tee-Object -FilePath outputs/evaluation_report.txt
```

Then separately:
```powershell
streamlit run app.py
```

---

## What you'll have afterward (for a demo / handoff)

| Artifact | Where | Use it for |
|---|---|---|
| `outputs/extracted_actions.csv` | file | Show the row-level extraction (owner, due date, priority, etc.) |
| `outputs/extracted_summaries.csv` | file | Show the one-line-per-account CRM-ready summary |
| `outputs/evaluation_report.txt` | file | Show measured accuracy vs. the reference dataset |
| `screenshots/*.png` | folder | Already-captured images of the live app, for slides/docs without re-running anything |
| `streamlit run app.py` | live | Interactive walkthrough for a stakeholder demo |
