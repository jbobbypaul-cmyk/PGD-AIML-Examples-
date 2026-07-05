"""
RuralCare AI — Agent 6: Health Worker Support Agent
Generates a structured briefing note for ASHA / ANM / CHW health workers.
"""

import time
from datetime import datetime
from typing import Any

from app.utils.safety_filter import hash_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

ACTIONS = {
    "EMERGENCY": (
        "URGENT: This patient may have had a medical emergency. "
        "Verify emergency care was received. Arrange follow-up with the treating doctor."
    ),
    "URGENT": (
        "Visit patient within 2–4 hours. Assess temperature, breathing, and hydration. "
        "Arrange referral to CHC or district hospital if the condition is serious."
    ),
    "MODERATE": (
        "Visit patient within 24 hours. Check temperature and hydration status. "
        "Ensure the patient has a plan to visit the PHC within 48 hours."
    ),
    "MILD": (
        "Follow up with the patient in 3 days by phone or home visit. "
        "Provide general health guidance. Remind patient to seek care if symptoms worsen."
    ),
}

SCHEMES_BY_TRIAGE = {
    "EMERGENCY": ["PM-JAY / Ayushman Bharat — hospitalization coverage", "NHM Emergency Transport"],
    "URGENT":    ["PM-JAY / Ayushman Bharat", "NHM Free Drug Scheme at CHC"],
    "MODERATE":  ["NHM Free Drug Scheme at PHC", "Ayushman Bharat Health & Wellness Centre"],
    "MILD":      ["NHM Free Drug Scheme at Sub-Centre", "ASHA incentive for home visits"],
}


def health_worker_support_agent(state: dict[str, Any]) -> dict[str, Any]:
    start = time.time()

    triage   = state.get("triage_level", "MODERATE")
    token    = state.get("patient_token", "UNKNOWN")
    session  = state.get("session_id", "")[:12]
    lang     = state.get("language", "en")
    symptoms = ", ".join(state.get("symptoms", [])) or "Not extracted"
    chief    = state.get("chief_complaint", "Not specified")
    duration = state.get("symptom_duration", "unknown")
    severity = state.get("symptom_severity", "unknown")
    guidance_summary = _summarise_guidance(state.get("health_guidance", ""))
    sources  = ", ".join(state.get("rag_sources", [])) or "General health guidelines"
    plan     = state.get("followup_plan", {})
    facility = state.get("recommended_facility", "Visit nearest PHC").split("\n")[0]
    schemes  = SCHEMES_BY_TRIAGE.get(triage, [])
    action   = ACTIONS.get(triage, ACTIONS["MODERATE"])
    date_str = datetime.utcnow().strftime("%d %B %Y %H:%M UTC")

    lang_note = (
        f"\nPatient's language: {lang.upper()}. Please communicate in that language during your visit."
        if lang != "en" else ""
    )

    briefing = f"""PATIENT BRIEFING NOTE — RuralCare AI
{'='*50}
Session  : {session}...
Token    : {token}
Date     : {date_str}{lang_note}

TRIAGE SUMMARY
{'-'*30}
Level    : {triage}
Complaint: {chief}
Duration : {duration}
Severity : {severity}
Symptoms : {symptoms}

HEALTH WORKER ACTION
{'-'*30}
{action}

CLINICAL NOTES (RAG-Grounded)
{'-'*30}
{guidance_summary}
Source: {sources}

FOLLOW-UP SCHEDULE
{'-'*30}
Visit patient in : {plan.get('follow_up_in', 'As needed')}
Monitor for      : {', '.join(plan.get('watch_for', []))}
Escalate if      : {', '.join(plan.get('return_immediately_if', []))}
Facility         : {facility}

GOVERNMENT SCHEME ELIGIBILITY
{'-'*30}
{chr(10).join('• ' + s for s in schemes)}

NOTES
{'-'*30}
• Clinical judgment of the health worker overrides this AI-generated briefing.
• This note is based on patient-reported symptoms only — no clinical examination.
• Refer to a doctor for diagnosis and treatment decisions.

⚠️ RuralCare AI is not a doctor. This note is for health worker reference only.
"""

    state["health_worker_briefing"] = briefing.strip()
    state.setdefault("audit_log", []).append({
        "agent_name": "health_worker_support",
        "triage_level": triage,
        "input_hash": hash_text(chief),
        "output_hash": hash_text(briefing),
        "latency_ms": int((time.time() - start) * 1000),
    })
    logger.info("health_worker_support done for token %s", token)
    return state


def _summarise_guidance(text: str, max_chars: int = 300) -> str:
    if not text:
        return "No specific guidance retrieved. Conduct full assessment during home visit."
    clean = text.replace("\n\n", " ").replace("\n", " ").strip()
    return clean[:max_chars] + ("…" if len(clean) > max_chars else "")
