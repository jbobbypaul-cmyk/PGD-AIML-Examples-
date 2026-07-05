# PROJECT_SCOPE.md — RuralCare AI

## Purpose

Define the boundaries, goals, non-goals, target users, and constraints of the RuralCare AI system so that every implementation decision can be evaluated against a clear reference.

---

## Problem Statement

Rural populations — particularly in India, Sub-Saharan Africa, and Southeast Asia — face a compound healthcare access crisis:

1. **Geographic distance** — PHCs and hospitals are hours away.
2. **Workforce shortage** — Doctor-to-patient ratios are critically low.
3. **Language barriers** — Most health information is in English or urban languages.
4. **Health literacy gaps** — Patients cannot distinguish emergencies from routine illness.
5. **Delayed escalation** — Patients wait too long before seeking care, causing preventable deaths.

RuralCare AI addresses these gaps as a **digital first-mile health assistant**.

---

## Scope

### In Scope

| Area | What is Included | Status |
|---|---|---|
| Symptom collection | Structured intake of patient-reported symptoms via voice or text | ✅ Complete |
| Triage classification | 4-level urgency: Emergency / Urgent / Moderate / Mild | ✅ Complete |
| Health information | RAG-grounded responses from verified public health documents | ✅ Complete |
| Facility discovery | Hybrid NHM static → OpenStreetMap → Google Places lookup | ✅ Complete |
| Follow-up support | Follow-up plan, adherence reminders, watch-for alerts | ✅ Complete |
| Health worker tools | Briefing notes for ASHA / ANM / CHW workers | ✅ Complete |
| Emergency escalation | Auto-escalation for life-threatening symptom patterns | ✅ Complete |
| Audit logging | Full interaction audit trail — SHA-256 hashes, never raw text | ✅ Complete |
| Multilingual support | 6 Indian languages + English (UI + Google Translate) | ✅ Complete |
| Voice input | Whisper-based transcription of audio uploads | ✅ Complete (optional install) |
| Demo deployment | Streamlit UI (port 8501) + FastAPI (port 8000) + Kaggle Notebook | ✅ Complete |
| Document upload | Hospital CSV/Excel → SQLite; Medical PDF/TXT → ChromaDB | ✅ Complete |
| Tamil Nadu hospitals | 87 government hospitals seeded across 38 districts | ✅ Complete |
| Local LLM support | Ollama llama3.2 (default) — no API key required | ✅ Complete |

### Out of Scope

| Area | Why Excluded |
|---|---|
| Medical diagnosis | Requires licensed physician — legally and ethically out of bounds |
| Prescription generation | Requires licensed prescriber — hard out of scope |
| Real-time telemedicine | Requires video infrastructure, not in v1 |
| Real patient data storage | Requires full HIPAA/DPDP compliance — phased in production only |
| Insurance claims | Out of scope for this health assistant |
| Drug interaction checking | Requires pharmacy-grade clinical database — future phase |
| Specialist referral matching | Complex matching logic — future phase |
| EHR integration | Requires HL7/FHIR compliance layer — future phase |

---

## Target Users

### Primary Users

| User | Description |
|---|---|
| Rural patient | 18–70 years, limited English, may have only a basic smartphone |
| Caregiver | Family member managing a patient's care |
| Community health worker (ASHA/ANM/CHW) | Trained frontline health workers using the tool to triage and brief patients |

### Secondary Users

| User | Description |
|---|---|
| District health officer | Reviews aggregated triage data and alerts |
| Public health researcher | Analyses de-identified symptom trends |
| NGO health program staff | Deploys RuralCare AI in field programs |

---

## System Boundaries

```
╔══════════════════════════════════════════════════════════╗
║                    INSIDE RURALCARE AI                   ║
║                                                          ║
║  Symptom intake → Triage → Health Info → Facility →      ║
║  Follow-up → Health Worker Briefing → Emergency Alert    ║
║  → Audit Log                                             ║
║  Document Upload → SQLite / ChromaDB                     ║
╚══════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════╗
║                    OUTSIDE (External Systems)            ║
║                                                          ║
║  • Actual medical diagnosis (doctor)                     ║
║  • Prescription management (pharmacist)                  ║
║  • Emergency dispatch (112/ambulance service)            ║
║  • Hospital EHR systems                                  ║
║  • Insurance systems                                     ║
╚══════════════════════════════════════════════════════════╝
```

---

## Constraints

### Technical

- LLM responses must be latency-optimized for low-bandwidth rural connectivity.
- ChromaDB must run locally (embedded `PersistentClient`) for offline/Kaggle demo scenarios.
- Streamlit app must run on a single CPU Kaggle/Colab notebook.
- SQLite used for demo; PostgreSQL-ready schema design.
- Ollama used as default LLM (local, no API cost); Claude/OpenAI/Gemini available via `LLM_PROVIDER` env var.
- Python 3.14 compatibility: `RecursiveCharacterTextSplitter` replaced by custom `chunk_text()` due to spacy wheel incompatibility.
- Windows: `PYTHONUTF8=1` required to avoid `cp1252` encoding errors.

### Ethical / Legal

- Must comply with India's Digital Personal Data Protection Act (DPDP) 2023 principles.
- Must not claim to be a doctor or medical professional.
- Every patient-facing message must carry a disclaimer.
- PHI anonymization is mandatory before any LLM call.

### Safety

- Red-flag symptom detection must run synchronously, before any LLM call.
- Emergency escalation must complete before any other agent response is shown.
- The system must gracefully degrade — if the LLM is unavailable, show verified static triage guidelines.
- All LLM outputs pass through regex safety filter before reaching the patient.

---

## Success Metrics

| Metric | MVP Target | Production Target |
|---|---|---|
| Triage accuracy vs. clinical benchmark | > 80% | > 92% |
| Emergency escalation sensitivity | > 95% | > 99% |
| Average response latency | < 8 seconds | < 3 seconds |
| Language coverage | 6 languages | 12+ languages |
| Audit log completeness | 100% | 100% |
| Safety filter false negative rate | < 1% | < 0.1% |
| Uptime | 95% | 99.9% |

---

## Assumptions

1. Patients have access to a smartphone with basic internet (2G/3G at minimum).
2. Voice input is optional — text must always work.
3. The system is not a legal medical device in the regulatory sense for demo purposes.
4. Knowledge base documents are sourced from publicly available WHO/NHM/CDC materials.
5. The first deployment target is India (English + Hindi + 4 regional languages).
6. Ollama is available on developer machines; cloud deployments may use Claude/OpenAI API.

---

## Dependencies

| Dependency | Type | Risk |
|---|---|---|
| Ollama (local LLM) | Open source | Model size; not available on Kaggle — use Claude/OpenAI API there |
| LLM API (Claude/OpenAI/Gemini) | External | API cost, availability |
| Whisper | Open source | Model size, CPU requirements; separate install |
| IndicTrans2 | Open source | Setup complexity; Google Translate used in current version |
| ChromaDB | Open source | Index size on large knowledge bases |
| OpenStreetMap Nominatim | Free API | Rate limits (1 req/sec) |
| LangSmith | SaaS | Optional; cost for high-volume tracing |

---

## Acceptance Criteria (MVP) — STATUS

- [x] Patient can enter symptoms in text and receive triage classification.
- [x] Emergency symptoms trigger an escalation alert before all other responses.
- [x] RAG pipeline retrieves a relevant document chunk for at least 80% of common symptom queries.
- [x] Facility search returns actual hospital name and details (NHM TN → OSM → Google Places).
- [x] Follow-up plan generated for MODERATE and URGENT cases; Health Worker Briefing for all non-emergency.
- [x] Audit log captures every interaction with timestamp and triage level.
- [x] At least 3 languages demonstrated (English, Hindi, Tamil, Bengali, Telugu, Kannada).
- [x] Safety filter blocks any LLM output containing a diagnosis or prescription.
- [x] Disclaimer appears on every patient-facing response.
- [x] Full demo runs via `streamlit run app/streamlit_app.py` with no external server required.
- [x] Document upload: hospital CSV → SQLite, medical PDF → ChromaDB.
- [x] 87 Tamil Nadu hospitals seeded and queryable by district (case-insensitive).
- [x] FastAPI running on port 8000 with Swagger docs at `/docs`.
