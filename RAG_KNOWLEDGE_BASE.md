# RAG_KNOWLEDGE_BASE.md — RuralCare AI Knowledge Base Design

## Purpose

Define the structure, sources, ingestion pipeline, retrieval strategy, and quality standards for the RuralCare AI medical knowledge base.

---

## Scope

The knowledge base contains **only publicly available, verified health information** from authoritative sources. It does not store:
- Patient records
- Proprietary clinical guidelines
- Drug formulary databases (commercial)
- Diagnostic imaging or lab reference ranges (out of scope for MVP)

---

## Knowledge Collections (ChromaDB)

Six collections in `ChromaDB PersistentClient`, each backed by a separate directory under `data/chroma/`.

### Collection 1: `who_health_guidelines`
**Source:** World Health Organization (who.int)
**Content:**
- Integrated Management of Childhood Illness (IMCI) guidelines
- WHO Diarrheal Disease Fact Sheets
- WHO Malaria Treatment Guidelines
- WHO Tuberculosis Treatment Guidelines
- WHO Maternal Health Guidelines
- WHO COVID-19 Home Care Guidance
- WHO First Aid Guidelines

**Document format:** PDF → chunked text
**Metadata tags:** `source: WHO`, `doc_type: guideline`, `symptoms_tags: [...]`

---

### Collection 2: `nhm_india_protocols`
**Source:** National Health Mission India (nhm.gov.in)
**Content:**
- ASHA Training Module (Modules 1–7)
- National Tuberculosis Elimination Programme (NTEP) protocols
- Janani Suraksha Yojana (JSY) guidelines
- National Vector Borne Disease Control guidelines
- PM-JAY scheme information
- JSSK (Janani Shishu Suraksha Karyakram) guidelines
- National Iron Plus Initiative

**Document format:** PDF/HTML → chunked text
**Metadata tags:** `source: NHM`, `doc_type: protocol`, `language: en`

---

### Collection 3: `symptom_disease_mapping`
**Source:** WHO ICD-11 Clinical Descriptions (public), MedlinePlus (NLM)
**Content:**
- Common symptom → condition mapping (non-diagnostic — for triage guidance only)
- Red-flag symptom patterns
- Common tropical disease symptom profiles (malaria, dengue, typhoid, TB)
- Maternal health danger signs
- Child health warning signs

**Important:** This collection is for triage guidance ONLY — retrieval helps agents understand severity, not diagnose.

**Document format:** Structured text (curated → text chunks)
**Metadata tags:** `source: WHO-ICD11`, `triage_relevance: EMERGENCY|URGENT|MODERATE|MILD`

---

### Collection 4: `drug_information_basic`
**Source:** NHM Essential Medicines List, WHO Model Formulary (public sections)
**Content:**
- Essential medicines listed on NHM schedule
- Basic OTC medication information (paracetamol, ORS, zinc)
- Medication storage and safety tips
- When to seek prescription (not substituting prescriptions)

**Strict rule:** This collection contains ONLY basic public health medication information (ORS, paracetamol, iron tablets as distributed by ASHA). Never used to recommend prescription drugs.

---

### Collection 5: `emergency_protocols`
**Source:** Indian Red Cross First Aid Manual (public), WHO Emergency Care Principles
**Content:**
- CPR guidance
- Choking first aid
- Burn first aid
- Snake bite first aid
- Drowning first aid
- Stroke recognition (F.A.S.T.)
- Heart attack recognition
- Seizure management
- Severe bleeding control
- Emergency contact numbers by state

**This collection is ALWAYS searched first when `emergency_flag=True`.**

---

### Collection 6: `regional_health_schemes`
**Source:** Ministry of Health and Family Welfare (mohfw.gov.in)
**Content:**
- PM-JAY scheme details and eligibility
- Ayushman Bharat Health and Wellness Centres
- State-specific health schemes (Tamil Nadu, Maharashtra, UP, etc.)
- Free diagnostic services under NHM
- Free drug distribution schemes
- ASHA incentive scheme information for health workers

---

## Document Ingestion Pipeline

Three ingestion paths are implemented.

### Path 1: Sample / Batch Load (CLI)

Used during initial setup to seed the knowledge base with sample documents:

```bash
python -m app.rag.document_loader --sample
```

**Implementation (`app/rag/document_loader.py`):**

```python
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
import chromadb

# Embeddings: Ollama nomic-embed-text (~768-dim, local, no API key)
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://localhost:11434",
)

# ChromaDB PersistentClient (not HttpClient — no separate server needed)
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """
    Custom separator-aware chunker.
    Replaces RecursiveCharacterTextSplitter — spacy wheel fails on Python 3.14.
    512-char window, 64-char overlap, tries paragraph/sentence breaks first.
    """
    separators = ["\n\n", "\n", ". ", "! ", "? ", " "]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            for sep in separators:
                pos = text.rfind(sep, start, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def load_document(text: str, metadata: dict, collection_name: str) -> int:
    from langchain_core.documents import Document
    chunks = chunk_text(text)
    docs = [
        Document(page_content=chunk, metadata={**metadata, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]
    get_vectorstore(collection_name).add_documents(docs)
    return len(docs)
```

**Why custom `chunk_text()` instead of `RecursiveCharacterTextSplitter`:**
`langchain_text_splitters.RecursiveCharacterTextSplitter` has a transitive dependency on `spacy`, whose binary wheel is not available for Python 3.14 on Windows as of 2026. The custom function reproduces the same separator-aware split logic without any external dependencies.

---

### Path 2: User Upload (Streamlit UI)

Users can upload hospital lists (CSV/Excel) or medical knowledge documents (PDF/TXT/MD) via the upload panel in the Streamlit UI.

**Implementation (`app/services/document_processor.py`):**

```
Hospital CSV/Excel → pandas parse → check-before-insert → facility_cache (SQLite)
Medical PDF/TXT/MD → text extraction → chunk_text() → ChromaDB collection
```

**PDF extraction strategy:**
```python
def _extract_pdf_text(file_bytes: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        pass
    # Fallback: write to temp file, use langchain PyPDFLoader
    import tempfile, os
    from langchain_community.document_loaders import PyPDFLoader
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return "\n".join(p.page_content for p in PyPDFLoader(tmp_path).load())
    finally:
        os.unlink(tmp_path)
```

**Hospital file validation:**
- Required columns: `name`, `facility_type`, `district`, `state`
- `facility_type` must be one of: `Hospital`, `CHC`, `PHC`, `Sub-Centre`
- Duplicate detection: `LOWER(TRIM(name)) + LOWER(TRIM(district)) + LOWER(TRIM(state))` — updates existing row if found

---

### Path 3: FastAPI Endpoint (Programmatic)

```
POST /api/v1/intake     → text symptoms → pipeline
POST /api/v1/voice      → audio upload → Whisper → pipeline
```

These paths do not ingest new knowledge — they use the existing ChromaDB collections to retrieve and ground LLM responses.

---

## Retrieval Strategy

### Vector Store Access

```python
# app/rag/vector_store.py

def get_vectorstore(collection_name: str) -> Chroma:
    return Chroma(
        client=chroma_client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )
```

### Standard Query (Symptom-based)

```python
# app/rag/retriever.py

def get_retriever(collection_name: str, k: int = 5):
    return get_vectorstore(collection_name).as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
        # score_threshold=None:
        # Ollama nomic-embed-text produces raw cosine scores not normalised to 0-1.
        # A hard threshold like 0.65 would incorrectly reject valid results.
        # Volume cap (k) is used instead.
    )
```

### Multi-Collection Sweep

For comprehensive health guidance, all 6 collections are queried in priority order:

```python
QUERY_ORDER = [
    "emergency_protocols",       # Always first
    "symptom_disease_mapping",   # Triage context
    "who_health_guidelines",     # Evidence-based guidance
    "nhm_india_protocols",       # India-specific protocols
    "drug_information_basic",    # OTC/ASHA distributed items only
    "regional_health_schemes",   # Scheme eligibility info
]

def retrieve_multi_collection(query: str, k: int = 5) -> list[Document]:
    seen, results = set(), []
    for collection_name in QUERY_ORDER:
        try:
            docs = get_retriever(collection_name, k).invoke(query)
            for doc in docs:
                content_hash = hash(doc.page_content[:100])
                if content_hash not in seen:
                    seen.add(content_hash)
                    results.append(doc)
        except Exception:
            continue  # skip unavailable collection, don't crash pipeline
    return results
```

### Emergency Fast Path

For emergency cases, bypass multi-collection sweep for speed:

```python
def get_emergency_retriever() -> BaseRetriever:
    return get_vectorstore("emergency_protocols").as_retriever(
        search_kwargs={"k": 3}   # top-3 only, fast
    )
```

---

## Prompt Template for RAG Generation

```python
RAG_SYSTEM_PROMPT = """You are a health information assistant for RuralCare AI.
Your role is to provide clear, simple health information to rural patients in India.

STRICT RULES:
1. Use ONLY the provided context documents to answer. Do not use outside knowledge.
2. Do NOT diagnose any disease or medical condition.
3. Do NOT recommend specific prescription medicines or dosages.
4. If the context does not address the question, say:
   "I don't have specific information on this. Please visit your nearest health center."
5. Use simple language (Grade 6 reading level).
6. Always end with the standard disclaimer.
7. Always cite the source document name.

CONTEXT DOCUMENTS:
{context}

PATIENT QUESTION (translated to English):
{question}

Provide a helpful, safe, grounded response in 3–5 sentences."""
```

---

## Sample Documents for Demo

For the Kaggle/demo version, the knowledge base is seeded with 8 small text files:

### `data/knowledge_base/sample_docs/`

```
sample_fever_guidance.txt       - Basic fever management (WHO-style)
sample_diarrhea_guidance.txt    - ORS and dehydration guidance
sample_malaria_info.txt         - Malaria symptoms and prevention
sample_tb_info.txt              - TB symptoms and NHM DOTS program
sample_maternal_health.txt      - Maternal danger signs
sample_emergency_protocols.txt  - First aid for common emergencies
sample_ors_preparation.txt      - ORS preparation instructions
sample_pmjay_info.txt           - PM-JAY scheme information
```

These are demo-only documents — not real clinical guidelines. Production version ingests actual WHO/NHM PDFs.

---

## Knowledge Base Quality Standards

### Inclusion Criteria
- Published by WHO, NHM India, CDC, or equivalent national health authority.
- Available in the public domain.
- Published within the last 5 years (or explicitly confirmed still current).
- Available in English (primary ingestion language).

### Exclusion Criteria
- Prescription drug information beyond NHM essential medicines.
- Drug dosage recommendations for prescription medicines.
- Diagnostic criteria for specific diseases (triage heuristics only).
- Commercial or proprietary content.
- Content that could enable self-diagnosis.

### Review Process
- New documents reviewed by a medical advisor before ingestion.
- Metadata must include source, date, and triage_relevance tag.
- Quarterly review of collection relevance and accuracy.

---

## Knowledge Base Metrics

| Metric | Demo State | Production Target |
|---|---|---|
| Total document chunks | ~100–200 (8 sample docs) | 10,000–50,000 |
| Collections | 6 | 6–12 |
| Embedding model | Ollama nomic-embed-text (~768-dim) | Same or cloud upgrade |
| Chunking | Custom `chunk_text()` — 512-char, 64-char overlap | Same |
| Score threshold | None (Ollama scores not normalised) | None (k cap) |
| Average retrieval latency | < 500ms (local Ollama) | < 200ms |
| Emergency protocol coverage | Top 20 emergencies | Top 50 emergencies |
| Language coverage | English only (translated at query time) | English + 6 Indian languages |

---

## Multilingual Knowledge Base (Production Roadmap)

Phase 2 will add translated knowledge chunks:
1. Use IndicTrans2 to translate ingested documents into Hindi, Tamil, Bengali, Telugu, Kannada, Marathi.
2. Store translated chunks in the same collections with `language: hi/ta/bn/te/kn/mr` metadata.
3. Retriever filters by language for direct multilingual RAG (no translation step at runtime).

---

## Acceptance Criteria

- [x] All 6 ChromaDB collections created and accessible via `get_vectorstore()`.
- [x] Sample documents seeded for demo via `python -m app.rag.document_loader --sample`.
- [x] Multi-collection sweep retrieves results for common symptom queries.
- [x] Emergency protocol retrieval works on `emergency_flag=True` path (top-3, fast).
- [x] User upload path adds chunks to ChromaDB immediately and makes them retrievable.
- [x] No document chunk contains diagnostic language.
- [x] All documents have correct metadata (source, collection, chunk_index).
- [x] Retrieval latency < 1 second on local Ollama hardware.
- [x] RAG response includes source citation for every factual claim.
