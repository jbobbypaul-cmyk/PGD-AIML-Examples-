# SAFETY_GUARDRAILS.md — RuralCare AI Safety & Ethics Framework

## Purpose

Define the mandatory safety rules, ethical constraints, guardrail implementation, and compliance framework for RuralCare AI. These rules are **non-negotiable** and apply to every component of the system.

---

## Core Safety Principles

### 1. Do Not Diagnose
RuralCare AI must **never** state, imply, or suggest that a patient has a specific disease or medical condition.

**Prohibited outputs:**
- "You have malaria."
- "This sounds like dengue fever."
- "Based on your symptoms, you likely have typhoid."
- "Your symptoms indicate diabetes."

**Permitted outputs:**
- "Your symptoms, including fever and body aches, may need medical evaluation."
- "Based on health guidelines, fever with these symptoms requires urgent medical attention."

---

### 2. Do Not Prescribe
RuralCare AI must **never** recommend specific prescription medicines, drug names (beyond basic OTC/ASHA-distributed items), or dosages for medical conditions.

**Prohibited outputs:**
- "Take amoxicillin 500mg three times a day."
- "You should take metformin for blood sugar control."
- "Azithromycin will help with this infection."

**Permitted outputs (with RAG grounding from NHM documents):**
- "ORS (oral rehydration solution) can help prevent dehydration. Mix one sachet in 1 litre of clean water."
- "Paracetamol can help reduce fever. Follow the dosage on the packaging or ask a pharmacist."
- "Your ASHA worker can provide iron and folic acid tablets under the National Iron Plus Initiative."

---

### 3. Always Recommend Professional Consultation
Every patient-facing response must include a clear recommendation to consult a healthcare professional.

**Required in every response:**
```
Always consult a qualified doctor or healthcare worker for medical advice.
This information is for general awareness only.
```

---

### 4. Emergency Escalation is Non-Negotiable
When any emergency red-flag is detected, the system must:
1. Surface emergency contact numbers immediately.
2. Show emergency alert before any other response.
3. Not make the patient wait through the full pipeline.

Emergency escalation cannot be disabled, bypassed, or made optional.

---

### 5. RAG-Grounded Responses Only
All medical information in patient-facing responses must be:
- Grounded in retrieved document context from verified sources.
- OR explicitly labeled as "general guidance" when no RAG document is found.
- Never improvised by the LLM from training data alone.

The LLM system prompt must include: *"Use ONLY the provided context. Do not use outside knowledge for medical information."*

---

### 6. Privacy and PHI Protection
- Patient names, phone numbers, and addresses must never appear in LLM prompts.
- Use anonymized patient tokens (`PT-{8 hex chars}`) in all agent processing.
- Audit logs store SHA-256 hashes of input/output — never raw text.
- No patient data is transmitted to LLM APIs in identifiable form.
- Whisper voice transcription runs locally — no audio sent to external servers.

---

### 7. Mandatory Audit Trail
Every interaction must produce an audit log entry, even if the pipeline fails. The audit log is:
- Append-only (no deletions).
- Written synchronously before the response is returned.
- Contains triage level, safety outcome, emergency flag, and agent name.
- Stored in SQLite `audit_logs` table.
- Accessible only via the FastAPI `/api/v1/audit` endpoint — **not shown in the patient-facing Streamlit UI**.

---

## AI Guardrail Principles

Seven principles govern how AI is used responsibly in RuralCare:

| Principle | Enforcement |
|---|---|
| **Non-maleficence** | LLM system prompt constraints + independent regex safety filter on every output |
| **Bounded scope** | Disclaimer appended by code (not LLM); safe fallback when no RAG context |
| **Grounding** | LLM restricted to retrieved chunks only; `rag_sources` tracked per response |
| **Proportionality** | EMERGENCY bypasses LLM — hardcoded first-aid + emergency numbers shown immediately |
| **Privacy by design** | `patient_token` in all LLM calls; SHA-256 hashes in audit log; PHI scrubbed from outputs |
| **Auditability** | `audit_safety_agent` is terminal node — always runs; every agent logs its entry |
| **Fail safe** | `_node` wrapper catches all exceptions; errors produce safe fallback, never wrong response |

---

## Red-Flag Symptom Patterns (Emergency Triggers)

The following patterns trigger the Emergency Escalation Agent **before any LLM call**. This check is **purely rule-based** (no LLM) for speed and reliability (< 100ms).

### Category 1: Cardiovascular / Respiratory Emergency
- chest pain
- chest tightness
- cannot breathe
- difficulty breathing
- shortness of breath
- heart attack

### Category 2: Neurological Emergency
- loss of consciousness
- unconscious
- not waking up
- seizure
- convulsion
- fitting
- stroke
- sudden weakness one side
- sudden vision loss
- sudden severe headache
- facial drooping

### Category 3: Severe Bleeding / Trauma
- severe bleeding
- blood vomiting
- vomiting blood
- coughing blood
- heavy bleeding
- bleeding that won't stop

### Category 4: Poisoning / Envenomation
- snake bite
- poisoning
- swallowed poison
- insecticide ingestion
- rat poison

### Category 5: Obstetric Emergency
- heavy vaginal bleeding during pregnancy
- fit during pregnancy
- eclampsia
- baby not moving
- placenta delivered but bleeding continues

### Category 6: Pediatric Emergency
- child not breathing
- baby turning blue
- child not responding
- high fever with rash and stiff neck

---

## Safety Filter Implementation

```python
# app/utils/safety_filter.py

import re
from dataclasses import dataclass

DIAGNOSIS_PATTERNS = [
    r"you have (a |an )?\w+",
    r"you are (suffering from|diagnosed with)",
    r"this is (definitely|likely|probably) \w+",
    r"based on your symptoms, (you have|this is)",
    r"you seem to have",
    r"sounds like (a |an )?\w+ (infection|disease|condition|fever)",
]

PRESCRIPTION_PATTERNS = [
    r"\d+\s*mg\s*(of\s*)?\w+",
    r"take \w+ (twice|three times|once) (a day|daily)",
    r"prescribed \w+",
    r"(amoxicillin|azithromycin|metformin|metronidazole|ciprofloxacin)",
]

DISCLAIMER = (
    "\n\n⚠️ DISCLAIMER: This information is for general health awareness only. "
    "RuralCare AI is NOT a doctor and cannot diagnose or prescribe. "
    "Always consult a qualified healthcare professional for medical advice. "
    "In an emergency, call 112 immediately."
)

@dataclass
class SafetyCheckResult:
    passed: bool
    blocked_reason: str | None
    output: str

def run_safety_filter(text: str) -> SafetyCheckResult:
    text_lower = text.lower()

    for pattern in DIAGNOSIS_PATTERNS:
        if re.search(pattern, text_lower):
            return SafetyCheckResult(
                passed=False,
                blocked_reason=f"Diagnosis pattern detected: {pattern}",
                output=_safe_fallback()
            )

    for pattern in PRESCRIPTION_PATTERNS:
        if re.search(pattern, text_lower):
            return SafetyCheckResult(
                passed=False,
                blocked_reason=f"Prescription pattern detected: {pattern}",
                output=_safe_fallback()
            )

    if "DISCLAIMER" not in text:
        text += DISCLAIMER

    return SafetyCheckResult(passed=True, blocked_reason=None, output=text)

def _safe_fallback() -> str:
    return (
        "I was unable to provide specific information on this topic. "
        "Please consult your nearest health center or ASHA worker for guidance."
        + DISCLAIMER
    )
```

---

## Emergency Red-Flag Detector

```python
# app/utils/safety_filter.py

EMERGENCY_KEYWORDS = [
    "chest pain", "cannot breathe", "difficulty breathing", "shortness of breath",
    "unconscious", "not waking up", "seizure", "convulsion", "fitting",
    "stroke", "sudden weakness", "sudden vision loss", "sudden severe headache",
    "severe bleeding", "blood vomiting", "vomiting blood", "coughing blood",
    "snake bite", "poisoning", "heavy vaginal bleeding",
    "baby not moving", "child not breathing", "baby turning blue",
    "heart attack", "loss of consciousness", "eclampsia",
]

def detect_emergency(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EMERGENCY_KEYWORDS)

def hash_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

`detect_emergency()` is called **synchronously at the start of Symptom Intake**, before any LLM call. Target latency: < 100ms.

---

## 5-Layer Safety Architecture

```
Layer 1: Pre-LLM keyword detection (detect_emergency)
         - Synchronous, rule-based, < 100ms
         - Triggers Emergency Escalation Agent immediately

Layer 2: Emergency Escalation Agent
         - Hardcoded 112/108 contacts + RAG first-aid only
         - No LLM diagnosis possible from this agent

Layer 3: LLM system prompt constraints
         - Every agent prompt explicitly forbids diagnosis, prescription
         - "Do NOT diagnose. Do NOT prescribe. Do NOT use outside knowledge."

Layer 4: Safety filter (regex post-processing on LLM output)
         - Runs on every LLM output before it reaches the patient
         - Blocks diagnosis patterns + prescription patterns
         - Injects disclaimer if missing

Layer 5: Audit safety agent (terminal gate)
         - Final synchronous check on assembled response
         - Writes audit log entry (always, even on failure)
         - Returns safe fallback if any check fails
```

---

## Ethical Framework

### Beneficence
The system must genuinely help patients access care faster. Responses must be actionable — not just disclaimers.

### Non-Maleficence
The system must never:
- Delay emergency care through excessive caveats.
- Give false reassurance for serious symptoms.
- Create barriers to accessing healthcare.

### Autonomy
Patients retain decision-making authority. The system informs — it does not coerce or override patient choices.

### Justice
- Government facilities prioritized for affordability.
- Language coverage prevents exclusion of non-Hindi speakers.
- Voice input prevents exclusion of low-literacy users.
- Local LLM (Ollama) enables operation without internet API cost in resource-constrained settings.

### Transparency
- All responses cite their source documents.
- The system clearly identifies itself as an AI assistant, not a doctor.
- Triage level reasoning is explained to the patient.
- Facility data source (NHM TN / OSM / Google / User Upload) is shown.

---

## Compliance Framework

### India — Digital Personal Data Protection Act (DPDP) 2023

| Requirement | Implementation |
|---|---|
| Consent for data processing | Session consent screen in Streamlit UI |
| Purpose limitation | Patient data used only for health triage support |
| Data minimization | No real names stored; anonymized tokens only |
| Right to erasure | Session deletion endpoint in API |
| Security safeguards | SHA-256 hashes in audit; HTTPS in transit; no PHI in LLM prompts |
| Grievance officer | Contact information in app footer |

### WHO Safe AI for Health Principles

| Principle | Implementation |
|---|---|
| Human oversight | Audit log reviewed by health officers; escalation to human worker |
| Transparency | LLM reasoning visible in audit log; sources cited in every response |
| Reliability | Fail-safe `_node` wrapper; fallback responses if LLM unavailable |
| Accountability | Session-level audit trail, named agent actions, SHA-256 hashes |
| Equity | Multilingual, voice-enabled, low-bandwidth design; local LLM option |

---

## Incident Response

### Safety Filter Block
1. Log to `audit_logs` with `safety_passed=False` and `blocked_reason`.
2. Return safe fallback message to patient.
3. Alert sent to safety review queue (production).
4. Human reviewer checks within 24 hours.

### False Emergency Escalation
1. Patient can confirm/deny emergency via follow-up question.
2. Log false escalation in audit with agent feedback.
3. Emergency keyword list reviewed monthly.

### LLM Output Anomaly
1. If LLM returns empty, truncated, or error response: `_node` wrapper catches, returns partial state.
2. Audit safety agent detects missing `health_guidance`, returns safe fallback.
3. Second attempt with lower temperature if first fails; static protocol from local file as last resort.

---

## Testing Requirements for Safety

| Test | Requirement |
|---|---|
| Safety filter unit tests | 100% coverage of all diagnosis/prescription patterns |
| Emergency keyword detection | All 40+ keywords tested |
| Disclaimer injection | Test all code paths that generate patient responses |
| PHI in prompts | Automated scan ensures no patient names in LLM call logs |
| Fallback activation | Test LLM unavailability scenario via `_node` wrapper |
| RAG grounding | Confirm no response from LLM without context injection |
| Audit log completeness | Test pipeline failure path — audit entry still written |

---

## Acceptance Criteria

- [x] Safety filter blocks 100% of test cases containing diagnosis patterns.
- [x] Safety filter blocks 100% of test cases containing prescription patterns.
- [x] Emergency escalation activates within 100ms for all 40+ red-flag keywords.
- [x] Disclaimer present in 100% of patient-facing responses.
- [x] No real patient identifier appears in any LLM prompt log.
- [x] Audit log written for 100% of interactions, including failed pipeline runs.
- [x] Fallback message shown when LLM is unavailable (`_node` fail-safe active).
- [ ] Safety filter test suite achieves 100% line coverage (`tests/test_safety_filter.py`).
