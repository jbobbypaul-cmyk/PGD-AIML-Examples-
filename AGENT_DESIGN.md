# AGENT_DESIGN.md — RuralCare AI Agent Specifications

## Purpose

Define the role, inputs, outputs, behavior, tools, system prompt strategy, and boundaries for each of the 8 agents in the RuralCare AI system.

---

## Agent Topology

```
                        ┌─────────────────────┐
                        │  Patient Input       │
                        │  (Text / Voice)      │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │  1. Symptom Intake  │
                        │     Agent           │
                        └──────────┬──────────┘
                          ┌────────┴────────┐
                          │ Emergency check  │
                       YES│                 │NO
               ┌──────────▼──────┐          │
               │ 7. Emergency    │          │
               │ Escalation Agent│          │
               └──────────┬──────┘          │
                          │        ┌─────────▼──────────┐
                          │        │  2. Medical Triage  │
                          │        │     Agent           │
                          │        └─────────┬──────────┘
                          │                  │
                          │        ┌─────────▼──────────┐
                          │        │  3. Medical RAG     │
                          │        │     Agent           │
                          │        └─────────┬──────────┘
                          │                  │
                          │        ┌─────────▼──────────┐
                          │        │  4. Appt/Facility   │
                          │        │     Agent           │
                          │        └─────────┬──────────┘
                          │                  │
                          │        ┌─────────▼──────────┐
                          │        │  5. Follow-up &     │
                          │        │  Adherence Agent    │
                          │        └─────────┬──────────┘
                          │                  │
                          │        ┌─────────▼──────────┐
                          │        │  6. Health Worker   │
                          │        │  Support Agent      │
                          │        └─────────┬──────────┘
                          │                  │
                          └──────────────────┤
                                             │
                                   ┌─────────▼──────────┐
                                   │  8. Audit, Safety  │
                                   │  & Compliance Agent│
                                   └─────────┬──────────┘
                                             │
                                   ┌─────────▼──────────┐
                                   │   Response to User │
                                   └────────────────────┘
```

### Fail-Safe Wrapper

Every agent node is wrapped with `_node()` in the LangGraph orchestrator. This prevents a single agent failure from crashing the pipeline:

```python
def _node(fn):
    def wrapper(state):
        try:
            return fn(state)
        except Exception as exc:
            state.setdefault("errors", []).append(str(exc))
            return state   # safe partial state, pipeline continues
    return wrapper
```

---

## Agent 1: Symptom Intake Agent

### Role
Collect, clean, structure, and normalize patient-reported symptoms from free-form text or transcribed voice input.

### Inputs
- `raw_input` — Free-form patient description in any language (translated to English)
- `language` — Detected language code
- `patient_token` — Anonymized patient identifier (`PT-{8 hex chars}`)

### Outputs
- `symptoms` — List of structured symptom strings
- `chief_complaint` — Primary complaint in one sentence
- `symptom_duration` — Duration of symptoms
- `symptom_severity` — Self-reported severity (mild/moderate/severe)
- `emergency_flag` — Boolean: true if any red-flag keyword detected

### Tools
- Red-flag keyword detector (synchronous, rule-based — runs **before** any LLM call)
- LLM (symptom extraction prompt)

### System Prompt Strategy
```
You are a symptom intake assistant for a rural health information system.
Your role is ONLY to extract and structure symptoms from patient input.
Do NOT diagnose. Do NOT suggest treatments. Do NOT mention medicines.
Extract: chief complaint, symptom list, duration, severity.
Identify if any emergency keywords are present (see red-flag list).
Output as JSON.
```

### Red-Flag Keywords (Partial List)
chest pain, cannot breathe, difficulty breathing, unconscious, not waking up, severe bleeding,
blood vomiting, stroke, seizure, fitting, convulsion, poisoning, snake bite, drowning,
heart attack, paralysis, sudden weakness, sudden vision loss, severe headache sudden onset

### Boundaries
- Does NOT attempt to diagnose.
- Does NOT ask follow-up questions (single-turn MVP).
- Emergency check happens BEFORE any LLM call — purely rule-based for speed (< 100ms).

### Acceptance Criteria
- Extracts at least 3 symptoms from a 30-word patient description.
- Emergency flag triggers within 100ms (rule-based keyword scan).
- Output is valid JSON every time.
- PHI is anonymized before LLM call.

---

## Agent 2: Medical Triage Agent

### Role
Classify the urgency level of the patient's situation using structured symptoms and clinical triage heuristics.

### Triage Levels

| Level | Definition | Action |
|---|---|---|
| EMERGENCY | Life-threatening, requires immediate care | Alert + Emergency Escalation |
| URGENT | Serious, needs care within 2–4 hours | Recommend nearest facility urgently |
| MODERATE | Needs care within 24–48 hours | Schedule appointment, give guidance |
| MILD | Self-care with monitoring | Home care guidance, follow-up if worsens |

### Inputs
- `symptoms` — Structured symptom list from Symptom Intake Agent
- `chief_complaint`
- `symptom_duration`
- `symptom_severity`

### Outputs
- `triage_level` — One of: EMERGENCY / URGENT / MODERATE / MILD
- `triage_reasoning` — 2–3 sentence explanation

### Tools
- LLM (triage classification prompt with WHO ICD-11 triage principles)
- Rule-based override: if `emergency_flag=True`, output is always EMERGENCY regardless of LLM

### System Prompt Strategy
```
You are a triage classification assistant for a rural health information system.
Your role is ONLY to classify urgency level: EMERGENCY, URGENT, MODERATE, or MILD.
Use WHO-aligned triage principles.
Do NOT diagnose. Do NOT name diseases. Do NOT prescribe.
Base your classification only on the symptom list provided.
If you are uncertain, default to the higher urgency level (conservative triage).
Output: { triage_level: "...", reasoning: "..." }
```

### Boundaries
- Never names a specific disease diagnosis.
- If uncertain, always defaults to higher urgency (conservative bias).
- Emergency override is rule-based, not LLM-based — LLM cannot downgrade a red-flag.

---

## Agent 3: Medical Knowledge RAG Agent

### Role
Retrieve relevant evidence-based health information from the knowledge base and generate a grounded, patient-appropriate response.

### Inputs
- `chief_complaint`
- `symptoms`
- `triage_level`
- ChromaDB 6 collections (queried via LangChain retriever)

### Outputs
- `rag_context` — Retrieved document chunks (raw, assembled into LLM context)
- `rag_sources` — Document source citations
- `health_guidance` — Patient-appropriate health information in accessible language

### Tools
- ChromaDB cosine similarity retriever (`vectorstore.as_retriever`)
- Multi-collection sweep in priority order with deduplication
- LLM (RAG generation prompt — grounded on retrieved context only)

### Retrieval Strategy

```python
# Multi-collection priority order
QUERY_ORDER = [
    "emergency_protocols",       # Always first
    "symptom_disease_mapping",
    "who_health_guidelines",
    "nhm_india_protocols",
    "drug_information_basic",
    "regional_health_schemes",
]

# Retriever per collection
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5},
    # score_threshold=None — Ollama cosine scores are not normalised 0-1;
    # volume cap (k=5) used instead.
)
```

Results from all collections are concatenated, deduplicated by content hash, and assembled as the LLM context.

### System Prompt Strategy
```
You are a health information assistant. Your role is to explain health information
in simple, accessible language for rural patients.
Use ONLY the provided document context below to answer. Do not use outside knowledge.
Do NOT diagnose. Do NOT prescribe medicines.
If the context does not contain relevant information, say:
"I don't have specific information on this. Please consult your nearest health center."
Always end with the standard disclaimer.
Always cite your source documents.
```

### RAG Quality Rules
- `score_threshold=None` — Ollama embeddings produce scores not normalised to 0–1; use `k` cap instead.
- If no documents retrieved: return fallback ("please visit health center").
- Source citations mandatory in every response.
- Response reading level: Grade 6–8 equivalent.
- No MultiQueryRetriever — not compatible with Ollama local inference in current stack.

### Boundaries
- Only uses information from ChromaDB collections — never improvises medical facts.
- Does not mention drug brand names.
- Does not quantify drug dosages unless from NHM official documents.

---

## Agent 4: Appointment & Facility Agent

### Role
Locate nearby healthcare facilities appropriate for the patient's triage level and help them access care.

### Inputs
- `location` — Patient's district/state (or lat/lon if geocoded)
- `triage_level`
- Facility type preference (derived from triage level)

### Outputs
- `facilities` — List of up to 3 nearby facilities with name, type, contact, address, source, distance
- `recommended_facility` — Single best recommendation with contact, address, source label, and government scheme note
- `_fac_debug` — Internal debug trace list (shown in Streamlit as a caption for transparency)

### Tools

**3-Level Hybrid Lookup (in order):**

| Level | Source | Trigger | Notes |
|---|---|---|---|
| 1 | SQLite NHM TN static cache | Always (primary) | 87 hospitals across 38 Tamil Nadu districts; case-insensitive `LOWER(TRIM())` query |
| 2 | OpenStreetMap Overpass API | Level 1 returns empty | Free, no API key; results cached back to SQLite with `source='osm'` |
| 3 | Google Places API | Level 2 returns empty AND `GOOGLE_MAPS_KEY` set | Optional; results cached with `source='google'` |

**Source labels:**
```python
SOURCE_LABELS = {
    "nhm_tn":      "NHM Tamil Nadu",
    "osm":         "OpenStreetMap",
    "google":      "Google Places",
    "user_upload": "User Upload",   # hospitals added via document upload UI
}
```

User-uploaded hospitals (via Streamlit upload panel) are stored with `source='user_upload'` and are immediately searchable.

### Facility Type Mapping to Triage Level

| Triage Level | Preferred Facility Types |
|---|---|
| EMERGENCY | Hospital |
| URGENT | CHC, Hospital |
| MODERATE | PHC, CHC |
| MILD | Sub-Centre, PHC |

Government facilities (`is_government=1`) are sorted first for affordability.

### Implementation Note (Direct SQLite in Streamlit)

The Streamlit UI uses a direct `sqlite3.connect(config.sqlite_path)` call to query `facility_cache`. This bypasses the `get_facilities_by_district()` function and its `lru_cache` chain, which was found to return empty results on first call due to module-level caching behavior. The direct connection is the reliable path for UI-layer lookups.

### Boundaries
- Does not make appointments (MVP) — provides contact information only.
- Distance shown as approximate km — not real-time navigation.
- Government facilities always prioritized over private.

---

## Agent 5: Follow-up & Adherence Agent

### Role
Create a follow-up care plan and support medication adherence for the patient.

### When Generated
- **Generated for:** MODERATE, URGENT (and post-emergency to support health worker follow-up)
- **Not generated for:** pipeline failures with no health guidance; MILD cases with purely self-care recommendations may produce abbreviated plans

### Inputs
- `triage_level`
- `health_guidance` (from RAG agent)
- `recommended_facility`
- `patient_token`

### Outputs
- `followup_plan` — Structured follow-up schedule
- `medication_reminders` — List of reminder items (if applicable)
- `adherence_tips` — Simple adherence guidance in patient's language

### Follow-up Plan Structure
```json
{
  "follow_up_in": "24 hours / 48 hours / 1 week",
  "watch_for": ["worsening fever", "difficulty breathing"],
  "return_immediately_if": ["chest pain", "loss of consciousness"],
  "home_care": ["rest", "drink fluids", "monitor temperature"],
  "reminders": [
    {"when": "tomorrow morning", "action": "Check temperature"},
    {"when": "3 days", "action": "Visit PHC if not improved"}
  ]
}
```

### UI Display
Follow-up Plan is displayed as a **full-width 3-column bordered container** in the Streamlit UI, below the facility section. Each column shows: plan timing + watch-for items; home care tips; return-immediately triggers.

### Boundaries
- Does not prescribe medicines.
- Reminder content is health guidance only — not clinical instructions.
- Follow-up timing is guidance — not a clinical protocol.
- In production: Celery + Redis handles actual SMS/notification delivery.

---

## Agent 6: Health Worker Support Agent

### Role
Generate a concise, structured briefing note for ASHA/ANM/CHW health workers who will follow up with the patient in person.

### When Generated
- **Generated for:** all cases where health guidance was produced (MODERATE, URGENT, post-emergency).
- **Not generated for:** pipeline failures with no guidance output.

### Inputs
- Complete `PatientState` (post-triage, post-RAG, post-facility)

### Outputs
- `health_worker_briefing` — Structured briefing note (plain text, full length)

### Briefing Structure
```
PATIENT BRIEFING NOTE
---------------------
Token: PT-xxxxxxxx
Date: [timestamp]
Chief Complaint: [chief complaint]
Triage Level: [EMERGENCY / URGENT / MODERATE / MILD]
Key Symptoms: [list]
Duration: [duration]

RAG-Grounded Guidance Summary:
[2-3 sentence summary for health worker]

Recommended Action:
[specific action for ASHA/ANM]

Watch For:
[red flags to monitor]

Health Schemes to Inform:
[e.g., PM-JAY, JSSK, NTEP, National Iron Plus Initiative]

Follow-up Due: [date/time]
```

### UI Display
Health Worker Briefing is displayed as a **separate full-width section** in the Streamlit UI, positioned after the Follow-up Plan. It uses `st.text()` (not `st.code()`) inside `st.container(border=True)` to show the complete text without scroll-height truncation.

### Boundaries
- Briefing is for trained health workers — can use clinical language.
- Still does not suggest diagnoses — health worker makes clinical judgment.
- Includes relevant government health scheme information for the patient's context.

---

## Agent 7: Emergency Escalation Agent

### Role
When a life-threatening emergency is detected, immediately surface emergency information and alert pathways before any other response.

### Inputs
- `emergency_flag` — True
- `symptoms`
- `chief_complaint`
- `location`

### Outputs
- Emergency alert message (patient-facing, shown immediately)
- Emergency contact numbers (112, 108)
- First aid guidance (from `emergency_protocols` ChromaDB collection, top-3 chunks)
- Alert notification (webhook/SMS — production only)

### Emergency Response Template
```
🚨 EMERGENCY ALERT 🚨

Based on your reported symptoms, you may need IMMEDIATE medical attention.

CALL EMERGENCY SERVICES NOW:
• National Emergency: 112
• Ambulance: 108
• Nearest Hospital: [facility from location data]

While waiting:
[First aid guidance from emergency_protocols RAG collection]

Do NOT wait. Seek immediate care.

[Disclaimer]
```

### Escalation Path
```
Emergency detected → Emergency Escalation Agent runs FIRST
                   → Patient sees emergency alert immediately
                   → Webhook/SMS alert sent to health worker (production)
                   → Audit log entry with EMERGENCY flag
                   → Other agents still run for health worker briefing
```

### Boundaries
- Always runs before other agents when `emergency_flag=True`.
- First aid guidance is RAG-grounded from `emergency_protocols` collection only.
- Never delays showing emergency contact numbers.

---

## Agent 8: Audit, Safety & Compliance Agent

### Role
Run final safety validation on all agent outputs, enforce disclaimers, write the audit log, and assemble the final patient response.

### Inputs
- Complete `PatientState` with all agent outputs

### Safety Checks Performed
1. Scan for disease diagnosis patterns (regex) → block if found.
2. Scan for prescription/medication dosage recommendations (regex) → block if found.
3. Verify disclaimer is present → inject if missing.
4. Verify RAG sources are cited → inject "source: general guidance" if missing.
5. Verify triage level is present in response.
6. PII scan — no names, phone numbers, or identifiers in final response.

### Outputs
- `final_response` — Validated, disclaimer-stamped patient response
- `safety_passed` — Boolean
- Audit log entry written to SQLite `audit_logs` table

### Audit Log Schema
```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    patient_token TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    triage_level TEXT,
    emergency_flag BOOLEAN,
    agent_name TEXT,
    input_hash TEXT,      -- SHA-256 of input (never raw text)
    output_hash TEXT,     -- SHA-256 of output (never raw text)
    safety_passed BOOLEAN,
    blocked_reason TEXT,
    rag_sources TEXT,
    latency_ms INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Standard Disclaimer
```
⚠️ DISCLAIMER: This information is for general health awareness only.
RuralCare AI is NOT a doctor and cannot diagnose or prescribe.
Always consult a qualified healthcare professional for medical advice.
In an emergency, call 112 immediately.
```

### Boundaries
- Final check is synchronous and mandatory — no response bypasses the audit agent.
- If safety check fails, a safe fallback message is returned instead of the blocked output.
- Audit log entry is written even if the pipeline fails midway.
- Audit log is **not shown in the Streamlit patient UI** — accessible via the FastAPI `/api/v1/audit` endpoint for administrative review only.
