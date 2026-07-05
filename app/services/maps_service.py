"""
RuralCare AI — Maps Service
Geocoding and healthcare facility discovery via OpenStreetMap (default) or Google Maps.
"""

import os
import time
import requests

from app.utils.logger import get_logger

logger = get_logger(__name__)

NOMINATIM_URL  = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL   = "https://overpass-api.de/api/interpreter"
NOMINATIM_HEADERS = {"User-Agent": "RuralCareAI/0.1 (health assistant; contact@ruralcare.ai)"}


def geocode_district(district: str, state: str) -> tuple[float, float] | None:
    """Convert district + state name to (lat, lon) via Nominatim."""
    query = f"{district}, {state}, India"
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
            headers=NOMINATIM_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:
        logger.warning("Geocoding failed for '%s, %s': %s", district, state, exc)
    return None


def find_healthcare_facilities(lat: float, lon: float, radius_m: int = 10000) -> list[dict]:
    """
    Query OpenStreetMap Overpass API for healthcare facilities near a coordinate.
    Returns a list of facility dicts.
    """
    query = f"""
[out:json][timeout:20];
(
  node(around:{radius_m},{lat},{lon})["amenity"~"hospital|clinic|health_centre|doctors"];
  way(around:{radius_m},{lat},{lon})["amenity"~"hospital|clinic|health_centre"];
);
out center body;
"""
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=25)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])

        results = []
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("name:en")
            if not name:
                continue
            fac_lat = el.get("lat") or el.get("center", {}).get("lat")
            fac_lon = el.get("lon") or el.get("center", {}).get("lon")
            dist_km = _haversine(lat, lon, fac_lat, fac_lon) if fac_lat else None
            results.append({
                "name":          name,
                "facility_type": _map_amenity(tags.get("amenity", "")),
                "address":       tags.get("addr:full") or tags.get("addr:street", ""),
                "contact":       tags.get("phone") or tags.get("contact:phone", ""),
                "distance_km":   round(dist_km, 2) if dist_km else None,
                "is_government": _is_government(tags),
                "lat":           fac_lat,
                "lon":           fac_lon,
            })

        results.sort(key=lambda x: (not x["is_government"], x["distance_km"] or 9999))
        logger.info("OSM found %d facilities near (%.4f, %.4f)", len(results), lat, lon)
        return results[:5]

    except Exception as exc:
        logger.warning("Overpass query failed: %s", exc)
        return []


def _map_amenity(amenity: str) -> str:
    return {
        "hospital":      "Hospital",
        "clinic":        "PHC",
        "health_centre": "PHC",
        "doctors":       "PHC",
    }.get(amenity, "Clinic")


def _is_government(tags: dict) -> bool:
    op = (tags.get("operator") or tags.get("operator:type") or "").lower()
    return "government" in op or "govt" in op or "public" in op


def google_places_nearby(
    lat: float, lon: float, api_key: str, radius_m: int = 10000
) -> list[dict]:
    """
    Query Google Places API for hospitals near (lat, lon).
    Returns facilities in the same format as find_healthcare_facilities().
    """
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    results = []
    next_page_token = None

    for _ in range(2):  # fetch at most 2 pages (40 results)
        params: dict = {
            "location": f"{lat},{lon}",
            "radius": radius_m,
            "type": "hospital",
            "key": api_key,
        }
        if next_page_token:
            params = {"pagetoken": next_page_token, "key": api_key}

        try:
            resp = requests.get(url, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Google Places API error: %s", exc)
            break

        for place in data.get("results", []):
            loc = place.get("geometry", {}).get("location", {})
            p_lat = loc.get("lat")
            p_lon = loc.get("lng")
            dist_km = _haversine(lat, lon, p_lat, p_lon) if p_lat else None
            name = place.get("name", "")
            types = place.get("types", [])
            facility_type = "Hospital" if "hospital" in types else "Clinic"
            is_govt = any(
                kw in name.lower()
                for kw in ("government", "govt", "rajiv", "district hospital",
                           "medical college", "gmch", "primary health")
            )
            results.append({
                "name":          name,
                "facility_type": facility_type,
                "address":       place.get("vicinity", ""),
                "contact":       "",
                "distance_km":   round(dist_km, 2) if dist_km else None,
                "is_government": is_govt,
                "lat":           p_lat,
                "lon":           p_lon,
                "source":        "google",
                "services":      [],
            })

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    results.sort(key=lambda x: (not x["is_government"], x.get("distance_km") or 9999))
    logger.info("Google Places found %d facilities near (%.4f, %.4f)", len(results), lat, lon)
    return results[:10]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))
