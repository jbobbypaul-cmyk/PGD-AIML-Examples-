"""
RuralCare AI — Agent 1: Symptom Intake
Extracts and structures symptoms from patient free-form text.
"""

import time
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from app.utils.safety_filter import detect_emergency, hash_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a symptom extraction assistant for a rural health information system.
Your ONLY role is to extract and structure symptoms from the patient's input.

STRICT RULES:
- Do NOT diagnose any disease or condition.
- Do NOT suggest any treatment or medicine.
- Do NOT mention any disease name.
- Output ONLY valid JSON matching the schema below. No extra text, no markdown fences.

JSON schema (use exactly these keys):
{{
  "chief_complaint": "one-sentence summary of main complaint",
  "symptoms": ["list", "of", "individual", "symptoms"],
  "symptom_duration": "duration as stated, e.g. '3 days' or 'unknown'",
  "symptom_severity": "mild | moderate | severe"
}}

If severity is not mentioned, default to "moderate".
If duration is not mentioned, use "unknown".
"""


class SymptomOutput(BaseModel):
    chief_complaint: str
    symptoms: list[str] = Field(default_factory=list)
    symptom_duration: str = "unknown"
    symptom_severity: str = "moderate"


def symptom_intake_agent(state: dict[str, Any], llm) -> dict[str, Any]:
    start = time.time()
    text = state.get("translated_input", state.get("raw_input", ""))

    # Emergency check runs here too as a belt-and-suspenders safeguard
    if detect_emergency(text):
        state["emergency_flag"] = True
        logger.warning("Emergency keyword detected in symptom intake for session %s", state.get("session_id"))

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Patient input: {input}"),
    ])

    chain = prompt | llm | JsonOutputParser()

    result: dict = {}
    try:
        result = chain.invoke({"input": text})
        output = SymptomOutput(**result)
    except Exception as exc:
        logger.warning("Symptom extraction failed (%s), retrying…", exc)
        try:
            result = chain.invoke({"input": text + "\n\nRespond with JSON only."})
            output = SymptomOutput(**result)
        except Exception as exc2:
            logger.error("Symptom extraction retry failed: %s", exc2)
            output = SymptomOutput(
                chief_complaint=text[:200],
                symptoms=[],
                symptom_duration="unknown",
                symptom_severity="moderate",
            )

    state["chief_complaint"] = output.chief_complaint
    state["symptoms"] = output.symptoms
    state["symptom_duration"] = output.symptom_duration
    state["symptom_severity"] = output.symptom_severity

    latency = int((time.time() - start) * 1000)
    state.setdefault("audit_log", []).append({
        "agent_name": "symptom_intake",
        "input_hash": hash_text(text),
        "output_hash": hash_text(str(output.model_dump())),
        "latency_ms": latency,
    })
    logger.info("symptom_intake done in %dms — chief: %s", latency, output.chief_complaint[:60])
    return state
