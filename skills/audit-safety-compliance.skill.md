# Skill: Audit, Safety & Compliance

## Skill Name
`audit-safety-compliance`

## Purpose
Run final safety validation on all agent outputs before they reach the patient, enforce mandatory disclaimers, detect and block unsafe content (diagnoses, prescriptions), write a complete audit log entry for the session, and assemble the final patient-facing response from all upstream agent outputs.

## When to Use
- Always the LAST agent node before END in the LangGraph pipeline.
- Use when implementing the `audit_safety_agent` function.
- Use when modifying the safety filter rules or disclaimer text.
- Use when investigating safety incidents or blocked outputs.
- Use when building the audit log display in the frontend.
- Use when preparing compliance documentation.

## Inputs Expected

Full PatientState with all upstream agent outputs populated:
```json
{
  "session_id": "uuid",
  "patient_token": "PT-xxxxxxxx",
  "language": "en",
  "triage_level": "MODERATE",
  "emergency_flag": false,
  "health_guidance": "Patient-facing health information...",
  "rag_sources": ["WHO_Fever_Guidelines_2023"],
  "recommended_facility": "Dharmapuri PHC...",
  "followup_plan": {...},
  "health_worker_briefing": "Briefing text...",
  "emergency_alert": null,
  "audit_log": [existing entries from upstream agents]
}
```

## Output Format

```json
{
  "final_response": "Complete, validated, disclaimer-stamped patient response",
  "safety_passed": true,
  "blocked_reason": null,
  "disclaimer": "Standard disclaimer text",
  "audit_log_entry": {
    "agent_name": "audit_safety_compliance",
    "safety_passed": true,
    "blocked_reason": null,
    "timestamp": "ISO 8601"
  }
}
```

## Decision Rules

### Safety Check Pipeline
```
1. Diagnosis pattern scan (regex)
2. Prescription pattern scan (regex)
3. PHI scan (name, phone number, email in response)
4. Disclaimer presence check
5. RAG source citation check
6. Triage level presence check
7. Response length check (< 600 words for patient response)

IF any check fails:
    → Replace problematic output with safe fallback
    → Log blocked_reason
    → safety_passed = False
    → Alert sent to safety review queue (production)
```

### Diagnosis Patterns (Blocked)
```python
DIAGNOSIS_PATTERNS = [
    r"you have (a |an )?\w+",
    r"you (are|seem to be) (suffering from|diagnosed with)",
    r"this is (definitely|likely|probably) \w+",
    r"sounds like (a |an )?\w+ (infection|disease|condition|fever|virus)",
    r"you seem to have",
    r"i can tell (you have|this is)",
    r"based on your symptoms,? (you have|this is|it appears to be)",
]
```

### Prescription Patterns (Blocked)
```python
PRESCRIPTION_PATTERNS = [
    r"\d+\s*mg\s*(of\s*)?\w+",           # Dosage: "500mg amoxicillin"
    r"take \w+ (twice|three|once) (a day|daily|per day)",
    r"prescribed?\s+\w+",
    r"(amoxicillin|azithromycin|metformin|metronidazole|ciprofloxacin|doxycycline|chloroquine|artemether)",
    r"antibiotic[s]?\s+(course|treatment)",
    r"dose of \w+",
]
```

### PHI Patterns (Blocked from Response)
```python
PHI_PATTERNS = [
    r"\b\d{10}\b",                          # Phone numbers
    r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",        # Name-like patterns
    r"\b\d{12}\b",                          # Aadhaar-like
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # Email
]
```

### Response Assembly
```python
def assemble_final_response(state: PatientState) -> str:
    sections = []

    # Emergency alert (always first if present)
    if state.get("emergency_alert"):
        sections.append(state["emergency_alert"])

    # Triage level header
    sections.append(f"TRIAGE LEVEL: {state['triage_level']}")

    # Health guidance (RAG-grounded)
    if state.get("health_guidance"):
        sections.append(state["health_guidance"])

    # Facility recommendation
    if state.get("recommended_facility"):
        sections.append(f"RECOMMENDED FACILITY:\n{state['recommended_facility']}")

    # Follow-up plan summary
    if state.get("followup_plan"):
        plan = state["followup_plan"]
        sections.append(
            f"FOLLOW-UP:\nVisit within: {plan.get('follow_up_in', 'as needed')}\n"
            f"Watch for: {', '.join(plan.get('watch_for', []))}\n"
            f"Return immediately if: {', '.join(plan.get('return_immediately_if', []))}"
        )

    # Disclaimer (always last)
    sections.append(STANDARD_DISCLAIMER)

    return "\n\n".join(sections)
```

### Audit Log Entry Creation
```python
def write_audit_log(state: PatientState, db: SQLiteClient):
    entry = {
        "session_id": state["session_id"],
        "patient_token": state["patient_token"],
        "agent_name": "audit_safety_compliance",
        "triage_level": state.get("triage_level"),
        "emergency_flag": state.get("emergency_flag", False),
        "input_hash": sha256(state["translated_input"].encode()).hexdigest(),
        "output_hash": sha256(state["final_response"].encode()).hexdigest(),
        "safety_passed": state["safety_passed"],
        "blocked_reason": state.get("blocked_reason"),
        "rag_sources": json.dumps(state.get("rag_sources", [])),
    }
    db.insert("audit_logs", entry)
```

### Standard Disclaimer
```
⚠️ DISCLAIMER: This information is for general health awareness only.
RuralCare AI is NOT a doctor and cannot diagnose illness or prescribe medicines.
All information provided is for educational purposes only.
Always consult a qualified doctor or healthcare professional for medical decisions.
In an emergency, call 112 (Emergency) or 108 (Ambulance) immediately.
```

## Safety Rules
- This agent MUST run for every pipeline execution — it cannot be skipped.
- Audit log MUST be written even if the safety check fails or the pipeline had errors.
- The disclaimer MUST be present in every patient-facing response, even partial fallbacks.
- If safety check fails: return safe fallback, not the blocked content.
- PHI must never appear in the audit log input_text field — only the SHA-256 hash.
- Safety filter must run synchronously — never async — because it gates the response.
- Blocked responses are still logged with blocked_reason for human review.

## Compliance Checks Performed
1. Disclaimer present: Yes/No
2. RAG sources cited: Yes/No (flag if No)
3. Triage level included: Yes/No
4. Diagnosis language: Detected/Clear
5. Prescription language: Detected/Clear
6. PHI in response: Detected/Clear
7. Response length: Within bounds / Truncated

## Example Input (Simplified)
```json
{
  "health_guidance": "You seem to have malaria. Take chloroquine 500mg twice daily.",
  "session_id": "abc123",
  "patient_token": "PT-a3f8b2c1"
}
```

## Example Output (Blocked Case)
```json
{
  "final_response": "I was unable to provide specific information on this topic. Please consult your nearest health centre or ASHA worker for guidance.\n\n⚠️ DISCLAIMER: ...",
  "safety_passed": false,
  "blocked_reason": "Diagnosis pattern detected: 'you seem to have'. Prescription pattern detected: '500mg chloroquine'.",
  "audit_log_entry": {
    "agent_name": "audit_safety_compliance",
    "safety_passed": false,
    "blocked_reason": "Diagnosis + Prescription patterns detected"
  }
}
```

## Failure Handling
- **Database write fails:** Log to stderr; still return response to patient; retry DB write asynchronously.
- **Safety filter crashes:** Default to fully blocking the response; show safe fallback; log exception.
- **Upstream agents all failed:** Return: "I am unable to provide guidance at this time. Please visit your nearest health centre. In an emergency, call 112." + disclaimer.
- **Response assembly fails:** Return safe fallback with disclaimer and triage level only.
