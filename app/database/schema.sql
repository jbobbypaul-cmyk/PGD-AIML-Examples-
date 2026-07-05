-- RuralCare AI — SQLite Schema
-- Compatible with PostgreSQL (same column names and types)

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    patient_token   TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    input_source    TEXT NOT NULL DEFAULT 'text',
    triage_level    TEXT,
    emergency_flag  INTEGER DEFAULT 0,
    safety_passed   INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'active',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_patient  ON sessions(patient_token);
CREATE INDEX IF NOT EXISTS idx_sessions_triage   ON sessions(triage_level);
CREATE INDEX IF NOT EXISTS idx_sessions_created  ON sessions(created_at);

-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS symptom_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    patient_token   TEXT NOT NULL,
    chief_complaint TEXT,
    symptoms        TEXT,           -- JSON array
    duration        TEXT,
    severity        TEXT,
    raw_input_hash  TEXT,           -- SHA-256 of raw input
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS triage_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    triage_level    TEXT NOT NULL,
    triage_reasoning TEXT,
    emergency_flag  INTEGER DEFAULT 0,
    rag_sources     TEXT,           -- JSON array
    health_guidance TEXT,
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    patient_token   TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    triage_level    TEXT,
    emergency_flag  INTEGER DEFAULT 0,
    input_hash      TEXT NOT NULL,  -- SHA-256 only — never raw text
    output_hash     TEXT NOT NULL,
    safety_passed   INTEGER NOT NULL DEFAULT 1,
    blocked_reason  TEXT,
    rag_sources     TEXT,           -- JSON array
    llm_provider    TEXT,
    token_count     INTEGER,
    latency_ms      INTEGER,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_session   ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_emergency ON audit_logs(emergency_flag);
CREATE INDEX IF NOT EXISTS idx_audit_safety    ON audit_logs(safety_passed);

-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS followup_reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    patient_token   TEXT NOT NULL,
    reminder_type   TEXT NOT NULL,  -- 'appointment' | 'medication' | 'symptom_check'
    reminder_text   TEXT NOT NULL,
    scheduled_at    TEXT NOT NULL,
    sent_at         TEXT,
    status          TEXT DEFAULT 'pending',
    contact_method  TEXT DEFAULT 'app',
    created_at      TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS facility_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    facility_type   TEXT NOT NULL,  -- 'PHC' | 'CHC' | 'Hospital' | 'Sub-Centre'
    district        TEXT NOT NULL,
    state           TEXT NOT NULL,
    address         TEXT,
    contact         TEXT,
    lat             REAL,
    lon             REAL,
    services        TEXT,           -- JSON array
    is_government   INTEGER DEFAULT 1,
    source          TEXT DEFAULT 'nhm_tn', -- 'nhm_tn' | 'osm' | 'google'
    last_updated    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_facility_location ON facility_cache(district, state);

-- ─────────────────────────────────────────────────────────────────────
-- Seed: Demo Facility Data
-- ─────────────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO facility_cache
    (id, name, facility_type, district, state, address, contact, lat, lon, services, is_government, last_updated)
VALUES
    (1, 'Dharmapuri District PHC', 'PHC', 'Dharmapuri', 'Tamil Nadu',
     'Main Road, Dharmapuri, TN 636701', '04342-123456',
     12.1211, 78.1580, '["OPD","Maternal Care","Immunization","Free Drugs"]', 1, '2026-01-01'),

    (2, 'Dharmapuri Community Health Centre', 'CHC', 'Dharmapuri', 'Tamil Nadu',
     'Hospital Road, Dharmapuri, TN 636701', '04342-234567',
     12.1289, 78.1601, '["OPD","Emergency","Surgery","Laboratory","Blood Bank"]', 1, '2026-01-01'),

    (3, 'Dharmapuri Government Hospital', 'Hospital', 'Dharmapuri', 'Tamil Nadu',
     'Collector Office Road, Dharmapuri, TN 636701', '04342-987654',
     12.1310, 78.1625, '["Emergency","ICU","Surgery","OPD","Maternity","Laboratory"]', 1, '2026-01-01'),

    (4, 'Krishnagiri PHC', 'PHC', 'Krishnagiri', 'Tamil Nadu',
     'NH-44, Krishnagiri, TN 635001', '04343-111222',
     12.5266, 78.2139, '["OPD","Immunization","Maternal Care"]', 1, '2026-01-01'),

    (5, 'Vellore Government Hospital', 'Hospital', 'Vellore', 'Tamil Nadu',
     'Adukkamparai, Vellore, TN 632001', '0416-222333',
     12.9165, 79.1325, '["Emergency","ICU","Surgery","OPD","Neurology","Cardiology"]', 1, '2026-01-01');
