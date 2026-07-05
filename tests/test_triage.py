"""
Tests for app/agents/medical_triage.py.
Uses a fake LLM to avoid API calls.
"""

import pytest
from unittest.mock import MagicMock, patch


def _make_state(triage_level_llm_output: str = "MODERATE", emergency: bool = False) -> dict:
    return {
        "translated_input": "I have had fever for 3 days",
        "chief_complaint": "fever",
        "symptoms": ["fever", "headache"],
        "symptom_duration": "3 days",
        "symptom_severity": "moderate",
        "triage_level": "",
        "triage_reasoning": "",
        "recommended_care_setting": "",
        "emergency_flag": emergency,
        "audit_log": [],
        "session_id": "test-session",
    }


def _fake_llm(output_text: str):
    """Return a mock LLM that produces output_text when called."""
    m = MagicMock()
    m.invoke.return_value.content = output_text
    return m


class TestMedicalTriageAgent:
    def _run(self, state, llm_output="MODERATE"):
        from app.agents.medical_triage import medical_triage_agent
        llm = _fake_llm(f'{{"triage_level": "{llm_output}", "reasoning": "test", "care_setting": "PHC"}}')
        return medical_triage_agent(state, llm)

    def test_mild_classification(self):
        state = _make_state()
        result = self._run(state, "MILD")
        assert result["triage_level"] == "MILD"

    def test_moderate_classification(self):
        state = _make_state()
        result = self._run(state, "MODERATE")
        assert result["triage_level"] == "MODERATE"

    def test_urgent_classification(self):
        state = _make_state()
        result = self._run(state, "URGENT")
        assert result["triage_level"] == "URGENT"

    def test_emergency_flag_cannot_be_downgraded(self):
        """If emergency_flag is already True, triage must be EMERGENCY regardless of LLM."""
        state = _make_state(emergency=True)
        result = self._run(state, "MILD")  # LLM says MILD
        assert result["triage_level"] == "EMERGENCY"

    def test_invalid_llm_output_defaults_to_urgent(self):
        """Conservative default: unknown output → URGENT."""
        state = _make_state()
        from app.agents.medical_triage import medical_triage_agent
        llm = _fake_llm('{"triage_level": "UNKNOWN_VALUE", "reasoning": "x", "care_setting": "y"}')
        result = medical_triage_agent(state, llm)
        assert result["triage_level"] == "URGENT"

    def test_malformed_json_defaults_to_urgent(self):
        state = _make_state()
        from app.agents.medical_triage import medical_triage_agent
        llm = _fake_llm("not valid json at all")
        result = medical_triage_agent(state, llm)
        assert result["triage_level"] == "URGENT"

    def test_reasoning_populated(self):
        state = _make_state()
        result = self._run(state, "MODERATE")
        assert result.get("triage_reasoning") is not None

    def test_audit_log_written(self):
        state = _make_state()
        result = self._run(state, "MODERATE")
        assert len(result.get("audit_log", [])) > 0
