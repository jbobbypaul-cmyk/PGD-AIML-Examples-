# IMPLEMENTATION_ROADMAP.md — RuralCare AI Implementation Roadmap

## Purpose

Define the phased implementation plan from MVP to production, with clear deliverables, timelines, dependencies, and acceptance criteria for each phase.

---

## Phase Overview

```
Phase 0: Foundation            ✅ COMPLETE
Phase 1: Core Agents — MVP     ✅ COMPLETE
Phase 2: RAG Pipeline          ✅ COMPLETE
Phase 3: Complete Pipeline     ✅ COMPLETE
Phase 4: Frontend + Demo       ✅ COMPLETE (Streamlit UI live on port 8501)
Phase 5: Multilingual + Voice  ⚠️  PARTIAL (translation works; Whisper optional install)
Phase 6: Production Hardening  ⚠️  PARTIAL (FastAPI running on port 8000; JWT/rate-limit pending)
Phase 7: Deployment            ⏳ PENDING
```

---

## Phase 0: Foundation ✅ COMPLETE

### Deliverables

- [x] Repository initialized with folder structure (`app/`, `data/`, `tests/`, `scripts/`, `docker/`).
- [x] `.env.example` created with all required variables.
- [x] `requirements.txt` with pinned dependencies.
- [x] `app/utils/config.py` — `AppConfig` with `__file__`-anchored absolute paths; `@lru_cache(maxsize=1)` on `get_config()`.
- [x] `app/models/data_models.py` — `PatientState` TypedDict + all Pydantic models.
- [x] `app/database/sqlite_client.py` — SQLite connection, all table creation, case-insensitive `LOWER(TRIM())` queries.
- [x] `app/utils/safety_filter.py` — Red-flag keyword detector + regex safety filter (no LLM).
- [x] `tests/test_safety_filter.py` — coverage of diagnosis and prescription patterns.
- [x] `.gitignore` — excludes `.env`, `*.db`, `__pycache__`, `data/chroma/`.

### Actual File Paths (differ from original plan — `src/` → `app/`)

```
app/
├── utils/
│   ├── config.py
│   ├── safety_filter.py
│   └── logger.py
├── models/
│   └── data_models.py
└── database/
    ├── sqlite_client.py
    └── schema.sql
tests/
└── test_safety_filter.py
.env.example
requirements.txt
.gitignore
```

### Tech Corrections vs Original Plan
- Python **3.14** (tested on Windows 11); 3.10+ required.
- `config.py` uses `__file__`-anchored absolute paths to fix `.env` loading from any working directory.
- `PYTHONUTF8=1` required on Windows to avoid `cp1252` encoding errors in logger.

---

## Phase 1: Core Agents — MVP ✅ COMPLETE

### Deliverables

- [x] `app/agents/symptom_intake.py` — LLM-based symptom extraction.
- [x] `app/agents/medical_triage.py` — Triage classification (EMERGENCY/URGENT/MODERATE/MILD).
- [x] `app/agents/emergency_escalation.py` — Emergency response with first-aid + contact numbers.
- [x] `app/agents/audit_safety.py` — Safety filter + audit log writer.
- [x] `app/orchestrator/langgraph_orchestrator.py` — LangGraph graph with fail-safe `_node` wrapper.
- [x] `app/utils/llm_factory.py` — Multi-provider LLM factory (Ollama / Claude / OpenAI / Gemini).
- [x] Tests for core agents.

### Key Implementation Details

**`_node` fail-safe wrapper (prevents pipeline crash on agent failure):**
```python
def _node(fn):
    def wrapper(state):
        try:
            return fn(state)
        except Exception as exc:
            state.setdefault("errors", []).append(str(exc))
            return state
    return wrapper
```

**LLM factory:**
```python
# app/utils/llm_factory.py
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")

if LLM_PROVIDER == "ollama":
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model="llama3.2", base_url="http://localhost:11434")
elif LLM_PROVIDER == "claude":
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model="claude-sonnet-4-6")
# ...
```

**LangGraph 8-node graph (entry at `symptom_intake`, conditional emergency routing):**
```python
graph.set_entry_point("symptom_intake")
graph.add_conditional_edges(
    "symptom_intake",
    lambda s: "emergency" if s.get("emergency_flag") else "normal",
    {"emergency": "emergency_escalation", "normal": "medical_triage"},
)
```

---

## Phase 2: RAG Pipeline ✅ COMPLETE

### Deliverables

- [x] `app/rag/document_loader.py` — PDF/TXT ingestion; custom `chunk_text()` (512-char, 64-char overlap).
- [x] `app/rag/vector_store.py` — ChromaDB `PersistentClient`, 6 collections, cosine similarity.
- [x] `app/rag/retriever.py` — Multi-collection sweep retriever with deduplication.
- [x] `app/agents/rag_agent.py` — RAG agent with context-grounded LLM generation.
- [x] `data/knowledge_base/sample_docs/` — 8 demo text documents seeded.
- [x] `scripts/load_knowledge_base.py` — CLI script to ingest documents.

### Key Tech Corrections vs Original Plan

| Original Plan | Actual Implementation |
|---|---|
| `RecursiveCharacterTextSplitter` (LangChain) | Custom `chunk_text()` — Python 3.14 + spacy wheel incompatibility |
| `HuggingFaceEmbeddings("all-MiniLM-L6-v2")` — 384-dim | `OllamaEmbeddings("nomic-embed-text")` — ~768-dim, local |
| `MultiQueryRetriever` | Direct cosine retriever — Ollama not compatible with MultiQueryRetriever |
| `score_threshold=0.65` | `score_threshold=None` — Ollama cosine scores are not normalised 0–1 |
| `search_type="similarity_score_threshold"` | `search_type="similarity"` with volume cap (`k`) |

---

## Phase 3: Complete Pipeline ✅ COMPLETE

### Deliverables

- [x] `app/agents/appointment_facility.py` — 3-level hybrid facility lookup.
- [x] `app/agents/followup_adherence.py` — Follow-up plan generation.
- [x] `app/agents/health_worker_support.py` — ASHA/ANM briefing generator.
- [x] `scripts/seed_tn_hospitals.py` — 87 Tamil Nadu hospitals seeded across 38 districts.
- [x] Updated `app/orchestrator/langgraph_orchestrator.py` — Full 8-node graph.

### Facility Lookup Implementation (3 Levels)

```
Level 1: SQLite NHM TN cache (87 hospitals, case-insensitive LOWER(TRIM()) query)
Level 2: OpenStreetMap Overpass API (if Level 1 empty) → cached to SQLite
Level 3: Google Places API (if Level 2 empty, only if GOOGLE_MAPS_KEY set)
```

Source labels: `nhm_tn` / `osm` / `google` / `user_upload`

Direct SQLite connection in Streamlit (`sqlite3.connect(config.sqlite_path)`) bypasses `get_config()` lru_cache chain that caused empty results on first call.

---

## Phase 4: Frontend + Demo ✅ COMPLETE

### Deliverables

- [x] `app/streamlit_app.py` — Complete Streamlit demo UI.
- [x] `notebooks/ruralcare_ai_demo.ipynb` — Kaggle Notebook.
- [x] Quick demo buttons (5 pre-loaded symptom scenarios).
- [x] Document upload (hospital CSV/Excel → SQLite; medical PDF/TXT → ChromaDB).
- [x] `app/services/document_processor.py` — Two ingestion paths.
- [x] `app/services/maps_service.py` — OSM + Google Places integration.

### Streamlit App Layout (Actual)

```
┌─────────────── Sidebar ──────────────────┐
│ Language selector (6 options)            │
│ Input mode (Text / Voice)                │
│ Quick demo buttons (5 scenarios)         │
└──────────────────────────────────────────┘
┌─────────────── Main Area ────────────────┐
│ Header + disclaimer warning              │
│ Symptom text area (key="symptoms_textarea")│
│ District + State inputs                  │
│ "Get Health Guidance" button             │
│                                          │
│ Results:                                 │
│  - Triage Level metric                   │
│  - Emergency Alert (if applicable)       │
│  - Health Guidance (RAG-grounded)        │
│  - Facility debug caption                │
│  - Facility cards (top 3, bordered)      │
│  - Follow-up Plan (3-column bordered)    │
│  - Health Worker Briefing (full-width)   │
│  - RAG Sources                           │
│  - Disclaimer                            │
│                                          │
│ Document Upload expander (bottom):       │
│  - Tab 1: Hospital CSV/Excel upload      │
│  - Tab 2: Medical knowledge PDF/TXT/MD   │
└──────────────────────────────────────────┘
```

### Key UI Bug Fixes Applied

| Bug | Root Cause | Fix |
|---|---|---|
| Demo buttons not loading symptoms | `st.text_area` with `key=` ignores `value=` after first render | Set both `st.session_state.symptoms_input` and `st.session_state.symptoms_textarea`; remove `value=` |
| Health Worker Briefing cut off | `st.code()` has fixed scroll height | Replace with `st.text()` inside `st.container(border=True)` |
| Facility showing "visit PHC" | `get_facilities_by_district()` caching chain returned empty | Direct `sqlite3.connect(config.sqlite_path)` in UI layer |

---

## Phase 5: Multilingual + Voice ⚠️ PARTIAL

### Completed
- [x] Language detection via `langdetect`.
- [x] Google Translate integration (input → English, response → patient's language).
- [x] 6 language options in Streamlit sidebar (English, Hindi, Tamil, Bengali, Telugu, Kannada).
- [x] Voice upload UI (file uploader in Streamlit).

### Pending
- [ ] `openai-whisper` — separate install; not bundled in `requirements.txt` due to large model size.
- [ ] IndicTrans2 — better Indic accuracy, larger model, optional setup.
- [ ] `tests/test_multilingual.py` — full Hindi/Tamil/Bengali test cases.

### Whisper Setup (manual, when needed)

```bash
pip install openai-whisper
# Then: WHISPER_MODEL=base in .env
```

---

## Phase 6: Production Hardening ⚠️ PARTIAL

### Completed

- [x] `app/main.py` — FastAPI application with lifespan context manager.
- [x] 7 API endpoints (health, intake, voice, facilities, audit, followup).
- [x] Auto Swagger docs at `http://localhost:8000/docs`.
- [x] `PYTHONUTF8=1` environment fix for Windows.

### Pending

- [ ] PostgreSQL schema migration.
- [ ] JWT authentication for API.
- [ ] Rate limiting (slowapi).
- [ ] Input sanitization and prompt injection detection.
- [ ] LangSmith tracing integration.
- [ ] Structured JSON logging (structlog).
- [ ] `docker/Dockerfile` and `docker/docker-compose.yml` — finalize.
- [ ] `tests/test_api.py` — FastAPI route tests.

---

## Phase 7: Deployment ⏳ PENDING

### Deliverables

- [ ] Hugging Face Spaces deployment (Streamlit SDK).
- [ ] Render deployment (FastAPI + Streamlit).
- [ ] GitHub Actions CI/CD pipeline.
- [ ] README.md with live demo links.
- [ ] Load testing results.

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy RuralCare AI
on:
  push:
    branches: [main]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/ --cov=app --cov-fail-under=80
  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Render
        run: curl -X POST ${{ secrets.RENDER_DEPLOY_HOOK }}
```

---

## MVP vs Production Split

| Feature | MVP (Phases 0–4) — COMPLETE | Production (Phases 5–7) |
|---|---|---|
| Symptom intake | Text only | Text + Voice (Whisper) |
| Languages | 6 languages (UI), English pipeline | 6 languages end-to-end |
| Database | SQLite | PostgreSQL |
| Facility search | 87 TN hospitals + OSM fallback | Live OSM + Google Places |
| Reminders | Logged only | SMS/notification delivery (Celery + Redis) |
| Authentication | None | JWT |
| Monitoring | Audit log only | LangSmith + structured logs |
| Deployment | Streamlit local (port 8501) | Docker + cloud |
| Knowledge base | 8 sample documents | 1000+ WHO/NHM documents |
| API | FastAPI local (port 8000) | Docker + cloud + rate limiting |
| Document upload | CSV → SQLite, PDF → ChromaDB | Same + admin review queue |

---

## Environment Setup (Quick Start — Current State)

```bash
# 1. Install Ollama from https://ollama.ai
ollama pull llama3.2
ollama pull nomic-embed-text

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env: set absolute SQLITE_PATH, CHROMA_DB_PATH

# 5. Initialize database and seed Tamil Nadu hospitals
python -m app.database.sqlite_client   # creates tables
python scripts/seed_tn_hospitals.py    # loads 87 TN hospitals

# 6. Load sample knowledge base
python -m app.rag.document_loader --sample

# 7. Run Streamlit demo
$env:PYTHONUTF8 = "1"
python -m streamlit run app/streamlit_app.py

# 8. Run FastAPI (separate terminal)
$env:PYTHONUTF8 = "1"
python -m uvicorn app.main:app --reload --port 8000
```

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| LLM safety filter bypass | Medium | High | Regex + LLM double-check + human review queue |
| LLM API cost overrun | Medium | Medium | Default to Ollama (local, free); token limits on cloud providers |
| Whisper accuracy for Indian languages | High | Medium | Google STT fallback |
| ChromaDB index corruption | Low | High | Daily backup, graceful fallback to general guidance |
| False emergency escalation | Medium | Medium | Symptom context check + user confirmation |
| Regulatory challenge (medical device) | Low | High | Prominent disclaimers, not marketed as diagnostic tool |
| Data breach | Low | Very High | PHI anonymization, SHA-256 hashes only, no real data in demo |
| Python 3.14 library incompatibilities | Medium | Medium | Custom chunk_text(), PYTHONUTF8=1, tested stack locked in requirements.txt |
