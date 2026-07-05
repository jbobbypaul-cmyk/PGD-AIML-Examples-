"""
RuralCare AI — Streamlit Demo UI
Run: streamlit run app/streamlit_app.py
"""

import sys
import os

# Ensure the project root is on sys.path so `from app.xxx import` works
# regardless of how or from where Streamlit is launched.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import json
import sqlite3 as _sqlite3
import streamlit as st
import pandas as pd

# ── Page Config (must be first Streamlit call) ────────────────────────

st.set_page_config(
    page_title="RuralCare AI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Startup (cached — runs once per session) ──────────────────────────

def _seed_if_empty(cfg) -> None:
    """Seed demo data on a fresh deployment (Render / HF Spaces) when no data exists."""
    from app.rag.vector_store import collection_doc_count, get_vectorstore

    # ── ChromaDB: seed demo documents if all collections are empty ────
    COLLECTIONS = [
        "who_health_guidelines", "nhm_india_protocols", "symptom_disease_mapping",
        "drug_information_basic", "emergency_protocols", "regional_health_schemes",
    ]
    DEMO_DOCS: dict[str, list[str]] = {
        "who_health_guidelines": [
            "Fever Management (WHO): Fever above 38°C lasting more than 3 days requires medical evaluation. "
            "For mild fever: rest, adequate hydration, and paracetamol for comfort. "
            "Danger signs: fever with stiff neck, rash, difficulty breathing, or altered consciousness. "
            "Source: WHO Fever Guidelines 2023",
            "Diarrhea and Dehydration (WHO): Oral Rehydration Solution (ORS) is the first-line treatment. "
            "Mix one ORS sachet in 1 litre of clean water. Give small sips frequently. "
            "Signs of severe dehydration: sunken eyes, dry mouth, no urination, lethargy. "
            "Seek immediate care for severe dehydration. Source: WHO 2023",
        ],
        "nhm_india_protocols": [
            "ASHA Health Worker Protocol — Fever (NHM India): Refer patients with fever lasting more than 3 days "
            "to the nearest PHC. Provide paracetamol for symptomatic relief while arranging referral. "
            "Collect blood slide for malaria in endemic areas. Source: NHM ASHA Training Module 4",
            "Iron and Folic Acid supplementation is provided free under the National Iron Plus Initiative "
            "through ASHA workers and PHC outreach. Pregnant women receive 180 tablets during pregnancy. "
            "Source: NHM India Maternal Health Programme",
        ],
        "symptom_disease_mapping": [
            "Common Fever Urgency Levels: MILD — low-grade fever under 38.5°C, duration less than 2 days, "
            "no serious symptoms. MODERATE — fever above 38.5°C lasting 2 to 5 days with headache or body aches. "
            "URGENT — high fever above 39.5°C with rigors, vomiting, unable to eat. "
            "EMERGENCY — fever with stiff neck, altered consciousness, difficulty breathing, rash. "
            "Source: WHO ICD-11 Triage Reference 2022",
        ],
        "emergency_protocols": [
            "Emergency First Aid — Unconscious Person (Indian Red Cross): "
            "1. Check response: tap shoulder and call out. "
            "2. Call for help: Dial 108 (ambulance) or 112. "
            "3. Open airway: tilt head back, lift chin. "
            "4. Check breathing for 10 seconds. "
            "5. If not breathing: begin CPR — 30 compressions, 2 rescue breaths. "
            "Do not leave the person alone. Source: Indian Red Cross First Aid Manual 2022",
            "Emergency First Aid — Breathing Difficulty: "
            "1. Call 108 immediately. "
            "2. Loosen tight clothing around neck and chest. "
            "3. Help person sit upright in forward-leaning position. "
            "4. Do NOT give food or water. "
            "5. Stay until ambulance arrives. Source: WHO Emergency Care 2022",
        ],
        "drug_information_basic": [
            "Paracetamol (Acetaminophen): Used for fever and mild pain. Standard adult dose: 500–1000 mg "
            "every 4 to 6 hours, maximum 4000 mg per day. Available free at government PHCs. "
            "Do not exceed recommended dose. Consult a doctor for children's dosing. Source: NHM Drug Formulary",
            "ORS (Oral Rehydration Salts): Used to prevent and treat dehydration from diarrhoea or vomiting. "
            "Mix one sachet in 1 litre of clean water. Sip slowly and frequently. "
            "Available free at ASHA workers and government PHCs. Source: NHM Diarrhoea Protocol",
        ],
        "regional_health_schemes": [
            "PM-JAY (Pradhan Mantri Jan Arogya Yojana): Health insurance of Rs 5 lakh per family per year. "
            "Covers hospitalization for 1,574 medical packages at empanelled hospitals. "
            "Check eligibility at pmjay.gov.in with Aadhaar card. Source: NHM PM-JAY Guidelines 2024",
            "Tamil Nadu Chief Minister's Comprehensive Health Insurance Scheme (CMCHIS): "
            "Covers up to Rs 5 lakh per year for families with annual income below Rs 72,000. "
            "Valid at government and empanelled private hospitals in Tamil Nadu. Source: TN Health Dept 2024",
        ],
    }

    total_docs = sum(collection_doc_count(c) for c in COLLECTIONS)
    if total_docs == 0:
        for col, texts in DEMO_DOCS.items():
            vs = get_vectorstore(col)
            vs.add_texts(texts)

    # ── SQLite: seed TN hospitals if facility_cache is empty ──────────
    try:
        conn = _sqlite3.connect(cfg.sqlite_path)
        count = conn.execute("SELECT COUNT(*) FROM facility_cache").fetchone()[0]
        conn.close()
    except Exception:
        count = 0

    if count == 0:
        from scripts.seed_tn_hospitals import TN_HOSPITALS, LAST_UPDATED
        from app.database.sqlite_client import upsert_facility_cache
        for rec in TN_HOSPITALS:
            rec = dict(rec)
            rec["last_updated"] = LAST_UPDATED
            rec["source"] = "nhm_tn"
            upsert_facility_cache(rec)


@st.cache_resource
def startup():
    from app.utils.config import get_config
    from app.database.sqlite_client import init_db
    from app.rag.vector_store import init_vector_store
    init_db()
    init_vector_store()
    cfg = get_config()
    _seed_if_empty(cfg)
    return cfg

config = startup()

# ── Session State Initialisation ──────────────────────────────────────

if "symptoms_input" not in st.session_state:
    st.session_state.symptoms_input = ""
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "en"

# ── Sidebar ───────────────────────────────────────────────────────────

LANGUAGE_OPTIONS = {
    "en": "English",
    "hi": "Hindi — हिंदी",
    "ta": "Tamil — தமிழ்",
    "bn": "Bengali — বাংলা",
    "te": "Telugu — తెలుగు",
    "kn": "Kannada — ಕನ್ನಡ",
}

with st.sidebar:
    st.title("⚙️ Settings")

    lang_code = st.selectbox(
        "Language / भाषा / மொழி",
        options=list(LANGUAGE_OPTIONS.keys()),
        format_func=lambda x: LANGUAGE_OPTIONS[x],
        index=list(LANGUAGE_OPTIONS.keys()).index(st.session_state.selected_language),
    )
    st.session_state.selected_language = lang_code

    st.divider()
    st.subheader("📍 Location (Optional)")
    district  = st.text_input("District", placeholder="e.g. Dharmapuri")
    loc_state = st.text_input("State",    placeholder="e.g. Tamil Nadu")

    st.divider()
    st.caption(f"Demo mode: {'ON' if config.demo_mode else 'OFF'}")
    st.caption(f"LLM: {config.llm_provider.upper()}")
    st.caption(f"DB: {config.sqlite_path.split('/')[-1]}")


    if st.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.last_result = None
        st.session_state.symptoms_input = ""
        st.rerun()

# ── Header ────────────────────────────────────────────────────────────

st.title("🏥 RuralCare AI")
st.markdown("**A first-level health support assistant for rural communities.**")
st.warning(
    "⚠️ **Important:** RuralCare AI is NOT a doctor. It cannot diagnose illness "
    "or prescribe medicines. All information is for general awareness only. "
    "Always consult a qualified healthcare professional. **In an emergency, call 112.**"
)
st.divider()

# ── Demo Case Buttons ─────────────────────────────────────────────────

DEMO_CASES = {
    "🟢 Mild — Headache":          ("I have a mild headache and feel a bit tired since this morning.", "en"),
    "🟡 Moderate — Fever 3 days":  ("I have had fever for 3 days, headache, and body aches. I feel weak.", "en"),
    "🟠 Urgent — Chest + Cough":   ("I have chest pain and have been coughing for 2 weeks. I am losing weight.", "en"),
    "🔴 Emergency — Unconscious":  ("My father is unconscious and cannot breathe.", "en"),
    "🌐 Hindi — Fever":            ("मुझे तीन दिनों से बुखार है और सिर दर्द हो रहा है", "hi"),
    "🌐 Tamil — Stomach pain":     ("எனக்கு வயிற்று வலியும் வாந்தியும் உள்ளது. இரண்டு நாட்களாக உள்ளது.", "ta"),
}

st.subheader("Quick Demo Cases")
demo_cols = st.columns(3)
for i, (label, (text, lang)) in enumerate(DEMO_CASES.items()):
    with demo_cols[i % 3]:
        if st.button(label, use_container_width=True, key=f"demo_{i}"):
            st.session_state.symptoms_input   = text
            st.session_state.symptoms_textarea = text   # must match the widget key
            st.session_state.selected_language = lang
            st.rerun()

st.divider()

# ── Input Area ────────────────────────────────────────────────────────

col_in, col_hint = st.columns([3, 1])

with col_in:
    st.subheader("Describe Your Symptoms")

    symptoms_text = st.text_area(
        "What symptoms are you experiencing?",
        height=130,
        max_chars=config.max_input_length,
        placeholder=(
            "Example: I have had fever for 3 days, headache, and body aches. "
            "I feel very weak."
        ),
        key="symptoms_textarea",
    )
    # symptoms_textarea key IS the source of truth; keep symptoms_input in sync
    st.session_state.symptoms_input = symptoms_text

with col_hint:
    st.subheader("Tips")
    st.markdown("""
- Describe ALL your symptoms
- Mention how long you've had them
- Say if symptoms are getting worse
- Include your age if relevant
- Mention if you are pregnant
""")

# ── Submit Button ─────────────────────────────────────────────────────

st.divider()
run_clicked = st.button("🔍 Get Health Guidance", type="primary", use_container_width=True)

# ── Run Pipeline ──────────────────────────────────────────────────────

if run_clicked:
    has_text = bool(symptoms_text and symptoms_text.strip())

    if not has_text:
        st.error("Please enter your symptoms in the text box.")
        st.stop()

    with st.spinner("Analysing your symptoms — please wait…"):
        try:
            from app.services.orchestrator import run_pipeline

            # BUG FIX: run_pipeline is now synchronous — no asyncio needed
            result = run_pipeline(
                raw_input=symptoms_text,
                language=st.session_state.selected_language,
                location_district=district or None,
                location_state=loc_state or None,
                input_source="text",
            )
            # Direct facility lookup — raw sqlite3 using module-level config
            # (bypasses get_config()/lru_cache chain to guarantee correct DB path)
            _d = (district or "").strip().title()
            _s = (loc_state or "").strip().title()
            _lookup_debug = {"district": _d, "state": _s, "total": 0, "shown": 0, "error": None}
            if _d:
                try:
                    _conn3 = _sqlite3.connect(config.sqlite_path)
                    _conn3.row_factory = _sqlite3.Row
                    try:
                        if _s:
                            _raw_rows = _conn3.execute(
                                "SELECT * FROM facility_cache"
                                " WHERE LOWER(TRIM(district))=LOWER(TRIM(?))"
                                "   AND LOWER(TRIM(state))=LOWER(TRIM(?))"
                                " ORDER BY is_government DESC",
                                (_d, _s),
                            ).fetchall()
                        else:
                            _raw_rows = _conn3.execute(
                                "SELECT * FROM facility_cache"
                                " WHERE LOWER(TRIM(district))=LOWER(TRIM(?))"
                                " ORDER BY is_government DESC",
                                (_d,),
                            ).fetchall()
                    finally:
                        _conn3.close()

                    _all = []
                    for _r in _raw_rows:
                        _row = dict(_r)
                        try:
                            _row["services"] = json.loads(_row.get("services") or "[]")
                        except Exception:
                            _row["services"] = []
                        _all.append(_row)

                    from app.agents.appointment_facility import FACILITY_TYPE_MAP, SCHEME_NOTE, SOURCE_LABELS
                    _triage    = result.get("triage_level", "MODERATE")
                    _preferred = FACILITY_TYPE_MAP.get(_triage, ["PHC", "CHC"])
                    _typed = [f for f in _all if f.get("facility_type") in _preferred]
                    _facs  = (_typed if _typed else _all)[:3]
                    _lookup_debug.update({"total": len(_all), "shown": len(_facs)})

                    if _facs:
                        result["facilities"] = _facs
                        _best = _facs[0]
                        _dist = f" - {_best['distance_km']:.1f} km" if _best.get("distance_km") else ""
                        _ct   = f" | {_best['contact']}" if _best.get("contact") else ""
                        result["recommended_facility"] = (
                            f"{_best['name']} ({_best['facility_type']}){_dist}{_ct}\n"
                            f"Address: {_best.get('address', '')}\n"
                            f"Source: {SOURCE_LABELS.get(_best.get('source', 'nhm_tn'), '')}\n"
                            f"{SCHEME_NOTE}"
                        )
                except Exception as _fac_exc:
                    _lookup_debug["error"] = str(_fac_exc)
            st.session_state["_lookup_debug"] = _lookup_debug

            st.session_state.last_result = result

        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.caption("Please check your API key in .env and try again.")
            st.stop()

# ── Results Display ───────────────────────────────────────────────────

result = st.session_state.last_result

if result:
    st.divider()
    st.subheader("Results")

    # Emergency alert — always first, most prominent
    if result.get("emergency_flag") and result.get("emergency_alert"):
        st.error(result["emergency_alert"])

    # Triage level metrics
    triage = result.get("triage_level", "UNKNOWN")
    emoji  = {"EMERGENCY": "🔴", "URGENT": "🟠", "MODERATE": "🟡", "MILD": "🟢"}.get(triage, "⚪")

    m1, m2, m3 = st.columns(3)
    m1.metric("Triage Level",  f"{emoji} {triage}")
    m2.metric("Language",      LANGUAGE_OPTIONS.get(result.get("language", "en"), "Unknown"))
    m3.metric("Safety Check",  "✅ Passed" if result.get("safety_passed") else "⚠️ Filtered")

    if result.get("triage_reasoning"):
        st.info(f"**Reasoning:** {result['triage_reasoning']}")

    if not result.get("safety_passed"):
        st.warning(f"⚠️ Safety filter triggered: {result.get('blocked_reason', 'Unknown')}")

    st.divider()

    # Main content columns
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("💊 Health Guidance")
        st.write(result.get("health_guidance") or "No guidance available.")

        if result.get("rag_sources"):
            with st.expander("📚 Source Documents"):
                for src in result["rag_sources"]:
                    st.caption(f"• {src}")

    with col_right:
        st.subheader("🏥 Recommended Facility")
        facilities = result.get("facilities") or []

        SOURCE_BADGE = {
            "nhm_tn":      "🏛️ NHM Tamil Nadu",
            "osm":         "🗺️ OpenStreetMap",
            "google":      "🔍 Google Places",
            "user_upload": "📤 User Upload",
        }
        TYPE_COLOR = {
            "Hospital":   "🔴",
            "CHC":        "🟠",
            "PHC":        "🟡",
            "Sub-Centre": "🟢",
        }

        # Debug caption — always show what district/state was searched
        _dbg = st.session_state.get("_lookup_debug", {})
        if _dbg.get("error"):
            st.caption(f"⚠️ Lookup error: {_dbg['error']}")
        elif _dbg.get("district"):
            st.caption(
                f"Searched: **{_dbg['district']}**"
                + (f", {_dbg['state']}" if _dbg.get("state") else "")
                + f" — {_dbg['total']} records found, {_dbg['shown']} shown"
            )
        else:
            st.caption("ℹ️ Enter a District in the left sidebar to see nearby facilities.")

        if facilities:
            best = facilities[0]
            source_label = SOURCE_BADGE.get(best.get("source", "nhm_tn"), "📍 Directory")
            type_icon    = TYPE_COLOR.get(best.get("facility_type", ""), "🏥")
            dist_txt     = f"  📏 **{best['distance_km']:.1f} km away**" if best.get("distance_km") else ""
            contact_txt  = f"  📞 **{best['contact']}**" if best.get("contact") else ""
            services     = best.get("services") or []

            with st.container(border=True):
                st.markdown(
                    f"### {type_icon} {best['name']}"
                )
                st.markdown(
                    f"`{best.get('facility_type', 'Facility')}` &nbsp; {source_label}"
                )
                if best.get("address"):
                    st.markdown(f"📍 {best['address']}")
                if dist_txt:
                    st.markdown(dist_txt)
                if contact_txt:
                    st.markdown(contact_txt)
                if services:
                    st.markdown("**Services:** " + " · ".join(services))
                if best.get("is_government"):
                    st.info(
                        "Free treatment available under Ayushman Bharat / PM-JAY "
                        "and NHM Free Drug Scheme.",
                        icon="ℹ️",
                    )

            # Additional nearby facilities
            if len(facilities) > 1:
                with st.expander(f"📋 {len(facilities) - 1} more nearby facilities"):
                    for fac in facilities[1:]:
                        src  = SOURCE_BADGE.get(fac.get("source", "nhm_tn"), "📍")
                        icon = TYPE_COLOR.get(fac.get("facility_type", ""), "🏥")
                        dist = f" — {fac['distance_km']:.1f} km" if fac.get("distance_km") else ""
                        st.markdown(
                            f"**{icon} {fac['name']}** `{fac.get('facility_type','')}`{dist}  \n"
                            f"{fac.get('address','')}  \n"
                            f"{src}"
                            + (f"  \n📞 {fac['contact']}" if fac.get("contact") else "")
                        )
                        st.divider()
        else:
            fac = result.get("recommended_facility")
            _dbg2 = st.session_state.get("_lookup_debug", {})
            if fac:
                st.info(fac)
            elif not _dbg2.get("district"):
                st.info(
                    "Enter your **District** (and optionally State) in the left sidebar, "
                    "then click **Get Health Guidance** again to see nearby facilities."
                )
            else:
                st.info(
                    f"No facility records found for **{_dbg2['district']}**. "
                    "Contact your district health officer or call **104** (Health Helpline)."
                )

    # ── Follow-up Plan (full width) ────────────────────────────────────
    plan     = result.get("followup_plan") or {}
    briefing = result.get("health_worker_briefing")

    if plan:
        st.divider()
        st.subheader("📅 Follow-up Plan")
        with st.container(border=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**Follow up in**  \n{plan.get('follow_up_in', 'As needed')}")
            with c2:
                if plan.get("watch_for"):
                    st.markdown("**Watch for**")
                    for item in plan["watch_for"]:
                        st.markdown(f"- {item}")
            with c3:
                if plan.get("home_care"):
                    st.markdown("**Home care**")
                    for tip in plan["home_care"]:
                        st.markdown(f"- {tip}")
            if plan.get("return_immediately_if"):
                st.warning(
                    "**Return immediately if:** "
                    + " · ".join(plan["return_immediately_if"])
                )

    # ── Health Worker Briefing (full-width panel below follow-up) ──────
    if briefing:
        st.divider()
        st.subheader("👩‍⚕️ Health Worker Briefing")
        with st.container(border=True):
            st.text(briefing)

    # Disclaimer
    st.divider()
    st.caption(
        "⚠️ DISCLAIMER: This information is for general health awareness only. "
        "RuralCare AI is NOT a doctor and cannot diagnose illness or prescribe medicines. "
        "Always consult a qualified healthcare professional. "
        "In an emergency, call **112** (Emergency) or **108** (Ambulance) immediately."
    )

# ── Upload: Hospital Data / Medical Knowledge ─────────────────────────

st.divider()
with st.expander("📁 Upload Hospital Data or Medical Knowledge", expanded=False):
    from app.rag.vector_store import COLLECTIONS

    up_tab_hosp, up_tab_know = st.tabs(
        ["🏥 Hospital List (CSV / Excel)", "📄 Medical Knowledge (PDF / TXT / MD)"]
    )

    # ── Tab 1: Hospital CSV / Excel ───────────────────────────────────
    with up_tab_hosp:
        st.markdown(
            "Upload a spreadsheet of hospitals or clinics. "
            "New records are inserted; existing records (same name + district + state) are updated."
        )

        st.markdown("**Required columns:** `name`, `facility_type`, `district`, `state`")
        st.markdown(
            "**facility_type** must be one of: `Hospital` · `CHC` · `PHC` · `Sub-Centre`  \n"
            "**Optional:** `address`, `contact`, `lat`, `lon`, `services` (comma-separated), "
            "`is_government` (1 or 0)"
        )

        # Template download
        from app.services.document_processor import get_hospital_csv_template
        st.download_button(
            label="⬇️ Download CSV Template",
            data=get_hospital_csv_template(),
            file_name="hospital_upload_template.csv",
            mime="text/csv",
        )

        hosp_file = st.file_uploader(
            "Choose CSV or Excel file",
            type=["csv", "xlsx", "xls"],
            key="hosp_uploader",
        )

        if hosp_file:
            st.caption(f"Selected: {hosp_file.name}  ({hosp_file.size:,} bytes)")
            if st.button("⬆️ Process Hospital File", key="btn_hosp_upload"):
                from app.services.document_processor import process_hospital_file
                with st.spinner("Importing hospital records…"):
                    res = process_hospital_file(hosp_file.read(), hosp_file.name)

                if not res["ok"]:
                    st.error(f"Upload failed: {res['error']}")
                else:
                    st.success(
                        f"Done — **{res['inserted']} inserted**, "
                        f"**{res['updated']} updated**, "
                        f"{res['skipped']} skipped  "
                        f"(of {res['total']} rows)"
                    )
                    if res["errors"]:
                        with st.expander(f"⚠️ {len(res['errors'])} row errors"):
                            for e in res["errors"]:
                                st.caption(e)

    # ── Tab 2: Medical Knowledge PDF / TXT ───────────────────────────
    with up_tab_know:
        st.markdown(
            "Upload a PDF, plain-text, or Markdown file to add to the RAG knowledge base. "
            "The document is chunked and embedded into the selected collection."
        )

        COLLECTION_LABELS = {
            "who_health_guidelines":    "WHO Health Guidelines",
            "nhm_india_protocols":      "NHM India Protocols",
            "symptom_disease_mapping":  "Symptom & Disease Mapping",
            "drug_information_basic":   "Drug Information (Basic)",
            "emergency_protocols":      "Emergency Protocols",
            "regional_health_schemes":  "Regional Health Schemes",
        }

        target_collection = st.selectbox(
            "Target knowledge collection",
            options=list(COLLECTIONS),
            format_func=lambda c: COLLECTION_LABELS.get(c, c),
            key="know_collection",
        )

        know_file = st.file_uploader(
            "Choose PDF, TXT, or MD file",
            type=["pdf", "txt", "md"],
            key="know_uploader",
        )

        if know_file:
            st.caption(f"Selected: {know_file.name}  ({know_file.size:,} bytes)")
            if st.button("⬆️ Process Knowledge Document", key="btn_know_upload"):
                from app.services.document_processor import process_knowledge_document
                with st.spinner("Embedding document — this may take a moment…"):
                    res = process_knowledge_document(
                        know_file.read(), know_file.name, target_collection
                    )

                if not res["ok"]:
                    st.error(f"Upload failed: {res['error']}")
                else:
                    st.success(
                        f"Added **{res['chunks']} chunks** from `{res['filename']}` "
                        f"to **{COLLECTION_LABELS.get(target_collection, target_collection)}**."
                    )
                    if res.get("preview"):
                        with st.expander("📄 Document preview (first 400 chars)"):
                            st.text(res["preview"])

# ── Footer ────────────────────────────────────────────────────────────

st.divider()
st.caption("RuralCare AI v0.1.0 · Demo Mode · Not for clinical use · MIT License")
