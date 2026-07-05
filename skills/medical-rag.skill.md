# Skill: Medical RAG

## Skill Name
`medical-rag`

## Purpose
Retrieve relevant, evidence-based health information from the verified knowledge base (ChromaDB) and generate a patient-appropriate health guidance response grounded exclusively in retrieved documents. This agent is the primary source of health information for patients.

## When to Use
- Called after Medical Triage Agent produces a triage level.
- Use when implementing the `medical_rag_agent` function.
- Use when adding new document collections to the knowledge base.
- Use when investigating irrelevant or hallucinated responses.
- Use when tuning retrieval parameters (k, score threshold, chunk size).

## Inputs Expected

```json
{
  "chief_complaint": "Fever with headache for 3 days",
  "symptoms": ["fever", "headache", "body aches", "chills"],
  "triage_level": "MODERATE",
  "patient_token": "PT-xxxxxxxx"
}
```

## Output Format

```json
{
  "rag_query": "fever headache body aches chills: management and guidance",
  "rag_context": "Retrieved document text chunks (internal use)",
  "rag_sources": ["WHO_Fever_Guidelines_2023", "NHM_ASHA_Module_4"],
  "health_guidance": "Patient-facing health information in accessible language",
  "grounding_confidence": "high | medium | low | none"
}
```

## Decision Rules

### Query Construction
```python
rag_query = f"{chief_complaint}: {', '.join(symptoms[:5])}"
# Example: "Fever with headache for 3 days: fever, headache, body aches, chills"
```

### Collection Priority
```
1. emergency_protocols         (if triage_level == EMERGENCY)
2. symptom_disease_mapping     (always — for context)
3. who_health_guidelines       (primary evidence)
4. nhm_india_protocols         (India-specific guidance)
5. drug_information_basic      (only for OTC/ASHA items)
6. regional_health_schemes     (always — for scheme awareness)
```

### Retrieval Parameters
```python
search_type = "similarity_score_threshold"
score_threshold = 0.65
k = 5  # top-5 chunks per collection
```

### Grounding Confidence
```
high   → at least 3 chunks with score > 0.75
medium → at least 1 chunk with score > 0.65
low    → chunks retrieved but score 0.50-0.65
none   → no chunks above threshold
```

### Fallback When No Relevant Documents Found
```
"I don't have specific information about your symptoms in our health guidelines.
Please visit your nearest Primary Health Centre or speak with your ASHA worker.
They can provide appropriate guidance based on your condition.
[DISCLAIMER]"
```

### LLM Generation Rules
1. Use ONLY the retrieved context — never improvise medical facts.
2. Write at Grade 6 reading level — simple, clear, short sentences.
3. Do NOT name diseases.
4. Mention relevant government schemes when applicable (PM-JAY, JSSK, etc.).
5. End every response with: "Visit your nearest health centre for proper evaluation."
6. Include source citations at the end.
7. Maximum response length: 300 words for patient-facing guidance.

### LLM System Prompt
```
You are a health information assistant for RuralCare AI.
Provide simple, clear health guidance for rural patients.

RULES:
- Use ONLY the provided context documents below. Never add information from outside.
- Do NOT diagnose any disease.
- Do NOT recommend prescription medicines.
- Use simple language (Grade 6 level).
- If context doesn't address the question: say "please visit your health centre."
- Always cite your source documents at the end.
- Always end with "Visit your nearest health centre for proper evaluation."

CONTEXT:
{context}

PATIENT QUERY: {query}
```

## Safety Rules
- Every response must be grounded in retrieved documents OR labeled as fallback.
- If the LLM response contains a disease name: run through safety filter to strip it.
- If the LLM response contains a drug dosage: run through safety filter to strip it.
- Response must always include source citations — no citations = run safety filter fallback.
- RAG queries must never include patient PHI — use chief_complaint and symptom list only.

## Example Input
```json
{
  "chief_complaint": "Fever with headache for 3 days",
  "symptoms": ["fever", "headache", "body aches", "chills"],
  "triage_level": "MODERATE"
}
```

## Example Output
```json
{
  "rag_query": "fever headache body aches chills: management and guidance",
  "rag_sources": ["WHO_Fever_Guidelines_2023", "NHM_ASHA_Module_4"],
  "health_guidance": "Fever that lasts more than 3 days with headache and body aches needs medical attention. Here is what you can do:\n\n1. Rest and drink plenty of clean water or ORS solution.\n2. Paracetamol can help reduce fever — follow the dosage on the package or ask a pharmacist.\n3. Visit your nearest Primary Health Centre (PHC) within the next 24-48 hours for proper evaluation.\n4. If your fever gets much worse, you develop difficulty breathing, or you lose consciousness — call 112 immediately.\n\nYou may be eligible for free treatment at your government health centre under PM-JAY or Ayushman Bharat.\n\nVisit your nearest health centre for proper evaluation.\n\nSource: WHO Fever Guidelines 2023 | NHM ASHA Training Module 4",
  "grounding_confidence": "high"
}
```

## Failure Handling
- **No relevant documents found (grounding_confidence=none):** Return fallback message; do NOT call LLM; log event.
- **Low confidence (<0.65):** Add disclaimer: "This is general guidance as our knowledge base lacks specific information on this topic."
- **LLM response too long (>400 words):** Truncate to 300 words; ensure disclaimer and sources still present.
- **LLM generates diagnosis:** Safety filter intercepts; return fallback.
- **ChromaDB unavailable:** Skip RAG; return static fallback message; flag `rag_context="unavailable"`.
