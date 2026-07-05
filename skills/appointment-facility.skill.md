# Skill: Appointment & Facility

## Skill Name
`appointment-facility`

## Purpose
Locate the most appropriate nearby healthcare facility based on the patient's triage level and location, and provide actionable contact and access information to help the patient reach care.

## When to Use
- Called after Medical RAG Agent has generated health guidance.
- Use when implementing the `appointment_facility_agent` function.
- Use when seeding or updating the facility cache database.
- Use when integrating with OpenStreetMap or Google Maps APIs.
- Use when a patient asks "where can I go for treatment?"

## Inputs Expected

```json
{
  "triage_level": "MODERATE",
  "location": {
    "district": "Dharmapuri",
    "state": "Tamil Nadu",
    "lat": null,
    "lon": null
  },
  "patient_token": "PT-xxxxxxxx"
}
```

## Output Format

```json
{
  "facilities": [
    {
      "name": "Dharmapuri District PHC",
      "type": "PHC",
      "distance_km": 4.2,
      "address": "Main Road, Dharmapuri, Tamil Nadu",
      "contact": "04342-123456",
      "services": ["OPD", "Maternal Care", "Immunization"],
      "is_government": true,
      "lat": 12.1211,
      "lon": 78.1580
    }
  ],
  "recommended_facility": "Dharmapuri District PHC — 4.2 km — Contact: 04342-123456",
  "recommended_reason": "PHC is appropriate for moderate symptoms and provides free government healthcare",
  "directions_hint": "Take the main road towards Dharmapuri town. The PHC is near the bus stand.",
  "health_scheme_note": "You can access free treatment here under Ayushman Bharat / PM-JAY."
}
```

## Decision Rules

### Facility Type Selection by Triage Level

```
EMERGENCY → District Hospital Emergency Wing / Government Hospital
            Show 112, 108 prominently first, then nearest hospital
URGENT    → Community Health Centre (CHC) or District Hospital OPD
MODERATE  → Primary Health Centre (PHC)
MILD      → Sub-Centre / ASHA worker contact / Self-care
```

### Facility Search Priority
```
1. Government facilities FIRST (free care, accessible)
2. Sort by distance (nearest first)
3. Filter by services matching triage (e.g., "Emergency" service for EMERGENCY cases)
4. Maximum results to show: 3 facilities
```

### Demo Mode vs Live Mode
```
DEMO_MODE=true:
  → Query SQLite facility_cache table by district/state
  → No external API calls

DEMO_MODE=false:
  → If lat/lon available: OpenStreetMap Overpass API
  → If only district: Nominatim geocoding → lat/lon → Overpass API
  → Cache results in SQLite for 24 hours
```

### OpenStreetMap Overpass Query
```sparql
[out:json][timeout:25];
node(around:10000,{lat},{lon})["amenity"~"hospital|clinic|doctors|health_centre"];
out body;
```

### Location Fallback Chain
```
1. If lat/lon provided: use directly
2. If district + state: Nominatim geocode → lat/lon
3. If only state: return district-level list from facility cache
4. If no location: return a message asking for location + national helpline
```

### Distance Display
- If distance < 1 km: "Less than 1 km"
- If distance 1–5 km: "X.X km"
- If distance > 5 km: "Approximately X km"
- Do not show distance if calculated from approximate geocoding (show "in your district" instead).

## Safety Rules
- For EMERGENCY cases: ALWAYS show 112 and 108 before any facility listing.
- Government facilities must be listed before private facilities (cost accessibility).
- Do not show facilities with no contact information for emergency cases.
- Do not make appointment bookings — provide contact information only (MVP scope).
- Do not share facility data that could be personally identifying for staff.

## Example Input
```json
{
  "triage_level": "MODERATE",
  "location": {
    "district": "Dharmapuri",
    "state": "Tamil Nadu"
  }
}
```

## Example Output
```json
{
  "facilities": [
    {
      "name": "Dharmapuri District PHC",
      "type": "PHC",
      "distance_km": 4.2,
      "address": "Main Road, Dharmapuri, Tamil Nadu",
      "contact": "04342-123456",
      "services": ["OPD", "Maternal Care", "Immunization"],
      "is_government": true
    },
    {
      "name": "Dharmapuri Community Health Centre",
      "type": "CHC",
      "distance_km": 8.5,
      "address": "Hospital Road, Dharmapuri",
      "contact": "04342-987654",
      "services": ["OPD", "Emergency", "Surgery", "Laboratory"],
      "is_government": true
    }
  ],
  "recommended_facility": "Dharmapuri District PHC — 4.2 km — Contact: 04342-123456",
  "recommended_reason": "PHC is the right facility for your symptoms. It is close, free, and provides the care you need.",
  "health_scheme_note": "You can receive free treatment at this government PHC under Ayushman Bharat."
}
```

## Failure Handling
- **No facilities found in cache:** Return district-level government hospital contact + district health office number.
- **Geocoding fails:** Ask patient to describe their nearest town; search by district.
- **Overpass API timeout:** Use cached facility list; log timeout.
- **EMERGENCY + no facility data:** Always show 112 and 108 immediately regardless of facility data availability.
- **Private facilities only available:** Show with explicit note: "Government facility not found nearby — private facility shown."
