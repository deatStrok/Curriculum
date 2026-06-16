from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from supabase import Client, create_client

from settings import (
    DEFAULT_SETTINGS,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)


def get_auth_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("SUPABASE_URL e SUPABASE_ANON_KEY não configurados.")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_admin_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY não configurados.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def _data(resp: Any) -> Any:
    return getattr(resp, "data", None)


def ensure_profile(user_id: str, email: str, full_name: str = "") -> None:
    supabase = get_admin_client()
    existing = _data(supabase.table("profiles").select("id").eq("id", user_id).limit(1).execute())
    if not existing:
        supabase.table("profiles").insert({"id": user_id, "email": email, "full_name": full_name}).execute()
    ensure_user_settings(user_id)


def ensure_user_settings(user_id: str) -> Dict[str, Any]:
    supabase = get_admin_client()
    existing = _data(
        supabase.table("user_settings").select("*").eq("user_id", user_id).limit(1).execute()
    )
    if existing:
        return existing[0]
    payload = {"user_id": user_id, **DEFAULT_SETTINGS}
    supabase.table("user_settings").insert(payload).execute()
    return payload


def get_user_settings(user_id: str) -> Dict[str, Any]:
    return ensure_user_settings(user_id)


def update_user_settings(user_id: str, updates: Dict[str, Any]) -> None:
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    get_admin_client().table("user_settings").update(updates).eq("user_id", user_id).execute()


def upload_resume(user_id: str, filename: str, content: bytes) -> Tuple[str, str]:
    safe_filename = filename.replace("/", "_").replace("\\", "_")
    storage_path = f"{user_id}/{safe_filename}"
    supabase = get_admin_client()
    try:
        supabase.storage.from_("resumes").remove([storage_path])
    except Exception:
        pass
    supabase.storage.from_("resumes").upload(
        storage_path,
        content,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    update_user_settings(user_id, {"resume_storage_path": storage_path, "resume_filename": safe_filename})
    return storage_path, safe_filename


def download_resume(user_id: str) -> Tuple[Optional[bytes], Optional[str]]:
    settings = get_user_settings(user_id)
    path = settings.get("resume_storage_path")
    filename = settings.get("resume_filename")
    if not path:
        return None, None
    content = get_admin_client().storage.from_("resumes").download(path)
    return content, filename or "curriculo.pdf"


def import_companies(user_id: str, df: pd.DataFrame) -> Tuple[int, int]:
    required = {"company_name", "email"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(sorted(missing))}")

    supabase = get_admin_client()
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        email = str(row.get("email", "")).strip().lower()
        company_name = str(row.get("company_name", "")).strip()
        if not email or not company_name or "@" not in email:
            skipped += 1
            continue

        payload = {
            "user_id": user_id,
            "company_name": company_name,
            "email": email,
            "website": str(row.get("website", "") or "").strip(),
            "city": str(row.get("city", "") or "").strip(),
            "state": str(row.get("state", "") or "").strip(),
            "country": str(row.get("country", "Brasil") or "Brasil").strip(),
            "sector": str(row.get("sector", "") or "").strip(),
            "desired_role": str(row.get("desired_role", "") or "").strip(),
            "source": str(row.get("source", "") or "").strip().lower(),
            "priority": int(row.get("priority", 3) or 3),
            "tags": str(row.get("tags", "") or "").strip(),
            "notes": str(row.get("notes", "") or "").strip(),
        }

        try:
            supabase.table("companies").insert(payload).execute()
            inserted += 1
        except Exception:
            skipped += 1

    return inserted, skipped


def list_companies(user_id: str, filters: Dict[str, Any], limit: int = 1000) -> List[Dict[str, Any]]:
    query = get_admin_client().table("companies").select("*").eq("user_id", user_id)

    if filters.get("status") and filters["status"] != "Todos":
        query = query.eq("status", filters["status"])
    if filters.get("source") and filters["source"] != "Todas":
        query = query.eq("source", filters["source"])
    if filters.get("approved") == "Aprovadas":
        query = query.eq("approved", True)
    elif filters.get("approved") == "Não aprovadas":
        query = query.eq("approved", False)
    if filters.get("blocked") == "Bloqueadas":
        query = query.eq("blocked", True)
    elif filters.get("blocked") == "Não bloqueadas":
        query = query.eq("blocked", False)
    if filters.get("only_eligible"):
        query = query.eq("approved", True).eq("blocked", False).is_("last_sent_at", "null")
    if filters.get("sector"):
        query = query.ilike("sector", f"%{filters['sector']}%")
    if filters.get("city"):
        query = query.ilike("city", f"%{filters['city']}%")
    if filters.get("state"):
        query = query.ilike("state", f"%{filters['state']}%")
    if filters.get("text"):
        text = filters["text"]
        query = query.or_(
            f"company_name.ilike.%{text}%,email.ilike.%{text}%,website.ilike.%{text}%,tags.ilike.%{text}%"
        )

    resp = query.order("priority", desc=False).order("created_at", desc=False).limit(limit).execute()
    return _data(resp) or []


def update_companies(user_id: str, rows: List[Dict[str, Any]]) -> None:
    supabase = get_admin_client()
    editable_fields = [
        "company_name", "email", "website", "city", "state", "country", "sector",
        "desired_role", "source", "priority", "tags", "status", "approved", "blocked", "notes"
    ]
    for row in rows:
        company_id = row.get("id")
        if not company_id:
            continue
        payload = {k: row.get(k) for k in editable_fields if k in row}
        if "email" in payload and payload["email"]:
            payload["email"] = str(payload["email"]).strip().lower()
        if "source" in payload and payload["source"]:
            payload["source"] = str(payload["source"]).strip().lower()
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        supabase.table("companies").update(payload).eq("id", company_id).eq("user_id", user_id).execute()


def create_company(user_id: str, payload: Dict[str, Any]) -> None:
    payload = {**payload, "user_id": user_id}
    payload["email"] = str(payload.get("email", "")).strip().lower()
    payload["source"] = str(payload.get("source", "")).strip().lower()
    get_admin_client().table("companies").insert(payload).execute()


def metrics(user_id: str) -> Dict[str, int]:
    rows = _data(get_admin_client().table("companies").select("status,approved,blocked,last_sent_at").eq("user_id", user_id).execute()) or []
    total = len(rows)
    approved = sum(1 for r in rows if r.get("approved"))
    sent = sum(1 for r in rows if r.get("status") == "enviado")
    eligible = sum(1 for r in rows if r.get("approved") and not r.get("blocked") and not r.get("last_sent_at"))
    return {"total": total, "approved": approved, "sent": sent, "eligible": eligible}


def list_logs(user_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    return _data(
        get_admin_client()
        .table("send_log")
        .select("sent_at,email,subject,provider,provider_status,error_message")
        .eq("user_id", user_id)
        .order("sent_at", desc=True)
        .limit(limit)
        .execute()
    ) or []
