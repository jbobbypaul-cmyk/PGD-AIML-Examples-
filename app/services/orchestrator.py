"""
RuralCare AI — LangGraph Orchestrator
Wires all 8 agents into a stateful pipeline with emergency fast-path routing.

Bug fixes applied:
  - Uses START node for conditional entry (correct LangGraph 0.2+ API)
  - run_pipeline() is synchronous — no asyncio issues in Streamlit or FastAPI
  - create_session() called at pipeline start
"""

import uuid
from datetime import datetime
from typing import Any

from langgraph.graph import StateGraph, END, START

from app.utils.config import get_config
from app.utils.safety_filter import detect_emergency
from app.utils.logger import get_logger
from app.services.translator import translate_text, detect_language
from app.database.sqlite_client import create_session
from app.agents.symptom_intake import symptom_intake_agent
from app.agents.medical_triage import medical_triage_agent
from app.agents.rag_agent import rag_agent
from app.agents.appointment_facility import appointment_facility_agent
from app.agents.followup_adherence import followup_adherence_agent
from app.agents.health_worker_support import health_worker_support_agent
from app.agents.emergency_escalation import emergency_escalation_agent
from app.agents.audit_safety import audit_safety_agent

logger = get_logger(__name__)

# ── LLM Factory ───────────────────────────────────────────────────────

def _get_llm():
    cfg = get_config()
    if cfg.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=cfg.ollama_model,
            base_url=cfg.ollama_base_url,
            temperature=0.1,
        )
    if cfg.llm_provider == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model="claude-sonnet-4-6",
            api_key=cfg.anthropic_api_key,
            temperature=0.1,
        )
    if cfg.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", api_key=cfg.openai_api_key, temperature=0.1)
    if cfg.llm_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=cfg.google_api_key,
            temperature=0.1,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {cfg.llm_provider}")


# ── State Initialisation ──────────────────────────────────────────────

def _init_state(
    raw_input: str,
    language: str,
    location_district: str | None,
    location_state: str | None,
    input_source: str,
) -> dict[str, Any]:
    if not language or language == "auto":
        language = detect_language(raw_input)

    translated = (
        translate_text(raw_input, src=language, dest="en")
        if language != "en"
        else raw_input
    )

    return {
        "session_id":      str(uuid.uuid4()),
        "patient_token":   f"PT-{uuid.uuid4().hex[:8]}",
        "language":        language,
        "timestamp":       datetime.utcnow().isoformat(),
        "raw_input":       raw_input,
        "translated_input": translated,
        "input_source":    input_source,
        "location": {
            "district": (location_district or "").strip().title(),
            "state":    (location_state or "").strip().title(),
            "lat":      None,
            "lon":      None,
        },
        # Symptom Intake
        "symptoms":        [],
        "chief_complaint": "",
        "symptom_duration": "",
        "symptom_severity": "",
        # Triage
        "triage_level":    "",
        "triage_reasoning": "",
        "recommended_care_setting": "",
        # RAG
        "rag_context":     "",
        "rag_sources":     [],
        "health_guidance": "",
        "grounding_confidence": "",
        # Facility
        "facilities":      [],
        "recommended_facility": "",
        # Follow-up
        "followup_plan":   {},
        # Health worker
        "health_worker_briefing": "",
        # Emergency
        "emergency_flag":  False,
        "emergency_alert": "",
        # Safety / audit
        "safety_passed":   True,
        "blocked_reason":  None,
        "disclaimer":      "",
        "audit_log":       [],
        # Final
        "final_response":  "",
        "error":           None,
    }


# ── Routing Functions ─────────────────────────────────────────────────

def _route_from_start(state: dict) -> str:
    """Emergency check: runs before any LLM call — purely rule-based."""
    return "emergency" if detect_emergency(state.get("translated_input", "")) else "normal"


def _route_after_triage(state: dict) -> str:
    return "escalate" if state.get("triage_level") == "EMERGENCY" else "continue"


# ── Safe Node Wrapper ─────────────────────────────────────────────────

def _node(fn, llm=None):
    """Wrap an agent so a crash never kills the whole pipeline."""
    def _inner(state: dict) -> dict:
        try:
            return fn(state, llm) if llm is not None else fn(state)
        except Exception as exc:
            logger.error("Agent '%s' raised: %s", fn.__name__, exc)
            state.setdefault("audit_log", []).append({
                "agent_name": fn.__name__,
                "error": str(exc),
            })
            return state
    return _inner


# ── Graph Builder ─────────────────────────────────────────────────────

def _build_graph(llm):
    g = StateGraph(dict)

    # Register nodes
    g.add_node("symptom_intake",       _node(symptom_intake_agent, llm))
    g.add_node("medical_triage",       _node(medical_triage_agent, llm))
    g.add_node("rag_agent",            _node(rag_agent, llm))
    g.add_node("appointment_facility", _node(appointment_facility_agent))
    g.add_node("followup_adherence",   _node(followup_adherence_agent))
    g.add_node("health_worker",        _node(health_worker_support_agent))
    g.add_node("emergency_escalation", _node(emergency_escalation_agent))
    g.add_node("audit_safety",         _node(audit_safety_agent))

    # ── Entry: conditional on emergency keyword check ─────────────────
    # Correct LangGraph 0.2+ pattern: add_conditional_edges from START
    g.add_conditional_edges(
        START,
        _route_from_start,
        {"emergency": "emergency_escalation", "normal": "symptom_intake"},
    )

    # ── Normal path ───────────────────────────────────────────────────
    g.add_edge("symptom_intake", "medical_triage")

    g.add_conditional_edges(
        "medical_triage",
        _route_after_triage,
        {"escalate": "emergency_escalation", "continue": "rag_agent"},
    )

    g.add_edge("rag_agent",            "appointment_facility")
    g.add_edge("appointment_facility", "followup_adherence")
    g.add_edge("followup_adherence",   "health_worker")
    g.add_edge("health_worker",        "audit_safety")

    # ── Emergency path always ends at audit ───────────────────────────
    g.add_edge("emergency_escalation", "audit_safety")

    g.add_edge("audit_safety", END)

    return g.compile()


# ── Public API — synchronous (works in Streamlit, FastAPI, notebooks) ─

def run_pipeline(
    raw_input: str,
    language: str = "en",
    location_district: str | None = None,
    location_state: str | None = None,
    input_source: str = "text",
) -> dict[str, Any]:
    """
    Run the full RuralCare AI pipeline synchronously.
    Safe to call from Streamlit, FastAPI (via asyncio.to_thread), or Jupyter.
    """
    llm   = _get_llm()
    graph = _build_graph(llm)
    state = _init_state(raw_input, language, location_district, location_state, input_source)

    # Persist session to DB immediately so audit entries have a parent row
    try:
        create_session(
            session_id=state["session_id"],
            patient_token=state["patient_token"],
            language=state["language"],
            input_source=input_source,
        )
    except Exception as exc:
        logger.warning("create_session failed (non-fatal): %s", exc)

    logger.info(
        "Pipeline start — session=%s lang=%s emergency_pre_check=%s",
        state["session_id"], language,
        detect_emergency(state.get("translated_input", "")),
    )

    result = graph.invoke(state)

    # Translate final response back to patient language
    if result.get("language", "en") != "en" and result.get("final_response"):
        try:
            result["final_response"] = translate_text(
                result["final_response"],
                src="en",
                dest=result["language"],
            )
        except Exception as exc:
            logger.warning("Response back-translation failed: %s", exc)

    logger.info(
        "Pipeline done — session=%s triage=%s safety=%s",
        result.get("session_id"),
        result.get("triage_level"),
        result.get("safety_passed"),
    )
    return result
