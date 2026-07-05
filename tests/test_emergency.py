"""
Tests for app/agents/emergency_escalation.py.
Emergency path is critical — must not depend on LLM being available.
"""

import pytest
from unittest.mock import MagicMock, patch


def _make_emergency_state(text: str = "My father is unconscious") -> dict:
    return {
        "translated_input": text,
        "raw_input": text,
        "language": "en",
        "chief_complaint": text,
        "symptoms": ["unconscious"],
        "triage_level": "EMERGENCY",
        "emergency_flag": True,
        "location": {"district": "Dharmapuri", "state": "Tamil Nadu", "lat": None, "lon": None},
        "patient_token": "PT-test0001",
        "session_id": "emer-test-001",
        "audit_log": [],
        "emergency_alert": "",
        "rag_context": "",
        "rag_sources": [],
        "health_guidance": "",
    }


class TestEmergencyEscalationAgent:
    def _run(self, state=None):
        from app.agents.emergency_escalation import emergency_escalation_agent
        if state is None:
            state = _make_emergency_state()
        return emergency_escalation_agent(state)

    def test_emergency_alert_populated(self):
        result = self._run()
        assert result.get("emergency_alert") not in (None, "")

    def test_emergency_flag_remains_true(self):
        result = self._run()
        assert result["emergency_flag"] is True

    def test_triage_level_emergency(self):
        result = self._run()
        assert result["triage_level"] == "EMERGENCY"

    def test_first_aid_included_in_alert(self):
        result = self._run()
        alert = result.get("emergency_alert", "").lower()
        assert any(word in alert for word in ["ambulance", "112", "108", "emergency", "call"])

    def test_unconscious_static_fallback(self):
        """Static first aid must work even if RAG/LLM are unavailable."""
        state = _make_emergency_state("He is unconscious and not breathing")
        with patch("app.agents.emergency_escalation.retrieve_emergency_context", side_effect=Exception("DB down")):
            result = self._run(state)
        assert result.get("emergency_alert") not in (None, "")

    def test_breathing_static_fallback(self):
        state = _make_emergency_state("She cannot breathe")
        with patch("app.agents.emergency_escalation.retrieve_emergency_context", side_effect=Exception("DB down")):
            result = self._run(state)
        assert result.get("emergency_alert") not in (None, "")

    def test_audit_log_written(self):
        result = self._run()
        assert any(
            e.get("agent_name") == "emergency_escalation"
            for e in result.get("audit_log", [])
        )

    def test_no_llm_required(self):
        """Emergency agent must produce output without any LLM."""
        state = _make_emergency_state()
        # emergency_escalation_agent signature takes only (state) — no llm arg
        from app.agents.emergency_escalation import emergency_escalation_agent
        result = emergency_escalation_agent(state)
        assert result.get("emergency_alert") not in (None, "")
