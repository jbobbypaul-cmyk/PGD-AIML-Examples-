"""
RuralCare AI — FastAPI Application Entry Point
Run: uvicorn app.main:app --reload
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.utils.config import get_config
from app.utils.logger import get_logger
from app.database.sqlite_client import init_db, get_audit_log, get_recent_audit_logs, write_followup_reminder
from app.rag.vector_store import init_vector_store

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RuralCare AI starting up…")
    init_db()
    init_vector_store()
    logger.info("Ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="RuralCare AI",
    description=(
        "Multi-Agent Rural Healthcare Assistant — first-level triage support only. "
        "NOT a diagnostic tool. Always consult a qualified healthcare professional."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Health Check ──────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ruralcare-ai", "version": "0.1.0"}


# ── Text Intake ───────────────────────────────────────────────────────

@app.post("/api/v1/intake")
def symptom_intake(
    symptoms_text: str,
    language: str = Query(default="en"),
    location_district: str | None = Query(default=None),
    location_state: str | None = Query(default=None),
):
    """
    Submit a text description of symptoms.
    Returns triage level, health guidance, facility recommendation, and follow-up plan.
    """
    cfg = get_config()
    text = symptoms_text.strip()
    if len(text) < 5:
        raise HTTPException(status_code=400, detail="Symptom description too short (min 5 characters).")
    if len(text) > cfg.max_input_length:
        text = text[: cfg.max_input_length]

    # Import here to avoid circular import at module load time
    from app.services.orchestrator import run_pipeline
    return run_pipeline(
        raw_input=text,
        language=language,
        location_district=location_district,
        location_state=location_state,
        input_source="text",
    )


# ── Facility Search ───────────────────────────────────────────────────

@app.get("/api/v1/facilities")
def get_facilities(
    district: str = Query(...),
    state: str = Query(...),
    triage_level: str = Query(default="MODERATE"),
):
    """Return ranked nearby healthcare facilities for a location and triage level."""
    from app.agents.appointment_facility import search_facilities
    results = search_facilities(district=district, state_name=state, triage_level=triage_level)
    return {"facilities": results, "count": len(results)}


# ── Audit Log ─────────────────────────────────────────────────────────

@app.get("/api/v1/audit/{session_id}")
def get_session_audit(session_id: str):
    """Return all audit log entries for a given session ID."""
    entries = get_audit_log(session_id)
    if not entries:
        raise HTTPException(status_code=404, detail="Session not found or no audit entries.")
    return {"session_id": session_id, "count": len(entries), "entries": entries}


@app.get("/api/v1/audit")
def list_recent_audit(limit: int = Query(default=20, le=100)):
    """Return the most recent audit log entries across all sessions."""
    return {"entries": get_recent_audit_logs(limit=limit)}


# ── Follow-up Reminder ────────────────────────────────────────────────

@app.post("/api/v1/followup")
def schedule_followup(
    session_id: str,
    patient_token: str,
    followup_type: str,
    scheduled_at: str,
    reminder_text: str = "",
):
    """Manually schedule a follow-up reminder for a patient session."""
    write_followup_reminder(
        session_id=session_id,
        patient_token=patient_token,
        followup_type=followup_type,
        scheduled_at=scheduled_at,
        reminder_text=reminder_text,
    )
    return {"status": "scheduled", "session_id": session_id, "scheduled_at": scheduled_at}
