"""
Tests for app/agents/symptom_intake.py.
Uses a mock LLM to avoid API calls.
"""

import json
import pytest
from unittest.mock import MagicMock


def _make_state(text: str = "I have fever and headache for 2 days") -> dict:
    return {
        "translated_input": text,
        "raw_input": text,
        "language": "en",
        "symptoms": [],
        "chief_complaint": "",
        "symptom_duration": "",
        "symptom_severity": "",
        "emergency_flag": False,
        "audit_log": [],
        "session_id": "test-intake",
    }


def _fake_llm(payload: dict):
    m = MagicMock()
    m.invoke.return_value.content = json.dumps(payload)
    return m


class TestSymptomIntakeAgent:
    def _run(self, state, llm_payload=None):
        from app.agents.symptom_intake import symptom_intake_agent
        if llm_payload is None:
            llm_payload = {
                "chief_complaint": "fever",
                "symptoms": ["fever", "headache"],
                "duration": "2 days",
                "severity": "moderate",
            }
        return symptom_intake_agent(state, _fake_llm(llm_payload))

    def test_symptoms_extracted(self):
        result = self._run(_make_state())
        assert len(result["symptoms"]) >= 1

    def test_chief_complaint_set(self):
        result = self._run(_make_state())
        assert result["chief_complaint"] != ""

    def test_duration_set(self):
        result = self._run(_make_state())
        assert result["symptom_duration"] != ""

    def test_severity_set(self):
        result = self._run(_make_state())
        assert result["symptom_severity"] != ""

    def test_audit_log_entry_added(self):
        result = self._run(_make_state())
        assert any(
            e.get("agent_name") == "symptom_intake" for e in result.get("audit_log", [])
        )

    def test_empty_input_does_not_crash(self):
        state = _make_state("")
        result = self._run(state)
        assert isinstance(result, dict)

    def test_malformed_llm_json_does_not_crash(self):
        from app.agents.symptom_intake import symptom_intake_agent
        llm = MagicMock()
        llm.invoke.return_value.content = "not json"
        state = _make_state()
        result = symptom_intake_agent(state, llm)
        assert isinstance(result, dict)
