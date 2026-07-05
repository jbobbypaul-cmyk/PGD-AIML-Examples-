"""
Generate RuralCare AI project documentation as a Word (.docx) file.
Run: python scripts/generate_docs.py
Output: RuralCare_AI_Documentation.docx (in project root)
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

# ── helpers ──────────────────────────────────────────────────────────────────

def add_heading(doc, text, level=1):
    h = doc.add_heading(text, level=level)
    h.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = h.runs[0] if h.runs else h.add_run(text)
    if level == 1:
        run.font.color.rgb = RGBColor(0x1A, 0x53, 0x76)   # dark blue
    elif level == 2:
        run.font.color.rgb = RGBColor(0x2E, 0x86, 0xAB)   # teal
    else:
        run.font.color.rgb = RGBColor(0x47, 0x47, 0x47)   # dark grey
    return h

def add_para(doc, text, bold=False, italic=False, size=11):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    return p

def add_bullet(doc, text, level=0):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.25 * (level + 1))
    run = p.add_run(text)
    run.font.size = Pt(11)
    return p

def add_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # Header row
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        run = hdr_cells[i].paragraphs[0].runs[0]
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tc = hdr_cells[i]._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), "1A5376")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:val"), "clear")
        tcPr.append(shd)

    # Data rows
    for r_idx, row_data in enumerate(rows):
        cells = table.rows[r_idx + 1].cells
        for c_idx, cell_text in enumerate(row_data):
            cells[c_idx].text = str(cell_text)
            if r_idx % 2 == 1:
                tc = cells[c_idx]._tc
                tcPr = tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd")
                shd.set(qn("w:fill"), "EBF5FB")
                shd.set(qn("w:color"), "auto")
                shd.set(qn("w:val"), "clear")
                tcPr.append(shd)

    if col_widths:
        for row in table.rows:
            for i, width in enumerate(col_widths):
                row.cells[i].width = Inches(width)

    return table

def add_code_block(doc, code_text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(code_text)
    run.font.name = "Courier New"
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x1C, 0x1C, 0x1C)
    # light grey background via shading on paragraph
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), "F4F6F7")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:val"), "clear")
    pPr.append(shd)
    return p

def add_callout(doc, text, bg="FEF9E7"):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.right_indent = Inches(0.3)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), bg)
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:val"), "clear")
    pPr.append(shd)
    return p

# ── build document ────────────────────────────────────────────────────────────

doc = Document()

# Page margins
for section in doc.sections:
    section.top_margin    = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)

# Default body font
doc.styles["Normal"].font.name = "Calibri"
doc.styles["Normal"].font.size = Pt(11)

# ─────────────────────────────────────────────────────────────────────────────
# COVER
# ─────────────────────────────────────────────────────────────────────────────
doc.add_picture   # skip cover image — add title directly
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("RuralCare AI")
r.bold = True
r.font.size = Pt(32)
r.font.color.rgb = RGBColor(0x1A, 0x53, 0x76)

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
r2 = subtitle.add_run("Multi-Agent Rural Healthcare Assistant")
r2.font.size = Pt(18)
r2.font.color.rgb = RGBColor(0x2E, 0x86, 0xAB)

doc.add_paragraph()
tagline = doc.add_paragraph()
tagline.alignment = WD_ALIGN_PARAGRAPH.CENTER
r3 = tagline.add_run(
    "A first-mile digital health assistant for rural and underserved communities.\n"
    "Symptom Triage · RAG-Grounded Health Guidance · Facility Discovery · Emergency Escalation"
)
r3.font.size = Pt(12)
r3.italic = True
r3.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

doc.add_paragraph()
meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta.add_run("Version: 1.0 (MVP Complete)   |   Platform: Python 3.14 · FastAPI · Streamlit · LangGraph · ChromaDB · Ollama")
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXECUTIVE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "1. Executive Summary", 1)
add_para(doc,
    "RuralCare AI is an open-source, multilingual, voice-enabled AI agent system designed to "
    "bridge the healthcare access gap in rural and underserved communities. It acts as a "
    "first-mile digital health assistant — available 24/7, multilingual, and grounded in "
    "verified public health knowledge from WHO and India's National Health Mission (NHM)."
)
doc.add_paragraph()
add_callout(doc,
    "⚠️  IMPORTANT: RuralCare AI is NOT a diagnostic tool and does NOT replace a licensed "
    "healthcare professional. All outputs are for informational guidance only.",
    bg="FDECEA"
)
doc.add_paragraph()

add_heading(doc, "Problem Being Solved", 2)
rows = [
    ("Geographic distance",  "PHCs and hospitals are hours away from rural communities"),
    ("Workforce shortage",   "Doctor-to-patient ratios are critically low in rural India"),
    ("Language barriers",    "Most health information is in English or urban languages only"),
    ("Health literacy gaps", "Patients cannot distinguish emergencies from routine illness"),
    ("Delayed escalation",   "Patients wait too long before seeking care — preventable deaths"),
]
add_table(doc, ["Challenge", "Impact"], rows, col_widths=[2.5, 4.0])
doc.add_paragraph()

add_heading(doc, "What RuralCare AI Does", 2)
bullets = [
    "Collects and structures patient-reported symptoms (text or voice)",
    "Classifies urgency: Emergency / Urgent / Moderate / Mild",
    "Retrieves evidence-based health guidance from WHO and NHM documents (RAG)",
    "Locates the nearest government clinic or hospital",
    "Generates a personalized follow-up care plan",
    "Produces a briefing note for ASHA / ANM / CHW health workers",
    "Auto-escalates life-threatening emergencies with first-aid instructions",
    "Logs every interaction with full audit trail for safety and compliance",
]
for b in bullets:
    add_bullet(doc, b)
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 2. KEY HIGHLIGHTS
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "2. Key Highlights", 1)

highlights = [
    ("🏥  Multilingual Support",
     "English, Hindi, Tamil, Bengali, Telugu, Kannada — patient input detected and "
     "translated automatically; response delivered in the patient's language."),
    ("🎙️  Voice Input",
     "OpenAI Whisper runs locally on the server — no audio is sent to external services. "
     "Supports .wav, .mp3, .ogg uploads."),
    ("🤖  8-Agent Pipeline",
     "LangGraph state machine with 8 specialist agents: Symptom Intake, Medical Triage, "
     "RAG Knowledge, Facility Lookup, Follow-up, Health Worker Briefing, Emergency Escalation, "
     "and Audit & Safety."),
    ("📚  RAG-Grounded Responses",
     "Every health answer is retrieved from 6 ChromaDB collections (WHO, NHM, emergency "
     "protocols, symptom mapping, drug info, health schemes) — the LLM is forbidden from "
     "improvising medical facts."),
    ("🚨  Sub-100ms Emergency Detection",
     "Emergency red-flag detection runs synchronously before any LLM call — purely rule-based "
     "keyword scan. Life-threatening symptoms trigger immediate escalation with 112/108 contacts."),
    ("🏛️  87 Tamil Nadu Hospitals",
     "Government hospitals and PHCs across all 38 Tamil Nadu districts pre-loaded in SQLite, "
     "with OpenStreetMap and Google Places as fallback layers."),
    ("🔒  Privacy by Design",
     "Patient names and contact details never enter LLM prompts. Anonymized tokens "
     "(PT-xxxxxxxx) used throughout. Audit logs store SHA-256 hashes only."),
    ("📤  Live Document Upload",
     "Hospital CSV/Excel files load directly into the facility database; medical PDF/TXT files "
     "are chunked and indexed into ChromaDB — both instantly searchable."),
    ("💻  Local LLM (No API Cost)",
     "Default LLM is Ollama llama3.2 running locally — free, offline, no API key needed. "
     "Switchable to Claude, GPT-4o, or Gemini by changing one environment variable."),
    ("⚖️  5-Layer Safety Architecture",
     "Pre-LLM keyword detection → Emergency agent → LLM system prompt constraints → "
     "Regex output filter → Audit safety agent. No diagnosis or prescription possible."),
]

for title_text, desc in highlights:
    p = doc.add_paragraph()
    r_title = p.add_run(title_text + "  ")
    r_title.bold = True
    r_title.font.size = Pt(12)
    r_title.font.color.rgb = RGBColor(0x1A, 0x53, 0x76)
    r_desc = p.add_run(desc)
    r_desc.font.size = Pt(11)
    p.paragraph_format.space_after = Pt(6)

doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 3. HOW TO USE IT
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "3. How to Use RuralCare AI", 1)

add_heading(doc, "3.1  Quick Setup (Local)", 2)
add_para(doc, "Prerequisites: Python 3.10+, Ollama installed (https://ollama.ai)")
doc.add_paragraph()
steps = [
    ("Step 1 — Pull LLM models",
     "ollama pull llama3.2\nollama pull nomic-embed-text"),
    ("Step 2 — Install dependencies",
     "pip install -r requirements.txt"),
    ("Step 3 — Configure environment",
     "copy .env.example .env\n# Edit .env to set absolute paths for SQLITE_PATH and CHROMA_DB_PATH"),
    ("Step 4 — Initialize database",
     "python scripts/seed_tn_hospitals.py"),
    ("Step 5 — Load sample knowledge base",
     "python -m app.rag.document_loader --sample"),
    ("Step 6 — Run Streamlit demo UI",
     "$env:PYTHONUTF8='1'\npython -m streamlit run app/streamlit_app.py"),
    ("Step 7 — (Optional) Run FastAPI",
     "$env:PYTHONUTF8='1'\npython -m uvicorn app.main:app --reload --port 8000"),
]
for step_label, step_code in steps:
    add_para(doc, step_label, bold=True)
    add_code_block(doc, step_code)
    doc.add_paragraph()

add_heading(doc, "3.2  Using the Streamlit UI (port 8501)", 2)
add_para(doc,
    "Open http://localhost:8501 in your browser. The interface has three main areas:"
)
ui_rows = [
    ("Sidebar",       "Select language (English/Hindi/Tamil/Bengali/Telugu/Kannada), Input mode (Text/Voice), and Quick Demo buttons"),
    ("Main input",    "Type symptoms in the text box; enter District and State for facility lookup; click 'Get Health Guidance'"),
    ("Results panel", "Triage Level metric, Emergency Alert, Health Guidance, Facility cards, Follow-up Plan, Health Worker Briefing"),
    ("Upload panel",  "Expand 'Upload Document' at the bottom to add hospital CSV files or medical PDF/TXT knowledge documents"),
]
add_table(doc, ["Area", "What to do"], ui_rows, col_widths=[1.8, 4.8])
doc.add_paragraph()

add_heading(doc, "3.3  Quick Demo Scenarios", 2)
demo_rows = [
    ("Demo 1", "Mild",       "Headache + tiredness",          "MILD — rest and monitor at home"),
    ("Demo 2", "Moderate",   "Fever 3 days + body aches",     "MODERATE — visit PHC within 48 hours"),
    ("Demo 3", "Urgent",     "Chest pain + 2 weeks cough",    "URGENT — see a doctor within 2–4 hours"),
    ("Demo 4", "Emergency",  "Unconscious, cannot breathe",   "EMERGENCY — call 112 immediately"),
    ("Demo 5", "Multilingual","Hindi fever + headache input",  "MODERATE — response returned in Hindi"),
]
add_table(doc, ["Button", "Triage", "Input", "Expected Output"], demo_rows,
          col_widths=[0.8, 1.0, 2.2, 2.6])
doc.add_paragraph()

add_heading(doc, "3.4  FastAPI Endpoints (port 8000)", 2)
add_para(doc, "Open http://localhost:8000/docs for interactive Swagger UI.")
api_rows = [
    ("GET",  "/health",                  "Liveness probe — confirms server is running"),
    ("POST", "/api/v1/intake",           "Submit text symptoms — runs full 8-agent pipeline"),
    ("POST", "/api/v1/voice",            "Upload audio file — Whisper transcription + pipeline"),
    ("GET",  "/api/v1/facilities",       "Facility lookup by district, state, triage level"),
    ("GET",  "/api/v1/audit/{session_id}","Retrieve audit log for a specific session"),
    ("GET",  "/api/v1/audit",            "List recent audit entries (paginated)"),
    ("POST", "/api/v1/followup",         "Schedule a follow-up reminder"),
]
add_table(doc, ["Method", "Endpoint", "Purpose"], api_rows, col_widths=[0.7, 2.8, 3.1])
doc.add_paragraph()

add_heading(doc, "3.5  Uploading Documents", 2)
add_para(doc,
    "The upload panel at the bottom of the Streamlit UI supports two document types:"
)
upload_rows = [
    ("Hospital list", "CSV or Excel (.csv, .xlsx, .xls)",
     "Adds hospitals to SQLite facility_cache — immediately searchable",
     "name, facility_type, district, state (required)"),
    ("Medical knowledge", "PDF, TXT, or Markdown (.pdf, .txt, .md)",
     "Chunks and indexes into ChromaDB — immediately retrievable in RAG",
     "Any WHO/NHM health document"),
]
add_table(doc, ["Type", "Format", "Effect", "Notes"], upload_rows,
          col_widths=[1.2, 1.5, 2.4, 1.5])
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 4. ARCHITECTURE
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "4. Architecture Overview", 1)

add_para(doc,
    "RuralCare AI is a multi-agent system orchestrated by LangGraph. Patient input flows "
    "through 8 specialist agents in sequence. Each agent reads from and writes to a shared "
    "PatientState object. A fail-safe wrapper around every agent ensures that a single "
    "failure never crashes the pipeline."
)
doc.add_paragraph()

add_heading(doc, "4.1  System Layers", 2)
arch_rows = [
    ("Patient Interface",   "Streamlit UI (port 8501) · FastAPI REST API (port 8000)"),
    ("Orchestration",       "LangGraph StateGraph — 8 nodes, conditional emergency routing, fail-safe _node wrapper"),
    ("LLM Layer",           "Ollama llama3.2 (default, local) · Claude · GPT-4o · Gemini (switchable via LLM_PROVIDER env)"),
    ("RAG / Knowledge",     "ChromaDB PersistentClient — 6 collections, cosine similarity, Ollama nomic-embed-text embeddings (~768-dim)"),
    ("Facility Lookup",     "SQLite NHM TN cache (87 hospitals) → OpenStreetMap Overpass → Google Places (3-level hybrid)"),
    ("Database",            "SQLite (demo) / PostgreSQL (production) — sessions, audit_logs, facility_cache, followup_reminders"),
    ("Voice",               "OpenAI Whisper (local) — .wav/.mp3/.ogg, no audio sent externally"),
    ("Translation",         "langdetect (detection) + Google Translate (translation to/from English)"),
    ("Safety",              "5-layer: pre-LLM keyword scan → emergency agent → LLM prompt → regex filter → audit gate"),
]
add_table(doc, ["Layer", "Technology"], arch_rows, col_widths=[1.8, 4.8])
doc.add_paragraph()

add_heading(doc, "4.2  The 8 Agents", 2)
agents_rows = [
    ("1", "Symptom Intake",       "Extracts structured symptoms from free-form text/voice. Runs emergency keyword check BEFORE any LLM call."),
    ("2", "Medical Triage",       "Classifies urgency: EMERGENCY / URGENT / MODERATE / MILD using WHO ICD-11 principles."),
    ("3", "Medical RAG",          "Queries 6 ChromaDB collections, assembles context, generates grounded health guidance via LLM."),
    ("4", "Appointment & Facility","3-level hybrid lookup: NHM TN SQLite → OSM Overpass → Google Places. Returns top 3 facilities."),
    ("5", "Follow-up & Adherence","Generates structured follow-up plan: watch-for items, home care, return-immediately triggers."),
    ("6", "Health Worker Support","Produces ASHA/ANM briefing note with patient token, triage, symptoms, recommended action, health schemes."),
    ("7", "Emergency Escalation", "Triggered pre-LLM on keyword detection. Shows 112/108, first-aid from RAG, nearest hospital."),
    ("8", "Audit, Safety & Compliance","Final gate: regex safety filter, disclaimer injection, SHA-256 audit log. Always runs, even on failure."),
]
add_table(doc, ["#", "Agent", "Role"], agents_rows, col_widths=[0.3, 1.9, 4.4])
doc.add_paragraph()

add_heading(doc, "4.3  RAG Pipeline", 2)
rag_rows = [
    ("Embedding model",   "Ollama nomic-embed-text (~768-dim) — local, no API cost"),
    ("Vector database",   "ChromaDB PersistentClient — embedded, no server needed"),
    ("Collections",       "6: who_health_guidelines, nhm_india_protocols, symptom_disease_mapping, drug_information_basic, emergency_protocols, regional_health_schemes"),
    ("Chunking",          "Custom chunk_text() — 512-char window, 64-char overlap, separator-aware (paragraph → sentence → word)"),
    ("Retrieval",         "Multi-collection cosine sweep in priority order; deduplicated by content hash"),
    ("Score threshold",   "None — Ollama cosine scores are not normalised 0-1; volume cap (k=5) used instead"),
    ("Grounding rule",    "LLM uses ONLY retrieved context — parametric knowledge forbidden"),
    ("Emergency path",    "emergency_protocols collection only, top-3 chunks, bypasses multi-collection sweep for speed"),
]
add_table(doc, ["Aspect", "Detail"], rag_rows, col_widths=[1.8, 4.8])
doc.add_paragraph()

add_heading(doc, "4.4  Data Flow Summary", 2)
flow_text = (
    "Patient input (text/voice)\n"
    "  → Language detection + Google Translate to English\n"
    "  → PHI anonymization (PT-xxxxxxxx token assigned)\n"
    "  → LangGraph Orchestrator\n"
    "     → [Emergency?] YES → Emergency Escalation → Audit → Response\n"
    "     → [Normal]         → Symptom Intake\n"
    "                           → Medical Triage\n"
    "                             → Medical RAG (6-collection sweep)\n"
    "                               → Facility Lookup (SQLite → OSM → Google)\n"
    "                                 → Follow-up Plan\n"
    "                                   → Health Worker Briefing\n"
    "                                     → Audit & Safety (regex filter + log)\n"
    "  → Translate response back to patient language\n"
    "  → Streamlit UI display / FastAPI JSON response"
)
add_code_block(doc, flow_text)
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 5. SAFETY & GUARDRAILS
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "5. Safety & Guardrails", 1)

add_callout(doc,
    "These rules are non-negotiable and apply to every component of the system.",
    bg="FDECEA"
)
doc.add_paragraph()

add_heading(doc, "5.1  What RuralCare AI Will Never Do", 2)
never_rows = [
    ("Diagnose",    "Will never say 'You have malaria' or any equivalent"),
    ("Prescribe",   "Will never recommend prescription drugs or dosages"),
    ("Skip disclaimer", "Every patient response includes the standard safety disclaimer"),
    ("Delay emergency", "Emergency contacts shown immediately — before any other output"),
    ("Store PHI",   "Patient names/contacts never stored; anonymized tokens only"),
    ("Improvise medicine", "LLM forbidden from using parametric knowledge for medical facts"),
]
add_table(doc, ["Prohibited Action", "Enforcement"], never_rows, col_widths=[2.0, 4.6])
doc.add_paragraph()

add_heading(doc, "5.2  7 AI Guardrail Principles", 2)
guardrail_rows = [
    ("Non-maleficence",   "LLM system prompt constraints + independent regex safety filter on every output"),
    ("Bounded scope",     "Disclaimer appended by code (not LLM); safe fallback when no RAG context found"),
    ("Grounding",         "LLM restricted to retrieved document chunks only; rag_sources tracked per response"),
    ("Proportionality",   "EMERGENCY bypasses LLM entirely — hardcoded first-aid + 112/108 shown immediately"),
    ("Privacy by design", "patient_token in all LLM calls; SHA-256 hashes in audit log; PHI scrubbed"),
    ("Auditability",      "audit_safety_agent is terminal node — always runs; every agent writes its log entry"),
    ("Fail safe",         "_node wrapper catches exceptions; errors produce safe fallback, never wrong response"),
]
add_table(doc, ["Principle", "How it is enforced"], guardrail_rows, col_widths=[1.8, 4.8])
doc.add_paragraph()

add_heading(doc, "5.3  Emergency Red-Flag Categories", 2)
emergency_rows = [
    ("Cardiovascular / Respiratory", "chest pain, cannot breathe, difficulty breathing, heart attack"),
    ("Neurological",                 "unconscious, seizure, stroke, sudden vision loss, sudden severe headache"),
    ("Severe Bleeding",              "severe bleeding, blood vomiting, coughing blood"),
    ("Poisoning / Envenomation",     "snake bite, poisoning, swallowed poison, insecticide ingestion"),
    ("Obstetric Emergency",          "heavy vaginal bleeding during pregnancy, eclampsia, baby not moving"),
    ("Pediatric Emergency",          "child not breathing, baby turning blue, high fever with rash and stiff neck"),
]
add_table(doc, ["Category", "Example Keywords"], emergency_rows, col_widths=[2.2, 4.4])
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 6. TECH STACK
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "6. Technology Stack", 1)

tech_rows = [
    ("Frontend",            "Streamlit 1.58.0",         "Demo UI on port 8501; multilingual, voice-upload capable"),
    ("Backend API",         "FastAPI + uvicorn",         "7 REST endpoints, auto Swagger docs at /docs, port 8000"),
    ("Agent Orchestration", "LangGraph",                 "8-node state graph, conditional routing, fail-safe wrappers"),
    ("RAG Framework",       "LangChain",                 "Retriever chains, prompt templates, LCEL composition"),
    ("Vector DB",           "ChromaDB PersistentClient", "6 collections, cosine similarity, embedded (no server)"),
    ("Embeddings",          "Ollama nomic-embed-text",   "Local ~768-dim; free, offline"),
    ("LLM (default)",       "Ollama llama3.2",           "Local inference, no API key; ~2GB download"),
    ("LLM (alts)",          "Claude / GPT-4o / Gemini",  "Set LLM_PROVIDER=claude|openai|gemini in .env"),
    ("Voice-to-text",       "OpenAI Whisper (local)",    "Runs on-device; supports 99 languages incl. all Indian"),
    ("Translation",         "Google Translate + langdetect","Input to English + back-translation"),
    ("Facility data",       "SQLite + OSM + Google Places","3-level hybrid; 87 TN hospitals pre-seeded"),
    ("Database",            "SQLite (demo) / PostgreSQL","Sessions, audit_logs, facility_cache, followup_reminders"),
    ("Chunking",            "Custom chunk_text()",       "512-char window, 64-char overlap, no spacy dependency"),
    ("Monitoring",          "LangSmith (optional)",      "Full pipeline traces; set LANGSMITH_API_KEY in .env"),
    ("Python",              "3.14 (tested) / 3.10+",    "Windows 11, PYTHONUTF8=1 required"),
]
add_table(doc, ["Layer", "Technology", "Notes"], tech_rows, col_widths=[1.8, 2.2, 2.6])
doc.add_paragraph()

add_heading(doc, "Switching the LLM", 2)
add_code_block(doc,
    "# In .env — no code changes required:\n"
    "LLM_PROVIDER=ollama          # local, free (default)\n"
    "LLM_PROVIDER=claude          # requires ANTHROPIC_API_KEY\n"
    "LLM_PROVIDER=openai          # requires OPENAI_API_KEY\n"
    "LLM_PROVIDER=gemini          # requires GOOGLE_API_KEY"
)
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 7. BENEFITS
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "7. Benefits", 1)

add_heading(doc, "For Patients", 2)
patient_benefits = [
    "Available 24/7 without travel to a clinic",
    "Works in their native language (6 Indian languages)",
    "Identifies emergencies immediately — no waiting",
    "Provides actionable guidance grounded in WHO/NHM documents",
    "Locates the nearest government facility with contact details",
    "Generates a simple follow-up plan to monitor recovery",
    "Voice input supports low-literacy users",
]
for b in patient_benefits:
    add_bullet(doc, b)

doc.add_paragraph()
add_heading(doc, "For Health Workers (ASHA / ANM / CHW)", 2)
hw_benefits = [
    "Automated structured briefing note ready before the home visit",
    "Patient token, triage level, chief complaint, watch-for items all pre-populated",
    "Relevant government health schemes (PM-JAY, JSSK, NTEP) flagged automatically",
    "Reduces manual note-taking and cognitive load during triage",
]
for b in hw_benefits:
    add_bullet(doc, b)

doc.add_paragraph()
add_heading(doc, "For Health Program Administrators", 2)
admin_benefits = [
    "Full audit trail on every interaction — SHA-256 hashed, append-only",
    "Aggregate triage data for district health planning",
    "Add new hospitals via CSV upload — no developer required",
    "Add new medical knowledge via PDF upload — immediately retrievable",
    "Configurable LLM (local Ollama for cost savings or cloud for quality)",
    "Docker-ready for deployment on Render, AWS, or Hugging Face Spaces",
]
for b in admin_benefits:
    add_bullet(doc, b)

doc.add_paragraph()
add_heading(doc, "Technical Benefits", 2)
tech_benefits = [
    "No diagnosis or prescription possible — enforced at code level, not just prompt level",
    "Privacy by design — patient identifiers never reach the LLM",
    "Fail-safe architecture — a single agent failure produces a safe fallback, not a crash",
    "Offline-capable with Ollama — runs without internet for LLM inference",
    "Modular — each agent is independently testable and replaceable",
    "Production-path clear — SQLite → PostgreSQL, Streamlit → React, demo → cloud",
]
for b in tech_benefits:
    add_bullet(doc, b)
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 8. PROJECT SCOPE
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "8. Project Scope", 1)

add_heading(doc, "In Scope (MVP Complete)", 2)
in_scope_rows = [
    ("Symptom collection",     "Structured intake via text or voice upload"),
    ("Triage classification",  "4 levels: Emergency / Urgent / Moderate / Mild"),
    ("Health information",     "RAG-grounded from 6 ChromaDB collections (WHO + NHM)"),
    ("Facility discovery",     "NHM Tamil Nadu (87 hospitals) + OpenStreetMap + Google Places"),
    ("Follow-up support",      "Follow-up plan with watch-for alerts and home care tips"),
    ("Health worker tools",    "Structured briefing note for ASHA/ANM/CHW"),
    ("Emergency escalation",   "Auto-escalation with 112/108 and first-aid from RAG"),
    ("Audit logging",          "Full interaction audit trail — SHA-256 hashes only"),
    ("Multilingual",           "6 Indian languages + English (UI + Google Translate pipeline)"),
    ("Voice input",            "Whisper-based local transcription (optional install)"),
    ("Demo deployment",        "Streamlit UI (port 8501) + FastAPI (port 8000)"),
    ("Document upload",        "Hospital CSV → SQLite; Medical PDF/TXT → ChromaDB"),
]
add_table(doc, ["Feature", "Implementation"], in_scope_rows, col_widths=[2.2, 4.4])
doc.add_paragraph()

add_heading(doc, "Out of Scope", 2)
out_scope_rows = [
    ("Medical diagnosis",       "Requires licensed physician — legally and ethically out of bounds"),
    ("Prescription generation", "Requires licensed prescriber — hard out of scope"),
    ("Real-time telemedicine",  "Requires video infrastructure — future phase"),
    ("EHR integration",         "Requires HL7/FHIR compliance layer — future phase"),
    ("Drug interaction checking","Requires pharmacy-grade database — future phase"),
]
add_table(doc, ["Feature", "Reason"], out_scope_rows, col_widths=[2.2, 4.4])
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 9. DEPLOYMENT & ROADMAP
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "9. Deployment & Roadmap", 1)

add_heading(doc, "Current Deployment Targets", 2)
deploy_rows = [
    ("Local dev",      "docker-compose up  OR  streamlit run app/streamlit_app.py",        "Complete"),
    ("Kaggle Demo",    "Kaggle Notebook — in-notebook pipeline, Claude API as LLM",         "Ready"),
    ("Hugging Face",   "Streamlit SDK Space — ANTHROPIC_API_KEY as HF secret",              "Pending"),
    ("Render / AWS",   "Docker container — FastAPI + Streamlit behind nginx",               "Pending"),
]
add_table(doc, ["Environment", "Method", "Status"], deploy_rows, col_widths=[1.5, 3.8, 1.0])
doc.add_paragraph()

add_heading(doc, "Implementation Roadmap Status", 2)
roadmap_rows = [
    ("Phase 0", "Foundation",             "Config, SQLite schema, safety filter, data models",     "✅ Complete"),
    ("Phase 1", "Core Agents",            "8 agents, LangGraph orchestrator, LLM factory",         "✅ Complete"),
    ("Phase 2", "RAG Pipeline",           "ChromaDB, chunk_text(), 6 collections, retriever",      "✅ Complete"),
    ("Phase 3", "Complete Pipeline",      "Facility agent, follow-up, health worker, 87 TN hospitals","✅ Complete"),
    ("Phase 4", "Frontend + Demo",        "Streamlit UI, document upload, FastAPI, demo buttons",  "✅ Complete"),
    ("Phase 5", "Multilingual + Voice",   "Translation + 6 languages; Whisper (optional install)", "⚠️  Partial"),
    ("Phase 6", "Production Hardening",   "FastAPI running; JWT/rate-limiting/PostgreSQL pending", "⚠️  Partial"),
    ("Phase 7", "Deployment",             "HF Spaces / Render / CI/CD pipeline",                   "⏳ Pending"),
]
add_table(doc, ["Phase", "Name", "Scope", "Status"], roadmap_rows,
          col_widths=[0.6, 1.6, 3.2, 1.0])
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 10. TARGET USERS
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "10. Target Users", 1)

add_heading(doc, "Primary Users", 2)
primary_rows = [
    ("Rural patient",           "18–70 years, limited English, basic smartphone",
     "Type or speak symptoms in their language; receive triage guidance and facility details"),
    ("Caregiver",               "Family member managing a patient's care",
     "Use on behalf of patient; share follow-up plan and facility contact"),
    ("ASHA / ANM / CHW",        "Trained frontline health workers",
     "Receive structured briefing note before home visits; use health scheme info"),
]
add_table(doc, ["User", "Profile", "Primary Use"], primary_rows, col_widths=[1.5, 2.0, 3.1])
doc.add_paragraph()

add_heading(doc, "Secondary Users", 2)
secondary_rows = [
    ("District health officer", "Reviews aggregated triage data and emergency patterns"),
    ("Public health researcher","Analyses de-identified symptom trends from audit log"),
    ("NGO health program staff","Deploys RuralCare AI in field programs; uploads local hospital lists"),
]
add_table(doc, ["User", "Use"], secondary_rows, col_widths=[2.2, 4.4])
doc.add_page_break()


# ─────────────────────────────────────────────────────────────────────────────
# 11. SUCCESS METRICS
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "11. Success Metrics", 1)

metrics_rows = [
    ("Triage accuracy",              "> 80%",     "> 92%"),
    ("Emergency escalation sensitivity","> 95%", "> 99%"),
    ("Average response latency",     "< 12s (Ollama local)", "< 3s (cloud LLM)"),
    ("Language coverage",            "6 languages",           "12+ languages"),
    ("Audit log completeness",       "100%",      "100%"),
    ("Safety filter false negatives","< 1%",      "< 0.1%"),
    ("System uptime",                "95%",       "99.9%"),
]
add_table(doc, ["Metric", "MVP Target", "Production Target"], metrics_rows,
          col_widths=[2.5, 2.0, 2.1])
doc.add_paragraph()


# ─────────────────────────────────────────────────────────────────────────────
# 12. DOCUMENTATION GUIDE
# ─────────────────────────────────────────────────────────────────────────────
add_heading(doc, "12. Project Documentation Guide", 1)
add_para(doc, "The following documentation files are available in the project root:")
doc_rows = [
    ("README.md",               "Quick start, tech stack, API endpoints, guardrail summary"),
    ("ARCHITECTURE.md",         "Complete system design — agents, RAG, chunking, FastAPI, privacy"),
    ("AGENT_DESIGN.md",         "Per-agent specs: role, inputs, outputs, system prompt, boundaries"),
    ("WORKFLOW.md",             "End-to-end step-by-step flow with code examples"),
    ("SAFETY_GUARDRAILS.md",    "7 guardrail principles, 5-layer safety architecture, compliance"),
    ("DATA_MODEL.md",           "All SQLite tables, Pydantic models, ChromaDB schema"),
    ("RAG_KNOWLEDGE_BASE.md",   "6 collections, chunking, retrieval strategy, user upload path"),
    ("TECH_STACK.md",           "Every technology choice with rationale and version notes"),
    ("PROJECT_SCOPE.md",        "In/out of scope, target users, constraints, acceptance criteria"),
    ("IMPLEMENTATION_ROADMAP.md","Phase 0–7 with completion status and quick-start commands"),
    ("KAGGLE_DEMO_PLAN.md",     "Notebook structure, 5 demo cases, Kaggle setup"),
    ("CLAUDE.md",               "Claude Code project instructions (LLM coding assistant context)"),
]
add_table(doc, ["File", "Contents"], doc_rows, col_widths=[2.4, 4.2])
doc.add_paragraph()


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER / DISCLAIMER
# ─────────────────────────────────────────────────────────────────────────────
doc.add_page_break()
footer_p = doc.add_paragraph()
footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = footer_p.add_run(
    "⚠️  DISCLAIMER\n\n"
    "RuralCare AI is a first-level health information and triage support tool. "
    "It does NOT diagnose, prescribe, or replace a licensed healthcare professional. "
    "All outputs are for informational guidance only. "
    "Always consult a qualified doctor for medical decisions. "
    "In an emergency, call 112 (National Emergency) or 108 (Ambulance) immediately."
)
r.bold = True
r.font.size = Pt(11)
r.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)


# ─────────────────────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────────────────────
output_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "RuralCare_AI_Documentation.docx"
)
doc.save(output_path)
print(f"Document saved: {output_path}")
