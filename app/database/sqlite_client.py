"""
RuralCare AI — SQLite Database Client
Handles all database operations for sessions, triage results, audit logs,
follow-up reminders, and facility cache.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.utils.config import get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _db_path() -> str:
    return get_config().sqlite_path


@contextmanager
def get_conn():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema Init ───────────────────────────────────────────────────────

def init_db() -> None:
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    schema = Path(__file__).parent / "schema.sql"
    with get_conn() as conn:
        conn.executescript(schema.read_text())
        # Migration: add source column to facility_cache if it pre-dates the schema update
        try:
            conn.execute("ALTER TABLE facility_cache ADD COLUMN source TEXT DEFAULT 'nhm_tn'")
        except Exception:
            pass  # column already exists
    logger.info("Database initialised: %s", _db_path())


# ── Sessions ──────────────────────────────────────────────────────────

def create_session(session_id: str, patient_token: str, language: str, input_source: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO sessions
               (id, patient_token, language, input_source, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, patient_token, language, input_source,
             datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )


def update_session_triage(session_id: str, triage_level: str, emergency_flag: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE sessions SET triage_level=?, emergency_flag=?, updated_at=?
               WHERE id=?""",
            (triage_level, emergency_flag, datetime.utcnow().isoformat(), session_id),
        )


# ── Audit Logs ────────────────────────────────────────────────────────

def write_audit_log(
    session_id: str,
    patient_token: str,
    agent_name: str,
    input_hash: str,
    output_hash: str,
    triage_level: str | None = None,
    emergency_flag: bool = False,
    safety_passed: bool = True,
    blocked_reason: str | None = None,
    rag_sources: list[str] | None = None,
    llm_provider: str | None = None,
    token_count: int | None = None,
    latency_ms: int | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO audit_logs
               (session_id, patient_token, agent_name, triage_level, emergency_flag,
                input_hash, output_hash, safety_passed, blocked_reason, rag_sources,
                llm_provider, token_count, latency_ms, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, patient_token, agent_name, triage_level, emergency_flag,
                input_hash, output_hash, safety_passed, blocked_reason,
                json.dumps(rag_sources or []),
                llm_provider, token_count, latency_ms,
                datetime.utcnow().isoformat(),
            ),
        )


def get_audit_log(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_logs WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_audit_logs(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Follow-up Reminders ───────────────────────────────────────────────

def write_followup_reminder(
    session_id: str,
    patient_token: str,
    followup_type: str,
    scheduled_at: str,
    reminder_text: str = "",
    contact_method: str = "app",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO followup_reminders
               (session_id, patient_token, reminder_type, reminder_text,
                scheduled_at, status, contact_method, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (session_id, patient_token, followup_type, reminder_text,
             scheduled_at, "pending", contact_method, datetime.utcnow().isoformat()),
        )


# ── Facility Cache ────────────────────────────────────────────────────

def get_facilities_by_district(
    district: str,
    state: str,
    user_lat: float | None = None,
    user_lon: float | None = None,
) -> list[dict]:
    with get_conn() as conn:
        if state and state.strip():
            rows = conn.execute(
                """SELECT * FROM facility_cache
                   WHERE LOWER(TRIM(district))=LOWER(TRIM(?))
                     AND LOWER(TRIM(state))=LOWER(TRIM(?))
                   ORDER BY is_government DESC""",
                (district, state),
            ).fetchall()
        else:
            # State not provided — match district only
            rows = conn.execute(
                """SELECT * FROM facility_cache
                   WHERE LOWER(TRIM(district))=LOWER(TRIM(?))
                   ORDER BY is_government DESC""",
                (district,),
            ).fetchall()
    results = []
    for r in rows:
        row = dict(r)
        row["services"] = json.loads(row.get("services") or "[]")
        if user_lat is not None and user_lon is not None and row.get("lat") and row.get("lon"):
            row["distance_km"] = _haversine(user_lat, user_lon, row["lat"], row["lon"])
        results.append(row)
    if user_lat is not None:
        results.sort(key=lambda x: (not x.get("is_government"), x.get("distance_km") or 9999))
    return results


def upsert_facility_cache(facility: dict) -> None:
    """Insert or update a facility record. Matches on name + district + state."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO facility_cache
               (name, facility_type, district, state, address, contact,
                lat, lon, services, is_government, source, last_updated)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT DO NOTHING""",
            (
                facility.get("name", ""),
                facility.get("facility_type", "Hospital"),
                facility.get("district", ""),
                facility.get("state", ""),
                facility.get("address", ""),
                facility.get("contact", ""),
                facility.get("lat"),
                facility.get("lon"),
                json.dumps(facility.get("services") or []),
                int(facility.get("is_government", True)),
                facility.get("source", "nhm_tn"),
                facility.get("last_updated", datetime.utcnow().strftime("%Y-%m-%d")),
            ),
        )


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return round(R * 2 * atan2(sqrt(a), sqrt(1 - a)), 2)
