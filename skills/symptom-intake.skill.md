# Skill: Symptom Intake

## Skill Name
`symptom-intake`

## Purpose
Extract, normalize, and structure patient-reported symptoms from free-form text or transcribed voice input. Produce a clean symptom profile that downstream agents (Triage, RAG) can act on reliably.

## When to Use
- First agent called after emergency check passes (no emergency flag).
- Use when implementing the `symptom_intake_agent` function.
- Use when modifying symptom extraction prompts or output schemas.
- Use when debugging why triage is incorrect (start here — bad intake = bad triage).

## Inputs Expected

```json
{
  "translated_input": "English translation of patient input",
  "patient_token": "PT-xxxxxxxx",
  "session_id": "uuid"
}
```

## Output Format

```json
{
  "symptoms": ["fever", "headache", "body aches", "chills"],
  "chief_complaint": "Fever with headache for 3 days",
  "symptom_duration": "3 days",
  "symptom_severity": "moderate",
  "additional_context": "Patient is 45 years old, no known allergies mentioned"
}
```

## Decision Rules

### Extraction Rules
1. Extract all distinct symptoms mentioned (not just the first).
2. Normalize symptom language — "head is hurting" → "headache".
3. Extract duration if mentioned: "since yesterday", "for 3 days", "this morning".
4. Map severity to: mild / moderate / severe only.
5. Preserve any relevant context (age, pregnancy, existing conditions if mentioned).
6. If severity not mentioned: default to "moderate" (conservative).
7. If duration not mentioned: set to "unknown".

### LLM System Prompt
```
You are a symptom extraction assistant for a rural health information system.
Your role is ONLY to extract and structure symptoms.
Do NOT diagnose. Do NOT suggest treatments. Do NOT name diseases.
Output strict JSON only. No explanation text.
JSON fields required: chief_complaint, symptoms (array), duration, severity
```

### Output Schema Validation
After LLM output, validate with Pydantic:
```python
class SymptomExtractionOutput(BaseModel):
    chief_complaint: str
    symptoms: list[str] = Field(min_length=1)
    symptom_duration: str = "unknown"
    symptom_severity: Literal["mild", "moderate", "severe"] = "moderate"
```
If validation fails: retry LLM once with explicit JSON format instruction.
If second attempt fails: use raw input as chief_complaint, symptoms=[], severity="moderate".

## Safety Rules
- NEVER include a disease name in the extracted symptoms.
- NEVER infer a diagnosis from symptoms.
- If patient mentions suicidal ideation or self-harm: set emergency_flag=True immediately.
- PHI (patient name, phone number) must be stripped from symptoms before storage.
- Symptom data must be stored only as part of the anonymized session.

## Example Input
```json
{
  "translated_input": "I have had fever for 3 days, my head hurts a lot, and I feel very weak. I also have chills at night.",
  "patient_token": "PT-a3f8b2c1",
  "session_id": "f4a8b2c1-0000-0000-0000-000000000001"
}
```

## Example Output
```json
{
  "symptoms": ["fever", "headache", "weakness", "chills"],
  "chief_complaint": "Fever with headache and chills for 3 days",
  "symptom_duration": "3 days",
  "symptom_severity": "moderate",
  "additional_context": ""
}
```

## Failure Handling
- **LLM returns empty:** Use raw input as chief_complaint, symptoms=["unknown"], severity="moderate". Continue pipeline.
- **LLM returns diagnosis:** Strip diagnosis from output; log safety event; use remaining fields.
- **JSON parse error:** Retry once. If fails again: fallback to basic extraction.
- **Input too short (< 5 chars):** Ask user to provide more detail. Do not call LLM.
- **Input too long (> 2000 chars):** Truncate to first 2000 characters; log truncation.
