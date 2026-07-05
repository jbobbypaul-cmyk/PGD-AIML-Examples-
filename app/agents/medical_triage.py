"""
RuralCare AI — Agent 2: Medical Triage
Classifies urgency level: EMERGENCY / URGENT / MODERATE / MILD.
"""

import time
from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.utils.safety_filter import hash_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

TRIAGE_LEVELS = {"EMERGENCY", "URGENT", "MODERATE", "MILD"}

SYSTEM_PROMPT = """You are a triage classification assistant for a rural health information system.
Classify the urgency of the patient's situation into exactly one level:
  EMERGENCY — life-threatening, call 112 immediately
  URGENT    — serious, seek care within 2–4 hours
  MODERATE  — needs care within 24–48 hours
  MILD      — self-care with monitoring

RULES:
- Use WHO-aligned triage principles.
- Do NOT name any specific disease or diagnosis.
- Do NOT recommend any medicine.
- When uncertain, choose the HIGHER urgency level (conservative bias).
- Output ONLY valid JSON (no markdown, no extra text): {{"triage_level": "...", "reasoning": "2-3 sentences", "care_setting": "..."}}

Care settings:
  EMERGENCY → District Hospital Emergency / Call 112
  URGENT    → Community Health Centre (CHC)
  MODERATE  → Primary Health Centre (PHC)
  MILD      → Sub-Centre / ASHA worker / self-care
"""

CARE_SETTINGS = {
    "EMERGENCY": "District Hospital Emergency — Call 112 / 108 immediately",
    "URGENT":    "Community Health Centre (CHC) — within 2–4 hours",
    "MODERATE":  "Primary Health Centre (PHC) — within 24–48 hours",
    "MILD":      "Sub-Centre or ASHA worker — monitor; seek care if worsens",
}


def medical_triage_agent(state: dict[str, Any], llm) -> dict[str, Any]:
    start = time.time()

    # Rule-based override — emergency flag from keyword detector can never be downgraded
    if state.get("emergency_flag"):
        state["triage_level"] = "EMERGENCY"
        state["triage_reasoning"] = "Emergency symptoms detected. Immediate medical attention required."
        state["recommended_care_setting"] = CARE_SETTINGS["EMERGENCY"]
        _append_audit(state, "medical_triage", start)
        return state

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", (
            "Chief complaint: {chief_complaint}\n"
            "Symptoms: {symptoms}\n"
            "Duration: {duration}\n"
            "Severity: {severity}"
        )),
    ])

    chain = prompt | llm | JsonOutputParser()

    try:
        result = chain.invoke({
            "chief_complaint": state.get("chief_complaint", ""),
            "symptoms":        ", ".join(state.get("symptoms", [])),
            "duration":        state.get("symptom_duration", "unknown"),
            "severity":        state.get("symptom_severity", "moderate"),
        })
        level = result.get("triage_level", "URGENT").upper()
        if level not in TRIAGE_LEVELS:
            logger.warning("Invalid triage level '%s' — defaulting to URGENT", level)
            level = "URGENT"

        state["triage_level"]          = level
        state["triage_reasoning"]      = result.get("reasoning", "")
        state["recommended_care_setting"] = CARE_SETTINGS.get(level, CARE_SETTINGS["URGENT"])

    except Exception as exc:
        logger.error("Triage classification failed: %s", exc)
        state["triage_level"]          = "URGENT"
        state["triage_reasoning"]      = "Unable to classify urgency. Defaulting to URGENT as a safety measure."
        state["recommended_care_setting"] = CARE_SETTINGS["URGENT"]

    _append_audit(state, "medical_triage", start)
    logger.info("medical_triage done — level: %s", state["triage_level"])
    return state


def _append_audit(state: dict, agent: str, start: float) -> None:
    state.setdefault("audit_log", []).append({
        "agent_name": agent,
        "triage_level": state.get("triage_level"),
        "emergency_flag": state.get("emergency_flag", False),
        "input_hash": hash_text(str(state.get("symptoms", ""))),
        "output_hash": hash_text(state.get("triage_level", "")),
        "latency_ms": int((time.time() - start) * 1000),
    })
