"""
RuralCare AI — User Document Processor
Two ingestion paths:
  1. Hospital CSV / Excel  -> facility_cache (SQLite)
  2. Medical PDF / TXT     -> ChromaDB RAG collection
"""

import io
import json
from datetime import datetime
from typing import Any

from app.utils.logger import get_logger

logger = get_logger(__name__)

HOSPITAL_REQUIRED = {"name", "facility_type", "district", "state"}

VALID_FACILITY_TYPES = {"Hospital", "CHC", "PHC", "Sub-Centre"}

# Downloadable template shown in the UI
HOSPITAL_CSV_TEMPLATE = (
    "name,facility_type,district,state,address,contact,lat,lon,services,is_government\n"
    "Salem Government Hospital,Hospital,Salem,Tamil Nadu,Salem Town,04427123456,"
    "11.6633,78.1460,\"OPD,Emergency,Maternity\",1\n"
    "Attur PHC,PHC,Salem,Tamil Nadu,Attur Block,,11.5986,78.5993,"
    "\"OPD,Immunisation\",1\n"
    "Madurai Government Medical College,Hospital,Madurai,Tamil Nadu,"
    "Panagal Road Madurai,04522-532535,9.9252,78.1198,"
    "\"OPD,Emergency,ICU,Surgery,Maternity\",1\n"
)


def get_hospital_csv_template() -> bytes:
    return HOSPITAL_CSV_TEMPLATE.encode("utf-8")


# ── Hospital CSV / Excel ──────────────────────────────────────────────

def process_hospital_file(file_bytes: bytes, filename: str) -> dict[str, Any]:
    """Parse CSV or Excel and upsert rows into facility_cache.
    Returns a summary dict with keys: ok, inserted, updated, skipped, errors, total.
    """
    import pandas as pd
    from app.database.sqlite_client import get_conn

    suffix = filename.rsplit(".", 1)[-1].lower()
    try:
        if suffix in ("xlsx", "xls"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as exc:
        return {"ok": False, "error": f"Could not parse file: {exc}"}

    # Normalise column names
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing = HOSPITAL_REQUIRED - set(df.columns)
    if missing:
        return {
            "ok":    False,
            "error": (
                f"Missing required columns: {', '.join(sorted(missing))}.\n"
                f"Required: {', '.join(sorted(HOSPITAL_REQUIRED))}"
            ),
        }

    inserted = updated = skipped = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            name     = str(row.get("name",     "") or "").strip()
            district = str(row.get("district", "") or "").strip()
            state    = str(row.get("state",    "") or "").strip()

            if not name or not district:
                skipped += 1
                continue

            ftype = str(row.get("facility_type", "") or "").strip()
            if ftype not in VALID_FACILITY_TYPES:
                errors.append(
                    f"Row {idx + 2}: facility_type '{ftype}' not in "
                    f"{sorted(VALID_FACILITY_TYPES)} — row skipped."
                )
                skipped += 1
                continue

            # Services field: accept "OPD,Emergency" or ["OPD","Emergency"]
            raw_svc = row.get("services", "")
            if isinstance(raw_svc, str):
                services = [s.strip() for s in raw_svc.split(",") if s.strip()]
            elif isinstance(raw_svc, (list, tuple)):
                services = [str(s) for s in raw_svc]
            else:
                services = []

            is_gov_raw = row.get("is_government", 1)
            if isinstance(is_gov_raw, str):
                is_gov = 0 if is_gov_raw.strip().lower() in ("0", "false", "no") else 1
            else:
                try:
                    is_gov = 0 if str(is_gov_raw).strip() in ("0", "nan", "") else 1
                except Exception:
                    is_gov = 1

            def _float(v) -> float | None:
                try:
                    s = str(v).strip()
                    return float(s) if s not in ("", "nan", "none", "null") else None
                except Exception:
                    return None

            services_json = json.dumps(services)
            today         = datetime.utcnow().strftime("%Y-%m-%d")
            address       = str(row.get("address", "") or "").strip()
            contact       = str(row.get("contact", "") or "").strip()
            lat           = _float(row.get("lat"))
            lon           = _float(row.get("lon"))

            with get_conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM facility_cache "
                    "WHERE LOWER(TRIM(name))=LOWER(TRIM(?)) "
                    "  AND LOWER(TRIM(district))=LOWER(TRIM(?)) "
                    "  AND LOWER(TRIM(state))=LOWER(TRIM(?))",
                    (name, district, state),
                ).fetchone()

                if existing:
                    conn.execute(
                        """UPDATE facility_cache SET
                               facility_type=?, address=?, contact=?,
                               lat=?, lon=?, services=?, is_government=?,
                               source='user_upload', last_updated=?
                           WHERE id=?""",
                        (ftype, address, contact, lat, lon,
                         services_json, is_gov, today, existing["id"]),
                    )
                    updated += 1
                else:
                    conn.execute(
                        """INSERT INTO facility_cache
                               (name, facility_type, district, state, address, contact,
                                lat, lon, services, is_government, source, last_updated)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (name, ftype, district, state, address, contact,
                         lat, lon, services_json, is_gov, "user_upload", today),
                    )
                    inserted += 1

        except Exception as exc:
            errors.append(f"Row {idx + 2}: {exc}")

    logger.info(
        "Hospital upload '%s': inserted=%d updated=%d skipped=%d errors=%d",
        filename, inserted, updated, skipped, len(errors),
    )
    return {
        "ok":       True,
        "inserted": inserted,
        "updated":  updated,
        "skipped":  skipped,
        "errors":   errors,
        "total":    len(df),
    }


# ── Medical Knowledge PDF / TXT ───────────────────────────────────────

def process_knowledge_document(
    file_bytes: bytes,
    filename: str,
    collection_name: str,
) -> dict[str, Any]:
    """Extract text from PDF/TXT/MD, chunk it, and add to a ChromaDB collection."""
    from langchain_core.documents import Document
    from app.rag.document_loader import chunk_text
    from app.rag.vector_store import get_vectorstore

    suffix = filename.rsplit(".", 1)[-1].lower()

    try:
        if suffix == "pdf":
            text = _extract_pdf_text(file_bytes)
        elif suffix in ("txt", "md"):
            text = file_bytes.decode("utf-8", errors="replace")
        else:
            return {
                "ok":    False,
                "error": f"Unsupported format: .{suffix}  Use PDF, TXT, or MD.",
            }
    except Exception as exc:
        return {"ok": False, "error": f"Could not read file: {exc}"}

    if not text.strip():
        return {"ok": False, "error": "File appears empty or could not be extracted."}

    chunks = chunk_text(text)
    docs = [
        Document(
            page_content=chunk,
            metadata={
                "source":      filename,
                "collection":  collection_name,
                "doc_type":    "user_upload",
                "chunk_index": i,
            },
        )
        for i, chunk in enumerate(chunks)
    ]

    try:
        get_vectorstore(collection_name).add_documents(docs)
    except Exception as exc:
        return {"ok": False, "error": f"Vector store error: {exc}"}

    logger.info(
        "Knowledge upload: %d chunks from '%s' -> collection '%s'",
        len(docs), filename, collection_name,
    )
    return {
        "ok":         True,
        "chunks":     len(docs),
        "collection": collection_name,
        "filename":   filename,
        "preview":    text[:400].strip() + ("…" if len(text) > 400 else ""),
    }


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Try pypdf first (no disk I/O); fall back to langchain PyPDFLoader via temp file."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except ImportError:
        pass

    import os, tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        from langchain_community.document_loaders import PyPDFLoader
        return "\n".join(p.page_content for p in PyPDFLoader(tmp_path).load())
    finally:
        os.unlink(tmp_path)
