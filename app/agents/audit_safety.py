"""
RuralCare AI — Agent 8: Audit, Safety & Compliance Agent
Final mandatory gate before any response reaches the patient.
Validates output, enforces disclaimer, writes audit log.
"""

import time
from typing import Any

from app.utils.safety_filter import run_safety_filter, hash_text, STANDARD_DISCLAIMER
from app.database.sqlite_client import write_audit_log
from app.utils.logger import get_logger

logger = get_logger(__name__)


def audit_safety_agent(state: dict[str, Any]) -> dict[str, Any]:
    start = time.time()

    guidance  = state.get("health_guidance", "")
    emergency = state.get("emergency_alert", "")

    # Run safety filter on primary health guidance
    safety = run_safety_filter(guidance)
    if not safety.passed:
        logger.warning("Safety filter blocked output: %s", safety.blocked_reason)
        state["health_guidance"] = safety.output
        state["safety_passed"]   = False
        state["blocked_reason"]  = safety.blocked_reason
    else:
        state["health_guidance"] = safety.output
        state["safety_passed"]   = True
        state["blocked_reason"]  = None

    # Assemble final patient-facing response
    state["final_response"] = _assemble_response(state)
    state["disclaimer"]     = STANDARD_DISCLAIMER.strip()

    # Write comprehensive audit entry
    latency = int((time.time() - start) * 1000)
    try:
        write_audit_log(
            session_id    = state.get("session_id", ""),
            patient_token = state.get("patient_token", ""),
            agent_name    = "audit_safety_compliance",
            input_hash    = hash_text(guidance),
            output_hash   = hash_text(state["final_response"]),
            triage_level  = state.get("triage_level"),
            emergency_flag= bool(state.get("emergency_flag")),
            safety_passed = state["safety_passed"],
            blocked_reason= state.get("blocked_reason"),
            rag_sources   = state.get("rag_sources"),
            latency_ms    = latency,
        )
    except Exception as exc:
        logger.error("Audit log write failed: %s", exc)

    state.setdefault("audit_log", []).append({
        "agent_name":    "audit_safety_compliance",
        "triage_level":  state.get("triage_level"),
        "emergency_flag":bool(state.get("emergency_flag")),
        "safety_passed": state["safety_passed"],
        "blocked_reason":state.get("blocked_reason"),
        "latency_ms":    latency,
    })

    logger.info("audit_safety done in %dms — safety_passed=%s", latency, state["safety_passed"])
    return state


def _assemble_response(state: dict) -> str:
    sections: list[str] = []

    if state.get("emergency_alert"):
        sections.append(state["emergency_alert"])

    triage = state.get("triage_level", "UNKNOWN")
    level_labels = {
        "EMERGENCY": "🔴 EMERGENCY",
        "URGENT":    "🟠 URGENT",
        "MODERATE":  "🟡 MODERATE",
        "MILD":      "🟢 MILD",
    }
    sections.append(f"TRIAGE LEVEL: {level_labels.get(triage, triage)}")

    if state.get("triage_reasoning"):
        sections.append(f"Reasoning: {state['triage_reasoning']}")

    if state.get("health_guidance"):
        sections.append(f"HEALTH GUIDANCE:\n{state['health_guidance']}")

    if state.get("rag_sources"):
        sections.append("Sources: " + " | ".join(state["rag_sources"]))

    if state.get("recommended_facility"):
        sections.append(f"RECOMMENDED FACILITY:\n{state['recommended_facility']}")

    plan = state.get("followup_plan", {})
    if plan:
        watch   = ", ".join(plan.get("watch_for", []))
        ret_if  = ", ".join(plan.get("return_immediately_if", []))
        sections.append(
            f"FOLLOW-UP:\n"
            f"  Visit in: {plan.get('follow_up_in', 'as needed')}\n"
            f"  Watch for: {watch}\n"
            f"  Return immediately if: {ret_if}"
        )

    sections.append(STANDARD_DISCLAIMER.strip())

    return "\n\n".join(sections)
