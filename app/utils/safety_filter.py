"""
RuralCare AI — Safety Filter & Emergency Keyword Detector
Runs synchronously on every patient-facing output. No LLM involved.
"""

import re
import hashlib
from dataclasses import dataclass


# ── Emergency Keywords ────────────────────────────────────────────────

EMERGENCY_KEYWORDS: list[str] = [
    # Cardiovascular / Respiratory
    "chest pain", "cannot breathe", "can't breathe", "difficulty breathing",
    "shortness of breath", "heart attack", "cardiac arrest",
    # Neurological
    "unconscious", "not waking up", "loss of consciousness", "seizure",
    "convulsion", "fitting", "stroke", "sudden weakness one side",
    "sudden vision loss", "sudden severe headache", "facial droop",
    # Bleeding / Trauma
    "severe bleeding", "blood vomiting", "vomiting blood", "coughing blood",
    "heavy bleeding", "bleeding won't stop", "bleeding that won't stop",
    # Poisoning / Envenomation
    "snake bite", "snakebite", "poisoning", "swallowed poison",
    "insecticide ingestion", "rat poison",
    # Obstetric
    "heavy vaginal bleeding", "eclampsia", "fit during pregnancy",
    "baby not moving", "placenta delivered but bleeding",
    # Pediatric
    "child not breathing", "baby turning blue", "baby not responding",
    "infant not breathing",
]

# ── Unsafe Output Patterns ────────────────────────────────────────────

DIAGNOSIS_PATTERNS: list[str] = [
    # "you have [disease]" — but NOT "you have a fever/symptoms/condition you reported"
    # Only block when followed by a specific disease/condition noun, not a symptom echo
    r"you have (a |an )?(malaria|dengue|typhoid|tuberculosis|tb|diabetes|hypertension|"
    r"pneumonia|meningitis|appendicitis|cholera|hepatitis|covid|infection|disease|disorder|syndrome)",
    r"you (are|seem to be) (suffering from|diagnosed with)",
    r"this is (definitely|likely|probably) (a |an )?\w+ (disease|condition|infection|disorder)",
    r"based on your symptoms[,]? (you have|this is) (a |an )?\w+ (disease|condition|infection)",
    r"i can (diagnose|tell you) (you have|this is)",
    r"sounds like (a |an )?\w+ (infection|disease|condition|virus|illness)",
    r"(it|this) (appears|seems) to be (a |an )?\w+ (disease|condition|infection|disorder)",
]

PRESCRIPTION_PATTERNS: list[str] = [
    # Specific dosage instructions (e.g. "500mg paracetamol", "10mg of X")
    r"\d+\s*mg\s*(of\s*)?\w+",
    # Direct take-X-times instructions
    r"\btake \w+ (twice|three times?|once) (a day|daily|per day)\b",
    # First-person or imperative prescribing ("I prescribe", "we prescribe you X")
    r"\b(i|we)\s+prescribe\b",
    r"\bprescribe you\b",
    # Specific prescription-only drug names
    r"\b(amoxicillin|azithromycin|metformin|metronidazole|ciprofloxacin|"
    r"doxycycline|chloroquine|artemether|ceftriaxone|clarithromycin)\b",
    # Explicit antibiotic dosing course instruction
    r"antibiotic[s]?\s+(course|treatment|for \d+ days?)",
]

PHI_PATTERNS: list[str] = [
    r"\b\d{10}\b",
    r"\b\d{12}\b",
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
]

STANDARD_DISCLAIMER = (
    "\n\n⚠️ DISCLAIMER: This information is for general health awareness only. "
    "RuralCare AI is NOT a doctor and cannot diagnose illness or prescribe medicines. "
    "Always consult a qualified healthcare professional for medical decisions. "
    "In an emergency, call 112 (Emergency) or 108 (Ambulance) immediately."
)


# ── Result Types ──────────────────────────────────────────────────────

@dataclass
class SafetyResult:
    passed: bool
    blocked_reason: str | None
    output: str


# ── Public API ────────────────────────────────────────────────────────

def detect_emergency(text: str) -> bool:
    """Rule-based emergency detection. Runs before any LLM call. Under 100ms."""
    lower = text.lower()
    return any(kw in lower for kw in EMERGENCY_KEYWORDS)


def run_safety_filter(text: str) -> SafetyResult:
    """
    Validate LLM output for diagnosis and prescription language.
    Returns SafetyResult with passed=False and safe fallback if blocked.
    """
    lower = text.lower()

    for pattern in DIAGNOSIS_PATTERNS:
        if re.search(pattern, lower):
            return SafetyResult(
                passed=False,
                blocked_reason=f"Diagnosis pattern: {pattern}",
                output=_safe_fallback(),
            )

    for pattern in PRESCRIPTION_PATTERNS:
        if re.search(pattern, lower):
            return SafetyResult(
                passed=False,
                blocked_reason=f"Prescription pattern: {pattern}",
                output=_safe_fallback(),
            )

    # Strip any PHI that leaked through
    for pattern in PHI_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text)

    # Ensure disclaimer is present
    if "DISCLAIMER" not in text:
        text += STANDARD_DISCLAIMER

    return SafetyResult(passed=True, blocked_reason=None, output=text)


def hash_text(text: str) -> str:
    """SHA-256 hash of text for audit log storage (never store raw input)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_fallback() -> str:
    return (
        "I was unable to provide specific information on this topic. "
        "Please visit your nearest health centre or speak with your ASHA worker."
        + STANDARD_DISCLAIMER
    )
