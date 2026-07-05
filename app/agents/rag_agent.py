"""
RuralCare AI — Agent 3: Medical RAG Agent
Retrieves evidence-based health information and generates a grounded response.
"""

import time
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from app.rag.retriever import retrieve_health_context, build_context_string
from app.utils.safety_filter import run_safety_filter, hash_text, STANDARD_DISCLAIMER
from app.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a health information assistant for RuralCare AI, serving rural patients in India.
Provide clear, simple health information to help the patient understand their situation.

STRICT RULES:
1. Use ONLY the provided context documents. Do NOT add medical information from your own knowledge.
2. Do NOT diagnose any disease or condition.
3. Do NOT recommend specific prescription medicines or dosages.
4. Write at Grade 6 reading level — short sentences, simple words.
5. If the context does not address the question, say exactly:
   "I don't have specific information on this. Please visit your nearest health centre."
6. Always end with: "Visit your nearest health centre for proper evaluation."
7. Always cite source document names at the end.
8. Maximum response: 300 words.

CONTEXT DOCUMENTS:
{context}
"""


def rag_agent(state: dict[str, Any], llm) -> dict[str, Any]:
    start = time.time()

    query = f"{state.get('chief_complaint', '')}: {', '.join(state.get('symptoms', []))}"
    triage = state.get("triage_level", "MODERATE")

    # Retrieve documents
    docs, sources = retrieve_health_context(query=query, triage_level=triage, llm=llm)
    context = build_context_string(docs)

    state["rag_context"] = context
    state["rag_sources"] = sources

    if not context.strip():
        fallback = (
            "I don't have specific information on your reported symptoms. "
            "Please visit your nearest Primary Health Centre (PHC) or speak with your ASHA worker."
            + STANDARD_DISCLAIMER
        )
        state["health_guidance"] = fallback
        state["grounding_confidence"] = "none"
        _append_audit(state, start, sources)
        return state

    # Generate response
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Patient situation: {query}\nTriage level: {triage}"),
    ])

    chain = prompt | llm | StrOutputParser()

    try:
        raw_response = chain.invoke({"context": context, "query": query, "triage": triage})
    except Exception as exc:
        logger.error("RAG generation failed: %s", exc)
        raw_response = (
            "I am currently unable to retrieve health information. "
            "Please visit your nearest health centre."
        )

    # Run safety filter
    safety = run_safety_filter(raw_response)
    if not safety.passed:
        logger.warning("RAG output blocked: %s", safety.blocked_reason)
        state.setdefault("audit_log", [])[-1:] and None  # mark last entry

    state["health_guidance"] = safety.output
    state["grounding_confidence"] = "high" if len(docs) >= 3 else "medium" if docs else "none"

    _append_audit(state, start, sources)
    logger.info("rag_agent done in %dms — %d docs, confidence: %s",
                int((time.time() - start) * 1000), len(docs), state["grounding_confidence"])
    return state


def _append_audit(state: dict, start: float, sources: list[str]) -> None:
    state.setdefault("audit_log", []).append({
        "agent_name": "medical_rag",
        "triage_level": state.get("triage_level"),
        "input_hash": hash_text(state.get("rag_context", "")),
        "output_hash": hash_text(state.get("health_guidance", "")),
        "rag_sources": sources,
        "latency_ms": int((time.time() - start) * 1000),
    })
