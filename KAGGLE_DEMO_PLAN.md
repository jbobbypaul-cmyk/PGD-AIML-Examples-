# KAGGLE_DEMO_PLAN.md — RuralCare AI Kaggle Demo Plan

## Purpose

Design a complete, self-contained Kaggle Notebook demonstration of RuralCare AI that runs without external servers, showcases all core features, and can serve as a competition submission or portfolio demo.

---

## Demo Goals

1. Show the complete multi-agent pipeline end-to-end in a Kaggle Notebook.
2. Demonstrate triage classification for 4 urgency levels.
3. Show RAG-grounded responses from sample medical documents.
4. Display multilingual support (English + Hindi).
5. Show emergency escalation path.
6. Display audit log table.
7. Run entirely on Kaggle's free CPU environment (no GPU required).
8. Complete in under 3 minutes per demo run.

---

## Kaggle Constraints

| Constraint | Value |
|---|---|
| RAM | 13 GB |
| CPU | 2 cores |
| GPU | Optional (not required) |
| Disk | 20 GB |
| Internet | Available (for API calls) |
| Runtime limit | 9 hours |
| Session persistence | None (fresh each run) |
| Ollama | Not available on Kaggle — use cloud LLM (Claude / OpenAI) |

**Important:** Ollama cannot be installed on Kaggle. Set `LLM_PROVIDER=claude` (or `openai`) and provide the API key as a Kaggle secret. The codebase automatically switches the LLM layer — no code changes required.

---

## Notebook Structure

### Notebook: `notebooks/ruralcare_ai_demo.ipynb`

```
Cell 1:  Title + Introduction + Safety Disclaimer (Markdown)
Cell 2:  Install dependencies (pip install)
Cell 3:  Import libraries + set environment variables (Kaggle secrets)
Cell 4:  Initialize ChromaDB, seed sample knowledge base
Cell 5:  Initialize SQLite, seed Tamil Nadu hospital data
Cell 6:  Verify setup (collection sizes, facility count)
Cell 7:  Agent function definitions (or import from app/)
Cell 8:  LangGraph orchestrator setup
Cell 9:  Demo Case 1 — Mild symptom (headache)
Cell 10: Demo Case 2 — Moderate (fever 3 days)
Cell 11: Demo Case 3 — Urgent (chest pain + cough)
Cell 12: Demo Case 4 — Emergency (cannot breathe + unconscious)
Cell 13: Demo Case 5 — Hindi language input
Cell 14: Audit log display (pandas DataFrame)
Cell 15: Results summary, limitations, and disclaimers
Cell 16: (Optional) Streamlit in-notebook via pyngrok
```

---

## Demo Cases

### Case 1 — Mild
```
Input: "I have a mild headache and feel a bit tired since this morning."
Language: English
Expected triage: MILD
Expected guidance: Rest, hydration, monitor for worsening
Emergency alert: No
Follow-up plan: Monitor at home; visit PHC if symptoms worsen
```

### Case 2 — Moderate
```
Input: "I have had fever for 3 days, headache, and body aches. I feel weak."
Language: English
Expected triage: MODERATE
Expected guidance: Fever management, hydration, visit PHC within 48 hours
Emergency alert: No
Facility shown: Nearest PHC/CHC from Tamil Nadu cache
```

### Case 3 — Urgent
```
Input: "I have chest pain and have been coughing for 2 weeks. I am losing weight."
Language: English
Expected triage: URGENT
Expected guidance: Respiratory symptoms requiring urgent evaluation; TB risk awareness
Emergency alert: No (chest pain in chronic context — triage as URGENT not EMERGENCY)
Note: Chronic cough + weight loss is URGENT; acute "chest pain right now" would be EMERGENCY
```

### Case 4 — Emergency
```
Input: "My father is unconscious and cannot breathe."
Language: English
Expected triage: EMERGENCY
Expected guidance: Emergency alert, call 112 / 108, CPR first aid
Emergency alert: YES — immediate escalation, pre-LLM
```

### Case 5 — Multilingual (Hindi)
```
Input: "मुझे तीन दिनों से बुखार है और सिर दर्द हो रहा है"
       (Translation: "I have had fever for three days and have a headache")
Language: Hindi
Expected triage: MODERATE
Expected guidance: Same as Case 2, response in Hindi
Emergency alert: No
```

---

## Simplified Pipeline for Kaggle Demo

In the Kaggle demo, a simplified single-file pipeline is used (no FastAPI server required):

```python
# notebooks/ruralcare_demo_pipeline.py

def run_demo_pipeline(symptoms_text: str, language: str = "en", district: str = "") -> dict:
    """
    Simplified pipeline for Kaggle demo.
    No external server. All in-memory.
    Uses cloud LLM (LLM_PROVIDER=claude or openai) since Ollama is unavailable on Kaggle.
    """
    state = init_state(symptoms_text, language, district)

    # Step 0: Emergency check (rule-based, pre-LLM)
    if detect_emergency(state["translated_input"]):
        state["emergency_flag"] = True
        state["triage_level"]   = "EMERGENCY"
        state = emergency_escalation_agent(state)
        state = audit_safety_agent(state)
        return format_demo_output(state)

    # Steps 1-7: Full pipeline
    state = symptom_intake_agent(state)
    state = medical_triage_agent(state)
    state = medical_rag_agent(state)
    state = appointment_facility_agent(state)
    state = followup_adherence_agent(state)
    state = health_worker_support_agent(state)
    state = audit_safety_agent(state)

    return format_demo_output(state)
```

---

## Demo Knowledge Base (Minimal Seed)

For Kaggle, the knowledge base is seeded with 8 small text files (no PDF parsing, fast setup):

```python
DEMO_DOCUMENTS = {
    "who_health_guidelines": [
        """Fever Management Guidelines (WHO)
        Fever (temperature above 38°C/100.4°F) lasting more than 3 days requires medical evaluation.
        For mild fever: Rest, adequate hydration, and paracetamol for comfort.
        Danger signs: fever with stiff neck, rash, difficulty breathing, or altered consciousness.
        Source: WHO Fever Guidelines 2023""",

        """Diarrhea and Dehydration (WHO)
        Oral Rehydration Solution (ORS) is the first-line treatment for diarrhea-related dehydration.
        Mix one ORS sachet in 1 litre of clean water. Give small sips frequently.
        Signs of severe dehydration: sunken eyes, dry mouth, no urination, lethargy.
        Seek immediate care for severe dehydration.
        Source: WHO Diarrhoeal Disease Fact Sheet 2023""",
    ],

    "nhm_india_protocols": [
        """ASHA Health Worker Protocol — Fever (NHM India)
        ASHAs should refer patients with fever lasting >3 days to the nearest PHC.
        Provide paracetamol for symptomatic relief while arranging referral.
        Collect blood slide sample for malaria if in malaria-endemic area.
        Source: NHM ASHA Training Module 4""",
    ],

    "emergency_protocols": [
        """Emergency First Aid — Unconscious Person (Indian Red Cross)
        1. Check for response: tap shoulder gently and call out.
        2. Call for help: Dial 108 (ambulance) or 112 (emergency).
        3. Open airway: tilt head back, lift chin.
        4. Check for breathing for 10 seconds.
        5. If not breathing: begin CPR — 30 compressions, 2 rescue breaths.
        Do not leave the person alone. Stay until help arrives.
        Source: Indian Red Cross First Aid Manual 2022""",

        """Emergency First Aid — Breathing Difficulty
        If a person cannot breathe:
        1. Call 108 immediately.
        2. Loosen tight clothing around neck and chest.
        3. Help person sit upright (forward-leaning position helps).
        4. Do NOT give food or water.
        5. Stay with them until ambulance arrives.
        Source: WHO Emergency Care Principles 2022""",
    ],

    "symptom_disease_mapping": [
        """Common Fever Patterns and Urgency (Clinical Triage Reference)
        MILD: Low-grade fever (<38.5°C), no other serious symptoms, duration <2 days
        MODERATE: Fever >38.5°C lasting 2-5 days, with headache or body aches
        URGENT: High fever >39.5°C, rigors, vomiting, unable to eat/drink
        EMERGENCY: Fever with stiff neck, altered consciousness, difficulty breathing, rash
        Source: WHO ICD-11 Triage Reference 2022""",
    ],

    "regional_health_schemes": [
        """PM-JAY (Pradhan Mantri Jan Arogya Yojana) — Key Facts
        PM-JAY provides health insurance coverage of Rs. 5 lakh per family per year.
        Eligibility: Based on Socio-Economic Caste Census (SECC) data.
        Coverage: Hospitalization for 1,574 medical packages.
        How to access: Visit any empanelled government or private hospital with Aadhaar card.
        Check eligibility at: pmjay.gov.in
        Source: NHM PM-JAY Guidelines 2024""",
    ],
}
```

---

## Demo Output Format (Kaggle Display)

```python
def display_demo_result(result: dict):
    print("=" * 60)
    print("RURALCARE AI -- TRIAGE RESULT")
    print("=" * 60)

    if result["emergency_flag"]:
        print("\n*** EMERGENCY ALERT ***")
        print(result.get("emergency_alert", "Call 112 immediately."))

    level_label = {
        "EMERGENCY": "[RED] EMERGENCY",
        "URGENT":    "[ORANGE] URGENT",
        "MODERATE":  "[YELLOW] MODERATE",
        "MILD":      "[GREEN] MILD",
    }
    print(f"\nTRIAGE LEVEL: {level_label.get(result['triage_level'], result['triage_level'])}")
    print(f"Reasoning: {result.get('triage_reasoning', '')}\n")

    print("HEALTH GUIDANCE:")
    print(result.get("health_guidance", "No guidance available."))
    print(f"\nSources: {', '.join(result.get('rag_sources', []))}\n")

    print("NEAREST FACILITY:")
    print(result.get("recommended_facility", "Contact your district health office."))

    print("\nFOLLOW-UP PLAN:")
    plan = result.get("followup_plan", {})
    if isinstance(plan, dict):
        print(f"  Follow up in: {plan.get('follow_up_in', 'N/A')}")
        print(f"  Watch for: {', '.join(plan.get('watch_for', []))}")
        print(f"  Return immediately if: {', '.join(plan.get('return_immediately_if', []))}")

    print("\nDISCLAIMER:")
    print(result.get("disclaimer", ""))
    print("=" * 60)
```

---

## Audit Log Display (Pandas DataFrame)

```python
import pandas as pd

def display_audit_log(audit_entries: list):
    df = pd.DataFrame(audit_entries)
    display_cols = [
        "agent_name", "triage_level", "emergency_flag",
        "safety_passed", "latency_ms", "blocked_reason",
    ]
    available = [c for c in display_cols if c in df.columns]
    print("\nAUDIT LOG:")
    print(df[available].to_string(index=False))
```

---

## Kaggle Notebook Installation Cell

```python
%%capture
!pip install langchain langchain-anthropic langchain-openai langchain-chroma \
             langchain-community langgraph chromadb \
             langdetect googletrans==4.0.0rc1 pydantic>=2.7.0 \
             pandas pypdf requests aiohttp

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONUTF8"] = "1"
```

**Note:** `sentence-transformers` and `openai-whisper` are NOT included in the Kaggle install. For Kaggle:
- Embeddings: use `langchain-openai` embeddings (OpenAI API) or `langchain-google-genai` embeddings if Ollama unavailable.
- Voice: text input only; Whisper is not used in Kaggle demo.

---

## Environment Variables for Kaggle

Set these as Kaggle Secrets (not in notebook code):
```
ANTHROPIC_API_KEY   → Your Claude API key
LLM_PROVIDER        → claude   (Ollama is not available on Kaggle)
DEMO_MODE           → true
```

Access in notebook:
```python
from kaggle_secrets import UserSecretsClient
secrets = UserSecretsClient()
os.environ["ANTHROPIC_API_KEY"] = secrets.get_secret("ANTHROPIC_API_KEY")
os.environ["LLM_PROVIDER"]      = "claude"
os.environ["DEMO_MODE"]         = "true"
```

---

## Hugging Face Spaces Deployment

For a hosted demo beyond Kaggle:

```yaml
# README.md front matter for HF Spaces
---
title: RuralCare AI Demo
emoji: 🏥
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.58.0
app_file: app/streamlit_app.py
pinned: true
---
```

Required HF Space secrets:
- `ANTHROPIC_API_KEY`
- `LLM_PROVIDER=claude`
- `DEMO_MODE=true`
- `SQLITE_PATH=/home/user/app/data/ruralcare.db`
- `CHROMA_DB_PATH=/home/user/app/data/chroma`

---

## Demo Acceptance Criteria

- [x] All 5 demo cases produce correct triage levels in local Streamlit run.
- [x] Emergency case (Case 4) shows alert within 2 seconds (pre-LLM keyword detection).
- [x] Hindi case (Case 5) shows translated input and translated output.
- [x] RAG response cites at least one source document.
- [x] Facility lookup returns actual hospital name for Salem and other TN districts.
- [x] Follow-up Plan displayed as full-width section.
- [x] Health Worker Briefing displayed as separate full-width section without truncation.
- [x] Disclaimer visible in all outputs.
- [ ] Kaggle Notebook — all cells run without errors (requires `LLM_PROVIDER=claude` + API key).
- [ ] Audit log table populated (accessible via FastAPI `/api/v1/audit`).
- [ ] Total Kaggle notebook runtime < 5 minutes (excluding package install).
- [ ] No external server required — runs entirely in-notebook.
- [ ] Notebook exports cleanly to HTML for sharing.
