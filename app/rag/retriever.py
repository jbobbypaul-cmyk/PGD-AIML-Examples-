"""
RuralCare AI — RAG Retrieval Logic
Provides standard and emergency retrievers over ChromaDB collections.
"""

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel

from app.rag.vector_store import get_retriever, get_vectorstore
from app.utils.config import get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)

STANDARD_COLLECTION_ORDER = [
    "symptom_disease_mapping",
    "who_health_guidelines",
    "nhm_india_protocols",
    "drug_information_basic",
    "regional_health_schemes",
]


def retrieve_health_context(
    query: str,
    triage_level: str,
    llm: BaseChatModel,
) -> tuple[list[Document], list[str]]:
    """
    Query relevant collections and return deduplicated, ranked document chunks
    along with their source citations.
    """
    cfg = get_config()
    collections = list(STANDARD_COLLECTION_ORDER)
    if triage_level == "EMERGENCY":
        collections.insert(0, "emergency_protocols")

    all_docs: list[Document] = []
    seen_content: set[str] = set()

    for col in collections:
        try:
            base = get_retriever(col, score_threshold=None)  # no threshold for broader recall
            docs = base.invoke(query)
            for doc in docs:
                if doc.page_content not in seen_content:
                    seen_content.add(doc.page_content)
                    all_docs.append(doc)
        except Exception as exc:
            logger.warning("Retrieval failed for collection '%s': %s", col, exc)

    all_docs = all_docs[: cfg.rag_top_k * 2]
    sources = list({
        doc.metadata.get("source", "Unknown Source")
        for doc in all_docs
    })

    logger.info("Retrieved %d chunks from %d collections.", len(all_docs), len(collections))
    return all_docs, sources


def retrieve_emergency_context(query: str) -> tuple[list[Document], list[str]]:
    """
    Fast path emergency retrieval — no MultiQueryRetriever, top-3 only, lower threshold.
    Target: under 500ms.
    """
    try:
        retriever = get_retriever("emergency_protocols", k=3, score_threshold=None)
        docs = retriever.invoke(query)
    except Exception as exc:
        logger.warning("Emergency retrieval failed: %s", exc)
        docs = []

    sources = [d.metadata.get("source", "Emergency Protocol") for d in docs]
    return docs, sources


def build_context_string(docs: list[Document]) -> str:
    if not docs:
        return ""
    return "\n\n---\n\n".join(d.page_content for d in docs)
