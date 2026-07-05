# WORKFLOW.md — RuralCare AI End-to-End Workflow

## Purpose

Document the complete interaction workflow from patient input to final response, covering all decision points, agent handoffs, data transformations, and output assembly.

---

## Workflow Overview

```
PATIENT ENTRY POINT
        │
        ├─── Text Input ────────────────────────────────────────────────┐
        │                                                               │
        └─── Voice Upload (.wav/.mp3) → Whisper STT → Transcribed Text─┘
                                                                        │
                                               ┌────────────────────────▼─────┐
                                               │   Language Detection          │
                                               │   (langdetect)                │
                                               └────────────────────────┬─────┘
                                                                        │
                                               ┌────────────────────────▼─────┐
                                               │   Translation to English      │
                                               │   (Google Translate)          │
                                               └────────────────────────┬─────┘
                                                                        │
                                               ┌────────────────────────▼─────┐
                                               │   PHI Anonymization           │
                                               │   Patient Token Assignment    │
                                               │   PT-{uuid4.hex[:8]}          │
                                               └────────────────────────┬─────┘
                                                                        │
                                         ┌──────────────────────────────▼─────┐
                                         │         LangGraph Orchestrator       │
                                         │   (8 nodes, fail-safe _node wrapper) │
                                         │                                      │
                                         │  ┌──────────────────────────────┐   │
                                         │  │   STEP 1: Emergency Check    │   │
                                         │  │   (Rule-based, pre-LLM)      │   │
                                         │  └──────────────┬───────────────┘   │
                                         │         YES     │    NO              │
                                         │  ┌──────────────▼──┐    │           │
                                         │  │  EMERGENCY       │    │           │
                                         │  │  ESCALATION      │    │           │
                                         │  │  AGENT           │    │           │
                                         │  └──────────────────┘    │           │
                                         │                           │           │
                                         │  ┌────────────────────────▼──────┐  │
                                         │  │   STEP 2: Symptom Intake Agent│  │
                                         │  │   Extract & structure symptoms │  │
                                         │  └────────────────────────┬──────┘  │
                                         │                            │         │
                                         │  ┌─────────────────────────▼──────┐ │
                                         │  │   STEP 3: Medical Triage Agent │ │
                                         │  │   Classify: E/U/M/MILD         │ │
                                         │  └─────────────────────────┬──────┘ │
                                         │                             │        │
                                         │  ┌──────────────────────────▼─────┐ │
                                         │  │   STEP 4: Medical RAG Agent    │ │
                                         │  │   Multi-collection cosine sweep│ │
                                         │  └──────────────────────────┬─────┘ │
                                         │                              │       │
                                         │  ┌───────────────────────────▼────┐ │
                                         │  │   STEP 5: Appointment &        │ │
                                         │  │   Facility Agent (3-level)     │ │
                                         │  └───────────────────────────┬────┘ │
                                         │                               │      │
                                         │  ┌────────────────────────────▼───┐ │
                                         │  │   STEP 6: Follow-up &          │ │
                                         │  │   Adherence Agent              │ │
                                         │  └────────────────────────────┬───┘ │
                                         │                                │     │
                                         │  ┌─────────────────────────────▼──┐ │
                                         │  │   STEP 7: Health Worker        │ │
                                         │  │   Support Agent                │ │
                                         │  └─────────────────────────────┬──┘ │
                                         │                                 │    │
                                         │  ┌──────────────────────────────▼─┐ │
                                         │  │   STEP 8: Audit, Safety &      │ │
                                         │  │   Compliance Agent             │ │
                                         │  └──────────────────────────────┬─┘ │
                                         └─────────────────────────────────┼───┘
                                                                           │
                                         ┌─────────────────────────────────▼──┐
                                         │   Response Assembly                 │
                                         │   (Translation back to patient lang)│
                                         └─────────────────────────────────┬──┘
                                                                           │
                                         ┌─────────────────────────────────▼──┐
                                         │   Patient-Facing Response           │
                                         │   (Streamlit UI / API Response)     │
                                         └─────────────────────────────────────┘
```

---

## Step-by-Step Workflow Detail

### Pre-Processing Phase

#### Step P1: Input Capture
```
IF voice_file uploaded:
    → Whisper.transcribe(audio) → raw_text
    (Whisper runs locally — no audio sent externally)
ELSE:
    → raw_text = user_text_input

max_length check: if len(raw_text) > 2000: truncate + warn user
```

#### Step P2: Language Detection & Translation
```
detected_lang = langdetect.detect(raw_text)
state.language = detected_lang

IF detected_lang != "en":
    state.translated_input = google_translate(raw_text, src=detected_lang, dest="en")
ELSE:
    state.translated_input = raw_text
```

#### Step P3: Session Initialization
```
state.session_id  = str(uuid4())
state.patient_token = f"PT-{uuid4().hex[:8]}"   # anonymized token
state.timestamp   = datetime.utcnow().isoformat()
state.audit_log   = []
```

---

### Agent Phase — LangGraph Execution

#### Step A0: Emergency Check (synchronous, pre-LLM)
```
emergency_flag = detect_emergency(state.translated_input)
# Pure keyword scan — < 100ms

IF emergency_flag:
    state.emergency_flag = True
    state.triage_level   = "EMERGENCY"
    → ROUTE to Emergency Escalation Agent

ELSE:
    state.emergency_flag = False
    → ROUTE to Symptom Intake Agent
```

---

#### Step A1: Symptom Intake Agent
**Input:** `state.translated_input`, `state.patient_token`

**LLM Prompt:**
```
System: Extract symptoms from patient input. Output JSON only. Do NOT diagnose.
        Fields: chief_complaint, symptoms (list), duration, severity (mild/moderate/severe)
Human:  Patient says: "{translated_input}"
```

**Output updates to state:**
```python
state.symptoms         = ["fever", "headache", "body aches", "chills"]
state.chief_complaint  = "Fever with headache for 3 days"
state.symptom_duration = "3 days"
state.symptom_severity = "moderate"
```

Audit entry written.

---

#### Step A2: Medical Triage Agent
**Input:** `state.symptoms`, `state.chief_complaint`, `state.symptom_duration`, `state.symptom_severity`

**LLM Prompt:**
```
System: Classify urgency: EMERGENCY, URGENT, MODERATE, MILD.
        Use WHO triage principles. Do NOT diagnose. Output JSON.
        If uncertain, default to higher urgency.
Human:  Chief complaint: {chief_complaint}
        Symptoms: {symptoms}
        Duration: {duration}, Severity: {severity}
```

**Output updates to state:**
```python
state.triage_level   = "MODERATE"
state.triage_reasoning = "Fever with headache lasting 3 days with moderate severity requires medical evaluation within 24-48 hours."
```

Audit entry written.

---

#### Step A3: Medical RAG Agent
**Input:** `state.chief_complaint`, `state.symptoms`, `state.triage_level`

**RAG Query:**
```python
rag_query = f"{chief_complaint}: {', '.join(symptoms)}"
```

**Collections queried (multi-collection sweep, priority order):**
1. `emergency_protocols` — always first
2. `symptom_disease_mapping`
3. `who_health_guidelines`
4. `nhm_india_protocols`
5. `drug_information_basic`
6. `regional_health_schemes`

**Retriever config:**
```python
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5},
    # score_threshold=None — Ollama cosine scores not normalised 0-1
)
```

Results deduplicated by content hash before LLM context assembly.

**LLM Prompt:**
```
System: [RAG system prompt — use ONLY provided context, no outside knowledge]
        CONTEXT: {retrieved_chunks}
Human:  {rag_query}
```

**Output updates to state:**
```python
state.rag_context     = "Retrieved chunk text..."
state.rag_sources     = ["WHO_Fever_Guidelines_2023", "NHM_ASHA_Module_3"]
state.health_guidance = "Fever lasting more than 3 days with headache and body aches may need medical evaluation..."
```

Audit entry written.

---

#### Step A4: Appointment & Facility Agent
**Input:** `state.location` (district, state), `state.triage_level`

**3-Level Hybrid Lookup:**
```python
# Level 1: SQLite NHM TN — case-insensitive
rows = conn.execute(
    "SELECT * FROM facility_cache "
    "WHERE LOWER(TRIM(district))=LOWER(TRIM(?)) "
    "  AND LOWER(TRIM(state))=LOWER(TRIM(?)) "
    "ORDER BY is_government DESC",
    (district, state),
).fetchall()

# Level 2: OpenStreetMap Overpass (if Level 1 empty)
if not rows:
    coords = geocode_district(district, state)
    rows = find_healthcare_facilities(lat, lon)

# Level 3: Google Places (if Level 2 empty + key set)
if not rows and config.google_maps_key:
    rows = google_places_nearby(lat, lon, config.google_maps_key)
```

**Output updates to state:**
```python
state.facilities = [
    {"name": "Salem Government Hospital", "facility_type": "Hospital",
     "contact": "04427123456", "source": "nhm_tn", "is_government": True, ...},
    ...
]
state.recommended_facility = (
    "Salem Government Hospital (Hospital)\n"
    "Address: Salem Town\n"
    "Contact: 04427123456\n"
    "Source: NHM Tamil Nadu\n"
    "You may be eligible for free treatment under Ayushman Bharat / PM-JAY."
)
state._fac_debug = [
    "district='Salem' state='Tamil Nadu' triage=MODERATE",
    "Level1 DB query returned 5 rows",
    "Level1 after type filter: 2 rows (preferred=['PHC', 'CHC'])",
]
```

Audit entry written.

---

#### Step A5: Follow-up & Adherence Agent
**Input:** `state.triage_level`, `state.health_guidance`

```python
state.followup_plan = {
    "follow_up_in": "48 hours",
    "watch_for": ["worsening fever", "difficulty breathing"],
    "return_immediately_if": ["chest pain", "loss of consciousness"],
    "home_care": ["rest", "drink fluids", "monitor temperature"],
    "reminders": [...]
}
```

Audit entry written.

---

#### Step A6: Health Worker Support Agent
**Input:** Complete state

```python
state.health_worker_briefing = """
PATIENT BRIEFING NOTE
Token: PT-a3f8b2c1 | Date: 2026-07-04
Triage: MODERATE | Chief Complaint: Fever with headache 3 days
...
"""
```

Audit entry written.

---

#### Step A7: Audit, Safety & Compliance Agent
**Input:** Complete state with all agent outputs

```python
check = run_safety_filter(state.health_guidance + state.final_response)

if not check.passed:
    state.final_response = check.output   # safe fallback
    state.safety_passed  = False
    state.blocked_reason = check.blocked_reason
else:
    state.safety_passed = True
    state.final_response = assemble_response(state)
    state.disclaimer     = STANDARD_DISCLAIMER

write_audit_log(state)   # SHA-256 hashes only — no raw text
```

Audit entry written (final, comprehensive).

---

### Post-Processing Phase

#### Step R1: Response Translation
```python
if state.language != "en":
    state.final_response = translate(
        state.final_response,
        src="en",
        dest=state.language,
    )
```

#### Step R2: Response Delivery

**Streamlit UI (actual layout):**
```python
# Triage metric
st.metric("Triage Level", state["triage_level"])

# Emergency alert (if applicable)
if state.get("emergency_flag"):
    st.error(state["emergency_alert"])

# Health guidance
st.subheader("Health Guidance")
st.write(state["health_guidance"])

# Facility debug caption
st.caption(f"Searched: {district}, {state_name} — {n} records found")

# Facility cards (top 3, each in st.container(border=True))
for facility in state["facilities"][:3]:
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        ...

# Follow-up Plan (full-width 3-column bordered container)
if state.get("followup_plan"):
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        ...

# Health Worker Briefing (separate full-width section)
if state.get("health_worker_briefing"):
    st.subheader("Health Worker Briefing")
    with st.container(border=True):
        st.text(state["health_worker_briefing"])  # st.text(), NOT st.code()

# RAG sources
with st.expander("Source Documents"):
    for src in state["rag_sources"]:
        st.caption(f"[source] {src}")

# Disclaimer
st.caption(state["disclaimer"])

# NOTE: Audit log is NOT shown in the patient UI.
# It is accessible via the FastAPI /api/v1/audit endpoint.
```

**API (FastAPI):**
```python
return TriageResponse(
    session_id=state["session_id"],
    triage_level=state["triage_level"],
    health_guidance=state["health_guidance"],
    recommended_facility=state["recommended_facility"],
    followup_plan=state["followup_plan"],
    disclaimer=state["disclaimer"],
    safety_passed=state["safety_passed"],
    ...
)
```

---

## Emergency Workflow (Accelerated Path)

```
Emergency detected (keyword scan, < 100ms)
    │
    ▼
Emergency Escalation Agent (< 1 second total)
    │
    ├── Retrieve first aid guidance (emergency_protocols collection, top-3 chunks)
    │
    ├── Generate emergency response:
    │   - Emergency alert header
    │   - Call 112 / 108 instruction
    │   - Nearest facility (from cache if location provided)
    │   - First aid guidance (RAG)
    │   - Disclaimer
    │
    ├── Write EMERGENCY audit log entry
    │
    ├── Send webhook/SMS alert (production only)
    │
    └── Return emergency response to patient IMMEDIATELY
        (Other agents continue in background for health worker briefing)
```

---

## Document Upload Workflow

```
User opens "Upload Document" expander in Streamlit
    │
    ├─── Tab 1: Hospital List (CSV / Excel)
    │       → file_bytes, filename → process_hospital_file()
    │       → pandas parse → column validation
    │       → check-before-insert (LOWER(TRIM()) match)
    │       → INSERT or UPDATE facility_cache
    │       → "Inserted 3, updated 1, skipped 0" result shown in UI
    │       → Immediately queryable in facility lookup
    │
    └─── Tab 2: Medical Knowledge (PDF / TXT / MD)
            → file_bytes, filename, collection_name → process_knowledge_document()
            → PDF: pypdf.PdfReader → text; fallback: PyPDFLoader temp file
            → TXT/MD: decode UTF-8
            → chunk_text() (512-char, 64-char overlap)
            → LangChain Document objects with metadata
            → get_vectorstore(collection_name).add_documents(docs)
            → "24 chunks added to who_health_guidelines" result shown in UI
            → Immediately retrievable in RAG pipeline
```

---

## Error Handling Workflow

```
LLM Call Fails
    │
    ├── _node fail-safe wrapper catches exception
    ├── error appended to state.errors list
    ├── pipeline continues with partial state
    └── Audit agent returns safe fallback message

ChromaDB Query Fails
    │
    ├── Exception caught in retrieve_multi_collection()
    ├── That collection skipped (others still queried)
    ├── If all collections fail: health_guidance = general fallback
    └── Log to audit with note

Translation Fails
    │
    ├── Proceed in English
    └── Add note: "Response provided in English as translation is unavailable."
```

---

## Timing Budget

| Step | Target Latency |
|---|---|
| Emergency keyword check | < 100ms |
| Language detection | < 200ms |
| Translation (Google API) | < 800ms |
| Symptom extraction (Ollama LLM) | < 3,000ms |
| Triage classification (Ollama LLM) | < 2,000ms |
| RAG retrieval (ChromaDB local) | < 500ms |
| RAG generation (Ollama LLM) | < 3,000ms |
| Facility search (SQLite cache) | < 200ms |
| Follow-up plan generation | < 500ms |
| Safety filter | < 100ms |
| Translation back | < 800ms |
| **Total (normal path, Ollama local)** | **< 12 seconds** |
| **Total (emergency path)** | **< 2,000ms** |
| **Total (cloud LLM — Claude/GPT-4o)** | **< 8 seconds** |

---

## Demo Workflow (Streamlit)

```
User selects Quick Demo button (5 pre-loaded scenarios)
    → st.session_state.symptoms_textarea = text
    → st.session_state.symptoms_input    = text
    → st.rerun()
    → Symptom text area pre-populated

OR

User types symptoms in text area
    → Optionally selects language and input mode in sidebar
    → Enters district + state for facility lookup
    → Clicks "Get Health Guidance"
    → Spinner shows while pipeline runs (LangGraph)
    → Results displayed:
        1. Triage Level (metric widget)
        2. Emergency Alert (if applicable)
        3. Health Guidance (RAG-grounded text)
        4. Facility debug caption
        5. Facility cards (top 3, government first)
        6. Follow-up Plan (3-column bordered container)
        7. Health Worker Briefing (full-width st.text)
        8. Source Documents (expander)
        9. Disclaimer (caption)

OR

User opens "Upload Document" expander
    → Uploads CSV/Excel for hospitals OR PDF/TXT for medical knowledge
    → Immediate confirmation with row/chunk counts
```
