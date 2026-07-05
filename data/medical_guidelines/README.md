# data/medical_guidelines/

Place verified public health documents here for ingestion into ChromaDB.

## Accepted Formats
- `.pdf` — WHO, NHM, CDC guidelines
- `.txt` — Plain text health protocols
- `.md`  — Structured health information

## How to Ingest

```bash
# Load demo sample documents (for Kaggle/local demo)
python -m app.rag.document_loader --sample

# Load a directory of PDFs into a specific collection
python -m app.rag.document_loader --dir data/medical_guidelines/who/ --collection who_health_guidelines
python -m app.rag.document_loader --dir data/medical_guidelines/nhm/ --collection nhm_india_protocols
```

## Recommended Folder Structure

```
data/medical_guidelines/
├── who/            ← WHO guidelines (PDFs from who.int)
├── nhm/            ← NHM India protocols (from nhm.gov.in)
├── emergency/      ← First aid manuals
├── schemes/        ← PM-JAY, JSY, JSSK scheme documents
└── symptoms/       ← Symptom-triage mapping documents
```

## Approved Sources Only

Documents must come from:
- World Health Organization (who.int)
- National Health Mission India (nhm.gov.in)
- Ministry of Health & Family Welfare (mohfw.gov.in)
- Indian Red Cross Society
- CDC (cdc.gov) — selected public health documents

Do NOT ingest: proprietary clinical guidelines, prescription drug databases,
commercial health content, or content not in the public domain.

