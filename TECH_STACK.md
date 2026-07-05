# TECH_STACK.md — RuralCare AI Technology Stack

## Purpose

Document every technology choice in the RuralCare AI stack, with rationale, version targets, configuration notes, and alternatives considered.

---

## Stack Summary Table

| Layer | Technology | Version (Actual) | Role |
|---|---|---|---|
| Frontend | Streamlit | 1.58.0 | Demo UI, port 8501 |
| Backend API | FastAPI + uvicorn | 0.111+ | REST API, port 8000 |
| Agent Orchestration | LangGraph | 0.2+ | State machine, 8 nodes, fail-safe `_node` wrapper |
| RAG Framework | LangChain | 0.2+ | Retriever chains, prompt templates, LLM chaining |
| Vector Database | ChromaDB `PersistentClient` | 0.5+ | 6 collections, cosine similarity, embedded |
| Embeddings | Ollama `nomic-embed-text` | local | Local ~768-dim; no external API |
| LLM (default) | Ollama `llama3.2` | local | Local inference, no API key required |
| LLM (alt 1) | Claude (Anthropic) | claude-sonnet-4-6 | Set `LLM_PROVIDER=claude` |
| LLM (alt 2) | OpenAI GPT-4o | gpt-4o | Set `LLM_PROVIDER=openai` |
| LLM (alt 3) | Google Gemini | gemini-2.0-flash | Set `LLM_PROVIDER=gemini` |
| Voice-to-text | OpenAI Whisper (local) | base/small | `.wav/.mp3/.ogg` transcription |
| Translation | Google Translate + langdetect | v3 | Cloud translation; IndicTrans2 as future option |
| Facility Data | SQLite + OSM + Google Places | — | 3-level hybrid lookup |
| Database (demo) | SQLite | 3.x | Sessions, audit, facility cache, follow-ups |
| Database (prod) | PostgreSQL | 15+ | Production data layer (same schema) |
| Data Validation | Pydantic | v2 | All request/response/state models |
| Task Queue | Celery + Redis | 5.x / 7.x | Follow-up reminders (production only) |
| Monitoring | LangSmith | latest | LLM tracing (optional, set `LANGSMITH_API_KEY`) |
| Logging | Python `logging` | — | No `print()` in production |
| Containerization | Docker + docker-compose | 24+ | Local dev + cloud packaging |
| Testing | pytest + pytest-asyncio | 8+ | Unit and integration tests |
| Code Quality | Black + isort | — | Formatting and import sorting |
| Secrets | python-dotenv | 1.0+ | `.env` loading with `__file__`-anchored absolute path |
| Python Runtime | Python | 3.14 (tested) | 3.10+ required; 3.14 validated on Windows 11 |

---

## Local LLM: Ollama

**Why Ollama (default for local dev):**
- No API key, no cost, fully offline.
- Runs on CPU — works on any developer machine.
- Single command install: `ollama pull llama3.2 && ollama pull nomic-embed-text`.
- Default in `.env`: `LLM_PROVIDER=ollama`.

**Setup:**
```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.2        # ~2GB, primary LLM
ollama pull nomic-embed-text # embedding model
# Verify:
ollama list
# Start Ollama server (runs on localhost:11434)
ollama serve
```

**LangChain integration:**
```python
from langchain_ollama import ChatOllama, OllamaEmbeddings

llm = ChatOllama(model="llama3.2", base_url="http://localhost:11434")
embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url="http://localhost:11434")
```

**Switching to Claude / OpenAI / Gemini:**
```bash
# .env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your_key_here
```
No code changes required — `app/utils/config.py` factory handles the switch.

---

## Frontend: Streamlit

**Version:** 1.58.0

**Why Streamlit:**
- Zero JavaScript — pure Python UI.
- Runs inside Kaggle Notebooks and Hugging Face Spaces natively.
- Sufficient for demo: symptom form, triage result, RAG output, facility list.
- Rapid iteration for MVP.

**Key widget patterns (actual implementation):**
```python
# Widget key is single source of truth — do NOT use value= after first render
symptoms = st.text_area("Symptoms", key="symptoms_textarea", height=120)

# Demo button fix: must set BOTH session_state keys + rerun
st.session_state.symptoms_input    = text
st.session_state.symptoms_textarea = text   # must match widget key
st.rerun()

# Use st.text() not st.code() to avoid fixed scroll-height truncation
st.text(briefing)   # full text, no height cap

# Caching
@st.cache_resource
def startup() -> dict:
    ...  # called once at startup; returns config + initialized components
```

**Production path:** React/Next.js frontend calling the FastAPI backend. Streamlit remains for internal tools and Kaggle demos.

---

## Backend: FastAPI

**Why FastAPI:**
- Async-native, high performance.
- Auto-generates OpenAPI docs at `/docs` and ReDoc at `/redoc`.
- Pydantic-native request/response validation.

**Start command (Windows, PYTHONUTF8 required):**
```bash
$env:PYTHONUTF8 = "1"
python -m uvicorn app.main:app --reload --port 8000
```

**All 7 endpoints:**
```
GET  /health                       → Liveness probe
POST /api/v1/intake                → Text symptoms → full 8-agent pipeline
POST /api/v1/voice                 → Audio upload → Whisper → pipeline
GET  /api/v1/facilities            → Facility lookup (district, state, triage)
GET  /api/v1/audit/{session_id}    → Session audit log
GET  /api/v1/audit                 → Recent audit entries (paginated)
POST /api/v1/followup              → Schedule follow-up reminder
```

**Note on Swagger / ReDoc:** Both are auto-generated and available when the server is running. If `localhost:8000/docs` doesn't respond, confirm the server started without encoding errors (`PYTHONUTF8=1` is required on Windows).

---

## Agent Orchestration: LangGraph

**Why LangGraph:**
- Explicit state graph — each agent is a named node.
- Conditional edges — emergency routing without hacks.
- Persistent state (`PatientState`) flows through all agents.
- Fail-safe `_node` wrapper catches exceptions and writes safe fallback.

**Core pattern (actual orchestrator):**
```python
from langgraph.graph import StateGraph, END

graph = StateGraph(PatientState)
graph.add_node("symptom_intake",        _node(symptom_intake_agent))
graph.add_node("medical_triage",        _node(medical_triage_agent))
graph.add_node("rag_agent",             _node(rag_agent))
graph.add_node("appointment_facility",  _node(appointment_facility_agent))
graph.add_node("followup_adherence",    _node(followup_adherence_agent))
graph.add_node("health_worker_support", _node(health_worker_support_agent))
graph.add_node("emergency_escalation",  _node(emergency_escalation_agent))
graph.add_node("audit_safety",          _node(audit_safety_agent))

graph.set_entry_point("symptom_intake")
graph.add_conditional_edges(
    "symptom_intake",
    lambda s: "emergency" if s.get("emergency_flag") else "normal",
    {"emergency": "emergency_escalation", "normal": "medical_triage"},
)
# ... remaining edges
app = graph.compile()
```

---

## RAG Framework: LangChain

**Why LangChain:**
- Mature document loaders (PDF, TXT, MD, HTML).
- Pluggable retrievers — works with ChromaDB, pgvector, Pinecone.
- LCEL (LangChain Expression Language) for composable chains.

**Actual retrieval pattern (no MultiQueryRetriever — Ollama-compatible):**
```python
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 5},
)
# score_threshold=None — Ollama cosine scores are not normalised 0-1;
# volume cap (k) is used instead of a fixed threshold.
```

**Multi-collection sweep (priority order):**
```python
QUERY_ORDER = [
    "emergency_protocols",       # Always first
    "symptom_disease_mapping",
    "who_health_guidelines",
    "nhm_india_protocols",
    "drug_information_basic",
    "regional_health_schemes",
]
# Results are deduplicated by content before LLM generation.
```

---

## Vector Database: ChromaDB

**Client type:** `chromadb.PersistentClient` (embedded, not HTTP server)

**Why ChromaDB:**
- Embedded mode — no separate server needed for demo or Kaggle.
- Python-native, simple API.
- Metadata filtering (filter by document category, language, source).
- Persistent storage at a single folder path.
- Production swap: pgvector in PostgreSQL.

**6 Collections:**
```
data/chroma/
├── who_health_guidelines/
├── nhm_india_protocols/
├── symptom_disease_mapping/
├── drug_information_basic/
├── emergency_protocols/
└── regional_health_schemes/
```

**Similarity metric:** Cosine (default in ChromaDB).

---

## Chunking: Custom `chunk_text()`

**Why custom chunker (not `RecursiveCharacterTextSplitter`):**

`RecursiveCharacterTextSplitter` from `langchain_text_splitters` has a transitive dependency on `spacy`, which fails to install on Python 3.14 (binary wheel incompatibility as of 2026). To avoid this, a custom chunker is used.

**Implementation (`app/rag/document_loader.py`):**
```python
def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """
    Separator-aware chunker: tries paragraph/sentence breaks first.
    Falls back to hard split at chunk_size.
    """
    separators = ["\n\n", "\n", ". ", "! ", "? ", " "]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            for sep in separators:
                pos = text.rfind(sep, start, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]
```

**Parameters:** 512-char window, 64-char overlap, separator-aware (paragraph → sentence → word).

---

## Embeddings: Ollama `nomic-embed-text`

**Primary:** `nomic-embed-text` via Ollama
- Runs locally on `localhost:11434`, no API cost.
- ~768-dimensional embeddings.
- Pull with: `ollama pull nomic-embed-text`.

**Fallback (cloud/Kaggle):** `HuggingFaceEmbeddings("all-MiniLM-L6-v2")` — 384-dim, runs on CPU without Ollama.

**Production upgrade:** `text-embedding-3-small` (OpenAI) or `embedding-001` (Google).

---

## Voice: OpenAI Whisper (local)

**Why Whisper:**
- Open source, runs entirely locally — no audio sent externally.
- Supports 99 languages including all major Indian languages.
- Models: `base` (fast, Kaggle demo), `small` (better accuracy), `medium` (production).

**Install:** `pip install openai-whisper` (installs separately from `openai`).

```python
import whisper
model = whisper.load_model("base")
result = model.transcribe("audio.wav")
text, lang = result["text"], result.get("language", "en")
```

---

## Translation: Google Translate + langdetect

**Current implementation:**
- `langdetect` for language detection (no API key).
- `googletrans` (free, unofficial) or `google-cloud-translate` (API key) for translation.
- Input → English for all LLM calls; response back-translated to patient's language.

**IndicTrans2 (future):**
- Open source, AI4Bharat, 22 Indian languages.
- Larger model (~1GB), better Indic accuracy.
- Planned for production Phase 5.

---

## Facility Lookup: 3-Level Hybrid

**Level 1 — NHM Tamil Nadu SQLite cache (primary):**
- 87 hospitals seeded across 38 Tamil Nadu districts via `scripts/seed_tn_hospitals.py`.
- Query: `LOWER(TRIM(district)) = LOWER(TRIM(?))` — case-insensitive, whitespace-tolerant.
- Government facilities sorted first (`ORDER BY is_government DESC`).

**Level 2 — OpenStreetMap Overpass API:**
- Free, no API key, open data.
- Triggered when SQLite returns no results.
- Results cached to SQLite with `source='osm'`.

**Level 3 — Google Places (optional):**
- Requires `GOOGLE_MAPS_KEY` in `.env`.
- Only called when Levels 1 and 2 return nothing.

---

## Database: SQLite → PostgreSQL

**SQLite (Demo, absolute path in `.env`):**
```
SQLITE_PATH=C:/Users/Bahwan/Brindha/RuralCare_AI_Claude/data/ruralcare.db
```

`app/utils/config.py` uses `__file__`-anchored absolute paths so the correct `.env` is found regardless of working directory.

**PostgreSQL (Production):**
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/ruralcare
```

Schema is identical — SQLAlchemy ORM abstracts the difference.

---

## Windows / Python 3.14 Compatibility Notes

| Issue | Fix |
|---|---|
| `UnicodeEncodeError` on Windows with Unicode arrows in logs | Set `PYTHONUTF8=1` in environment; use ASCII arrows (`->`) in logger calls |
| `spacy` wheel failure on Python 3.14 | Use custom `chunk_text()` instead of `RecursiveCharacterTextSplitter` |
| `load_dotenv()` relative path fails when Streamlit launched from wrong CWD | Use `__file__`-anchored path in `config.py` |
| `st.text_area` demo button not loading | Set both `st.session_state.symptoms_input` and `st.session_state.symptoms_textarea`; remove `value=` parameter |

---

## Monitoring: LangSmith (Optional)

```bash
LANGSMITH_API_KEY=your_key
LANGSMITH_PROJECT=ruralcare-ai
LANGCHAIN_TRACING_V2=true
```

What gets traced: every LangGraph node, token counts, latency, retrieved RAG chunks, LLM input/output (sanitized — no raw PHI).

---

## Deployment Stack

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501 8000
CMD ["supervisord", "-c", "supervisord.conf"]
```

### docker-compose
```yaml
services:
  streamlit:
    build: .
    command: streamlit run app/streamlit_app.py --server.port=8501
    ports: ["8501:8501"]
    env_file: .env
    environment:
      - PYTHONUTF8=1

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    env_file: .env
    environment:
      - PYTHONUTF8=1
```

### Hugging Face Spaces
- Space type: Docker or Streamlit SDK.
- `ANTHROPIC_API_KEY`, `LLM_PROVIDER=claude`, `DEMO_MODE=true` set as HF Space secrets.

---

## Requirements (Core — actual pinned)

```
langchain>=0.2.0
langchain-core>=0.2.0
langchain-ollama>=0.1.0
langchain-anthropic>=0.1.0
langchain-openai>=0.1.0
langchain-google-genai>=1.0.0
langchain-chroma>=0.1.0
langchain-community>=0.2.0
langgraph>=0.2.0
chromadb>=0.5.0
fastapi>=0.111.0
uvicorn>=0.30.0
streamlit>=1.35.0
pydantic>=2.7.0
python-dotenv>=1.0.0
requests>=2.31.0
aiohttp>=3.9.0
pandas>=2.0.0
pypdf>=4.0.0
langsmith>=0.1.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
black>=24.0.0
isort>=5.13.0
```

**Not required (removed):**
- `sentence-transformers` — replaced by Ollama `nomic-embed-text`
- `spacy` — indirect dependency conflict on Python 3.14
- `openai-whisper` — install separately only if voice input is used
