"""
RuralCare AI — Agent 7: Emergency Escalation Agent
Surfaces emergency contacts and first aid guidance immediately.
Must complete in under 2 seconds. Runs BEFORE all other agents on red-flag detection.
"""

import time
from typing import Any

from app.rag.retriever import retrieve_emergency_context, build_context_string
from app.utils.safety_filter import hash_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

EMERGENCY_NUMBERS = {
    "national_emergency": "112",
    "ambulance":          "108",
    "police":             "100",
    "health_helpline":    "104",
}

STATIC_FIRST_AID: dict[str, str] = {
    "default": (
        "1. Stay calm and call 108 or 112 immediately.\n"
        "2. Keep the person still and comfortable.\n"
        "3. Do NOT give food or water.\n"
        "4. If unconscious and not breathing: 30 chest compressions, then 2 breaths.\n"
        "5. Stay with the person until help arrives."
    ),
    "breathing": (
        "1. Call 108 immediately.\n"
        "2. Help person sit upright — lean slightly forward.\n"
        "3. Loosen tight clothing around neck and chest.\n"
        "4. Do NOT give food or water.\n"
        "5. Stay with the person."
    ),
    "unconscious": (
        "1. Call 108 immediately.\n"
        "2. Tap shoulder and call out — check for response.\n"
        "3. Tilt head back, lift chin to open airway.\n"
        "4. Check for breathing for 10 seconds.\n"
        "5. If not breathing: begin CPR — 30 compressions, 2 breaths."
    ),
    "snake_bite": (
        "1. Keep person calm and still. Movement spreads venom.\n"
        "2. Call 108 and go to the nearest hospital NOW.\n"
        "3. Remove jewellery near the bite site.\n"
        "4. Keep the bitten limb below heart level.\n"
        "5. Do NOT cut the bite, suck venom, or apply ice."
    ),
}


def emergency_escalation_agent(state: dict[str, Any]) -> dict[str, Any]:
    start = time.time()

    chief    = state.get("chief_complaint", state.get("translated_input", ""))
    location = state.get("location", {})
    facility = state.get("recommended_facility", "your nearest district hospital")

    # Classify emergency type for first aid selection
    lower = chief.lower()
    if any(k in lower for k in ("breathe", "breathing", "breath")):
        aid_key = "breathing"
    elif any(k in lower for k in ("unconscious", "waking", "consciousness")):
        aid_key = "unconscious"
    elif "snake" in lower or "bite" in lower:
        aid_key = "snake_bite"
    else:
        aid_key = "default"

    # Try RAG first aid retrieval (fast path — k=3, low threshold)
    try:
        docs, sources = retrieve_emergency_context(chief)
        first_aid = build_context_string(docs) if docs else STATIC_FIRST_AID[aid_key]
        source_note = f"\nSource: {', '.join(sources)}" if sources else "\nSource: Standard first aid protocol"
    except Exception:
        first_aid = STATIC_FIRST_AID[aid_key]
        source_note = "\nSource: Standard first aid protocol (offline)"

    # Nearest emergency facility from state or generic fallback
    emerg_facility_line = facility.split("\n")[0] if facility else "your nearest district hospital"

    alert = (
        f"🚨 EMERGENCY — IMMEDIATE ACTION NEEDED 🚨\n\n"
        f"Based on what you described, this may be a MEDICAL EMERGENCY.\n\n"
        f"CALL FOR HELP IMMEDIATELY:\n"
        f"• Emergency:    {EMERGENCY_NUMBERS['national_emergency']}\n"
        f"• Ambulance:    {EMERGENCY_NUMBERS['ambulance']}\n"
        f"• Health Line:  {EMERGENCY_NUMBERS['health_helpline']}\n\n"
        f"NEAREST EMERGENCY FACILITY:\n{emerg_facility_line}\n\n"
        f"WHAT TO DO RIGHT NOW:\n{first_aid}\n"
        f"{source_note}\n\n"
        f"Do NOT wait. Every second counts.\n"
        f"If you cannot call, ask someone nearby to help immediately.\n\n"
        f"⚠️ DISCLAIMER: RuralCare AI is not a doctor. "
        f"Follow the advice of emergency medical services at all times."
    )

    state["emergency_alert"] = alert
    state["emergency_flag"]  = True
    state["triage_level"]    = "EMERGENCY"

    # Production: send webhook alert
    _send_webhook_alert(state)

    state.setdefault("audit_log", []).append({
        "agent_name":     "emergency_escalation",
        "triage_level":   "EMERGENCY",
        "emergency_flag": True,
        "input_hash":     hash_text(chief),
        "output_hash":    hash_text(alert),
        "latency_ms":     int((time.time() - start) * 1000),
    })

    latency = int((time.time() - start) * 1000)
    logger.warning("EMERGENCY escalation complete in %dms for session %s", latency, state.get("session_id"))
    return state


def _send_webhook_alert(state: dict) -> None:
    import os
    webhook_url = os.getenv("EMERGENCY_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        import requests
        requests.post(webhook_url, json={
            "session_id":    state.get("session_id"),
            "patient_token": state.get("patient_token"),
            "location":      state.get("location"),
            "chief_complaint": state.get("chief_complaint"),
        }, timeout=3)
    except Exception as exc:
        logger.error("Emergency webhook failed: %s", exc)
