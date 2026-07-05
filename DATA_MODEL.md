# DATA_MODEL.md — RuralCare AI Data Models

## Purpose

Define all data schemas, database tables, Pydantic models, and LangGraph state structures used in RuralCare AI.

---

## 1. LangGraph State — PatientState

The central data object passed between all agents. Each agent reads from and writes to this `TypedDict`.

```python
# app/models/data_models.py

from typing import TypedDict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PatientState(TypedDict):
    # ── Session ──────────────────────────────────────────────
    session_id: str
    patient_token: str          # Anonymized: "PT-{uuid4.hex[:8]}"
    language: str               # ISO 639-1 code: "en", "hi", "ta", etc.
    timestamp: str              # ISO 8601

    # ── Input ────────────────────────────────────────────────
    raw_input: str              # Original text / transcribed audio
    translated_input: str       # English translation for LLM
    input_source: str           # "text" | "voice"
    audio_file_path: Optional[str]

    # ── Symptom Extraction ───────────────────────────────────
    symptoms: list[str]
    chief_complaint: str
    symptom_duration: str
    symptom_severity: str       # "mild" | "moderate" | "severe"
    emergency_flag: bool

    # ── Triage ───────────────────────────────────────────────
    triage_level: str           # "EMERGENCY" | "URGENT" | "MODERATE" | "MILD"
    triage_reasoning: str

    # ── RAG ──────────────────────────────────────────────────
    rag_query: str
    rag_context: str
    rag_sources: list[str]
    health_guidance: str

    # ── Facility ─────────────────────────────────────────────
    location: dict              # {"district": str, "state": str, "lat": float, "lon": float}
    facilities: list[dict]
    recommended_facility: str
    _fac_debug: list[str]       # Internal debug trace: query params, row counts, exceptions

    # ── Follow-up ────────────────────────────────────────────
    followup_plan: dict
    medication_reminders: list[str]
    adherence_tips: str

    # ── Health Worker ─────────────────────────────────────────
    health_worker_briefing: str

    # ── Safety & Audit ───────────────────────────────────────
    safety_passed: bool
    blocked_reason: Optional[str]
    disclaimer: str
    audit_log: list[dict]

    # ── Final Output ──────────────────────────────────────────
    final_response: str
    response_language: str      # Language of final response
    error: Optional[str]
    errors: list[str]           # Accumulated from _node fail-safe wrapper
```

---

## 2. Pydantic API Models

### Request Models

```python
class SymptomIntakeRequest(BaseModel):
    patient_token: Optional[str] = None
    symptoms_text: str = Field(..., min_length=5, max_length=2000)
    language: str = Field(default="en", pattern="^[a-z]{2}$")
    location_district: Optional[str] = None
    location_state: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "symptoms_text": "I have had fever for 3 days and headache",
                "language": "en",
                "location_district": "Salem",
                "location_state": "Tamil Nadu"
            }
        }


class VoiceIntakeRequest(BaseModel):
    patient_token: Optional[str] = None
    language: str = Field(default="auto")
    location_district: Optional[str] = None
    location_state: Optional[str] = None
    # Audio file sent as multipart form data


class FollowupScheduleRequest(BaseModel):
    session_id: str
    patient_token: str
    followup_type: str          # "appointment" | "medication" | "symptom_check"
    scheduled_at: datetime
    contact_method: str         # "sms" | "voice" | "app"
    contact_info: str           # Anonymized — phone hash or token
```

### Response Models

```python
class TriageResponse(BaseModel):
    session_id: str
    triage_level: str
    triage_reasoning: str
    health_guidance: str
    rag_sources: list[str]
    recommended_facility: Optional[str]
    emergency_alert: Optional[str]
    followup_plan: dict
    disclaimer: str
    safety_passed: bool
    timestamp: str


class FacilityResponse(BaseModel):
    facilities: list[FacilityRecord]
    recommended: FacilityRecord
    search_location: str


class FacilityRecord(BaseModel):
    name: str
    type: str               # "PHC" | "CHC" | "Hospital" | "Sub-Centre"
    distance_km: Optional[float]
    address: str
    contact: Optional[str]
    services: list[str]
    lat: Optional[float]
    lon: Optional[float]
    source: str             # "nhm_tn" | "osm" | "google" | "user_upload"
    is_government: bool


class AuditLogResponse(BaseModel):
    session_id: str
    entries: list[AuditLogEntry]


class AuditLogEntry(BaseModel):
    id: int
    session_id: str
    agent_name: str
    triage_level: Optional[str]
    emergency_flag: bool
    safety_passed: bool
    blocked_reason: Optional[str]
    timestamp: str
```

---

## 3. Database Schema — SQLite / PostgreSQL

### Table: sessions

```sql
CREATE TABLE sessions (
    id              TEXT PRIMARY KEY,           -- UUID
    patient_token   TEXT NOT NULL,              -- Anonymized patient ID
    language        TEXT NOT NULL DEFAULT 'en',
    input_source    TEXT NOT NULL,              -- 'text' | 'voice'
    triage_level    TEXT,
    emergency_flag  BOOLEAN DEFAULT FALSE,
    safety_passed   BOOLEAN DEFAULT TRUE,
    status          TEXT DEFAULT 'active',      -- 'active' | 'completed' | 'escalated'
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_patient_token ON sessions(patient_token);
CREATE INDEX idx_sessions_triage_level ON sessions(triage_level);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
```

### Table: symptom_reports

```sql
CREATE TABLE symptom_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    patient_token   TEXT NOT NULL,
    chief_complaint TEXT,
    symptoms        TEXT,                       -- JSON array as string
    duration        TEXT,
    severity        TEXT,
    raw_input_hash  TEXT,                       -- SHA-256 of raw input, never raw text
    translated_hash TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: triage_results

```sql
CREATE TABLE triage_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    triage_level    TEXT NOT NULL,
    triage_reasoning TEXT,
    emergency_flag  BOOLEAN DEFAULT FALSE,
    rag_context     TEXT,                       -- Stored for audit (compressed)
    rag_sources     TEXT,                       -- JSON array
    health_guidance TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: audit_logs

```sql
CREATE TABLE audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    patient_token   TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    triage_level    TEXT,
    emergency_flag  BOOLEAN DEFAULT FALSE,
    input_hash      TEXT NOT NULL,             -- SHA-256, never raw
    output_hash     TEXT NOT NULL,
    safety_passed   BOOLEAN NOT NULL DEFAULT TRUE,
    blocked_reason  TEXT,
    rag_sources     TEXT,                      -- JSON
    llm_provider    TEXT,
    token_count     INTEGER,
    latency_ms      INTEGER,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_session ON audit_logs(session_id);
CREATE INDEX idx_audit_emergency ON audit_logs(emergency_flag) WHERE emergency_flag = TRUE;
CREATE INDEX idx_audit_safety ON audit_logs(safety_passed) WHERE safety_passed = FALSE;
```

### Table: followup_reminders

```sql
CREATE TABLE followup_reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    patient_token   TEXT NOT NULL,
    reminder_type   TEXT NOT NULL,             -- 'appointment' | 'medication' | 'symptom_check'
    reminder_text   TEXT NOT NULL,
    scheduled_at    DATETIME NOT NULL,
    sent_at         DATETIME,
    status          TEXT DEFAULT 'pending',    -- 'pending' | 'sent' | 'failed'
    contact_method  TEXT,                      -- 'sms' | 'voice' | 'app'
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: facility_cache

```sql
CREATE TABLE facility_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    facility_type   TEXT NOT NULL,             -- 'PHC' | 'CHC' | 'Hospital' | 'Sub-Centre'
    district        TEXT NOT NULL,
    state           TEXT NOT NULL,
    address         TEXT,
    contact         TEXT,
    lat             REAL,
    lon             REAL,
    services        TEXT,                      -- JSON array
    is_government   BOOLEAN DEFAULT TRUE,
    source          TEXT DEFAULT 'nhm_tn',     -- 'nhm_tn' | 'osm' | 'google' | 'user_upload'
    last_updated    TEXT                       -- YYYY-MM-DD string
);

CREATE INDEX idx_facility_district ON facility_cache(district, state);
```

**Note:** `facility_cache` has no UNIQUE constraint — the document processor uses a check-before-insert pattern (`SELECT id WHERE LOWER(TRIM(name))=... AND district=... AND state=...`) to avoid duplicates on repeated uploads.

**Seed data:** 87 Tamil Nadu hospitals across 38 districts seeded via `scripts/seed_tn_hospitals.py` with `source='nhm_tn'`.

### Table: knowledge_documents

```sql
CREATE TABLE knowledge_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    source          TEXT NOT NULL,             -- 'WHO' | 'NHM' | 'CDC' | 'user_upload'
    collection      TEXT NOT NULL,             -- ChromaDB collection name
    doc_type        TEXT,                      -- 'guideline' | 'protocol' | 'factsheet' | 'user_upload'
    language        TEXT DEFAULT 'en',
    loaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    chunk_count     INTEGER,
    chroma_ids      TEXT                       -- JSON array of ChromaDB doc IDs
);
```

---

## 4. ChromaDB Document Schema

Each document chunk stored in ChromaDB (embedding model: Ollama `nomic-embed-text`, ~768-dim):

```python
{
    "ids": ["doc_001_chunk_003"],
    "documents": ["The WHO recommends oral rehydration therapy (ORT) for..."],
    "metadatas": [
        {
            "source": "WHO_Diarrhea_Guidelines_2023",
            "collection": "who_health_guidelines",
            "doc_type": "guideline",
            "language": "en",
            "page": 3,
            "chunk_index": 3,
            "symptoms_tags": ["diarrhea", "dehydration", "vomiting"],
            "triage_relevance": "MODERATE"
        }
    ],
    "embeddings": [[0.123, 0.456, ...]]  # ~768-dim (nomic-embed-text)
}
```

**User upload metadata:**
```python
{
    "source": "uploaded_filename.pdf",
    "collection": "who_health_guidelines",
    "doc_type": "user_upload",
    "chunk_index": 0,
}
```

---

## 5. Follow-up Plan Schema

```python
class FollowupPlan(BaseModel):
    follow_up_in: str           # "24 hours" | "48 hours" | "3 days" | "1 week"
    watch_for: list[str]        # Symptoms that indicate worsening
    return_immediately_if: list[str]   # Emergency triggers
    home_care: list[str]        # What to do at home
    reminders: list[FollowupReminder]
    health_scheme_info: Optional[str]  # Relevant government scheme


class FollowupReminder(BaseModel):
    when: str                   # "tomorrow morning" | "in 3 days"
    action: str                 # "Check temperature" | "Visit PHC"
    priority: str               # "high" | "medium" | "low"
```

---

## 6. Audit Log Entry Schema (Python)

```python
class AuditLogEntryCreate(BaseModel):
    session_id: str
    patient_token: str
    agent_name: str
    triage_level: Optional[str]
    emergency_flag: bool = False
    input_text: str             # Hashed before storage — never stored raw
    output_text: str            # Hashed before storage — never stored raw
    safety_passed: bool = True
    blocked_reason: Optional[str] = None
    rag_sources: Optional[list[str]] = None
    llm_provider: Optional[str] = None
    token_count: Optional[int] = None
    latency_ms: Optional[int] = None

    def to_db_entry(self) -> dict:
        import hashlib, json
        return {
            "session_id":    self.session_id,
            "patient_token": self.patient_token,
            "agent_name":    self.agent_name,
            "triage_level":  self.triage_level,
            "emergency_flag": self.emergency_flag,
            "input_hash":    hashlib.sha256(self.input_text.encode()).hexdigest(),
            "output_hash":   hashlib.sha256(self.output_text.encode()).hexdigest(),
            "safety_passed": self.safety_passed,
            "blocked_reason": self.blocked_reason,
            "rag_sources":   json.dumps(self.rag_sources or []),
            "llm_provider":  self.llm_provider,
            "token_count":   self.token_count,
            "latency_ms":    self.latency_ms,
        }
```

---

## 7. Environment Configuration Model

```python
class AppConfig(BaseModel):
    # LLM — default is Ollama (local, no API key)
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embed_model: str = "nomic-embed-text"

    # Cloud LLM API keys (optional — used when llm_provider != "ollama")
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Voice
    whisper_model: str = "base"

    # ChromaDB — absolute path required on Windows
    chroma_db_path: str = "./data/chroma"

    # Database — absolute path required on Windows
    sqlite_path: str = "./data/ruralcare.db"
    database_url: Optional[str] = None         # PostgreSQL URL (production)

    # LangSmith (optional tracing)
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "ruralcare-ai"

    # Translation
    translate_provider: str = "google"

    # Maps
    maps_provider: str = "openstreetmap"
    google_maps_key: Optional[str] = None

    # App
    log_level: str = "INFO"
    demo_mode: bool = True
    max_input_length: int = 2000

    @classmethod
    @lru_cache(maxsize=1)
    def from_env(cls) -> "AppConfig":
        from dotenv import load_dotenv
        # __file__-anchored so .env is found regardless of working directory
        _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        load_dotenv(dotenv_path=os.path.join(_PROJECT_ROOT, ".env"))
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            # ...
        )
```

---

## 8. Document Processor Result Schema

Returned by `app/services/document_processor.py` after processing an uploaded file:

```python
# Hospital CSV/Excel result
{
    "ok":       True,
    "inserted": 3,       # New rows inserted into facility_cache
    "updated":  1,       # Existing rows updated (matched by name+district+state)
    "skipped":  0,       # Rows skipped (blank name/district or invalid facility_type)
    "errors":   [],      # Row-level error messages
    "total":    4,       # Total rows in uploaded file
}

# Medical knowledge PDF/TXT/MD result
{
    "ok":         True,
    "chunks":     24,    # Number of chunks added to ChromaDB
    "collection": "who_health_guidelines",
    "filename":   "fever_guidelines.pdf",
    "preview":    "Fever Management Guidelines (WHO)\n...",  # First 400 chars
}
```
