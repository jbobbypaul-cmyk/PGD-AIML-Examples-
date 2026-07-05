# CLAUDE.md — RuralCare AI Project Instructions

## Project Identity

**Name:** RuralCare AI
**Type:** Multi-Agent Rural Healthcare Assistant
**Purpose:** First-level symptom triage, health information, facility location, and follow-up support for rural patients — not a diagnostic tool.
**Stack:** Python + FastAPI + LangGraph + LangChain + ChromaDB + Streamlit + Whisper

---

## Working Directory Layout

```
RuralCare_AI_Claude/
├── CLAUDE.md                    ← This file
├── README.md
├── PROJECT_SCOPE.md
├── ARCHITECTURE.md
├── TECH_STACK.md
├── AGENT_DESIGN.md
├── DATA_MODEL.md
├── RAG_KNOWLEDGE_BASE.md
├── SAFETY_GUARDRAILS.md
├── WORKFLOW.md
├── KAGGLE_DEMO_PLAN.md
├── IMPLEMENTATION_ROADMAP.md
├── skills/
│   ├── orchestrator.skill.md
│   ├── symptom-intake.skill.md
│   ├── medical-triage.skill.md
│   ├── medical-rag.skill.md
│   ├── appointment-facility.skill.md
│   ├── followup-adherence.skill.md
│   ├── health-worker-support.skill.md
│   ├── emergency-escalation.skill.md
│   ├── audit-safety-compliance.skill.md
│   └── multilingual-voice.skill.md
├── src/
│   ├── agents/
│   │   ├── symptom_intake.py
│   │   ├── medical_triage.py
│   │   ├── rag_agent.py
│   │   ├── appointment_facility.py
│   │   ├── followup_adherence.py
│   │   ├── health_worker_support.py
│   │   ├── emergency_escalation.py
│   │   └── audit_safety.py
│   ├── orchestrator/
│   │   └── langgraph_orchestrator.py
│   ├── rag/
│   │   ├── vector_store.py
│   │   ├── document_loader.py
│   │   └── retriever.py
│   ├── voice/
│   │   ├── whisper_transcriber.py
│   │   └── tts_engine.py
│   ├── translation/
│   │   └── translator.py
│   ├── models/
│   │   └── data_models.py
│   ├── api/
│   │   ├── main.py
│   │   └── routes/
│   ├── db/
│   │   ├── sqlite_client.py
│   │   └── audit_logger.py
│   └── utils/
│       ├── safety_filter.py
│       └── config.py
├── frontend/
│   └── streamlit_app.py
├── data/
│   ├── knowledge_base/
│   └── sample_audio/
├── tests/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Key Architectural Decisions

1. **Agent orchestration** via LangGraph state machine — each agent is a node.
2. **RAG pipeline** uses ChromaDB with LangChain for document retrieval.
3. **LLM is configurable** — set `LLM_PROVIDER=claude|openai|gemini` in `.env`.
4. **Safety filter runs on every LLM output** before it reaches the patient.
5. **Audit log** is written after every agent interaction — non-negotiable.
6. **No diagnosis, no prescription** — enforced in the safety filter and system prompts.
7. **Voice** is optional — Whisper transcribes `.wav/.mp3` uploads, text input always works.

---

## Environment Variables (see `.env.example`)

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
WHISPER_MODEL=base
CHROMA_DB_PATH=./data/chroma
SQLITE_PATH=./data/ruralcare.db
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=ruralcare-ai
TRANSLATE_PROVIDER=google
MAPS_PROVIDER=openstreetmap
LOG_LEVEL=INFO
DEMO_MODE=true
```

---

## Safety Non-Negotiables

These rules must never be violated by any agent or code change:

1. Never output a medical diagnosis.
2. Never recommend specific medication by name unless referencing a verified public health document.
3. Always include a disclaimer on every patient-facing response.
4. Always escalate chest pain, difficulty breathing, severe bleeding, loss of consciousness, stroke symptoms.
5. All responses must be RAG-grounded or explicitly labeled as general guidance.
6. Audit logs must be written — never skip them.
7. PHI (patient name, contact, location) must not appear in LLM prompts in plaintext — use anonymized tokens.

---

## Code Style

- Python 3.10+
- Black formatting, isort imports
- Pydantic v2 for all data models
- Type hints everywhere
- Async FastAPI routes
- No print() in production — use Python `logging`
- Tests in `/tests` using pytest

---

## How to Work with This Project

- Read `ARCHITECTURE.md` first to understand system design.
- Read `AGENT_DESIGN.md` to understand each agent's role and boundaries.
- Read `SAFETY_GUARDRAILS.md` before touching any patient-facing output code.
- Use skills in `/skills/` as behavioral contracts for each agent.
- Run `streamlit run frontend/streamlit_app.py` for the demo UI.
- Run `uvicorn src.api.main:app --reload` for the API server.

---

## Testing Approach

- Unit tests for each agent (mock LLM responses).
- Integration tests for RAG pipeline with sample documents.
- End-to-end smoke test via Streamlit for each triage path.
- Safety filter must have 100% test coverage on red-flag detection.

---

## Deployment Targets

| Environment | Method |
|---|---|
| Local dev | `docker-compose up` |
| Kaggle Demo | Kaggle Notebook + Streamlit |
| Cloud demo | Hugging Face Spaces |
| Production | Render / AWS ECS |
