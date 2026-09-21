"""
rules.py
--------
Static rule tables used by the extraction engine: category keywords,
owner-role patterns, urgency/priority cues, and vagueness markers.

Kept separate from engine.py so that sales-ops can tune wording/keywords
without touching extraction logic.
"""

import re

# ---------------------------------------------------------------------------
# Follow-up categories (mirrors category_owner_mapping.csv)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "pricing_quote": [
        "pricing", "price", "quote", "seat", "seats", "billing model",
        "discount", "commercial band", "cost breakdown", "revised quote",
        "annual billing", "quote reissue",
    ],
    "technical_clarification": [
        "connector", "api", "hosting", "data residency", "integration",
        "technical", "admin rights", "sso", "setup requirement",
        "environment", "security question", "region question",
    ],
    "procurement_vendor_setup": [
        "vendor portal", "tax document", "bank document", "po path",
        "purchase order", "procurement registration", "vendor registration",
        "portal field", "portal status", "procurement",
    ],
    "legal_security_review": [
        "dpa", "security report", "subprocessor", "soc2", "soc 2",
        "security review", "legal review", "msa", "contract redline",
        "infosec",
    ],
    "renewal_commercial": [
        "renewal", "renew", "invoice clarification", "renewal quote",
        "renewal proposal",
    ],
    "demo_pilot": [
        "demo", "pilot", "recap", "import template", "trial",
        "enablement", "workflow demo", "check-in",
    ],
    "account_research": [
        "reference account", "customer reference", "use-case",
        "use case confirmation", "account context", "similar account",
    ],
    "proposal_collateral": [
        "roi summary", "dashboard export", "recap document",
        "commercial pack", "proposal deck", "collateral",
    ],
    "internal_approval": [
        "manager approval", "payment exception", "package scope",
        "internal approval", "sign-off", "signoff",
    ],
    "meeting_scheduling": [
        "follow-up call", "follow up call", "next meeting", "schedule a call",
        "check-in call", "tentatively", "call scheduled",
    ],
    "crm_update": [
        "stage update", "crm evidence", "update the crm", "metadata cleanup",
        "update stage", "log this",
    ],
    "billing_clarification": [
        "invoice", "billing", "payment terms", "one-time onboarding",
        "line item",
    ],
}

# Order matters when a note matches multiple categories equally; earlier
# categories win ties only when keyword-hit counts are equal.
CATEGORY_PRIORITY_ORDER = list(CATEGORY_KEYWORDS.keys())

# ---------------------------------------------------------------------------
# Owner roles
# ---------------------------------------------------------------------------
# Explicit "ROLE-##" style identifiers already used in this CRM's shorthand.
OWNER_ID_PATTERN = re.compile(
    r"\b(AE|SE|CSM|RevOps|LegalOps|InfoSec|Billing|RM)-\d{1,2}\b",
    re.IGNORECASE,
)

# Bare role mentions (no numeric id) that still indicate *who* should act.
OWNER_ROLE_WORDS = {
    "ae": "AE",
    "account executive": "AE",
    "se": "SE",
    "solutions engineer": "SE",
    "sales engineer": "SE",
    "csm": "CSM",
    "customer success manager": "CSM",
    "revops": "RevOps",
    "rev ops": "RevOps",
    "legalops": "LegalOps",
    "legal": "LegalOps",
    "infosec": "InfoSec",
    "security team": "InfoSec",
    "billing": "Billing",
    "finance": "Billing",
    "sales manager": "Sales Manager",
    "manager": "Sales Manager",
}

# Category -> fallback role used only when nothing in the sentence names an
# owner AND the note's own crm_owner field does not resolve the ambiguity.
CATEGORY_DEFAULT_OWNER_ROLE = {
    "pricing_quote": "AE",
    "technical_clarification": "SE",
    "procurement_vendor_setup": "RevOps",
    "legal_security_review": "LegalOps",
    "renewal_commercial": "CSM",
    "demo_pilot": "AE",
    "account_research": "AE",
    "proposal_collateral": "AE",
    "internal_approval": "Sales Manager",
    "meeting_scheduling": "AE",
    "crm_update": "RevOps",
    "billing_clarification": "RevOps",
}

# Phrases that explicitly signal the note itself could not pin an owner down.
OWNER_UNCLEAR_MARKERS = [
    "owner unclear", "unclear owner", "no owner", "not assigned",
    "owner tbd", "owner not stated",
]

# ---------------------------------------------------------------------------
# Timing / urgency
# ---------------------------------------------------------------------------
WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]

# Regex fragments used to pull a timing phrase out of a sentence.
TIMING_PATTERNS = [
    r"\btoday\b",
    r"\btomorrow\b",
    r"\bthis week\b",
    r"\bnext week\b",
    r"\bearly next week\b",
    r"\bend of (the )?week\b",
    r"\bmonth-?end\b",
    r"\bby (next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)( \d{1,2}\s?(am|pm))?\b",
    r"\bas soon as possible\b",
    r"\basap\b",
    r"\bwithin \d+ (day|days|week|weeks)\b",
    r"\bin \d+ (day|days|week|weeks)\b",
    r"\bwhen status changes\b",
    r"\bafter (the )?portal update\b",
    r"\bno firm date\b",
    r"\bno rush\b",
    r"\bnot urgent\b",
]
TIMING_REGEX = re.compile("|".join(TIMING_PATTERNS), re.IGNORECASE)

# Markers that mean "do not compute a hard due_date_iso, this is vague".
VAGUE_TIME_MARKERS = [
    "early next week", "no firm date", "should work", "soon",
    "as soon as possible", "asap", "tentative", "tentatively", "maybe",
    "roughly", "not confirmed", "no rush",
]

HIGH_PRIORITY_MARKERS = [
    "today", "urgent", "asap", "as soon as possible", "escalate",
    "before month-end", "blocking", "blocked", "high priority",
    "cannot proceed", "at risk",
]

LOW_PRIORITY_MARKERS = [
    "not urgent", "no rush", "low priority", "whenever", "nice to have",
]

# ---------------------------------------------------------------------------
# Action-clause detection
# ---------------------------------------------------------------------------
# Concrete, unambiguous action verbs used to recognize imperative /
# modal-triggered follow-up clauses. Kept deliberately narrower than a
# generic "any business verb" list so that descriptive/background
# sentences (e.g. "CSM says usage is strong") are not mistaken for tasks.
ACTION_VERBS = [
    "send", "confirm", "clarify", "schedule", "complete", "notify",
    "prepare", "update", "resolve", "provide", "share", "arrange",
    "upload", "answer", "inform", "verify", "reissue", "register",
    "finalize", "validate", "escalate", "tell", "reach out",
    "follow up", "follow-up",
]
_VERB_ALT = "|".join(sorted((re.escape(v) for v in ACTION_VERBS), key=len, reverse=True))

# A broader cue list retained only for deciding whether two halves of a
# sentence joined by "and" each look action-ish (used for splitting
# compound clauses, not for the initial detection pass).
ACTION_CUE_REGEX = re.compile(
    r"\b(?:" + _VERB_ALT + r"|need(?:s)?|should|must|will|asked|requested|wants?|requires?)\b",
    re.IGNORECASE,
)

# Trigger 1: modal / infinitive immediately before a concrete action verb,
# e.g. "to send", "should confirm", "needs to clarify", or a sentence that
# simply *starts* with the imperative verb itself ("Send the recap...").
TRIGGER_REGEX = re.compile(
    r"(?:\b(?:to|should|must|will|need(?:s)?\s+to)\s+(?:we can\s+|us to\s+)?(?P<verb>" + _VERB_ALT + r")\b)"
    r"|(?:^(?P<verb2>" + _VERB_ALT + r")\b)",
    re.IGNORECASE,
)

# Trigger 2: someone in the note explicitly asked for / requested / wanted
# something. These often lack a clean modal+verb structure but are clearly
# a follow-up request.
ASK_IF_REGEX = re.compile(r"\basked\s+(?:if|whether|us to|to)\s+(?:we can\s+|us to\s+)?", re.IGNORECASE)
ASK_FOR_REGEX = re.compile(r"\basked\s+for\s+", re.IGNORECASE)
REQUEST_REGEX = re.compile(r"\brequested\s+", re.IGNORECASE)
WANT_REGEX = re.compile(r"\bwant(?:s|ed)?\s+", re.IGNORECASE)

# Trigger 3: bare "need(s) <noun phrase>" (no "to <verb>"), e.g.
# "Need billing clarification before renewal quote is reissued."
BARE_NEED_REGEX = re.compile(r"\bneed(?:s)?\s+(?!to\b)(?=[a-z])", re.IGNORECASE)

# Continuation cut points: once an action phrase is captured, trim off any
# trailing contrastive clause that is really separate background context.
CUT_AT_BUT_REGEX = re.compile(r"\bbut\b", re.IGNORECASE)
LEADING_FILLER_TO_STRIP = re.compile(r"^(we can|we should|we will|they can|us to)\s+", re.IGNORECASE)

# Markers that indicate an implied-but-not-explicit action -> lower confidence
IMPLIED_ACTION_MARKERS = [
    "wondering if", "not sure if", "might need", "may need", "possibly",
    "unclear if", "seemed interested", "hinted", "mentioned in passing",
]

# Notes where context signals extra ambiguity regardless of per-action cues.
CONTEXT_REVIEW_MARKERS = [
    "partner handover", "revived opportunity", "reopened opportunity",
    "incomplete context", "messy", "unclear", "owner unclear",
    "no firm date", "tentative", "tentatively", "not confirmed",
    "multiple possible owners", "ambiguous",
]
