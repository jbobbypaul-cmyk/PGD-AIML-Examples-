# Skill: Follow-up & Adherence

## Skill Name
`followup-adherence`

## Purpose
Generate a structured, actionable follow-up care plan for the patient based on their triage level and health guidance, including what to watch for, when to return to care, home-care instructions, and simulated reminders. Support medication adherence for ASHA-distributed items.

## When to Use
- Called after Appointment & Facility Agent has provided facility information.
- Use when implementing the `followup_adherence_agent` function.
- Use when setting up the follow-up reminder database entries.
- Use when designing the follow-up plan structure.
- Use when a health worker needs a follow-up schedule for a patient.

## Inputs Expected

```json
{
  "triage_level": "MODERATE",
  "symptoms": ["fever", "headache", "body aches"],
  "chief_complaint": "Fever with headache for 3 days",
  "health_guidance": "RAG-grounded guidance text",
  "recommended_facility": "Dharmapuri PHC — 4.2 km — 04342-123456",
  "patient_token": "PT-xxxxxxxx",
  "session_id": "uuid"
}
```

## Output Format

```json
{
  "followup_plan": {
    "follow_up_in": "48 hours",
    "urgency_note": "Do not wait longer than 48 hours before visiting the PHC.",
    "watch_for": ["temperature above 39.5°C", "difficulty breathing", "stiff neck", "skin rash"],
    "return_immediately_if": ["cannot breathe", "loss of consciousness", "convulsions", "severe bleeding"],
    "home_care": [
      "Rest completely",
      "Drink at least 2-3 litres of clean water or ORS per day",
      "Take paracetamol for fever — follow package dosage",
      "Keep a note of your temperature twice daily"
    ],
    "reminders": [
      {"when": "today evening", "action": "Check temperature", "priority": "high"},
      {"when": "tomorrow morning", "action": "Check temperature and note any new symptoms", "priority": "high"},
      {"when": "48 hours from now", "action": "Visit Dharmapuri PHC if not improved", "priority": "high"}
    ],
    "adherence_tips": "Take medicines at the same time each day. Keep a simple diary of symptoms.",
    "health_scheme_info": "You may receive free medicines at the PHC under the free drug distribution scheme."
  }
}
```

## Decision Rules

### Follow-up Timeframe by Triage Level
```
EMERGENCY → Already escalated; follow-up is "after emergency care"
URGENT    → Follow up within 4-6 hours if not at facility yet
MODERATE  → Follow up within 24-48 hours
MILD      → Follow up in 3-7 days; sooner if worsens
```

### Watch-For Symptoms (by Common Presentations)
```
Fever symptoms:
  watch_for: [temperature above 39.5°C, stiff neck, skin rash, difficulty breathing]
  return_immediately_if: [cannot breathe, convulsions, loss of consciousness]

Diarrhea/vomiting:
  watch_for: [sunken eyes, dry mouth, no urination for 8+ hours, blood in stool]
  return_immediately_if: [completely unable to drink fluids, severe abdominal pain]

Respiratory symptoms:
  watch_for: [worsening breathlessness, blue lips or fingertips, coughing blood]
  return_immediately_if: [cannot breathe, blue lips]

General/mild:
  watch_for: [any worsening, new symptoms, fever not improving]
  return_immediately_if: [loss of consciousness, seizures, severe bleeding]
```

### Home Care Instructions
- Based on triage level and symptoms — selected from a curated template library.
- Include ORS preparation instructions for any GI symptoms.
- Include temperature monitoring guidance for fever.
- Include rest and hydration for all cases.
- Do NOT include prescription drug instructions.
- Only paracetamol (OTC) and ORS (ASHA-distributed) may be mentioned.

### Reminder Scheduling (Demo Mode)
```python
reminders = []
if triage_level in ["MODERATE", "URGENT"]:
    reminders.append({"when": "today evening", "action": "Check temperature"})
    reminders.append({"when": "tomorrow morning", "action": "Note any changes"})
    reminders.append({"when": f"{followup_hours} hours from now",
                      "action": f"Visit {recommended_facility_name}"})

# Write to followup_reminders table
db.write_reminders(session_id, patient_token, reminders)
```

In production: Celery task scheduled for SMS/push notification delivery.

### Health Scheme Information
Always check if triage conditions match any government scheme and include:
- PM-JAY: for hospitalization cases
- JSSK: for pregnant women or newborns
- NHM Free Drug: for any PHC/CHC visit
- National Iron Plus: for anemia-related symptoms

## Safety Rules
- Do NOT schedule follow-up reminders that contain diagnosis or prescription information.
- Reminder content must pass through the same safety filter as patient-facing responses.
- "Return immediately if" list must always include: loss of consciousness, cannot breathe, severe bleeding, convulsions.
- Do not set follow-up timeframe longer than 1 week for any case that is not MILD.
- Adherence tips must not mention prescription drugs by name.

## Example Input
```json
{
  "triage_level": "MODERATE",
  "symptoms": ["fever", "headache", "body aches"],
  "chief_complaint": "Fever with headache for 3 days",
  "recommended_facility": "Dharmapuri PHC"
}
```

## Example Output
```json
{
  "followup_plan": {
    "follow_up_in": "48 hours",
    "watch_for": ["temperature above 39.5°C", "difficulty breathing", "stiff neck"],
    "return_immediately_if": ["cannot breathe", "loss of consciousness", "convulsions"],
    "home_care": ["Rest", "Drink 2-3 litres of water daily", "Paracetamol for fever"],
    "reminders": [
      {"when": "today evening", "action": "Check temperature", "priority": "high"},
      {"when": "48 hours", "action": "Visit Dharmapuri PHC if not improved", "priority": "high"}
    ],
    "adherence_tips": "Track your temperature twice daily and note any new symptoms.",
    "health_scheme_info": "Free medicines are available at the PHC under NHM free drug scheme."
  }
}
```

## Failure Handling
- **LLM fails:** Generate follow-up plan from template based on triage_level alone. Templates cover all 4 levels.
- **No facility recommended:** Omit facility from reminders; include "visit your nearest health centre."
- **Database write fails:** Log error; still include follow-up plan in response to patient; retry once.
- **Patient is in EMERGENCY:** Do not generate a standard follow-up plan. Generate: "Follow up with your doctor after emergency care. Do not delay."
