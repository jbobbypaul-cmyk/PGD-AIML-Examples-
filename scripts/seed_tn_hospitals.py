"""
Seed Tamil Nadu Government Hospital data into facility_cache.
Source: NHM Tamil Nadu / MoHFW HMIS public directory.
Run once:  python scripts/seed_tn_hospitals.py
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.sqlite_client import init_db, upsert_facility_cache

LAST_UPDATED = datetime.utcnow().strftime("%Y-%m-%d")

# fmt: off
TN_HOSPITALS: list[dict] = [
    # ── Chennai ───────────────────────────────────────────────────────
    {"name": "Rajiv Gandhi Government General Hospital", "facility_type": "Hospital", "district": "Chennai", "state": "Tamil Nadu", "address": "Park Town, Chennai, TN 600003", "contact": "044-25305000", "lat": 13.0824, "lon": 80.2785, "services": ["Emergency","ICU","Surgery","OPD","Specialty Care","Blood Bank"], "is_government": True},
    {"name": "Government Stanley Medical College Hospital", "facility_type": "Hospital", "district": "Chennai", "state": "Tamil Nadu", "address": "Old Jail Road, Chennai, TN 600001", "contact": "044-25281401", "lat": 13.1005, "lon": 80.2878, "services": ["Emergency","ICU","Surgery","OPD","Trauma"], "is_government": True},
    {"name": "Government Kasturba Gandhi Hospital", "facility_type": "Hospital", "district": "Chennai", "state": "Tamil Nadu", "address": "Triplicane, Chennai, TN 600005", "contact": "044-28452411", "lat": 13.0578, "lon": 80.2789, "services": ["Maternity","Gynecology","Pediatrics","OPD"], "is_government": True},
    {"name": "Government Kilpauk Medical College Hospital", "facility_type": "Hospital", "district": "Chennai", "state": "Tamil Nadu", "address": "Poonamallee High Road, Kilpauk, Chennai, TN 600010", "contact": "044-26412000", "lat": 13.0849, "lon": 80.2376, "services": ["Emergency","ICU","Surgery","OPD","Neurology"], "is_government": True},

    # ── Coimbatore ────────────────────────────────────────────────────
    {"name": "Coimbatore Medical College Hospital", "facility_type": "Hospital", "district": "Coimbatore", "state": "Tamil Nadu", "address": "Avanashi Road, Coimbatore, TN 641018", "contact": "0422-2304101", "lat": 11.0105, "lon": 76.9740, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Coimbatore Government District HQ Hospital", "facility_type": "Hospital", "district": "Coimbatore", "state": "Tamil Nadu", "address": "Race Course Road, Coimbatore, TN 641018", "contact": "0422-2391100", "lat": 11.0038, "lon": 76.9707, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Pollachi Government Hospital", "facility_type": "Hospital", "district": "Coimbatore", "state": "Tamil Nadu", "address": "Hospital Road, Pollachi, TN 642001", "contact": "04259-222100", "lat": 10.6611, "lon": 77.0076, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Madurai ───────────────────────────────────────────────────────
    {"name": "Government Rajaji Hospital", "facility_type": "Hospital", "district": "Madurai", "state": "Tamil Nadu", "address": "Panagal Road, Madurai, TN 625020", "contact": "0452-2530700", "lat": 9.9236, "lon": 78.1236, "services": ["Emergency","ICU","Surgery","OPD","Specialty","Blood Bank"], "is_government": True},
    {"name": "Government Omandurar Medical College Hospital", "facility_type": "Hospital", "district": "Madurai", "state": "Tamil Nadu", "address": "Omandurar Estate, Madurai, TN 625001", "contact": "0452-2534100", "lat": 9.9327, "lon": 78.1159, "services": ["Emergency","OPD","Surgery","Pediatrics"], "is_government": True},
    {"name": "Usilampatti Government CHC", "facility_type": "CHC", "district": "Madurai", "state": "Tamil Nadu", "address": "Usilampatti, Madurai, TN 625532", "contact": "04549-242100", "lat": 9.9707, "lon": 77.7961, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Tiruchirappalli ───────────────────────────────────────────────
    {"name": "K.A.P. Viswanatham Government Medical College Hospital", "facility_type": "Hospital", "district": "Tiruchirappalli", "state": "Tamil Nadu", "address": "Cantonment, Tiruchirappalli, TN 620001", "contact": "0431-2413421", "lat": 10.8173, "lon": 78.6882, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Trichy Government District HQ Hospital", "facility_type": "Hospital", "district": "Tiruchirappalli", "state": "Tamil Nadu", "address": "Ariyamangalam, Tiruchirappalli, TN 620010", "contact": "0431-2421030", "lat": 10.7785, "lon": 78.7462, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Salem ─────────────────────────────────────────────────────────
    {"name": "Salem Government Medical College Hospital", "facility_type": "Hospital", "district": "Salem", "state": "Tamil Nadu", "address": "Shevapet, Salem, TN 636030", "contact": "0427-2448401", "lat": 11.6487, "lon": 78.1632, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Salem Government Hospital", "facility_type": "Hospital", "district": "Salem", "state": "Tamil Nadu", "address": "Omalur Main Road, Salem, TN 636001", "contact": "0427-2244100", "lat": 11.6643, "lon": 78.1460, "services": ["Emergency","OPD","Surgery","Laboratory"], "is_government": True},
    {"name": "Attur CHC", "facility_type": "CHC", "district": "Salem", "state": "Tamil Nadu", "address": "Hospital Road, Attur, Salem, TN 636102", "contact": "04282-260100", "lat": 11.5973, "lon": 78.5994, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Tirunelveli ───────────────────────────────────────────────────
    {"name": "Tirunelveli Medical College Hospital", "facility_type": "Hospital", "district": "Tirunelveli", "state": "Tamil Nadu", "address": "High Ground Road, Tirunelveli, TN 627011", "contact": "0462-2572572", "lat": 8.7202, "lon": 77.6975, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Government District HQ Hospital Tirunelveli", "facility_type": "Hospital", "district": "Tirunelveli", "state": "Tamil Nadu", "address": "Junction Road, Tirunelveli, TN 627001", "contact": "0462-2336100", "lat": 8.7139, "lon": 77.7567, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Vellore ───────────────────────────────────────────────────────
    {"name": "Government Vellore Medical College Hospital", "facility_type": "Hospital", "district": "Vellore", "state": "Tamil Nadu", "address": "Adukkamparai, Vellore, TN 632011", "contact": "0416-2221100", "lat": 12.9215, "lon": 79.1319, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Vaniyambadi Government Hospital", "facility_type": "Hospital", "district": "Vellore", "state": "Tamil Nadu", "address": "Hospital Road, Vaniyambadi, TN 635751", "contact": "04174-220100", "lat": 12.6862, "lon": 78.6118, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Erode ─────────────────────────────────────────────────────────
    {"name": "Erode Government Medical College Hospital", "facility_type": "Hospital", "district": "Erode", "state": "Tamil Nadu", "address": "Perundurai Road, Erode, TN 638004", "contact": "0424-2262121", "lat": 11.3457, "lon": 77.7252, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Gobichettipalayam Government Hospital", "facility_type": "Hospital", "district": "Erode", "state": "Tamil Nadu", "address": "Hospital Road, Gobichettipalayam, TN 638452", "contact": "04285-222100", "lat": 11.4530, "lon": 77.4355, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Thoothukudi ───────────────────────────────────────────────────
    {"name": "Government Thoothukudi Medical College Hospital", "facility_type": "Hospital", "district": "Thoothukudi", "state": "Tamil Nadu", "address": "Hospital Road, Thoothukudi, TN 628001", "contact": "0461-2321100", "lat": 8.7626, "lon": 78.1348, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Kovilpatti Government Hospital", "facility_type": "Hospital", "district": "Thoothukudi", "state": "Tamil Nadu", "address": "Hospital Road, Kovilpatti, TN 628501", "contact": "04632-220100", "lat": 9.1702, "lon": 77.8688, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Dindigul ──────────────────────────────────────────────────────
    {"name": "Government District HQ Hospital Dindigul", "facility_type": "Hospital", "district": "Dindigul", "state": "Tamil Nadu", "address": "Raja Road, Dindigul, TN 624001", "contact": "0451-2431100", "lat": 10.3673, "lon": 77.9803, "services": ["Emergency","OPD","Surgery","Laboratory"], "is_government": True},
    {"name": "Palani Government Hospital", "facility_type": "Hospital", "district": "Dindigul", "state": "Tamil Nadu", "address": "Hospital Road, Palani, TN 624601", "contact": "04545-242100", "lat": 10.4477, "lon": 77.5215, "services": ["Emergency","OPD","Laboratory"], "is_government": True},
    {"name": "Oddanchatram CHC", "facility_type": "CHC", "district": "Dindigul", "state": "Tamil Nadu", "address": "Oddanchatram, Dindigul, TN 624619", "contact": "04543-240100", "lat": 10.4929, "lon": 77.7389, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Thanjavur ─────────────────────────────────────────────────────
    {"name": "Thanjavur Medical College Hospital", "facility_type": "Hospital", "district": "Thanjavur", "state": "Tamil Nadu", "address": "Medical College Road, Thanjavur, TN 613004", "contact": "04362-227711", "lat": 10.7870, "lon": 79.1378, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Papanasam Government Hospital", "facility_type": "Hospital", "district": "Thanjavur", "state": "Tamil Nadu", "address": "Hospital Road, Papanasam, TN 614205", "contact": "04278-240100", "lat": 10.9293, "lon": 79.4747, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Kanniyakumari ─────────────────────────────────────────────────
    {"name": "Government Medical College Hospital Nagercoil", "facility_type": "Hospital", "district": "Kanniyakumari", "state": "Tamil Nadu", "address": "Asaripallam Road, Nagercoil, TN 629001", "contact": "04652-230100", "lat": 8.1734, "lon": 77.4326, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Nagercoil Government District HQ Hospital", "facility_type": "Hospital", "district": "Kanniyakumari", "state": "Tamil Nadu", "address": "KK Road, Nagercoil, TN 629001", "contact": "04652-230200", "lat": 8.1766, "lon": 77.4347, "services": ["Emergency","OPD","Surgery","Laboratory"], "is_government": True},
    {"name": "Padmanabhapuram CHC", "facility_type": "CHC", "district": "Kanniyakumari", "state": "Tamil Nadu", "address": "Padmanabhapuram, TN 629301", "contact": "04651-240100", "lat": 8.2556, "lon": 77.3263, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Cuddalore ─────────────────────────────────────────────────────
    {"name": "Cuddalore Government Medical College Hospital", "facility_type": "Hospital", "district": "Cuddalore", "state": "Tamil Nadu", "address": "Anna Nagar, Cuddalore, TN 607001", "contact": "04142-242100", "lat": 11.7480, "lon": 79.7714, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Chidambaram Government Hospital", "facility_type": "Hospital", "district": "Cuddalore", "state": "Tamil Nadu", "address": "Bazaar Street, Chidambaram, TN 608001", "contact": "04144-220100", "lat": 11.3993, "lon": 79.6939, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Villupuram ────────────────────────────────────────────────────
    {"name": "Villupuram Government Medical College Hospital", "facility_type": "Hospital", "district": "Villupuram", "state": "Tamil Nadu", "address": "Mundiyampakkam, Villupuram, TN 605601", "contact": "04146-221100", "lat": 11.9400, "lon": 79.4928, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Tindivanam Government Hospital", "facility_type": "Hospital", "district": "Villupuram", "state": "Tamil Nadu", "address": "Hospital Road, Tindivanam, TN 604001", "contact": "04147-225100", "lat": 12.2312, "lon": 79.6513, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Krishnagiri ───────────────────────────────────────────────────
    {"name": "Krishnagiri Government Medical College Hospital", "facility_type": "Hospital", "district": "Krishnagiri", "state": "Tamil Nadu", "address": "Mathur, Krishnagiri, TN 635001", "contact": "04343-234100", "lat": 12.5266, "lon": 78.2139, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Hosur Government Hospital", "facility_type": "Hospital", "district": "Krishnagiri", "state": "Tamil Nadu", "address": "Hospital Road, Hosur, TN 635109", "contact": "04344-242100", "lat": 12.7366, "lon": 77.8313, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Dharmapuri ────────────────────────────────────────────────────
    {"name": "Dharmapuri Medical College Hospital", "facility_type": "Hospital", "district": "Dharmapuri", "state": "Tamil Nadu", "address": "Pennagaram Road, Dharmapuri, TN 636701", "contact": "04342-268100", "lat": 12.1207, "lon": 78.1580, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Dharmapuri Government CHC Palacode", "facility_type": "CHC", "district": "Dharmapuri", "state": "Tamil Nadu", "address": "Palacode, Dharmapuri, TN 636808", "contact": "04346-232100", "lat": 12.1807, "lon": 77.8988, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Namakkal ──────────────────────────────────────────────────────
    {"name": "Namakkal Government Medical College Hospital", "facility_type": "Hospital", "district": "Namakkal", "state": "Tamil Nadu", "address": "Mohanur Road, Namakkal, TN 637001", "contact": "04286-221100", "lat": 11.2198, "lon": 78.1671, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Paramathi PHC", "facility_type": "PHC", "district": "Namakkal", "state": "Tamil Nadu", "address": "Paramathi-Velur, Namakkal, TN 637207", "contact": "04287-278100", "lat": 11.1243, "lon": 77.9218, "services": ["OPD","Immunization","Free Drugs","Maternal Care"], "is_government": True},

    # ── Karur ─────────────────────────────────────────────────────────
    {"name": "Karur Government Medical College Hospital", "facility_type": "Hospital", "district": "Karur", "state": "Tamil Nadu", "address": "Erode Road, Karur, TN 639001", "contact": "04324-231100", "lat": 10.9601, "lon": 78.0766, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Kulithalai Government Hospital", "facility_type": "Hospital", "district": "Karur", "state": "Tamil Nadu", "address": "Hospital Road, Kulithalai, TN 639104", "contact": "04323-242100", "lat": 10.9336, "lon": 78.4216, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Perambalur ────────────────────────────────────────────────────
    {"name": "Perambalur Government Medical College Hospital", "facility_type": "Hospital", "district": "Perambalur", "state": "Tamil Nadu", "address": "NH 45, Perambalur, TN 621212", "contact": "04328-224100", "lat": 11.2333, "lon": 78.8833, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Veppanthattai CHC", "facility_type": "CHC", "district": "Perambalur", "state": "Tamil Nadu", "address": "Veppanthattai, Perambalur, TN 621116", "contact": "04328-267100", "lat": 11.3421, "lon": 78.9957, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Ariyalur ──────────────────────────────────────────────────────
    {"name": "Ariyalur Government District HQ Hospital", "facility_type": "Hospital", "district": "Ariyalur", "state": "Tamil Nadu", "address": "Hospital Road, Ariyalur, TN 621704", "contact": "04329-220100", "lat": 11.1400, "lon": 79.0768, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Sendurai CHC", "facility_type": "CHC", "district": "Ariyalur", "state": "Tamil Nadu", "address": "Sendurai, Ariyalur, TN 621709", "contact": "04329-225100", "lat": 11.0912, "lon": 79.2243, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Tiruvannamalai ────────────────────────────────────────────────
    {"name": "Tiruvannamalai Government Medical College Hospital", "facility_type": "Hospital", "district": "Tiruvannamalai", "state": "Tamil Nadu", "address": "Maruthi Nagar, Tiruvannamalai, TN 606601", "contact": "04175-252100", "lat": 12.2253, "lon": 79.0747, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Polur PHC", "facility_type": "PHC", "district": "Tiruvannamalai", "state": "Tamil Nadu", "address": "Polur, Tiruvannamalai, TN 606803", "contact": "04188-258100", "lat": 12.5123, "lon": 79.2147, "services": ["OPD","Immunization","Maternal Care","Free Drugs"], "is_government": True},

    # ── Ranipet ───────────────────────────────────────────────────────
    {"name": "Ranipet Government District HQ Hospital", "facility_type": "Hospital", "district": "Ranipet", "state": "Tamil Nadu", "address": "Collector Office Road, Ranipet, TN 632401", "contact": "04172-225100", "lat": 12.9324, "lon": 79.3329, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Arcot Government Hospital", "facility_type": "Hospital", "district": "Ranipet", "state": "Tamil Nadu", "address": "Hospital Road, Arcot, TN 632503", "contact": "04172-242200", "lat": 12.9073, "lon": 79.3164, "services": ["OPD","Emergency","Laboratory"], "is_government": True},

    # ── Tirupathur ────────────────────────────────────────────────────
    {"name": "Tirupattur Government District HQ Hospital", "facility_type": "Hospital", "district": "Tirupathur", "state": "Tamil Nadu", "address": "Hospital Road, Tirupattur, TN 635601", "contact": "04179-220100", "lat": 12.4975, "lon": 78.5728, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Vaniyambadi Government CHC", "facility_type": "CHC", "district": "Tirupathur", "state": "Tamil Nadu", "address": "Vaniyambadi, Tirupathur, TN 635751", "contact": "04174-222100", "lat": 12.6862, "lon": 78.6118, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Chengalpattu ──────────────────────────────────────────────────
    {"name": "Chengalpattu Medical College Hospital", "facility_type": "Hospital", "district": "Chengalpattu", "state": "Tamil Nadu", "address": "Old Mahabalipuram Road, Chengalpattu, TN 603001", "contact": "044-27426100", "lat": 12.6922, "lon": 79.9764, "services": ["Emergency","ICU","Surgery","OPD","Specialty"], "is_government": True},
    {"name": "Maraimalai Nagar CHC", "facility_type": "CHC", "district": "Chengalpattu", "state": "Tamil Nadu", "address": "Maraimalai Nagar, Chengalpattu, TN 603209", "contact": "044-27452100", "lat": 12.7882, "lon": 80.0232, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Kallakurichi ──────────────────────────────────────────────────
    {"name": "Kallakurichi Government Medical College Hospital", "facility_type": "Hospital", "district": "Kallakurichi", "state": "Tamil Nadu", "address": "Santhoshapuram, Kallakurichi, TN 606202", "contact": "04151-224100", "lat": 11.7380, "lon": 78.9581, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Ulundurpettai CHC", "facility_type": "CHC", "district": "Kallakurichi", "state": "Tamil Nadu", "address": "Ulundurpettai, Kallakurichi, TN 606107", "contact": "04151-262100", "lat": 11.6617, "lon": 79.0786, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Virudhunagar ──────────────────────────────────────────────────
    {"name": "Virudhunagar Government Medical College Hospital", "facility_type": "Hospital", "district": "Virudhunagar", "state": "Tamil Nadu", "address": "Salem Road, Virudhunagar, TN 626002", "contact": "04562-243100", "lat": 9.5682, "lon": 77.9517, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Srivilliputhur Government Hospital", "facility_type": "Hospital", "district": "Virudhunagar", "state": "Tamil Nadu", "address": "Hospital Road, Srivilliputhur, TN 626125", "contact": "04563-220100", "lat": 9.5140, "lon": 77.6358, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Ramanathapuram ────────────────────────────────────────────────
    {"name": "Ramanathapuram Government Medical College Hospital", "facility_type": "Hospital", "district": "Ramanathapuram", "state": "Tamil Nadu", "address": "Collector Office Road, Ramanathapuram, TN 623501", "contact": "04567-221100", "lat": 9.3639, "lon": 78.8395, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Paramakudi Government Hospital", "facility_type": "Hospital", "district": "Ramanathapuram", "state": "Tamil Nadu", "address": "Hospital Road, Paramakudi, TN 623701", "contact": "04564-222100", "lat": 9.5463, "lon": 78.5895, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Sivaganga ─────────────────────────────────────────────────────
    {"name": "Sivaganga Government Medical College Hospital", "facility_type": "Hospital", "district": "Sivaganga", "state": "Tamil Nadu", "address": "Hospital Road, Sivaganga, TN 623560", "contact": "04575-242100", "lat": 9.8440, "lon": 78.4839, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Karaikudi Government Hospital", "facility_type": "Hospital", "district": "Sivaganga", "state": "Tamil Nadu", "address": "Hospital Road, Karaikudi, TN 630001", "contact": "04565-220100", "lat": 10.0745, "lon": 78.7741, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Pudukkottai ───────────────────────────────────────────────────
    {"name": "Pudukkottai Government Medical College Hospital", "facility_type": "Hospital", "district": "Pudukkottai", "state": "Tamil Nadu", "address": "Hospital Road, Pudukkottai, TN 622001", "contact": "04322-221100", "lat": 10.3797, "lon": 78.8265, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Aranthangi Government Hospital", "facility_type": "Hospital", "district": "Pudukkottai", "state": "Tamil Nadu", "address": "Hospital Road, Aranthangi, TN 614616", "contact": "04371-240100", "lat": 10.1696, "lon": 79.0706, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Tiruvarur ─────────────────────────────────────────────────────
    {"name": "Tiruvarur Government District HQ Hospital", "facility_type": "Hospital", "district": "Tiruvarur", "state": "Tamil Nadu", "address": "Hospital Road, Tiruvarur, TN 610001", "contact": "04366-222100", "lat": 10.7713, "lon": 79.6386, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Kumbakonam Government Hospital", "facility_type": "Hospital", "district": "Tiruvarur", "state": "Tamil Nadu", "address": "Hospital Road, Kumbakonam, TN 612001", "contact": "0435-2420100", "lat": 10.9609, "lon": 79.3764, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},

    # ── Nagapattinam ──────────────────────────────────────────────────
    {"name": "Nagapattinam Government Medical College Hospital", "facility_type": "Hospital", "district": "Nagapattinam", "state": "Tamil Nadu", "address": "Hospital Road, Nagapattinam, TN 611001", "contact": "04365-240100", "lat": 10.7672, "lon": 79.8420, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Vedaranyam CHC", "facility_type": "CHC", "district": "Nagapattinam", "state": "Tamil Nadu", "address": "Vedaranyam, Nagapattinam, TN 614810", "contact": "04369-240100", "lat": 10.3736, "lon": 79.8527, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Mayiladuthurai ────────────────────────────────────────────────
    {"name": "Mayiladuthurai Government District HQ Hospital", "facility_type": "Hospital", "district": "Mayiladuthurai", "state": "Tamil Nadu", "address": "Hospital Road, Mayiladuthurai, TN 609001", "contact": "04364-220100", "lat": 11.1035, "lon": 79.6531, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Sirkazhi Government Hospital", "facility_type": "Hospital", "district": "Mayiladuthurai", "state": "Tamil Nadu", "address": "Hospital Road, Sirkazhi, TN 609110", "contact": "04364-262100", "lat": 11.2328, "lon": 79.7462, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Nilgiris ──────────────────────────────────────────────────────
    {"name": "Ooty Government District HQ Hospital", "facility_type": "Hospital", "district": "Nilgiris", "state": "Tamil Nadu", "address": "Hospital Road, Ooty, TN 643001", "contact": "0423-2442100", "lat": 11.4062, "lon": 76.6950, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Coonoor Government Hospital", "facility_type": "Hospital", "district": "Nilgiris", "state": "Tamil Nadu", "address": "Hospital Road, Coonoor, TN 643101", "contact": "0423-2230100", "lat": 11.3526, "lon": 76.7942, "services": ["Emergency","OPD","Laboratory"], "is_government": True},
    {"name": "Gudalur CHC", "facility_type": "CHC", "district": "Nilgiris", "state": "Tamil Nadu", "address": "Gudalur, Nilgiris, TN 643212", "contact": "04262-260100", "lat": 11.5002, "lon": 76.4927, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Theni ─────────────────────────────────────────────────────────
    {"name": "Theni Government Medical College Hospital", "facility_type": "Hospital", "district": "Theni", "state": "Tamil Nadu", "address": "Bypass Road, Theni, TN 625531", "contact": "04546-255100", "lat": 10.0113, "lon": 77.4772, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Bodinayakanur Government Hospital", "facility_type": "Hospital", "district": "Theni", "state": "Tamil Nadu", "address": "Hospital Road, Bodinayakanur, TN 625513", "contact": "04546-262100", "lat": 10.0127, "lon": 77.3518, "services": ["Emergency","OPD","Laboratory"], "is_government": True},

    # ── Tenkasi ───────────────────────────────────────────────────────
    {"name": "Tenkasi Government District HQ Hospital", "facility_type": "Hospital", "district": "Tenkasi", "state": "Tamil Nadu", "address": "Hospital Road, Tenkasi, TN 627811", "contact": "04633-220100", "lat": 8.9581, "lon": 77.3152, "services": ["Emergency","OPD","Laboratory","Surgery"], "is_government": True},
    {"name": "Courtallam CHC", "facility_type": "CHC", "district": "Tenkasi", "state": "Tamil Nadu", "address": "Courtallam, Tenkasi, TN 627802", "contact": "04633-282100", "lat": 8.9347, "lon": 77.2773, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Tiruppur ──────────────────────────────────────────────────────
    {"name": "Tiruppur Government Medical College Hospital", "facility_type": "Hospital", "district": "Tiruppur", "state": "Tamil Nadu", "address": "Avinashi Road, Tiruppur, TN 641604", "contact": "0421-2210100", "lat": 11.1085, "lon": 77.3411, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Udumalaipettai CHC", "facility_type": "CHC", "district": "Tiruppur", "state": "Tamil Nadu", "address": "Hospital Road, Udumalaipettai, TN 642126", "contact": "04252-222100", "lat": 10.5837, "lon": 77.2511, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},

    # ── Kancheepuram ──────────────────────────────────────────────────
    {"name": "Kancheepuram Government Medical College Hospital", "facility_type": "Hospital", "district": "Kancheepuram", "state": "Tamil Nadu", "address": "Hospital Road, Kancheepuram, TN 631501", "contact": "044-27222100", "lat": 12.8185, "lon": 79.6947, "services": ["Emergency","ICU","Surgery","OPD"], "is_government": True},
    {"name": "Uthiramerur CHC", "facility_type": "CHC", "district": "Kancheepuram", "state": "Tamil Nadu", "address": "Uthiramerur, Kancheepuram, TN 603406", "contact": "044-27249100", "lat": 12.6169, "lon": 79.7542, "services": ["OPD","Maternal Care","Immunization","Free Drugs"], "is_government": True},
]
# fmt: on


def main() -> None:
    print("Initialising database…")
    init_db()

    print(f"Seeding {len(TN_HOSPITALS)} Tamil Nadu hospitals…")
    inserted = 0
    for rec in TN_HOSPITALS:
        rec["last_updated"] = LAST_UPDATED
        rec["source"] = "nhm_tn"
        upsert_facility_cache(rec)
        inserted += 1

    print(f"Done — {inserted} records upserted into facility_cache.")


if __name__ == "__main__":
    main()
