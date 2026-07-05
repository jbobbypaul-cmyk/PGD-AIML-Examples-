"""
RuralCare AI - Agent 4: Appointment & Facility Agent
Hybrid lookup: NHM TN static data -> OpenStreetMap -> Google Places (fallback).
"""

import time
from typing import Any

from app.database.sqlite_client import get_facilities_by_district, upsert_facility_cache
from app.services.maps_service import geocode_district, find_healthcare_facilities, google_places_nearby
from app.utils.config import get_config
from app.utils.safety_filter import hash_text
from app.utils.logger import get_logger

logger = get_logger(__name__)

FACILITY_TYPE_MAP = {
    "EMERGENCY": ["Hospital"],
    "URGENT":    ["CHC", "Hospital"],
    "MODERATE":  ["PHC", "CHC"],
    "MILD":      ["Sub-Centre", "PHC"],
}

SCHEME_NOTE = (
    "You may be eligible for free treatment at this government facility "
    "under Ayushman Bharat / PM-JAY or NHM Free Drug Scheme."
)

SOURCE_LABELS = {
    "nhm_tn":      "NHM Tamil Nadu",
    "osm":         "OpenStreetMap",
    "google":      "Google Places",
    "user_upload": "User Upload",
}


def appointment_facility_agent(state: dict[str, Any]) -> dict[str, Any]:
    start   = time.time()
    config  = get_config()
    debug   = []                          # written to state so UI can display it

    triage    = state.get("triage_level", "MODERATE")
    location  = state.get("location", {})
    district  = (location.get("district") or "").strip()
    loc_state = (location.get("state") or "").strip()

    preferred_types = FACILITY_TYPE_MAP.get(triage, ["PHC", "CHC"])
    facilities: list[dict] = []
    coords: tuple[float, float] | None = None

    debug.append(f"district={district!r} state={loc_state!r} triage={triage}")
    debug.append(f"preferred_types={preferred_types}")
    debug.append(f"sqlite_path={config.sqlite_path}")

    # Level 1: Static NHM TN / SQLite lookup
    if district:
        try:
            all_facs = get_facilities_by_district(district, loc_state)
            debug.append(f"Level1 DB query returned {len(all_facs)} rows")
            typed = [f for f in all_facs if f.get("facility_type") in preferred_types]
            debug.append(f"Level1 after type filter: {len(typed)} rows (preferred={preferred_types})")
            facilities = typed if typed else all_facs
        except Exception as exc:
            debug.append(f"Level1 EXCEPTION: {exc}")

    # Level 2: OpenStreetMap Overpass
    if not facilities and district:
        try:
            coords = geocode_district(district, loc_state)
            if coords:
                lat, lon = coords
                osm_facs = find_healthcare_facilities(lat, lon)
                for f in osm_facs:
                    f.update({"district": district, "state": loc_state, "source": "osm"})
                    upsert_facility_cache(f)
                typed = [f for f in osm_facs if f.get("facility_type") in preferred_types]
                facilities = typed if typed else osm_facs
                debug.append(f"Level2 OSM: {len(facilities)} facilities")
        except Exception as exc:
            debug.append(f"Level2 EXCEPTION: {exc}")

    # Level 3: Google Places
    if not facilities and district and config.google_maps_key:
        try:
            if not coords:
                coords = geocode_district(district, loc_state)
            if coords:
                lat, lon = coords
                gfacs = google_places_nearby(lat, lon, config.google_maps_key)
                for f in gfacs:
                    f.update({"district": district, "state": loc_state})
                    upsert_facility_cache(f)
                typed = [f for f in gfacs if f.get("facility_type") in preferred_types]
                facilities = typed if typed else gfacs
                debug.append(f"Level3 Google: {len(facilities)} facilities")
        except Exception as exc:
            debug.append(f"Level3 EXCEPTION: {exc}")

    # Compute distances if geocoded
    if coords and facilities:
        lat, lon = coords
        for f in facilities:
            if f.get("lat") and f.get("lon") and not f.get("distance_km"):
                from math import radians, sin, cos, sqrt, atan2
                R = 6371
                d_lat = radians(f["lat"] - lat)
                d_lon = radians(f["lon"] - lon)
                a = sin(d_lat / 2) ** 2 + cos(radians(lat)) * cos(radians(f["lat"])) * sin(d_lon / 2) ** 2
                f["distance_km"] = round(R * 2 * atan2(sqrt(a), sqrt(1 - a)), 2)
        facilities.sort(key=lambda x: (not x.get("is_government"), x.get("distance_km") or 9999))

    facilities = facilities[:3]
    state["_fac_debug"] = debug

    if not facilities:
        state["facilities"] = []
        state["recommended_facility"] = (
            f"No facility data found for {district or 'your area'}. "
            "Please contact your district health office or call 104 (health helpline)."
        )
        _append_audit(state, start)
        return state

    best = facilities[0]
    dist_str    = f" - {best['distance_km']:.1f} km away" if best.get("distance_km") else ""
    contact_str = f" | Contact: {best['contact']}" if best.get("contact") else ""
    source_str  = SOURCE_LABELS.get(best.get("source", "nhm_tn"), "")

    state["recommended_facility"] = (
        f"{best['name']} ({best['facility_type']}){dist_str}{contact_str}\n"
        f"Address: {best.get('address', 'Contact district health office for directions')}\n"
        f"Source: {source_str}\n"
        f"{SCHEME_NOTE}"
    )
    state["facilities"] = facilities

    _append_audit(state, start)
    # ASCII-only log to avoid any encoding issues on Windows
    logger.info("appointment_facility done: %s (source: %s)", best["name"], best.get("source"))
    return state


def search_facilities(district: str, state_name: str, triage_level: str) -> list[dict]:
    preferred = FACILITY_TYPE_MAP.get(triage_level, ["PHC", "CHC"])
    all_facs  = get_facilities_by_district(district, state_name)
    typed     = [f for f in all_facs if f.get("facility_type") in preferred]
    return typed if typed else all_facs


def _append_audit(state: dict, start: float) -> None:
    state.setdefault("audit_log", []).append({
        "agent_name": "appointment_facility",
        "input_hash": hash_text(str(state.get("location", ""))),
        "output_hash": hash_text(state.get("recommended_facility", "")),
        "latency_ms": int((time.time() - start) * 1000),
    })
