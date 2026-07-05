# Skill: Medical Triage

## Skill Name
`medical-triage`

## Purpose
Classify the clinical urgency of a patient's situation into one of four levels (EMERGENCY / URGENT / MODERATE / MILD) based on structured symptom data. Guide downstream agents on the appropriate care pathway.

## When to Use
- Called after Symptom Intake Agent produces structured symptoms.
- Use when implementing the `medical_triage_agent` function.
- Use when modifying triage classification prompts or urgency thresholds.
- Use when investigating misclassified triage levels.

## Inputs Expected

```json
{
  "symptoms": ["fever", "headache", "body aches", "chills"],
  "chief_complaint": "Fever with headache for 3 days",
  "symptom_duration": "3 days",
  "symptom_severity": "moderate",
  "patient_token": "PT-xxxxxxxx"
}
```

## Output Format

```json
{
  "triage_level": "MODERATE",
  "triage_reasoning": "Fever lasting 3 days with headache and body aches requires medical evaluation within 24-48 hours. No immediate life-threatening symptoms present.",
  "recommended_care_setting": "Primary Health Centre (PHC)",
  "urgency_timeframe": "Within 48 hours"
}
```

## Decision Rules

### Triage Level Definitions

| Level | Definition | Timeframe |
|---|---|---|
| EMERGENCY | Life-threatening: airway, breathing, circulation compromised; altered consciousness; severe bleeding; poisoning | Immediately (call 112) |
| URGENT | Serious but not immediately life-threatening: high fever >39.5C, severe pain, inability to eat/drink, rapidly worsening | Within 2-4 hours |
| MODERATE | Needs medical evaluation: fever 3+ days, moderate pain, multiple symptoms | Within 24-48 hours |
| MILD | Can self-monitor with guidance: low-grade fever <1 day, mild discomfort, no danger signs | Monitor; seek care if worsens |

### Classification Rules
1. If emergency_flag=True from Symptom Intake: output EMERGENCY without LLM call (rule-based override).
2. If uncertain between two levels: always choose the higher urgency (conservative triage).
3. Fever >3 days = at least MODERATE.
4. Child under 5 with any fever = at least URGENT (conservative for pediatric).
5. Pregnant woman with fever = at least URGENT.
6. Elderly (mentioned >65) with moderate symptoms = at least URGENT.
7. If patient mentions worsening symptoms: escalate one level.

### LLM System Prompt
```
You are a triage classification assistant for a rural health information system.
Classify the urgency level: EMERGENCY, URGENT, MODERATE, or MILD.
Use WHO-aligned triage principles. Be conservative — when uncertain, choose higher urgency.
Do NOT name any disease or diagnosis.
Do NOT recommend any medicine.
Output JSON only: { triage_level, triage_reasoning, recommended_care_setting, urgency_timeframe }
```

### Care Setting Mapping
```
EMERGENCY → District Hospital Emergency / Dial 112
URGENT    → Community Health Centre (CHC) or District Hospital OPD
MODERATE  → Primary Health Centre (PHC)
MILD      → Sub-Centre / ASHA worker home visit / Self-care
```

## Safety Rules
- Emergency flag from Symptom Intake OVERRIDES LLM triage — cannot be downgraded.
- Triage reasoning must NEVER mention a specific disease name.
- Conservative bias is mandatory — false positive escalations are safer than missed emergencies.
- Do not factor in patient's stated preference ("I don't want to go to hospital") — triage is clinical, not social.
- Pediatric and maternal cases default to higher urgency tier.

## Example Input
```json
{
  "symptoms": ["fever", "headache", "body aches", "chills"],
  "chief_complaint": "Fever with headache for 3 days",
  "symptom_duration": "3 days",
  "symptom_severity": "moderate"
}
```

## Example Output
```json
{
  "triage_level": "MODERATE",
  "triage_reasoning": "Persistent fever lasting 3 days with associated headache and body aches requires medical evaluation within 48 hours. No immediate danger signs are present, but continued monitoring without medical attention is not recommended.",
  "recommended_care_setting": "Primary Health Centre (PHC)",
  "urgency_timeframe": "Within 48 hours"
}
```

## Failure Handling
- **LLM returns invalid level:** Validate against ["EMERGENCY", "URGENT", "MODERATE", "MILD"]. If invalid: default to URGENT (conservative).
- **LLM mentions disease name:** Strip disease name; keep triage level; log safety event.
- **LLM returns no reasoning:** Use standard template reasoning based on triage level.
- **Empty symptom list:** Default to URGENT (cannot triage without symptoms; patient may be in distress).
- **LLM error:** Default to URGENT; return static triage guidance; log error.
