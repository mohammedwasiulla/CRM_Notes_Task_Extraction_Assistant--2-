"""
engine.py
---------
Rule-based / regex extraction engine for the CRM Notes -> Follow-Up Task
workflow assistant.

Design goals (per project brief):
  * No live CRM access, no external API calls required to run.
  * Operates purely on the note_body text plus the structured metadata
    columns already present in the CRM export (crm_owner, current_blocker_tag,
    existing_next_action_field, interaction_date, interaction_type).
  * Never invents a hard date when the note text is vague ("soon",
    "early next week", "ASAP") -- timing_reference preserves the phrase,
    due_date_iso is left blank instead.
  * Flags a note / action for manual_review_required when ownership,
    timing, or context is genuinely ambiguous, rather than guessing.
  * Produces operational output only: no coaching language, no rep
    scoring, no deal-strategy recommendations.
"""

from __future__ import annotations

import re
import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from . import rules


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ExtractedAction:
    note_id: str
    action_seq: int
    action_text: str
    suggested_owner: str
    timing_reference: str
    due_date_iso: str
    priority: str
    follow_up_category: str
    blocker_dependency: str
    confidence: str
    manual_review_required: str
    supporting_text: str
    review_reason: str = ""

    @property
    def action_id(self) -> str:
        return f"ACT-{self.note_id.replace('CRM-', '')}-{self.action_seq:02d}"

    def as_row(self) -> dict:
        return {
            "action_id": self.action_id,
            "note_id": self.note_id,
            "action_text": self.action_text,
            "suggested_owner": self.suggested_owner,
            "timing_reference": self.timing_reference,
            "due_date_iso": self.due_date_iso,
            "priority": self.priority,
            "follow_up_category": self.follow_up_category,
            "blocker_dependency": self.blocker_dependency,
            "confidence": self.confidence,
            "manual_review_required": self.manual_review_required,
            "supporting_text": self.supporting_text,
        }


@dataclass
class NoteSummary:
    note_id: str
    account_alias: str
    crm_ready_summary: str
    primary_follow_up_category: str
    overall_priority: str
    manual_review_required: str
    reason_for_review: str
    action_count: int

    def as_row(self) -> dict:
        return {
            "note_id": self.note_id,
            "account_alias": self.account_alias,
            "crm_ready_summary": self.crm_ready_summary,
            "primary_follow_up_category": self.primary_follow_up_category,
            "overall_priority": self.overall_priority,
            "manual_review_required": self.manual_review_required,
            "reason_for_review": self.reason_for_review,
            "action_count": self.action_count,
        }


# ---------------------------------------------------------------------------
# Sentence / clause splitting
# ---------------------------------------------------------------------------
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def _split_and_if_both_actionish(phrase: str) -> list[str]:
    """Split a captured phrase on ' and ' only when both halves independently
    look like their own action (each contains an action cue word)."""
    if " and " not in phrase.lower():
        return [phrase]
    idx = phrase.lower().find(" and ")
    left, right = phrase[:idx], phrase[idx + 5:]
    if rules.ACTION_CUE_REGEX.search(left) and rules.ACTION_CUE_REGEX.search(right):
        return [left.strip(" ,;"), right.strip(" ,;.")]
    return [phrase]


def find_action_phrases(sentence: str) -> list[str]:
    """Return 0, 1, or 2 action phrase strings found in a single sentence.

    Uses a small set of precise triggers (modal+verb, imperative start,
    'asked if/for', 'requested', 'wanted', bare 'need <noun>') rather than
    flagging any sentence that merely contains a business-y word, so that
    narrative/background sentences are not mistaken for follow-up tasks.
    """
    s = sentence.strip()
    if not s:
        return []

    # 1. modal / imperative verb trigger(s) -- may fire more than once in a
    #    single sentence ("Send X and confirm Y").
    trigger_spans = []  # (full_match_start, verb_start)
    for m in rules.TRIGGER_REGEX.finditer(s):
        verb_start = m.start("verb") if m.group("verb") else m.start("verb2")
        trigger_spans.append((m.start(), verb_start))
    if trigger_spans:
        phrases = []
        for i, (_, verb_start) in enumerate(trigger_spans):
            end = trigger_spans[i + 1][0] if i + 1 < len(trigger_spans) else len(s)
            phrase = s[verb_start:end]
            phrase = rules.CUT_AT_BUT_REGEX.split(phrase)[0]
            # drop a trailing dangling connector left over from the next
            # trigger's lead-in, e.g. "...before Thursday and CSM to"
            phrase = re.sub(r"\s*[;,]?\s*(?:and|then)\s+\S+\s+to\s*$", "", phrase, flags=re.IGNORECASE)
            phrase = re.sub(r"\s+and\s*$", "", phrase, flags=re.IGNORECASE)
            # drop a trailing dangling role name left immediately before the
            # next trigger's own "to <verb>" lead-in, e.g. "...fields; AE"
            phrase = re.sub(
                r"\s*[;,]?\s*\b(?:AE|SE|CSM|RevOps|LegalOps|InfoSec|Billing|RM)(?:-\d+)?\s*$",
                "", phrase, flags=re.IGNORECASE,
            )
            phrase = phrase.strip(" ,;.")
            if phrase:
                phrases.append(phrase)
        # also allow an " and " split within a single captured phrase
        expanded = []
        for p in phrases:
            expanded.extend(_split_and_if_both_actionish(p))
        return expanded

    # 2. "asked if/whether/to ..." -> capture the request itself
    m = rules.ASK_IF_REGEX.search(s)
    if m:
        phrase = s[m.end():]
        phrase = rules.CUT_AT_BUT_REGEX.split(phrase)[0].strip(" ,;.")
        phrase = rules.LEADING_FILLER_TO_STRIP.sub("", phrase)
        if phrase:
            return _split_and_if_both_actionish(phrase)

    # 3. "asked for X" -> treat X as something to provide/send
    m = rules.ASK_FOR_REGEX.search(s)
    if m:
        phrase = s[m.end():]
        phrase = rules.CUT_AT_BUT_REGEX.split(phrase)[0].strip(" ,;.")
        if phrase:
            return _split_and_if_both_actionish(phrase)

    # 4. "requested X"
    m = rules.REQUEST_REGEX.search(s)
    if m:
        phrase = s[m.end():]
        phrase = rules.CUT_AT_BUT_REGEX.split(phrase)[0].strip(" ,;.")
        if phrase:
            return _split_and_if_both_actionish(phrase)

    # 5. "want(s)/wanted X" -- skip common non-actionable sentiment phrasing
    m = rules.WANT_REGEX.search(s)
    if m and not re.search(r"kept warm|over-?promised|to know how it feels", s, re.IGNORECASE):
        phrase = s[m.end():]
        phrase = rules.CUT_AT_BUT_REGEX.split(phrase)[0].strip(" ,;.")
        if phrase:
            return _split_and_if_both_actionish(phrase)

    # 6. bare "need(s) <noun phrase>" fallback -- whole sentence retained,
    #    since the requirement and its context are usually intertwined.
    if rules.BARE_NEED_REGEX.search(s):
        return [s]

    return []


def is_action_clause(sentence: str) -> bool:
    return bool(find_action_phrases(sentence))


def extract_timing_reference(clause: str, full_note: str) -> str:
    match = rules.TIMING_REGEX.search(clause)
    if match:
        return match.group(0).strip()
    # fall back to searching the whole note if the clause itself lacks timing
    match = rules.TIMING_REGEX.search(full_note)
    return match.group(0).strip() if match else ""


def is_vague_timing(timing_ref: str, clause: str, full_note: str) -> bool:
    haystack = f"{clause} {full_note}".lower()
    if not timing_ref:
        return True
    for marker in rules.VAGUE_TIME_MARKERS:
        if marker in haystack and marker in timing_ref.lower():
            return True
    if timing_ref.lower() in ("early next week", "no firm date", "asap",
                               "as soon as possible", "no rush", "not urgent"):
        return True
    return False


_NEXT_WEEKDAY_RE = re.compile(
    r"\b(next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def compute_due_date(timing_ref: str, interaction_date: Optional[date]) -> str:
    """Return an ISO date string, or '' when timing is too vague to ground."""
    if not timing_ref or interaction_date is None:
        return ""

    t = timing_ref.lower()

    if is_vague_timing(timing_ref, timing_ref, timing_ref):
        return ""

    if "today" in t:
        return interaction_date.isoformat()

    if "tomorrow" in t:
        return (interaction_date + timedelta(days=1)).isoformat()

    if "month-end" in t or "month end" in t:
        last_day = calendar.monthrange(interaction_date.year, interaction_date.month)[1]
        return date(interaction_date.year, interaction_date.month, last_day).isoformat()

    if "next week" in t and "early" not in t:
        return (interaction_date + timedelta(days=7)).isoformat()

    weekday_match = _NEXT_WEEKDAY_RE.search(t)
    if weekday_match:
        target_name = weekday_match.group(2).lower()
        target_idx = rules.WEEKDAYS.index(target_name)
        days_ahead = (target_idx - interaction_date.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (interaction_date + timedelta(days=days_ahead)).isoformat()

    return ""


def extract_owner(clause: str, full_note: str, crm_owner: str, category: str) -> tuple[str, bool]:
    """Returns (owner, was_inferred_generic_role)."""
    haystack = f"{clause} {full_note}"

    for marker in rules.OWNER_UNCLEAR_MARKERS:
        if marker in haystack.lower():
            return "", False

    id_match = rules.OWNER_ID_PATTERN.search(haystack)
    if id_match:
        return id_match.group(0).upper().replace("AE-", "AE-"), False

    lower_hay = haystack.lower()
    for phrase, role in rules.OWNER_ROLE_WORDS.items():
        if phrase in lower_hay:
            return role, False

    if crm_owner:
        return crm_owner, False

    default_role = rules.CATEGORY_DEFAULT_OWNER_ROLE.get(category, "")
    if default_role:
        return default_role, True

    return "", False


def classify_category(clause: str, full_note: str, product_interest: str) -> str:
    haystack = f"{clause} {full_note} {product_interest}".lower()
    best_cat, best_score = "", 0
    for cat in rules.CATEGORY_PRIORITY_ORDER:
        kws = rules.CATEGORY_KEYWORDS[cat]
        score = sum(1 for kw in kws if kw in haystack)
        if score > best_score:
            best_cat, best_score = cat, score
    return best_cat or "account_research"  # safe generic fallback


def determine_priority(clause: str, full_note: str, category: str, due_date_iso: str,
                        interaction_date: Optional[date]) -> str:
    haystack = f"{clause} {full_note}".lower()
    for marker in rules.HIGH_PRIORITY_MARKERS:
        if marker in haystack:
            return "High"
    for marker in rules.LOW_PRIORITY_MARKERS:
        if marker in haystack:
            return "Low"
    if due_date_iso and interaction_date is not None:
        try:
            due = date.fromisoformat(due_date_iso)
            if (due - interaction_date).days <= 2:
                return "High"
        except ValueError:
            pass
    if category in ("billing_clarification", "renewal_commercial", "pricing_quote",
                     "procurement_vendor_setup"):
        return "Medium"
    return "Medium"


def determine_blocker(full_note: str, current_blocker_tag: str) -> str:
    if current_blocker_tag and current_blocker_tag.strip().lower() not in ("none", "n/a", ""):
        return current_blocker_tag.strip()
    m = re.search(r"(blocked by|blocking|depends on|pending)\s+([^.;]+)", full_note, re.IGNORECASE)
    if m:
        return m.group(0).strip()
    return ""


def determine_confidence(owner: str, owner_inferred: bool, timing_ref: str,
                          due_date_iso: str, clause: str) -> str:
    haystack = clause.lower()
    implied = any(marker in haystack for marker in rules.IMPLIED_ACTION_MARKERS)
    score = 0
    score += 1 if (owner and not owner_inferred) else 0
    score += 1 if (timing_ref and not is_vague_timing(timing_ref, clause, clause)) else 0
    score += 1 if due_date_iso else 0
    if implied:
        return "Low"
    if score >= 2:
        return "High"
    if score == 1:
        return "Medium"
    return "Low" if not owner and not timing_ref else "Medium"


def determine_manual_review(owner: str, owner_inferred: bool, timing_ref: str,
                             clause: str, full_note: str, category: str,
                             blocker: str) -> tuple[str, str]:
    reasons = []
    haystack = f"{clause} {full_note}".lower()

    if not owner:
        reasons.append("owner is not clearly identified in the note")
    elif owner_inferred:
        reasons.append("owner was inferred from category defaults, not stated in the note")

    if is_vague_timing(timing_ref, clause, full_note) and timing_ref:
        reasons.append("timing is vague or tentative")
    elif not timing_ref:
        reasons.append("no timing reference found")

    for marker in rules.CONTEXT_REVIEW_MARKERS:
        if marker in haystack:
            reasons.append(f"note context flagged: '{marker}'")
            break

    review_hint = rules.CATEGORY_KEYWORDS.get(category, [])
    _ = review_hint  # category-specific hint reserved for future tuning

    if reasons:
        return "Yes", "; ".join(dict.fromkeys(reasons))  # de-dupe, preserve order
    return "No", "No major ambiguity beyond normal sales-ops review."


# ---------------------------------------------------------------------------
# Top-level per-note processing
# ---------------------------------------------------------------------------
def _parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(value.strip())
    except Exception:
        return None


def extract_actions_for_note(note: dict) -> list[ExtractedAction]:
    note_id = note.get("note_id", "").strip()
    note_body = note.get("note_body", "") or ""
    crm_owner = (note.get("crm_owner") or "").strip()
    product_interest = note.get("product_interest_area", "") or ""
    current_blocker_tag = note.get("current_blocker_tag", "") or ""
    interaction_date = _parse_date(note.get("interaction_date", ""))

    sentences = split_sentences(note_body)

    # Each item: (action_phrase_for_display, source_sentence_for_context)
    candidates: list[tuple[str, str]] = []
    for sentence in sentences:
        for phrase in find_action_phrases(sentence):
            candidates.append((phrase, sentence))

    # Fallback: if nothing matched a verb cue but an existing_next_action_field
    # was supplied by the CRM itself, treat that as the single action so a
    # note never silently produces zero rows when the CRM already has intent.
    if not candidates:
        existing = (note.get("existing_next_action_field") or "").strip()
        if existing:
            candidates = [(existing, existing)]

    actions: list[ExtractedAction] = []
    seq = 1
    for phrase, context_sentence in candidates:
        clean_phrase = phrase.strip(" .;,")
        if not clean_phrase:
            continue

        # context_sentence carries surrounding info (owner name, timing,
        # conditions) that the trimmed action phrase alone may have lost.
        category = classify_category(clean_phrase, note_body, product_interest)
        owner, owner_inferred = extract_owner(context_sentence, note_body, crm_owner, category)
        timing_ref = extract_timing_reference(context_sentence, note_body)
        due_date = compute_due_date(timing_ref, interaction_date)
        priority = determine_priority(context_sentence, note_body, category, due_date, interaction_date)
        blocker = determine_blocker(note_body, current_blocker_tag)
        confidence = determine_confidence(owner, owner_inferred, timing_ref, due_date, context_sentence)
        review_flag, review_reason = determine_manual_review(
            owner, owner_inferred, timing_ref, context_sentence, note_body, category, blocker
        )

        action_text = normalize_action_text(clean_phrase)

        actions.append(
            ExtractedAction(
                note_id=note_id,
                action_seq=seq,
                action_text=action_text,
                suggested_owner=owner,
                timing_reference=timing_ref,
                due_date_iso=due_date,
                priority=priority,
                follow_up_category=category,
                blocker_dependency=blocker,
                confidence=confidence,
                manual_review_required=review_flag,
                supporting_text=context_sentence.strip(),
                review_reason=review_reason,
            )
        )
        seq += 1

    return actions


_LEADING_FILLER = re.compile(
    r"^(they |champion |customer |account |manager |finance |procurement |"
    r"buying team )?(asked|wants?|requested|said|mentioned)( if| that| to)?\s*",
    re.IGNORECASE,
)


def normalize_action_text(clause: str) -> str:
    """Best-effort rewrite of a raw clause into a short imperative task
    line, e.g. 'Champion asked if we can send a recap' -> 'Send recap'.
    Falls back to the original clause (capitalized) if no clean rewrite
    is confidently possible -- we do not want to fabricate meaning."""
    text = clause.strip()
    stripped = _LEADING_FILLER.sub("", text)
    stripped = re.sub(r"^(we can|we should|to)\s+", "", stripped, flags=re.IGNORECASE)
    stripped = stripped.strip(" .,;")
    if not stripped:
        stripped = text
    return stripped[0].upper() + stripped[1:] if stripped else stripped


# ---------------------------------------------------------------------------
# Note-level summary
# ---------------------------------------------------------------------------
_PRIORITY_RANK = {"High": 3, "Medium": 2, "Low": 1, "": 0}


def build_note_summary(note: dict, actions: list[ExtractedAction]) -> NoteSummary:
    note_id = note.get("note_id", "").strip()
    account_alias = note.get("account_alias", "").strip()
    interaction_type = (note.get("interaction_type") or "interaction").strip().lower()
    current_blocker_tag = (note.get("current_blocker_tag") or "").strip()

    if actions:
        cat_counts: dict[str, int] = {}
        for a in actions:
            cat_counts[a.follow_up_category] = cat_counts.get(a.follow_up_category, 0) + 1
        primary_category = max(cat_counts.items(), key=lambda kv: kv[1])[0]
        overall_priority = max((a.priority for a in actions), key=lambda p: _PRIORITY_RANK.get(p, 0))
        review_flags = [a for a in actions if a.manual_review_required == "Yes"]
        manual_review = "Yes" if review_flags else "No"
        if review_flags:
            reason_for_review = review_flags[0].review_reason or "See per-action notes for detail."
        else:
            reason_for_review = "No major ambiguity beyond normal sales-ops review."
    else:
        primary_category = "account_research"
        overall_priority = "Low"
        manual_review = "Yes"
        reason_for_review = "No explicit follow-up action could be detected in the note text."

    category_label = primary_category.replace("_", " ")
    blocker_clause = f" Current blocker: {current_blocker_tag}." if current_blocker_tag else ""

    summary = (
        f"{account_alias} requires {len(actions)} follow-up item(s) after {interaction_type}. "
        f"Primary focus is {category_label}.{blocker_clause} "
        f"Overall priority is {overall_priority}; manual review: {manual_review}."
    )

    return NoteSummary(
        note_id=note_id,
        account_alias=account_alias,
        crm_ready_summary=summary,
        primary_follow_up_category=primary_category,
        overall_priority=overall_priority,
        manual_review_required=manual_review,
        reason_for_review=reason_for_review,
        action_count=len(actions),
    )


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------
def process_notes(notes: list[dict]) -> tuple[list[ExtractedAction], list[NoteSummary], list[dict]]:
    """Returns (all_actions, all_summaries, processing_log_entries)."""
    all_actions: list[ExtractedAction] = []
    all_summaries: list[NoteSummary] = []
    log: list[dict] = []

    for note in notes:
        actions = extract_actions_for_note(note)
        summary = build_note_summary(note, actions)
        all_actions.extend(actions)
        all_summaries.append(summary)
        log.append({
            "note_id": note.get("note_id", ""),
            "actions_found": len(actions),
            "manual_review_required": summary.manual_review_required,
            "primary_follow_up_category": summary.primary_follow_up_category,
        })

    return all_actions, all_summaries, log
