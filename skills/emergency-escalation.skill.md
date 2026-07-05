# Skill: Emergency Escalation

## Skill Name
`emergency-escalation`

## Purpose
When a life-threatening emergency is detected — either by the rule-based keyword detector or by the Medical Triage Agent — immediately surface emergency contact numbers, relevant first aid guidance (RAG-grounded), and alert pathways. This agent runs BEFORE all other agents and its output appears at the top of every response for emergency cases.

## When to Use
- Triggered when `emergency_flag=True` in PatientState.
- Triggered when `triage_level="EMERGENCY"` from Medical Triage Agent.
- Use when implementing the `emergency_escalation_agent` function.
- Use when updating emergency keyword lists or red-flag patterns.
- Use when modifying the emergency alert template.

## Inputs Expected

```json
{
  "emergency_flag": true,
  "symptoms": ["cannot breathe", "unconscious"],
  "chief_complaint": "Father unconscious and cannot breathe",
  "translated_input": "My father is unconscious and cannot breathe",
  "location": {
    "district": "Dharmapuri",
    "state": "Tamil Nadu"
  },
  "patient_token": "PT-xxxxxxxx",
  "session_id": "uuid"
}
```

## Output Format

```json
{
  "emergency_alert": "Full emergency alert text shown to patient",
  "emergency_contact_numbers": {
    "national_emergency": "112",
    "ambulance": "108",
    "police": "100",
    "fire": "101"
  },
  "first_aid_guidance": "RAG-grounded first aid steps",
  "first_aid_source": "Indian Red Cross First Aid Manual 2022",
  "nearest_emergency_facility": "Dharmapuri Government Hospital — Emergency: 04342-987654",
  "alert_sent": true,
  "triage_level": "EMERGENCY"
}
```

## Decision Rules

### Emergency Detection — Rule-Based (Synchronous, No LLM)
```python
EMERGENCY_KEYWORDS = [
    # Cardiovascular / Respiratory
    "chest pain", "cannot breathe", "difficulty breathing", "shortness of breath",
    "heart attack",
    # Neurological
    "unconscious", "not waking up", "loss of consciousness", "seizure",
    "convulsion", "fitting", "stroke", "sudden weakness", "sudden vision loss",
    "sudden severe headache", "facial droop",
    # Bleeding / Trauma
    "severe bleeding", "blood vomiting", "vomiting blood", "coughing blood",
    "heavy bleeding", "bleeding that won't stop",
    # Poisoning / Envenomation
    "snake bite", "poisoning", "swallowed poison", "insecticide",
    # Obstetric
    "heavy vaginal bleeding", "eclampsia", "fit during pregnancy",
    # Pediatric
    "child not breathing", "baby turning blue", "baby not responding"
]

def detect_emergency(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in EMERGENCY_KEYWORDS)
```

This check runs in < 100ms — before any LLM call.

### First Aid Guidance Retrieval
```python
# Fast path: use emergency_protocols collection only
# k=3 (fast retrieval)
# score_threshold=0.60 (lower to ensure something is returned)
emergency_chunks = emergency_retriever.get_relevant_documents(
    query=chief_complaint
)
first_aid_text = "\n".join([doc.page_content for doc in emergency_chunks[:3]])
```

If no chunks retrieved: use hardcoded static first aid for the detected emergency type.

### Emergency Type Classification (for First Aid Selection)
```
"cannot breathe" / "unconscious"  → CPR and airway protocol
"chest pain"                        → Chest pain / heart attack protocol
"seizure" / "convulsion"           → Seizure management protocol
"stroke"                           → F.A.S.T. stroke protocol
"severe bleeding"                  → Bleeding control protocol
"snake bite"                       → Snake bite protocol
"poisoning"                        → Poisoning / ingestion protocol
"pregnancy emergency"              → Obstetric emergency protocol
default                            → General emergency protocol
```

### Emergency Alert Template
```
🚨 EMERGENCY — IMMEDIATE ACTION NEEDED 🚨

Based on what you described, this may be a MEDICAL EMERGENCY.

CALL FOR HELP IMMEDIATELY:
• Emergency: 112
• Ambulance: 108

NEAREST EMERGENCY FACILITY:
{nearest_emergency_facility}

WHAT TO DO RIGHT NOW:
{first_aid_guidance}

Do NOT wait. Every second counts.
If you cannot call, ask someone nearby to help.

Source: {first_aid_source}

⚠️ DISCLAIMER: RuralCare AI is not a doctor. This is emergency guidance only.
Always follow the advice of emergency medical services.
```

### Alert Notification (Production Only)
```python
if not demo_mode:
    send_webhook_alert({
        "session_id": session_id,
        "patient_token": patient_token,
        "emergency_type": detected_emergency_type,
        "location": location,
        "timestamp": timestamp
    })
    # Webhook target: health worker alert system, district health officer
```

### Static Fallback (if ChromaDB unavailable)
```
WHAT TO DO RIGHT NOW (General Emergency):
1. Stay calm and call 108 or 112 immediately.
2. Keep the person still and comfortable.
3. Do not give food or water.
4. If unconscious and not breathing: begin CPR (30 chest compressions, 2 breaths).
5. Stay with the person until help arrives.
```

## Safety Rules
- Emergency escalation MUST complete before any other agent output is shown to the patient.
- Emergency contact numbers MUST always be shown — never omit, even if other parts fail.
- Emergency alert MUST appear at the very top of the patient-facing response.
- First aid guidance must be RAG-grounded; if no RAG available, use hardcoded static guidance.
- Do NOT add caveats that delay the patient calling for help (e.g., "but you should check first").
- Emergency alert is NOT filtered for "diagnosis language" — first aid must be direct and clear.
- The emergency path MUST complete in under 2 seconds total.

## Example Input
```json
{
  "emergency_flag": true,
  "chief_complaint": "Father unconscious and cannot breathe",
  "location": {"district": "Dharmapuri", "state": "Tamil Nadu"}
}
```

## Example Output
```json
{
  "emergency_alert": "🚨 EMERGENCY — IMMEDIATE ACTION NEEDED 🚨\n\nBased on what you described, this may be a MEDICAL EMERGENCY.\n\nCALL FOR HELP IMMEDIATELY:\n• Emergency: 112\n• Ambulance: 108\n\nNEAREST EMERGENCY FACILITY:\nDharmapuri Government Hospital — Emergency: 04342-987654\n\nWHAT TO DO RIGHT NOW:\n1. Check if the person responds — tap shoulder and call their name.\n2. Call 108 immediately.\n3. Open the airway: gently tilt the head back and lift the chin.\n4. Check for breathing for 10 seconds.\n5. If not breathing: begin CPR — 30 chest compressions, then 2 breaths.\n6. Continue until ambulance arrives.\n\nDo NOT wait. Every second counts.\n\nSource: Indian Red Cross First Aid Manual 2022\n\n⚠️ DISCLAIMER: RuralCare AI is not a doctor. Follow emergency services guidance.",
  "triage_level": "EMERGENCY",
  "alert_sent": false
}
```

## Failure Handling
- **ChromaDB unavailable:** Use hardcoded static first aid (always loaded in memory at startup).
- **Location unknown:** Show national numbers (112, 108) without local facility. Do not delay for location.
- **Alert webhook fails:** Log; do not fail the agent. Patient response is more important than webhook.
- **Any exception in this agent:** Show hardcoded emergency message with 112 and 108. Never fail silently.
