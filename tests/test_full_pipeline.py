"""
Integration tests for run_pipeline() end-to-end.
Mocks the LLM to avoid API costs; real DB and RAG run in temp directories.
"""

import os
import json
import tempfile
import pytest
from unittest.mock import MagicMock, patch


SYMPTOM_INTAKE_RESPONSE = json.dumps({
    "chief_complaint": "fever",
    "symptoms": ["fever", "headache"],
    "duration": "3 days",
    "severity": "moderate",
})

TRIAGE_RESPONSE = json.dumps({
    "triage_level": "MODERATE",
    "reasoning": "Fever for 3 days warrants PHC visit.",
    "care_setting": "PHC",
})

RAG_RESPONSE = "Stay hydrated. Visit the nearest PHC if fever exceeds 102°F."


def _fake_llm_sequence(*responses):
    """LLM that cycles through a list of responses per call."""
    call_count = {"n": 0}
    m = MagicMock()
    def _invoke(*args, **kwargs):
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        r = MagicMock()
        r.content = responses[idx]
        return r
    m.invoke.side_effect = _invoke
    return m


@pytest.fixture(scope="module")
def temp_db_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture(scope="module")
def temp_chroma_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


class TestFullPipeline:
    @patch("app.services.orchestrator._get_llm")
    def test_mild_case_completes(self, mock_get_llm, temp_db_dir, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{temp_db_dir}/test.db")
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        mock_get_llm.return_value = _fake_llm_sequence(
            SYMPTOM_INTAKE_RESPONSE, TRIAGE_RESPONSE, RAG_RESPONSE, "{}", "{}", "{}"
        )
        from app.database.sqlite_client import init_db
        from app.rag.vector_store import init_vector_store
        from app.rag.document_loader import ingest_demo_docs
        init_db()
        init_vector_store()
        ingest_demo_docs()

        from app.services.orchestrator import run_pipeline
        result = run_pipeline(
            raw_input="I have had fever for 3 days and headache.",
            language="en",
        )
        assert result.get("triage_level") in ("MILD", "MODERATE", "URGENT", "EMERGENCY")
        assert result.get("session_id") is not None
        assert isinstance(result.get("audit_log"), list)

    @patch("app.services.orchestrator._get_llm")
    def test_emergency_fast_path(self, mock_get_llm, temp_db_dir, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{temp_db_dir}/test.db")
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        mock_get_llm.return_value = _fake_llm_sequence(RAG_RESPONSE)

        from app.services.orchestrator import run_pipeline
        result = run_pipeline(
            raw_input="My father is unconscious and cannot breathe.",
            language="en",
        )
        assert result.get("emergency_flag") is True
        assert result.get("triage_level") == "EMERGENCY"
        assert result.get("emergency_alert") not in (None, "")

    @patch("app.services.orchestrator._get_llm")
    def test_safety_disclaimer_always_present(self, mock_get_llm, temp_db_dir, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{temp_db_dir}/test.db")
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        mock_get_llm.return_value = _fake_llm_sequence(
            SYMPTOM_INTAKE_RESPONSE, TRIAGE_RESPONSE, RAG_RESPONSE, "{}", "{}", "{}"
        )
        from app.services.orchestrator import run_pipeline
        result = run_pipeline(raw_input="I feel a bit tired.", language="en")
        final = result.get("final_response", "") + result.get("disclaimer", "")
        assert "not a doctor" in final.lower() or "healthcare professional" in final.lower() \
               or "disclaimer" in final.lower() or "awareness" in final.lower()

    @patch("app.services.orchestrator._get_llm")
    def test_session_id_unique_per_call(self, mock_get_llm, temp_db_dir, temp_chroma_dir, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{temp_db_dir}/test.db")
        monkeypatch.setenv("CHROMA_DB_PATH", temp_chroma_dir)
        mock_get_llm.return_value = _fake_llm_sequence(*([SYMPTOM_INTAKE_RESPONSE, TRIAGE_RESPONSE, RAG_RESPONSE] * 4))
        from app.services.orchestrator import run_pipeline
        r1 = run_pipeline(raw_input="headache", language="en")
        r2 = run_pipeline(raw_input="headache", language="en")
        assert r1["session_id"] != r2["session_id"]
