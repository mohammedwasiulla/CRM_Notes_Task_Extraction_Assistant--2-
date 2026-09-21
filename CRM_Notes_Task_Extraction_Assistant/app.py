"""
CRM Notes -> Follow-Up Task Extraction Assistant
Streamlit UI for the Sales Operations workflow.

Run with:
    streamlit run app.py

VISUAL DESIGN NOTE
-------------------
Theme: "case file / audit dossier" -- the same dark-ink, teal-accent theme
used across this team's due-diligence tooling, reused here because the
subject matter has the same shape: an automated first-pass extraction
whose output is source-linked (each action carries its supporting_text)
and pending manual sign-off, not a final decision.
  - dark ink sidebar = the case file cover (where the reviewer sets up
    the request: upload/sample choice, then runs the extraction)
  - dark desk main panel = where the summaries and action ledger get
    reviewed
  - IBM Plex Mono for owners / categories / timestamps = evidence labels
  - a rotated rubber-stamp badge reports overall review status at a glance
  - a 3-step tracker at the top mirrors the actual pipeline
    (Load Notes -> Extract & Review -> Export)
All extraction logic is unchanged -- only the presentation layer.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from extractor import process_notes

# Anchor all relative file paths to this script's own directory rather than
# the process's current working directory. Streamlit Cloud (and some other
# hosts) run the app with the working directory set to the repo root, which
# may not be the folder app.py lives in if the repo has a nested structure
# -- a bare "sample_data/..." path then fails with FileNotFoundError even
# though the file is right there next to app.py.
BASE_DIR = Path(__file__).resolve().parent
SAMPLE_FILE = BASE_DIR / "sample_data" / "sample_input_10_records.csv"

st.set_page_config(
    page_title="CRM Notes → Follow-Up Task Extractor",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# THEME / DESIGN TOKENS -- dark "case file" theme
# --------------------------------------------------------------------------
SIDEBAR_INK = "#0C151B"
MAIN_BG = "#121D25"
CARD_BG = "#182530"
CARD_BG_ALT = "#1D2B37"
BORDER = "#2A3944"
TEXT_INK = "#ECE7D9"
TEXT_MUTED = "#8A96A0"
TEXT_ON_INK = "#ECE7D9"
TEXT_ON_INK_MUTED = "#8A96A0"
ACCENT_VERIFIED = "#4FB088"   # pass / low-risk / clear
ACCENT_FLAG = "#D9A24B"       # amber warning / medium
ACCENT_LOW = "#E2827D"        # fail / high-priority / needs review
ACCENT_LINK = "#7FB3D5"

PRIORITY_COLOR = {"High": ACCENT_LOW, "Medium": ACCENT_FLAG, "Low": ACCENT_VERIFIED}
REVIEW_COLOR = {"Yes": ACCENT_LOW, "No": ACCENT_VERIFIED}

THEME_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
}}

[data-testid="stAppViewContainer"] {{ background: {MAIN_BG}; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stToolbar"] * {{ color: {TEXT_MUTED} !important; }}

/* ---------- Sidebar = case file cover ---------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {SIDEBAR_INK} 0%, {CARD_BG} 100%);
    border-right: 1px solid #060B0F;
}}
[data-testid="stSidebar"] * {{ color: {TEXT_ON_INK} !important; }}
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] label {{
    color: {TEXT_ON_INK_MUTED} !important;
    font-size: 0.85rem;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: {TEXT_ON_INK} !important;
    letter-spacing: 0.01em;
}}
[data-testid="stSidebar"] hr {{ border-color: {BORDER} !important; }}
[data-testid="stSidebar"] [data-testid="stTextArea"] textarea,
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
    background: {CARD_BG_ALT} !important;
    color: {TEXT_ON_INK} !important;
    border: 1px solid {BORDER} !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
}}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    font-family: 'IBM Plex Mono', monospace !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: 0.7rem !important;
    color: #7C8891 !important;
}}
[data-testid="stSidebar"] code {{
    background: {CARD_BG_ALT} !important;
    color: {ACCENT_LINK} !important;
}}

/* ---------- Headings ---------- */
h1, h2, h3, h4, h5 {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: {TEXT_INK} !important;
}}
p, span, li, label, .stMarkdown, [data-testid="stCaptionContainer"] {{ color: {TEXT_INK}; }}
[data-testid="stCaptionContainer"] {{ color: {TEXT_MUTED} !important; }}
[data-testid="stAppViewContainer"] a {{ color: {ACCENT_LINK} !important; }}

/* ---------- Containers / cards ---------- */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {CARD_BG};
    border: 1px solid {BORDER} !important;
    border-radius: 6px !important;
}}

/* ---------- Expanders ---------- */
[data-testid="stExpander"] {{
    border: 1px dashed #3C4C58 !important;
    border-radius: 4px !important;
    background: {CARD_BG};
    margin-bottom: 8px;
}}
[data-testid="stExpander"] summary {{
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.82rem !important;
    color: {TEXT_INK} !important;
}}

/* ---------- Metrics ---------- */
[data-testid="stMetric"] {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 10px 14px;
}}
[data-testid="stMetricLabel"] p {{
    font-family: 'IBM Plex Mono', monospace !important;
    text-transform: uppercase;
    font-size: 0.68rem !important;
    letter-spacing: 0.06em;
    color: {TEXT_MUTED} !important;
}}
[data-testid="stMetricValue"] {{
    font-family: 'Space Grotesk', sans-serif !important;
    color: {TEXT_INK} !important;
}}

/* ---------- Alerts ---------- */
[data-testid="stAlert"] {{
    border-radius: 4px;
    font-size: 0.88rem;
    background: {CARD_BG} !important;
    border: 1px solid {BORDER} !important;
}}
[data-testid="stAlert"] p {{ color: {TEXT_INK} !important; }}
[data-testid="stAlertContentWarning"] {{ border-left: 3px solid {ACCENT_FLAG} !important; }}
[data-testid="stAlertContentInfo"] {{ border-left: 3px solid {ACCENT_LINK} !important; }}
[data-testid="stAlertContentSuccess"] {{ border-left: 3px solid {ACCENT_VERIFIED} !important; }}

/* ---------- Buttons ---------- */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {{
    background: {ACCENT_VERIFIED} !important;
    border: none !important;
    border-radius: 3px !important;
    font-family: 'Space Grotesk', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 0.8rem !important;
    padding: 0.65rem 1rem !important;
    color: #0C1712 !important;
    box-shadow: 0 2px 0 rgba(0,0,0,0.45);
    width: 100%;
}}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p {{ color: #0C1712 !important; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {{ filter: brightness(1.12); }}

[data-testid="stAppViewContainer"] [data-testid="stBaseButton-secondary"],
[data-testid="stAppViewContainer"] [data-testid="stDownloadButton"] button {{
    border: 1px solid {ACCENT_LINK} !important;
    color: {TEXT_INK} !important;
    background: transparent !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    border-radius: 3px !important;
}}
[data-testid="stAppViewContainer"] [data-testid="stBaseButton-secondary"] p,
[data-testid="stAppViewContainer"] [data-testid="stDownloadButton"] button p {{ color: {TEXT_INK} !important; }}
[data-testid="stAppViewContainer"] [data-testid="stBaseButton-secondary"]:hover,
[data-testid="stAppViewContainer"] [data-testid="stDownloadButton"] button:hover {{ background: {ACCENT_LINK} !important; }}
[data-testid="stAppViewContainer"] [data-testid="stBaseButton-secondary"]:hover p,
[data-testid="stAppViewContainer"] [data-testid="stDownloadButton"] button:hover p {{ color: {SIDEBAR_INK} !important; }}

/* ---------- Dataframe wrapper ---------- */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 4px;
    overflow: hidden;
}}

/* ---------- Custom components ---------- */
.dossier-eyebrow {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: {TEXT_MUTED};
    margin-bottom: 2px;
}}
.dossier-title {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 2.1rem;
    color: {TEXT_INK};
    margin: 0 0 2px 0;
    line-height: 1.15;
}}
.dossier-subtitle {{
    color: {TEXT_MUTED};
    font-size: 0.95rem;
    margin-bottom: 1.1rem;
}}

.stepper {{
    display: flex; gap: 0;
    margin: 0.4rem 0 1.6rem 0;
    border: 1px solid {BORDER};
    border-radius: 6px;
    overflow: hidden;
    background: {CARD_BG};
}}
.stepper-step {{
    flex: 1; padding: 10px 16px;
    border-right: 1px solid {BORDER};
    display: flex; align-items: center; gap: 10px;
}}
.stepper-step:last-child {{ border-right: none; }}
.stepper-step.inactive {{ opacity: 0.45; }}
.stepper-num {{
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700; font-size: 0.95rem;
    width: 26px; height: 26px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    background: {ACCENT_VERIFIED}; color: #0C1712;
}}
.stepper-step.inactive .stepper-num {{ background: {BORDER}; color: {TEXT_MUTED}; }}
.stepper-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em;
    color: {TEXT_INK};
}}

.tag-chip {{
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 2px 8px;
    border-radius: 3px;
    margin: 2px 4px 2px 0;
    background: rgba(79,176,136,0.14);
    color: {ACCENT_VERIFIED};
    border: 1px solid rgba(79,176,136,0.40);
}}
.tag-chip.amber {{
    background: rgba(217,162,75,0.14);
    color: {ACCENT_FLAG};
    border-color: rgba(217,162,75,0.40);
}}
.tag-chip.missing {{
    background: rgba(226,130,125,0.12);
    color: {ACCENT_LOW};
    border-color: rgba(226,130,125,0.38);
}}
.tag-chip.empty {{
    background: {CARD_BG_ALT};
    color: {TEXT_MUTED};
    border-color: {BORDER};
}}

.stamp {{
    display: inline-flex; flex-direction: column; align-items: center;
    border: 3px double var(--stamp-color);
    color: var(--stamp-color);
    border-radius: 8px;
    padding: 10px 22px;
    transform: rotate(-3deg);
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; text-align: center;
    background: color-mix(in srgb, var(--stamp-color) 12%, transparent);
}}
.stamp .stamp-level {{ font-size: 1.4rem; line-height: 1.1; }}
.stamp .stamp-caption {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.62rem; letter-spacing: 0.1em; margin-top: 2px;
}}

.section-label {{
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: {TEXT_MUTED};
    border-bottom: 1px solid {BORDER};
    padding-bottom: 4px;
    margin: 1.1rem 0 0.5rem 0;
}}
.scope-line {{
    display: flex; align-items: baseline; gap: 8px;
    font-size: 0.85rem; padding: 3px 0;
}}
.scope-yes {{ color: {ACCENT_VERIFIED}; }}
.scope-no {{ color: {ACCENT_LOW}; }}
</style>
"""

st.markdown(THEME_CSS, unsafe_allow_html=True)

REQUIRED_COLUMNS = ["note_id", "account_alias", "note_body"]


def render_stepper(current: int) -> str:
    steps = ["Load Notes", "Extract & Review", "Export"]
    parts = []
    for i, label in enumerate(steps, start=1):
        cls = "stepper-step" if i <= current else "stepper-step inactive"
        parts.append(
            f'<div class="{cls}"><div class="stepper-num">{i}</div>'
            f'<div class="stepper-label">{label}</div></div>'
        )
    return f'<div class="stepper">{"".join(parts)}</div>'


def priority_chip(value: str) -> str:
    cls = {"High": "missing", "Medium": "amber", "Low": ""}.get(value, "empty")
    return f'<span class="tag-chip {cls}">{value}</span>'


def review_chip(value: str) -> str:
    cls = "missing" if value == "Yes" else ""
    return f'<span class="tag-chip {cls}">{value}</span>'


# --------------------------------------------------------------------------
# HEADER
# --------------------------------------------------------------------------
st.markdown('<div class="dossier-eyebrow">Sales Operations · Workflow Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="dossier-title">🗂️ CRM Notes → Follow-Up Task Extraction</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="dossier-subtitle">Reads CRM-style notes and extracts follow-up actions, owners, '
    'due dates, blockers, priority, and CRM-ready summaries. Runs locally — no live CRM access, '
    'no external API calls.</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# SIDEBAR = case file cover: scope + input + run control
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Case File Scope")
    st.markdown(
        f"""
<div class="scope-line"><span class="scope-yes">✅</span> Follow-up action extraction</div>
<div class="scope-line"><span class="scope-yes">✅</span> Owner / timing / priority / category tagging</div>
<div class="scope-line"><span class="scope-yes">✅</span> CRM-ready summaries</div>
<div class="scope-line"><span class="scope-yes">✅</span> Manual-review flags for ambiguous notes</div>
<div class="scope-line"><span class="scope-no">❌</span> Score rep performance</div>
<div class="scope-line"><span class="scope-no">❌</span> Give sales coaching advice</div>
<div class="scope-line"><span class="scope-no">❌</span> Recommend deal strategy</div>
<div class="scope-line"><span class="scope-no">❌</span> Connect to a live CRM</div>
<div class="scope-line"><span class="scope-no">❌</span> Send emails or calendar invites</div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("### Load Notes")
    uploaded = st.file_uploader(
        "Upload CRM notes (CSV or JSON)",
        type=["csv", "json"],
        help="Use the sample_data/ files in this project to try it out.",
    )
    use_sample = st.checkbox("Use bundled 10-record sample", value=not uploaded)

    st.divider()
    st.markdown("### Input columns expected")
    st.code(
        "note_id, account_alias, interaction_date,\n"
        "interaction_type, opportunity_stage, crm_owner,\n"
        "product_interest_area, note_body,\n"
        "current_blocker_tag, existing_next_action_field",
        language="text",
    )
    st.divider()
    run = st.button("▶ Extract Follow-Up Tasks", type="primary")


def load_dataframe(file, use_sample_flag: bool) -> pd.DataFrame:
    if use_sample_flag:
        return pd.read_csv(SAMPLE_FILE)
    if file is None:
        return pd.DataFrame()
    if file.name.lower().endswith(".json"):
        data = json.load(file)
        if isinstance(data, dict) and "records" in data:
            data = data["records"]
        return pd.DataFrame(data)
    return pd.read_csv(file)


df = load_dataframe(uploaded, use_sample)

if df.empty:
    st.markdown(render_stepper(1), unsafe_allow_html=True)
    st.info("Upload a CRM notes file or check the sample-data box in the sidebar to get started.")
    st.stop()

missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
if missing:
    st.markdown(render_stepper(1), unsafe_allow_html=True)
    st.error(f"Input is missing required column(s): {', '.join(missing)}")
    st.stop()

if run:
    st.session_state["processed_notes"] = df.fillna("").to_dict(orient="records")

processed = "processed_notes" in st.session_state
st.markdown(render_stepper(2 if not processed else 3), unsafe_allow_html=True)

st.markdown('<div class="section-label">1 · Input preview</div>', unsafe_allow_html=True)
st.dataframe(df.head(10), use_container_width=True, hide_index=True)
st.caption(f"{len(df)} CRM note record(s) loaded. Use ▶ Extract Follow-Up Tasks in the sidebar to run the pipeline.")

if processed:
    notes = st.session_state["processed_notes"]
    with st.spinner("Processing CRM notes..."):
        actions, summaries, log = process_notes(notes)

    action_rows = [a.as_row() for a in actions]
    summary_rows = [s.as_row() for s in summaries]

    actions_df = pd.DataFrame(action_rows)
    summaries_df = pd.DataFrame(summary_rows)

    st.success(
        f"Extracted {len(action_rows)} follow-up action(s) across {len(summary_rows)} note(s)."
    )

    review_count = int((summaries_df["manual_review_required"] == "Yes").sum()) if len(summaries_df) else 0
    high_priority_count = int((actions_df["priority"] == "High").sum()) if len(actions_df) else 0

    # ---- KPI row + status stamp ----
    kpi_col, stamp_col = st.columns([4, 1])
    with kpi_col:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("CRM notes processed", len(df))
        col2.metric("Follow-up actions found", len(action_rows))
        col3.metric("High priority actions", high_priority_count)
        col4.metric("Notes flagged for manual review", f"{review_count} / {len(summary_rows)}")
    with stamp_col:
        if review_count == 0:
            stamp_color, stamp_level, stamp_caption = ACCENT_VERIFIED, "CLEAR", "no review flags"
        elif review_count <= len(summary_rows) / 2:
            stamp_color, stamp_level, stamp_caption = ACCENT_FLAG, "SPOT-CHECK", f"{review_count} flagged"
        else:
            stamp_color, stamp_level, stamp_caption = ACCENT_LOW, "REVIEW", f"{review_count} flagged"
        st.markdown(
            f'<div class="stamp" style="--stamp-color:{stamp_color};">'
            f'<span class="stamp-level">{stamp_level}</span>'
            f'<span class="stamp-caption">{stamp_caption}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">2 · CRM-ready summaries</div>', unsafe_allow_html=True)
    st.dataframe(summaries_df, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label">3 · Extracted follow-up actions</div>', unsafe_allow_html=True)
    st.markdown(
        f'{priority_chip("High")} {priority_chip("Medium")} {priority_chip("Low")}'
        f'&nbsp;&nbsp;·&nbsp;&nbsp; Review flag: {review_chip("Yes")} {review_chip("No")}',
        unsafe_allow_html=True,
    )
    filter_cols = st.columns(3)
    with filter_cols[0]:
        cat_options = ["All"] + sorted(actions_df["follow_up_category"].unique().tolist()) if len(actions_df) else ["All"]
        cat_filter = st.selectbox("Filter by category", cat_options)
    with filter_cols[1]:
        prio_options = ["All", "High", "Medium", "Low"]
        prio_filter = st.selectbox("Filter by priority", prio_options)
    with filter_cols[2]:
        review_options = ["All", "Yes", "No"]
        review_filter = st.selectbox("Filter by manual review", review_options)

    filtered = actions_df.copy()
    if len(filtered):
        if cat_filter != "All":
            filtered = filtered[filtered["follow_up_category"] == cat_filter]
        if prio_filter != "All":
            filtered = filtered[filtered["priority"] == prio_filter]
        if review_filter != "All":
            filtered = filtered[filtered["manual_review_required"] == review_filter]

    st.dataframe(filtered, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label">4 · Export for sales-ops review</div>', unsafe_allow_html=True)
    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)

    exp_col1.download_button(
        "⬇ extracted_actions.csv",
        data=actions_df.to_csv(index=False).encode("utf-8"),
        file_name="extracted_actions.csv",
        mime="text/csv",
    )
    exp_col2.download_button(
        "⬇ extracted_actions.json",
        data=json.dumps(action_rows, indent=2).encode("utf-8"),
        file_name="extracted_actions.json",
        mime="application/json",
    )
    exp_col3.download_button(
        "⬇ extracted_summaries.csv",
        data=summaries_df.to_csv(index=False).encode("utf-8"),
        file_name="extracted_summaries.csv",
        mime="text/csv",
    )
    exp_col4.download_button(
        "⬇ extracted_summaries.json",
        data=json.dumps(summary_rows, indent=2).encode("utf-8"),
        file_name="extracted_summaries.json",
        mime="application/json",
    )

    with st.expander("Processing log (per-note diagnostics)"):
        st.json(log)
