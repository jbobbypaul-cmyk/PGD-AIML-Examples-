---
title: RuralCare AI
emoji: 🏥
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.35.0
app_file: app/streamlit_app.py
pinned: true
python_version: "3.11"
---

# RuralCare AI — Multi-Agent Rural Healthcare Assistant

> **Disclaimer:** RuralCare AI is a first-level health information and triage support tool. It does **not** diagnose, prescribe, or replace a licensed healthcare professional. All outputs are for informational guidance only. Always consult a doctor for medical decisions.

---

## What is RuralCare AI?

RuralCare AI is an open-source, multilingual, voice-enabled AI agent system designed to bridge the healthcare access gap in rural and underserved communities. It combines large language models, retrieval-augmented generation (RAG), and a multi-agent orchestration pipeline to provide:

- **Symptom intake** in the patient's native language
- **Safe triage guidance** — Emergency / Urgent / Moderate / Mild
- **RAG-grounded health information** from verified public health documents
- **Nearby clinic and facility discovery** (NHM static data + OpenStreetMap + Google Places)
- **Follow-up reminders and medication adherence support**
- **Health worker briefing notes** for ASHA / ANM / CHW workers
- **Automatic emergency escalation** with first-aid instructions
- **Full audit logging** for safety and compliance

---

## Why This Matters

In India alone, over 600 million people live in rural areas with limited access to primary health centers, specialist physicians, and health literacy resources. RuralCare AI acts as a **first-mile digital health assistant** — available 24/7, multilingual, voice-capable, and grounded in verified public health knowledge.

---

## Architecture Overview

```
Patient (Voice / Text)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Streamlit UI (port 8501)  │  FastAPI (port 8000)   │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│             LangGraph Orchestrator                   │
│                                                      │
│  START → [emergency keyword?] → emergency_escalation │
│  START → symptom_intake → medical_triage             │
│       → rag_agent → appointment_facility             │
│       → followup_adherence → health_worker_support   │
│       → audit_safety → END                          │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
  ChromaDB (RAG)         SQLite / PostgreSQL
  6 collections          sessions, audit_logs,
  cosine similarity      facility_cache,
  nomic-embed-text       followup_reminders
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) running locally with `llama3.2` and `nomic-embed-text` models
- OR an API key for Claude / OpenAI / Gemini (set `LLM_PROVIDER` in `.env`)

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and edit environment config
cp .env.example .env

# 3. Initialise the database and seed knowledge base
python -m app.rag.document_loader --sample

# 4. Run the Streamlit demo
python -m streamlit run app/streamlit_app.py

# 5. (Optional) Run the FastAPI server in a second terminal
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker-compose up --build
# Streamlit UI:  http://localhost:8501
# FastAPI docs:  http://localhost:8000/docs
# ReDoc:         http://localhost:8000/redoc
```

---

## Core Agents

| # | Agent | Role |
|---|---|---|
| 1 | Symptom Intake | Collects and structures patient-reported symptoms |
| 2 | Medical Triage | Classifies urgency: Emergency / Urgent / Moderate / Mild |
| 3 | Medical RAG | Retrieves evidence-based guidance from health documents |
| 4 | Appointment & Facility | Locates nearby clinics (NHM → OSM → Google Places) |
| 5 | Follow-up & Adherence | Generates structured follow-up plan and reminders |
| 6 | Health Worker Support | Produces briefing notes for ASHA/ANM/CHW workers |
| 7 | Emergency Escalation | Routes life-threatening cases to emergency services |
| 8 | Audit & Safety | Final gate — safety filter, disclaimer, audit log |

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Streamlit | Demo UI, port 8501 |
| Backend API | FastAPI + uvicorn | REST API, port 8000, auto Swagger docs |
| Agent Orchestration | LangGraph | Stateful graph, conditional routing, fail-safe wrappers |
| RAG Framework | LangChain | Retriever, prompt templates, LLM chaining |
| Vector DB | ChromaDB `PersistentClient` | Embedded, 6 collections, cosine similarity |
| Embeddings | Ollama `nomic-embed-text` | Local, ~768-dim; HuggingFace all-MiniLM fallback |
| LLM (default) | Ollama `llama3.2` | Local, no API key; switchable to Claude/GPT-4o/Gemini |
| Voice-to-Text | OpenAI Whisper (local) | `.wav/.mp3/.ogg`; install separately |
| Translation | Google Translate + langdetect | Input → English; response back-translated |
| Facility Data | SQLite + OSM + Google Places | 3-level hybrid lookup |
| Relational DB | SQLite (demo) / PostgreSQL (prod) | Sessions, audit, follow-ups, facility cache |
| Monitoring | LangSmith | Pipeline tracing (optional) |
| Deployment | Docker + Render / Hugging Face Spaces | |

---

## RAG Pipeline Summary

| Aspect | Detail |
|---|---|
| Chunking | Custom `chunk_text()` — 512-char window, 64-char overlap, separator-aware |
| Embedding | Ollama `nomic-embed-text` — local, no external API |
| Similarity | Cosine similarity via ChromaDB |
| Retrieval | Multi-collection sweep in priority order; deduplication by content |
| Collections | 6: WHO guidelines, NHM protocols, symptom mapping, drugs, emergency, schemes |
| Grounding | LLM uses **only** retrieved chunks — parametric knowledge forbidden |
| Emergency | Fast path — `emergency_protocols` only, top-3, no LLM overhead |
| Score threshold | Disabled (`None`) — Ollama cosine scores not normalised 0–1; volume cap used instead |

---

## FastAPI Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/intake` | Submit text symptoms — full pipeline |
| `POST` | `/api/v1/voice` | Upload audio — Whisper + full pipeline |
| `GET` | `/api/v1/facilities` | Facility lookup by district + state + triage |
| `GET` | `/api/v1/audit/{session_id}` | Session audit log |
| `GET` | `/api/v1/audit` | Recent audit entries |
| `POST` | `/api/v1/followup` | Schedule follow-up reminder |

Interactive docs: **http://localhost:8000/docs**

---

## AI Guardrail Principles

| Principle | Enforcement |
|---|---|
| Non-maleficence | LLM system prompt + independent regex safety filter on every output |
| Bounded scope | Disclaimer appended by code (not LLM); safe fallback when no RAG context |
| Grounding | LLM restricted to retrieved chunks only; `grounding_confidence` tracked |
| Proportionality | EMERGENCY bypasses LLM — hardcoded first-aid + emergency numbers shown |
| Privacy by design | `patient_token` in all LLM calls; SHA-256 hashes in audit log; PHI scrubbed from outputs |
| Auditability | `audit_safety_agent` is terminal node — always runs; every agent logs its entry |
| Fail safe | `_node` wrapper catches exceptions; errors produce safe fallback, never wrong response |

---

## Token and Privacy Strategy

- **Patient token** — `PT-{8 hex chars}` generated per session; used in all LLM prompts instead of real name
- **Input hashing** — raw text never stored; SHA-256 hash stored in audit log
- **PHI scrubbing** — phone numbers, Aadhaar (12-digit), email addresses redacted from LLM outputs
- **Local processing** — Whisper runs locally; embeddings via local Ollama; no audio or raw text sent externally

---

## Supported Languages

English · Hindi (हिंदी) · Tamil (தமிழ்) · Bengali (বাংলা) · Telugu (తెలుగు) · Kannada (ಕನ್ನಡ)

Input translated to English → processed → response back-translated to patient's language.

---

## Document Upload (Live via UI)

The Streamlit UI includes an upload panel at the bottom of the page:

| Upload Type | Format | Destination |
|---|---|---|
| Hospital list | CSV / Excel | SQLite `facility_cache` — immediately searchable |
| Medical knowledge | PDF / TXT / MD | ChromaDB collection of your choice — immediately retrievable |

Download the CSV template from the upload panel for the correct hospital data format.

---

## Safety & Compliance

- No diagnosis — only triage classification and grounded health information
- No prescription — specific drug names and dosages blocked by regex filter
- All responses grounded in RAG documents or clearly labelled as general guidance
- Automatic red-flag detection with emergency escalation (< 100ms, pre-LLM)
- Audit log on every interaction — SHA-256 hashes only, never raw text
- PHI anonymisation before every LLM call
- Mandatory disclaimer on every patient-facing output — enforced by code

See `SAFETY_GUARDRAILS.md` for full details.

---

## Project Documentation

| File | Description |
|---|---|
| `ARCHITECTURE.md` | Complete system architecture — agents, RAG, chunking, retrieval, FastAPI, guardrails |
| `SAFETY_GUARDRAILS.md` | Safety rules, compliance framework, guardrail principles |
| `AGENT_DESIGN.md` | Per-agent design specs and boundaries |
| `DATA_MODEL.md` | Database schemas and data models |
| `RAG_KNOWLEDGE_BASE.md` | Knowledge base design and document types |
| `TECH_STACK.md` | Technology choices and rationale |
| `WORKFLOW.md` | End-to-end interaction workflow |
| `KAGGLE_DEMO_PLAN.md` | Kaggle competition demo plan |
| `IMPLEMENTATION_ROADMAP.md` | MVP to production roadmap |
| `CLAUDE.md` | Claude Code project instructions |

---

## Contributing

This project follows a safety-first development approach. Before contributing:

1. Read `SAFETY_GUARDRAILS.md` completely.
2. Read `AGENT_DESIGN.md` to understand agent boundaries.
3. All PRs must include tests for safety filter changes.
4. No code that could produce medical diagnoses or prescriptions will be merged.

---

## License

MIT License — see `LICENSE` file.

---

## Acknowledgments

- WHO Health for All Framework
- National Health Mission (NHM) India guidelines
- OpenAI Whisper for local voice transcription
- LangChain and LangGraph teams
- ChromaDB team
- Ollama for local LLM and embedding inference
