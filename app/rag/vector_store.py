"""
RuralCare AI — ChromaDB Vector Store
Manages all ChromaDB collections for the medical knowledge base.
"""

from pathlib import Path

import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from app.utils.config import get_config
from app.utils.logger import get_logger

logger = get_logger(__name__)

COLLECTIONS = [
    "who_health_guidelines",
    "nhm_india_protocols",
    "symptom_disease_mapping",
    "drug_information_basic",
    "emergency_protocols",
    "regional_health_schemes",
]

_embeddings: Embeddings | None = None
_client: chromadb.ClientAPI | None = None


def get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is None:
        cfg = get_config()
        if cfg.embed_provider == "ollama":
            from langchain_ollama import OllamaEmbeddings
            _embeddings = OllamaEmbeddings(
                model=cfg.ollama_embed_model,
                base_url=cfg.ollama_base_url,
            )
            logger.info("Embeddings: Ollama/%s @ %s", cfg.ollama_embed_model, cfg.ollama_base_url)
        else:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            _embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            logger.info("Embeddings: HuggingFace/all-MiniLM-L6-v2")
    return _embeddings


def get_collection_names() -> list[str]:
    return list(COLLECTIONS)


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        path = get_config().chroma_db_path
        Path(path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def init_vector_store() -> None:
    client = get_chroma_client()
    for name in COLLECTIONS:
        client.get_or_create_collection(name)
    logger.info("ChromaDB initialised with %d collections.", len(COLLECTIONS))


def get_vectorstore(collection_name: str) -> Chroma:
    if collection_name not in COLLECTIONS:
        raise ValueError(f"Unknown collection: {collection_name}")
    return Chroma(
        client=get_chroma_client(),
        collection_name=collection_name,
        embedding_function=get_embeddings(),
    )


def get_retriever(collection_name: str, k: int | None = None, score_threshold: float | None = None):
    cfg = get_config()
    _k = k or cfg.rag_top_k
    # Use plain similarity when score_threshold is None (avoids threshold filtering issues
    # when embedding model scores are not in the 0-1 range expected by langchain_chroma)
    if score_threshold is None:
        return get_vectorstore(collection_name).as_retriever(
            search_kwargs={"k": _k},
        )
    return get_vectorstore(collection_name).as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": _k, "score_threshold": score_threshold},
    )


def collection_doc_count(collection_name: str) -> int:
    return get_chroma_client().get_collection(collection_name).count()
