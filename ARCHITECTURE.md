# ARCHITECTURE.md — RuralCare AI System Architecture

## Purpose

Document the complete system architecture of RuralCare AI, including all components, data flows, agent topology, RAG pipeline, chunking strategy, retrieval logic, token strategy, AI guardrail principles, FastAPI design, and infrastructure layers.

---

## System Overview

RuralCare AI is a **multi-agent, RAG-augmented healthcare assistant** built on LangGraph. The architecture follows a layered design:

1. **Presentation Layer** — Streamlit UI + FastAPI REST
2. **Orchestration Layer** — LangGraph state machine
3. **Agent Layer** — 8 specialised agents
4. **Knowledge Layer** — ChromaDB + verified health documents
5. **Data Layer** — SQLite (demo) / PostgreSQL (production)
6. **Infrastructure Layer** — Docker + cloud deployment

---

## High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                            │
│                                                                      │
│   ┌──────────────────┐          ┌──────────────────────────────┐    │
│   │  Streamlit UI    │          │  FastAPI REST API            │    │
│   │  (Demo Frontend) │          │  localhost:8000/docs         │    │
│   └────────┬─────────┘          └──────────────┬───────────────┘    │
│            │ Text / Voice Upload               │ JSON Requests       │
└────────────┼───────────────────────────────────┼────────────────────┘
             │                                   │
             ▼                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   VOICE & TRANSLATION MIDDLEWARE                     │
│                                                                      │
│   ┌─────────────────┐        ┌──────────────────────────────┐       │
│   │ Whisper STT     │        │ Google Translate / LangDetect │       │
│   │ (.wav/.mp3 in)  │        │ (→ English for LLM processing)│       │
│   └────────┬────────┘        └──────────────┬───────────────��       │
└────────────┼────────────────────────────────┼────────────────────────┘
             │ Transcribed Text               │ Translated Text
             ▼                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                             │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                  LangGraph State Machine                      │  │
│   │                                                               │  │
│   │  START ──[emergency keyword?]──► emergency_escalation         │  │
│   │    │                                    │                     │  │
│   │    └──[normal]──► symptom_intake         │                    │  │
│   │                       │                 │                     │  │
│   │                  medical_triage          │                    │  │
│   │                  ├─[EMERGENCY]──► emergency_escalation        │  │
│   │                  └─[continue]──► rag_agent                    │  │
│   │                                     │                         │  │
│   │                           appointment_facility                │  │
│   │                                     │                         │  │
│   │                           followup_adherence                  │  │
│   │                                     │                         │  │
│   │                           health_worker_support               │  │
│   │                                     │  ◄──────────────────────┘  │
│   │                           audit_safety ──► END                │  │
│   └──────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph State Machine Design

### State Schema (dict-based, Python 3.10+)

```python
{
    # Session identity
    "session_id":      str,   # UUID4
    "patient_token":   str,   # PT-{8 hex chars} — anonymised, used in LLM prompts
    "language":        str,   # ISO 639-1 code e.g. "en", "ta", "hi"
    "timestamp":       str,   # UTC ISO 8601

    # Input
    "raw_input":        str,  # Original patient text (never sent to LLM)
    "translated_input": str,  # English translation for LLM processing

    # Symptom processing
    "symptoms":          list[str],
    "chief_complaint":   str,
    "symptom_duration":  str,
    "symptom_severity":  str,

    # Triage
    "triage_level":    str,   # "EMERGENCY" | "URGENT" | "MODERATE" | "MILD"
    "triage_reasoning": str,
    "emergency_flag":  bool,

    # RAG
    "rag_context":          str,       # Retrieved document chunks
    "rag_sources":          list[str], # Source citations
    "health_guidance":      str,       # Final patient-facing guidance
    "grounding_confidence": str,       # "high" | "medium" | "none"

    # Facility
    "location":              dict,        # {district, state, lat, lon}
    "facilities":            list[dict],  # Matched facility records
    "recommended_facility":  str,

    # Follow-up
    "followup_plan":  dict,  # {follow_up_in, watch_for, return_immediately_if, home_care}

    # Health worker
    "health_worker_briefing": str,

    # Safety
    "safety_passed":   bool,
    "blocked_reason":  str | None,
    "disclaimer":      str,

    # Output
    "final_response":  str,
    "audit_log":       list[dict],  # One entry appended per agent
    "error":           str | None,
}
```

### Graph Routing Logic

```python
# Pre-LLM emergency check — purely rule-based, runs in < 100ms
def _route_from_start(state) -> str:
    return "emergency" if detect_emergency(state["translated_input"]) else "normal"

# Post-triage escalation check
def _route_after_triage(state) -> str:
    return "escalate" if state["triage_level"] == "EMERGENCY" else "continue"
```

### Safe Node Wrapper

Every agent is wrapped so an unhandled exception never crashes the pipeline:

```python
def _node(fn, llm=None):
    def _inner(state):
        try:
            return fn(state, llm) if llm else fn(state)
        except Exception as exc:
            logger.error("Agent '%s' raised: %s", fn.__name__, exc)
            state["audit_log"].append({"agent_name": fn.__name__, "error": str(exc)})
            return state   # degraded state — pipeline continues
    return _inner
```

---

## Agent Layer

### Agent Responsibility Map

| # | Agent | LLM Required | Runs in Emergency | Pattern |
|---|---|---|---|---|
| 1 | Symptom Intake | Yes | Skipped | Rule-first → LLM extraction |
| 2 | Medical Triage | Yes | Skipped | Conservative default (invalid → URGENT) |
| 3 | Medical RAG | Yes | Skipped | RAG-grounded, context-only |
| 4 | Appointment & Facility | No | Skipped | 3-level hybrid DB lookup |
| 5 | Follow-up & Adherence | No | Skipped | Rule-based, lookup table |
| 6 | Health Worker Support | No | Skipped | Template-based briefing |
| 7 | Emergency Escalation | No (RAG optional) | **Always** | Static first aid + RAG fast path |
| 8 | Audit & Safety | No | **Always** | Mandatory terminal gate |

### Triage Levels

| Level | Urgency | Facility Target | Follow-up |
|---|---|---|---|
| EMERGENCY | Life-threatening | District Hospital Emergency | After emergency care |
| URGENT | Serious < 4 hours | CHC or Hospital | 6 hours |
| MODERATE | Needs care < 48 hours | PHC or CHC | 2 days |
| MILD | Self-care + monitoring | Sub-Centre or PHC | 4 days |

---

## FastAPI REST API

### Overview

File: `app/main.py`
Run: `uvicorn app.main:app --reload --port 8000`
Docs: http://localhost:8000/docs (Swagger UI), http://localhost:8000/redoc

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `POST` | `/api/v1/intake` | Submit symptoms as text — runs full LangGraph pipeline |
| `POST` | `/api/v1/voice` | Upload `.wav/.mp3/.ogg` — Whisper transcribes, then pipeline |
| `GET` | `/api/v1/facilities` | Facility lookup by district + state + triage level |
| `GET` | `/api/v1/audit/{session_id}` | Retrieve audit log for a session |
| `GET` | `/api/v1/audit` | List recent audit entries (default last 20) |
| `POST` | `/api/v1/followup` | Manually schedule a follow-up reminder |

### Key Design Decisions

- **Lifespan context manager** — `init_db()` and `init_vector_store()` run once at startup
- **CORS** — `allow_origins=["*"]` for demo; restrict to known origins in production
- **Shared pipeline** — `POST /api/v1/intake` and the Streamlit UI call the same `run_pipeline()` function
- **Voice validation** — audio files validated by extension and capped at 10 MB before transcription
- **No async pipeline** — `run_pipeline()` is synchronous; FastAPI runs it in a thread pool automatically
- **Input sanitisation** — minimum 5 characters, maximum `MAX_INPUT_LENGTH` (default 2000) characters

### `/api/v1/intake` Request Parameters

```
symptoms_text       string  (required)   Patient symptom description
language            string  (default: en) ISO 639-1 language code
location_district   string  (optional)   District name for facility lookup
location_state      string  (optional)   State name for facility lookup
```

### Response Shape (all endpoints that call the pipeline)

```json
{
  "session_id": "uuid",
  "patient_token": "PT-a3f2c1b0",
  "triage_level": "MODERATE",
  "triage_reasoning": "...",
  "health_guidance": "...",
  "rag_sources": ["who_fever_management.pdf"],
  "recommended_facility": "...",
  "facilities": [...],
  "followup_plan": { "follow_up_in": "2 days", ... },
  "health_worker_briefing": "...",
  "emergency_flag": false,
  "emergency_alert": "",
  "safety_passed": true,
  "final_response": "...",
  "disclaimer": "..."
}
```

---

## Token and Privacy Strategy

### Patient Token

Every session generates an anonymous `patient_token` at pipeline start:

```python
state["patient_token"] = f"PT-{uuid4().hex[:8]}"   # e.g. PT-a3f92c1d
```

- Real patient names, phone numbers, and Aadhaar numbers **never enter any LLM prompt**
- The token is the only patient identifier used in LLM calls, audit logs, and follow-up reminders
- Tokens are not reversible — there is no mapping table from token to real identity in this system

### Input Hashing (Audit Log)

Raw text is never stored. Every audit entry stores only SHA-256 hashes:

```python
def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# In every agent's audit entry:
"input_hash":  hash_text(chief_complaint),
"output_hash": hash_text(health_guidance),
```

### PHI Scrubbing (Safety Filter)

Before any response reaches the patient, the safety filter scans and redacts:

```python
PHI_PATTERNS = [
    r"\b\d{10}\b",    # 10-digit phone numbers
    r"\b\d{12}\b",    # 12-digit Aadhaar numbers
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # Email addresses
]
# Matches replaced with [REDACTED]
```

### LLM Prompt Anonymisation

All LangGraph agents that call the LLM use only the anonymised token and structured clinical fields — never raw patient text:

```
Patient token   : PT-a3f92c1d
Chief complaint : fever and body aches
Duration        : 3 days
Severity        : moderate
Symptoms        : fever, headache, fatigue
Triage level    : MODERATE
```

---

## AI Guardrail Principles

Seven safety principles are enforced by code, not by instruction alone.

### 1. Non-Maleficence — Do No Harm

The LLM is prohibited from diagnosing (system prompt) **and** independently checked by a regex safety filter after every response. If either layer catches a violation, the output is replaced with a safe fallback — the patient never receives a partially harmful response.

### 2. Bounded Scope — Know What You Are Not

The system enforces its own limits technically:
- The disclaimer is appended by `audit_safety_agent` in code — the LLM cannot omit it
- When RAG returns no documents, a fixed safe fallback is shown — the LLM is not asked to improvise
- The RAG system prompt: *"If the context does not address the question, say exactly: I don't have specific information on this"*

### 3. Grounding — No Medical Hallucination

Every patient-facing health statement must come from a retrieved source document:
- LLM is given retrieved chunks and instructed to use **only those**
- `rag_sources` tracks citations of the actual documents used
- `grounding_confidence` is recorded (`high` ≥3 docs, `medium` 1–2 docs, `none` 0 docs)
- Zero-doc fallback: safe message shown, LLM not invoked for medical content

### 4. Proportionality — Response Severity Matches Clinical Urgency

- MILD/MODERATE/URGENT: LLM generates grounded guidance + follow-up plan
- EMERGENCY: LLM is bypassed entirely; hardcoded first-aid instructions are shown with emergency numbers (112, 108) — LLM latency and potential error are unacceptable in life-threatening situations

### 5. Privacy by Design — PHI Never in the Clear

- `patient_token` used in all LLM calls instead of real name
- Raw text hashed before audit log storage
- PHI scrubbed from LLM output before it reaches the patient
- Audio files processed locally by Whisper — never sent to external APIs

### 6. Auditability — Every Decision is Traceable

- `audit_safety_agent` is the terminal node of every pipeline path — it always runs
- Every agent appends its own audit entry (agent name, input hash, output hash, latency, safety result)
- Emergency events flagged separately
- Accessible via `GET /api/v1/audit/{session_id}`

### 7. Fail Safe — Errors Default to Safety, Not Silence

| Failure | Safe Outcome |
|---|---|
| Agent exception | `_node` wrapper catches it, pipeline continues with remaining agents |
| RAG returns 0 docs | Fallback message shown; LLM not asked to improvise |
| Safety filter blocks output | Standard safe fallback shown; patient not left without response |
| Emergency webhook fails | Logged as error; does not crash the pipeline |
| No district entered | Clear instruction shown; no crash |

---

## Safety Filter — Technical Detail

File: `app/utils/safety_filter.py`
Applied by: `rag_agent` (inline) + `audit_safety_agent` (final gate)

### Diagnosis Block Patterns (regex, case-insensitive)

```python
r"you have (a |an )?(malaria|dengue|typhoid|tuberculosis|tb|diabetes|...)"
r"you (are|seem to be) (suffering from|diagnosed with)"
r"this is (definitely|likely|probably) (a |an )?\w+ (disease|condition|infection)"
r"sounds like (a |an )?\w+ (infection|disease|condition|virus|illness)"
r"i can (diagnose|tell you) (you have|this is)"
```

### Prescription Block Patterns (regex, case-insensitive)

```python
r"\d+\s*mg\s*(of\s*)?\w+"              # "500mg paracetamol"
r"\btake \w+ (twice|three times?) (a day|daily)"
r"\b(i|we)\s+prescribe\b"
r"\b(amoxicillin|azithromycin|metronidazole|ciprofloxacin|...)\b"
r"antibiotic[s]?\s+(course|treatment|for \d+ days?)"
```

If any pattern matches → response replaced with:
```
"I was unable to provide specific information on this topic.
 Please visit your nearest health centre or speak with your ASHA worker."
 + STANDARD_DISCLAIMER
```

### Emergency Keywords (30+, pre-LLM check)

Organised by clinical category:
- Cardiovascular/Respiratory: `chest pain`, `cannot breathe`, `cardiac arrest`, `heart attack`
- Neurological: `unconscious`, `seizure`, `stroke`, `facial droop`, `sudden severe headache`
- Bleeding/Trauma: `severe bleeding`, `vomiting blood`, `bleeding won't stop`
- Poisoning: `snake bite`, `poisoning`, `swallowed poison`, `insecticide ingestion`
- Obstetric: `eclampsia`, `heavy vaginal bleeding`, `baby not moving`
- Paediatric: `child not breathing`, `baby turning blue`, `infant not breathing`

---

## RAG Pipeline Architecture

### Document Ingestion — Three Paths

```
Path 1: Seed (one-time demo data)
  python -m app.rag.document_loader --sample
  → Loads 10 curated WHO/NHM/emergency text documents
  → Chunked and embedded into all 6 collections
  → Source tagged as "demo_{collection}_{i}"

Path 2: Directory ingestion (bulk)
  python -m app.rag.document_loader --dir /path/to/pdfs --collection who_health_guidelines
  → Loads all .pdf, .txt, .md files from a directory
  → Uses PyPDFLoader / TextLoader (lazy import — avoids Python 3.14 spacy issue)
  → Metadata: source filename, collection, doc_type

Path 3: User upload (live via UI)
  Upload panel in Streamlit → app/services/document_processor.py
  → Supported: .pdf, .txt, .md (knowledge) | .csv, .xlsx (hospitals)
  → PDF: extracted via pypdf (in-memory) or PyPDFLoader (temp file fallback)
  → Knowledge docs → chunked → ChromaDB collection of user's choice
  → Hospital CSVs → parsed by pandas → upserted to facility_cache (SQLite)
  → Source tagged as "user_upload"
```

### Chunking Strategy

File: `app/rag/document_loader.py` — custom `chunk_text()` function

> Note: LangChain's `RecursiveCharacterTextSplitter` is intentionally NOT used — its dependency chain pulls in `SpacyTextSplitter` which is incompatible with Python 3.14.

```python
CHUNK_SIZE    = 512   # characters (not tokens)
CHUNK_OVERLAP = 64    # characters shared between adjacent chunks
SEPARATORS    = ["\n\n", "\n", ". ", "! ", "? ", " "]
```

**Algorithm:**
1. Take a 512-character window from the current position
2. If not at end of document, scan backwards from the midpoint for the last natural separator in priority order: `\n\n` → `\n` → `. ` → `! ` → `? ` → ` `
3. Cut at that separator — chunks always end at a clean boundary
4. Advance position by `chunk_length - 64` (the 64-char overlap carries context forward)
5. Repeat until document is fully consumed

**Why character-based, not token-based:**
- Consistent across all embedding models regardless of tokenizer
- The `nomic-embed-text` context window is ~8192 tokens; 512 characters ≈ 100–150 tokens — well within limit
- Simpler, faster, no tokenizer dependency

**Chunk metadata stored with every chunk:**

```python
{
    "source":      "filename.pdf",      # origin file
    "collection":  "who_health_guidelines",
    "doc_type":    "demo" | "guideline" | "user_upload",
    "chunk_index": 0, 1, 2, ...         # position within document
}
```

### Embedding Model

| Setting | Value |
|---|---|
| Default provider | Ollama `nomic-embed-text` (local, no API key) |
| Fallback provider | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| Vector dimensions | ~768 (nomic-embed-text) / 384 (all-MiniLM) |
| Runtime | Fully local — no external API call |
| Config | `EMBED_PROVIDER=ollama` or `huggingface` in `.env` |

### Vector Store — ChromaDB

| Setting | Value |
|---|---|
| Library | `chromadb>=0.5.0` + `langchain-chroma` |
| Mode | `PersistentClient` — data written to disk |
| Storage path | `data/chroma/` (absolute path in `.env`) |
| Similarity metric | Cosine similarity (ChromaDB default) |
| Collections | 6 named collections |

### The 6 Collections

| Collection | Content | Priority in Query |
|---|---|---|
| `symptom_disease_mapping` | WHO ICD-11 symptom-severity classifications | 1st (standard) |
| `who_health_guidelines` | WHO fever, diarrhea, dehydration, TB, maternal | 2nd |
| `nhm_india_protocols` | ASHA modules, NTEP, NVBDCP, NHM free drugs | 3rd |
| `drug_information_basic` | ORS, paracetamol, iron — ASHA-distributed only | 4th |
| `regional_health_schemes` | PM-JAY, Ayushman Bharat, JSY, JSSK | 5th |
| `emergency_protocols` | CPR, snake bite, breathing, unconscious first aid | Moved to 1st when triage = EMERGENCY |

### Semantic Retrieval — How It Works

File: `app/rag/retriever.py`

**Query construction** (in `rag_agent`):
```python
query = f"{chief_complaint}: {', '.join(symptoms)}"
# e.g. "fever and body aches: fever, headache, fatigue"
```

**Multi-collection sweep:**
```python
for collection in STANDARD_COLLECTION_ORDER:
    docs = get_retriever(collection, score_threshold=None).invoke(query)
    # Deduplicate by exact content match
    # Accumulate all unique chunks
all_docs = all_docs[: RAG_TOP_K * 2]   # cap at 10
```

**Why `score_threshold=None`:**
- With Ollama embeddings the cosine scores are not normalised to a fixed 0–1 range
- A hard threshold would silently drop valid results
- Volume cap (`top_k * 2`) provides the recall boundary instead

**Emergency fast path (separate retriever):**
```python
retriever = get_retriever("emergency_protocols", k=3, score_threshold=None)
docs = retriever.invoke(query)   # top-3 only, no LLM overhead
# Falls back to STATIC_FIRST_AID dict if ChromaDB unavailable
```

**Deduplication:**
```python
seen_content: set[str] = set()
for doc in docs:
    if doc.page_content not in seen_content:
        seen_content.add(doc.page_content)
        all_docs.append(doc)
```

**Grounding confidence:**
```python
"high"   if len(docs) >= 3
"medium" if len(docs) in (1, 2)
"none"   if len(docs) == 0   # → safe fallback, LLM not called
```

### RAG Generation Prompt (enforced at every call)

```
SYSTEM:
You are a health information assistant for RuralCare AI, serving rural patients in India.

STRICT RULES:
1. Use ONLY the provided context documents. Do NOT add medical information from your own knowledge.
2. Do NOT diagnose any disease or condition.
3. Do NOT recommend specific prescription medicines or dosages.
4. Write at Grade 6 reading level — short sentences, simple words.
5. If context is insufficient, say exactly:
   "I don't have specific information on this. Please visit your nearest health centre."
6. Always end with: "Visit your nearest health centre for proper evaluation."
7. Always cite source document names at the end.
8. Maximum response: 300 words.

CONTEXT DOCUMENTS:
{context}
```

---

## Facility Lookup — 3-Level Hybrid

File: `app/agents/appointment_facility.py`

```
Level 1: SQLite static data (NHM Tamil Nadu — 87+ records)
  LOWER(TRIM(district)) = LOWER(TRIM(?))
  AND LOWER(TRIM(state)) = LOWER(TRIM(?))
  → Case-insensitive, whitespace-tolerant exact match
  → Covers 38 Tamil Nadu districts

Level 2: OpenStreetMap Overpass API (if Level 1 returns 0 results)
  → Geocode district → query healthcare facilities within radius
  → Results upserted to facility_cache with source='osm'

Level 3: Google Places API (if Level 2 returns 0, and GOOGLE_MAPS_API_KEY set)
  → nearbysearch for hospitals/clinics
  → Results upserted to facility_cache with source='google'
```

**Facility type mapping by triage:**

```python
FACILITY_TYPE_MAP = {
    "EMERGENCY": ["Hospital"],
    "URGENT":    ["CHC", "Hospital"],
    "MODERATE":  ["PHC", "CHC"],
    "MILD":      ["Sub-Centre", "PHC"],
}
```

---

## LLM Integration Layer

### Provider Abstraction

```python
# Configured via LLM_PROVIDER in .env
LLM_PROVIDER=ollama    # default — local, no API key needed
LLM_PROVIDER=claude    # Anthropic Claude (claude-sonnet-4-6)
LLM_PROVIDER=openai    # OpenAI GPT-4o
LLM_PROVIDER=gemini    # Google Gemini 2.0 Flash
```

### Ollama (Default)

```python
ChatOllama(
    model="llama3.2",            # OLLAMA_MODEL in .env
    base_url="http://localhost:11434",
    temperature=0.1,             # low temperature for consistent clinical output
)
```

---

## Voice Pipeline

```
Patient Audio (.wav / .mp3 / .ogg)
  → Whisper (base model by default — configurable via WHISPER_MODEL)
  → Transcribed text + auto-detected language
  → Google Translate / langdetect (→ English)
  → Standard LangGraph pipeline
  → Final response back-translated to patient language
```

**Note:** `openai-whisper` must be installed separately (`pip install openai-whisper`). Text mode works without it.

---

## Security Architecture

| Layer | Control |
|---|---|
| Input | Max length limit, minimum length check |
| LLM Prompt | PHI anonymisation — `patient_token` replaces real identity |
| LLM Output | Safety filter — blocks diagnosis, prescriptions, PHI leakage |
| Audit | SHA-256 hash only — raw text never stored |
| API | CORS middleware; rate limiting recommended in production |
| Network | HTTPS only in production |

---

## Failure Modes and Fallbacks

| Failure | Fallback |
|---|---|
| LLM unavailable / timeout | `_node` wrapper catches exception; pipeline returns degraded state |
| ChromaDB unavailable | `retrieve_health_context` logs warning; `grounding_confidence="none"`; safe fallback shown |
| RAG returns 0 documents | Fixed safe fallback message — LLM not called for medical content |
| Safety filter blocks output | Standard safe fallback replaces response |
| Emergency webhook POST fails | Error logged; pipeline continues |
| No district entered | UI shows "Enter a District in the sidebar" — no crash |
| User CSV missing required columns | `process_hospital_file` returns error dict; UI shows human-readable message |

---

## Deployment Architecture

### Demo / Local

```
python -m streamlit run app/streamlit_app.py   # port 8501
uvicorn app.main:app --reload --port 8000       # port 8000
```

### Docker

```
docker-compose up --build
# Streamlit: http://localhost:8501
# FastAPI:   http://localhost:8000
```

### Production (recommended)

```
Load Balancer (Nginx)
  ├── Streamlit Service  (2 replicas)
  ├── FastAPI Service    (4 replicas, autoscale)
  ├── ChromaDB Service   (PersistentClient, persistent volume)
  └── PostgreSQL         (managed — Supabase / RDS)

Secrets:  Render / AWS Secrets Manager
CI/CD:    GitHub Actions → Docker Hub → Render / ECS
```

---

## Key Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Orchestration | LangGraph | Explicit state machine, conditional routing, fail-safe node wrapper |
| Vector DB | ChromaDB `PersistentClient` | Embedded mode — no server needed, works in Kaggle notebook |
| Embedding | Ollama `nomic-embed-text` | Local, no API key, high-quality semantic embeddings |
| Chunking | Custom `chunk_text()` | Avoids Python 3.14 spacy incompatibility; gives full control |
| Retrieval | Direct cosine search, no MultiQueryRetriever | Simpler, lower latency; score threshold disabled to avoid Ollama normalisation issue |
| LLM default | Ollama `llama3.2` | Fully local — no API cost for demo; swappable to Claude/GPT-4o via `.env` |
| Safety | Synchronous regex filter on every output | Safety cannot be async, batched, or optional |
| Audit | Append-only SQLite table | Tamper resistance, portable, no external dependency |
| PHI | Token + hash — never raw text | DPDP compliance, no reversible patient data |
| Emergency detection | Rule-based keyword scan before LLM | < 100ms guaranteed; LLM latency unacceptable for life-threatening cases |
| Frontend | Streamlit | Fastest to demo, no JS required, runs in Kaggle |
| API | FastAPI + uvicorn | Async-ready, auto-docs, production-grade |
