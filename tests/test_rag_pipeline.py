"""
Tests for app/rag/ — vector_store, document_loader, retriever.
Uses an in-memory/temp ChromaDB instance so no persistent DB needed.
"""

import os
import tempfile
import pytest


@pytest.fixture(scope="module")
def temp_chroma_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestVectorStore:
    def test_init_vector_store_creates_collections(self, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        from app.rag.vector_store import init_vector_store, get_collection_names
        init_vector_store()
        names = get_collection_names()
        assert "who_health_guidelines" in names
        assert "emergency_protocols" in names
        assert len(names) >= 6

    def test_reinit_is_idempotent(self, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        from app.rag.vector_store import init_vector_store
        init_vector_store()
        init_vector_store()  # should not raise


class TestDocumentLoader:
    def test_demo_docs_exist(self):
        from app.rag.document_loader import DEMO_DOCS
        assert len(DEMO_DOCS) >= 5
        for key, content in DEMO_DOCS.items():
            assert isinstance(content, str) and len(content) > 50

    def test_chunk_text_splits_long_doc(self):
        from app.rag.document_loader import chunk_text
        long_text = "Fever is a common symptom. " * 100
        chunks = chunk_text(long_text)
        assert len(chunks) > 1

    def test_chunk_text_short_doc_single_chunk(self):
        from app.rag.document_loader import chunk_text
        chunks = chunk_text("Short text.")
        assert len(chunks) >= 1

    def test_ingest_demo_docs_does_not_raise(self, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        from app.rag.vector_store import init_vector_store
        from app.rag.document_loader import ingest_demo_docs
        init_vector_store()
        ingest_demo_docs()  # should complete without raising


class TestRetriever:
    def test_retrieve_returns_string(self, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        from app.rag.vector_store import init_vector_store
        from app.rag.document_loader import ingest_demo_docs
        from app.rag.retriever import retrieve_health_context
        init_vector_store()
        ingest_demo_docs()
        ctx, sources = retrieve_health_context("fever headache body pain")
        assert isinstance(ctx, str)
        assert isinstance(sources, list)

    def test_emergency_retrieve_is_fast(self, temp_chroma_dir, monkeypatch):
        import time
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        from app.rag.vector_store import init_vector_store
        from app.rag.document_loader import ingest_demo_docs
        from app.rag.retriever import retrieve_emergency_context
        init_vector_store()
        ingest_demo_docs()
        start = time.time()
        ctx, sources = retrieve_emergency_context("unconscious not breathing")
        elapsed = time.time() - start
        assert elapsed < 5.0  # must be fast even on cold start
        assert isinstance(ctx, str)
