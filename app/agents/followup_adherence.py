"""
RuralCare AI — Agent 5: Follow-up & Adherence Agent
Generates a structured follow-up care plan and writes reminders to the database.
"""

import time
from datetime import datetime, timedelta
from typing import Any

from app.database.sqlite_client import write_followup_reminder
from app.utils.safety_filter import hash_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

FOLLOWUP_HOURS = {"EMERGENCY": 0, "URGENT": 6, "MODERATE": 48, "MILD": 96}

WATCH_FOR_MAP = {
    "EMERGENCY": ["any worsening after emergency care"],
    "URGENT":    ["high fever above 39.5°C", "difficulty breathing", "persistent vomiting"],
    "MODERATE":  ["temperature above 39°C", "inability to eat or drink", "new symptoms"],
    "MILD":      ["any worsening of current symptoms", "fever above 38.5°C"],
}

RETURN_IF_MAP = {
    "EMERGENCY": ["condition worsens after hospital discharge"],
    "URGENT":    ["cannot breathe", "loss of consciousness", "convulsions"],
    "MODERATE":  ["cannot breathe", "loss of consciousness", "convulsions", "severe bleeding"],
    "MILD":      ["cannot breathe", "loss of consciousness", "very high fever with rash"],
}

HOME_CARE_MAP = {
    "EMERGENCY": ["Follow all instructions from emergency medical team."],
    "URGENT":    ["Rest completely.", "Drink plenty of fluids.", "Monitor temperature every 4 hours."],
    "MODERATE":  [
        "Rest and avoid exertion.",
        "Drink 2–3 litres of clean water or ORS daily.",
        "Paracetamol for fever — follow package dosage.",
        "Keep a note of your temperature twice daily.",
    ],
    "MILD":      [
        "Rest and stay hydrated.",
        "Monitor symptoms and note any changes.",
        "Seek care if symptoms worsen or persist beyond 3 days.",
    ],
}


def followup_adherence_agent(state: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    triage  = state.get("triage_level", "MODERATE")
    session = state.get("session_id", "")
    token   = state.get("patient_token", "")

    hours = FOLLOWUP_HOURS.get(triage, 48)
    followup_in = (
        "after emergency care" if triage == "EMERGENCY"
        else f"{hours} hours" if hours <= 24
        else f"{hours // 24} days"
    )

    reminders = _build_reminders(triage, hours, state.get("recommended_facility", ""))
    plan = {
        "follow_up_in":        followup_in,
        "watch_for":           WATCH_FOR_MAP.get(triage, WATCH_FOR_MAP["MODERATE"]),
        "return_immediately_if": RETURN_IF_MAP.get(triage, RETURN_IF_MAP["MODERATE"]),
        "home_care":           HOME_CARE_MAP.get(triage, HOME_CARE_MAP["MODERATE"]),
        "reminders":           reminders,
        "adherence_tips":      "Take medicines at the same time each day. Keep a simple symptom diary.",
        "health_scheme_info":  "Free medicines may be available at your government PHC or CHC.",
    }
    state["followup_plan"] = plan

    # Persist reminders
    if session:
        for rem in reminders:
            try:
                write_followup_reminder(
                    session_id=session,
                    patient_token=token,
                    followup_type="symptom_check",
                    scheduled_at=rem.get("scheduled_at", ""),
                    reminder_text=rem.get("action", ""),
                )
            except Exception as exc:
                logger.warning("Failed to write reminder to DB: %s", exc)

    state.setdefault("audit_log", []).append({
        "agent_name": "followup_adherence",
        "input_hash": hash_text(triage),
        "output_hash": hash_text(followup_in),
        "latency_ms": int((time.time() - start) * 1000),
    })
    logger.info("followup_adherence done — follow up in: %s", followup_in)
    return state


def _build_reminders(triage: str, hours: int, facility: str) -> list[dict]:
    now = datetime.utcnow()
    reminders = []

    if triage == "EMERGENCY":
        return [{"when": "after emergency care", "action": "Follow up with doctor.", "priority": "high",
                 "scheduled_at": (now + timedelta(days=1)).isoformat()}]

    reminders.append({
        "when": "today evening",
        "action": "Check temperature and note any new symptoms.",
        "priority": "high",
        "scheduled_at": (now + timedelta(hours=8)).isoformat(),
    })

    if triage == "URGENT":
        reminders.append({
            "when": "in 4–6 hours",
            "action": f"Visit {facility.split(chr(10))[0] if facility else 'CHC or hospital'} if not improved.",
            "priority": "high",
            "scheduled_at": (now + timedelta(hours=5)).isoformat(),
        })

    if triage in ("MODERATE", "MILD"):
        reminders.append({
            "when": f"in {hours} hours",
            "action": f"Visit {facility.split(chr(10))[0] if facility else 'PHC'} if not improved.",
            "priority": "medium",
            "scheduled_at": (now + timedelta(hours=hours)).isoformat(),
        })

    return reminders
