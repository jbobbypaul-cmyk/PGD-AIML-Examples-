"""
RuralCare AI — Knowledge Base Document Loader
Ingests PDFs, text files, and markdown into ChromaDB collections.

Usage:
    python -m app.rag.document_loader --sample        # Load demo documents
    python -m app.rag.document_loader --dir path/to/pdfs --collection who_health_guidelines
"""

import argparse
from pathlib import Path

from app.rag.vector_store import get_vectorstore, get_chroma_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Inline chunker — avoids langchain_text_splitters/__init__.py which eagerly
# imports SpacyTextSplitter and breaks on Python 3.14 (spacy not compatible).
_CHUNK_SIZE    = 512
_CHUNK_OVERLAP = 64
_SEPARATORS    = ["\n\n", "\n", ". ", "! ", "? ", " "]


def chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks at natural boundaries."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        segment = text[start:end]
        # Try to end at the last natural separator in the back half of the segment
        if end < len(text):
            for sep in _SEPARATORS:
                idx = segment.rfind(sep, chunk_size // 2)
                if idx != -1:
                    segment = segment[: idx + len(sep)]
                    break
        chunk = segment.strip()
        if chunk:
            chunks.append(chunk)
        start += max(1, len(segment) - overlap)
    return chunks


def _split_documents(docs: list) -> list:
    """Chunk a list of langchain Document objects using the inline chunker."""
    from langchain_core.documents import Document
    result = []
    for doc in docs:
        for chunk in chunk_text(doc.page_content):
            result.append(Document(page_content=chunk, metadata=dict(doc.metadata)))
    return result

# ── Demo Seed Documents ───────────────────────────────────────────────

DEMO_DOCS: dict[str, list[str]] = {
    "who_health_guidelines": [
        """Fever Management Guidelines (WHO 2023)
Fever (temperature above 38°C/100.4°F) lasting more than 3 days requires medical evaluation.
For mild fever: rest, adequate hydration, and paracetamol for comfort.
Danger signs requiring immediate care: fever with stiff neck, skin rash, difficulty breathing,
or altered consciousness. Always measure temperature with a thermometer if available.
Source: WHO Fever and Acute Illness Guidelines 2023""",

        """Diarrhea and Dehydration Management (WHO 2023)
Oral Rehydration Solution (ORS) is the first-line treatment for diarrhea-related dehydration.
Mix one ORS sachet in 1 litre of clean water. Give small sips frequently.
Signs of severe dehydration: sunken eyes, dry mouth, no urination for 8+ hours, lethargy.
Zinc supplementation (10–20 mg/day for 10–14 days) reduces duration and severity.
Seek immediate care for blood in stool, high fever, or inability to drink.
Source: WHO Diarrhoeal Disease Fact Sheet 2023""",
    ],
    "nhm_india_protocols": [
        """ASHA Health Worker Protocol — Fever (NHM India)
ASHAs should refer patients with fever lasting more than 3 days to the nearest PHC.
Provide paracetamol for symptomatic relief while arranging referral.
Collect blood slide sample for malaria if the patient lives in a malaria-endemic area.
Ensure patient is hydrated. Advise rest and follow-up within 48 hours.
Source: NHM ASHA Training Module 4""",

        """National Iron Plus Initiative (NHM India)
Weekly Iron and Folic Acid Supplementation (WIFS) for adolescent girls and boys.
Daily IFA supplementation for pregnant women (one tablet per day throughout pregnancy).
ASHAs distribute IFA tablets free of charge at sub-centre and PHC level.
Benefits: prevents anaemia, supports healthy pregnancy outcomes.
Source: NHM National Iron Plus Initiative Guidelines 2024""",
    ],
    "emergency_protocols": [
        """Emergency First Aid — Unconscious Person (Indian Red Cross 2022)
1. Check for response: tap shoulder gently and call out loudly.
2. Call for help: Dial 108 (ambulance) or 112 (emergency services) immediately.
3. Open airway: tilt head back gently and lift the chin.
4. Check for breathing for 10 seconds — look, listen, feel.
5. If not breathing: begin CPR — 30 chest compressions followed by 2 rescue breaths.
6. Continue CPR until ambulance arrives or person starts breathing.
Do NOT leave the person alone. Keep them warm.
Source: Indian Red Cross First Aid Manual 2022""",

        """Emergency First Aid — Difficulty Breathing (WHO Emergency Care 2022)
If a person cannot breathe or is struggling to breathe:
1. Call 108 immediately. Do not delay.
2. Help person sit upright — forward-leaning position (tripod position) helps open the airway.
3. Loosen tight clothing around neck and chest.
4. Do NOT give food or water.
5. Stay with the person. Keep them calm. Reassure them help is coming.
6. If breathing stops: begin rescue breathing.
Source: WHO Emergency Care Principles 2022""",

        """Emergency First Aid — Snake Bite (NHM India)
1. Keep the person calm and still. Movement spreads venom faster.
2. Call 108 (ambulance) or take patient to nearest hospital immediately.
3. Remove any tight jewellery or clothing near the bite site.
4. Immobilise the bitten limb below heart level.
5. Do NOT cut the bite, suck venom, apply tourniquet, or apply ice.
6. Note the time of bite and description of snake if safe to do so.
Anti-snake venom is available at government hospitals and CHCs.
Source: NHM Snake Bite Management Protocol 2022""",
    ],
    "symptom_disease_mapping": [
        """Fever Urgency Classification (WHO ICD-11 Triage Reference 2022)
MILD: Low-grade fever below 38.5°C, no other serious symptoms, duration less than 2 days.
   Action: Rest, hydration, paracetamol, monitor.
MODERATE: Fever above 38.5°C lasting 2 to 5 days, with headache or body aches.
   Action: Visit PHC within 24–48 hours.
URGENT: High fever above 39.5°C, rigors, vomiting, unable to eat or drink.
   Action: Visit CHC or district hospital within 2–4 hours.
EMERGENCY: Fever with stiff neck, altered consciousness, difficulty breathing, or petechial rash.
   Action: Call 112 immediately. Do not wait.
Source: WHO ICD-11 Clinical Triage Reference 2022""",
    ],
    "regional_health_schemes": [
        """PM-JAY (Pradhan Mantri Jan Arogya Yojana) — Key Information
PM-JAY provides health insurance coverage of Rs. 5 lakh per family per year.
Eligibility: Families listed under SECC (Socio-Economic Caste Census) database.
Coverage: 1,574 medical and surgical packages including hospitalization.
How to access: Visit any empanelled government or private hospital with Aadhaar card.
Check eligibility online at pmjay.gov.in or call helpline 14555.
Source: NHM PM-JAY Beneficiary Guidelines 2024""",

        """Janani Suraksha Yojana (JSY) — Maternal Health Scheme
JSY provides cash assistance to pregnant women who deliver in government health facilities.
Eligible: Below poverty line (BPL) women, SC/ST women, women aged 19 and above.
Cash benefit: Rs. 1,400 in rural areas, Rs. 1,000 in urban areas (Low Performing States).
How to access: Register with ASHA worker or PHC during antenatal care.
Also provides: Free antenatal check-ups, iron tablets, tetanus injection under JSSK.
Source: NHM JSY Programme Guidelines 2024""",
    ],
    "drug_information_basic": [
        """Oral Rehydration Solution (ORS) — Patient Information
ORS replaces fluids and salts lost during diarrhea and vomiting.
How to prepare: Mix one ORS sachet in 1 litre of clean boiled water (cooled).
How to give: Small sips every few minutes. Give continuously.
For children: 50–100 ml after each loose stool.
For adults: as much as tolerated.
ORS sachets are available free at sub-centres, PHCs, and ASHAs.
Do NOT add sugar, salt, or other ingredients to prepared ORS.
Source: WHO/UNICEF ORS Use Guidelines 2023""",
    ],
}


def load_sample_docs() -> None:
    """Seed ChromaDB with demo documents for Kaggle/local demo."""
    from langchain_core.documents import Document

    total = 0
    for collection_name, texts in DEMO_DOCS.items():
        vs = get_vectorstore(collection_name)
        docs = []
        for i, text in enumerate(texts):
            for j, chunk in enumerate(chunk_text(text)):
                docs.append(Document(
                    page_content=chunk,
                    metadata={
                        "source": f"demo_{collection_name}_{i}",
                        "collection": collection_name,
                        "doc_type": "demo",
                        "chunk_index": j,
                    },
                ))
        vs.add_documents(docs)
        total += len(docs)
        logger.info("Loaded %d chunks into '%s'.", len(docs), collection_name)

    logger.info("Sample knowledge base loaded: %d total chunks.", total)


def load_directory(dir_path: str, collection_name: str, doc_type: str = "guideline") -> int:
    """Load all PDFs and text files from a directory into a ChromaDB collection."""
    # Lazy import — keeps spacy out of the import chain on Python 3.14
    from langchain_community.document_loaders import PyPDFLoader, TextLoader

    path = Path(dir_path)
    if not path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    all_docs = []
    for file in path.glob("**/*"):
        if file.suffix.lower() == ".pdf":
            loader = PyPDFLoader(str(file))
        elif file.suffix.lower() in {".txt", ".md"}:
            loader = TextLoader(str(file), encoding="utf-8")
        else:
            continue

        try:
            raw = loader.load()
            chunks = _split_documents(raw)
            for chunk in chunks:
                chunk.metadata.update({
                    "source": file.name,
                    "collection": collection_name,
                    "doc_type": doc_type,
                })
            all_docs.extend(chunks)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", file, exc)

    if all_docs:
        get_vectorstore(collection_name).add_documents(all_docs)
        logger.info("Loaded %d chunks from %s into '%s'.", len(all_docs), dir_path, collection_name)

    return len(all_docs)


# Alias used by streamlit_app.py, notebooks, and tests
ingest_demo_docs = load_sample_docs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RuralCare AI Knowledge Base Loader")
    parser.add_argument("--sample", action="store_true", help="Load demo sample documents")
    parser.add_argument("--dir", help="Directory path of documents to ingest")
    parser.add_argument("--collection", help="Target ChromaDB collection name")
    args = parser.parse_args()

    from app.rag.vector_store import init_vector_store
    init_vector_store()

    if args.sample:
        load_sample_docs()
    elif args.dir and args.collection:
        count = load_directory(args.dir, args.collection)
        print(f"Loaded {count} chunks into '{args.collection}'.")
    else:
        parser.print_help()
