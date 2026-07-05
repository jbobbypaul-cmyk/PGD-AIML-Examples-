# Skill: Orchestrator

## Skill Name
`orchestrator`

## Purpose
Coordinate the full RuralCare AI multi-agent pipeline using LangGraph. Route patient requests through the correct sequence of agents, handle emergency fast-path routing, manage shared state, and ensure the audit and safety agent always runs last before the response is returned to the patient.

## When to Use
- Invoke this skill for every patient interaction — it is the entry point for all requests.
- Use when a new session is created (new symptom input, voice upload, or API call).
- Use when implementing or modifying the LangGraph graph structure.
- Use when adding a new agent node to the pipeline.
- Use when debugging routing logic or agent sequencing.

## Inputs Expected
```json
{
  "raw_input": "Patient's symptom description (text or transcribed voice)",
  "language": "ISO 639-1 language code (e.g., en, hi, ta)",
  "location_district": "Optional: Patient's district",
  "location_state": "Optional: Patient's state",
  "input_source": "text | voice",
  "patient_token": "Optional: existing token, else generated"
}
```

## Output Format
```json
{
  "session_id": "uuid",
  "patient_token": "PT-xxxxxxxx",
  "triage_level": "EMERGENCY | URGENT | MODERATE | MILD",
  "emergency_flag": true | false,
  "emergency_alert": "Alert text if emergency",
  "health_guidance": "RAG-grounded health information",
  "rag_sources": ["source1", "source2"],
  "recommended_facility": "Facility name and contact",
  "followup_plan": {...},
  "health_worker_briefing": "Briefing text",
  "final_response": "Complete patient-facing response",
  "disclaimer": "Standard disclaimer text",
  "safety_passed": true | false,
  "audit_log": [...]
}
```

## Decision Rules

### Routing Logic
```
START
  │
  ├── emergency_check(raw_input)
  │     ├── True → emergency_escalation_agent → audit_safety_agent → END
  │     └── False → symptom_intake_agent
  │                   → medical_triage_agent
  │                       ├── triage_level == EMERGENCY → also run emergency_escalation
  │                       └── continue → medical_rag_agent
  │                                        → appointment_facility_agent
  │                                            → followup_adherence_agent
  │                                                → health_worker_support_agent
  │                                                    → audit_safety_agent → END
```

### State Initialization
```python
session_id = str(uuid4())
patient_token = f"PT-{uuid4().hex[:8]}"
timestamp = datetime.utcnow().isoformat()
emergency_flag = False
safety_passed = True
audit_log = []
```

### Error Handling
- If any agent raises an exception: log to audit, continue to next agent with partial state.
- If LLM unavailable: load static fallback, mark `error` in state, proceed to audit.
- If emergency agent fails: show emergency numbers from static file immediately.

### Pre-Processing Before Agents
1. PHI anonymization — assign patient_token, strip names/contacts from input.
2. Language detection — set `state.language`.
3. Translation to English — set `state.translated_input`.
4. Session creation in SQLite.

## Safety Rules
- Emergency check MUST run before any LLM call — it is synchronous and rule-based.
- Audit & Safety agent MUST always be the last node before END.
- No agent can return a response directly to the user — all responses go through audit_safety_agent.
- State is never passed to external services in raw form — always anonymized.

## Example Input
```json
{
  "raw_input": "मुझे तीन दिनों से बुखार है और सिर दर्द हो रहा है",
  "language": "hi",
  "location_district": "Dharmapuri",
  "location_state": "Tamil Nadu",
  "input_source": "text"
}
```

## Example Output
```json
{
  "session_id": "f4a8b2c1-...",
  "patient_token": "PT-a3f8b2c1",
  "triage_level": "MODERATE",
  "emergency_flag": false,
  "health_guidance": "Fever lasting more than 3 days with headache needs medical evaluation...",
  "rag_sources": ["WHO_Fever_Guidelines_2023"],
  "recommended_facility": "Dharmapuri PHC — 4.2 km — 04342-123456",
  "followup_plan": {"follow_up_in": "48 hours", ...},
  "final_response": "...(full Hindi response)...",
  "disclaimer": "⚠️ DISCLAIMER: ...",
  "safety_passed": true,
  "audit_log": [...]
}
```

## Failure Handling
- **LLM down:** Return static triage guidelines from local file; show emergency contacts; log failure.
- **ChromaDB down:** Skip RAG; label response as "general guidance"; continue pipeline.
- **Translation fails:** Proceed in English; add language note to response.
- **Emergency agent fails:** Show emergency contacts from hardcoded static list immediately.
- **Partial state:** If any agent updates fail, include `error` key; do not crash full pipeline.
