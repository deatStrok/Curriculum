from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import download_resume, get_admin_client, get_user_settings, list_companies
from email_service import send_email_sendgrid
from settings import ALLOWED_SOURCES, PLATFORM_FROM_EMAIL, PLATFORM_FROM_NAME
from templates import build_email_body, build_subject


def _log_send(
    user_id: str,
    company: Dict[str, Any],
    subject: str,
    body: str,
    provider: str,
    provider_status: str,
    error_message: Optional[str] = None,
) -> None:
    get_admin_client().table("send_log").insert({
        "user_id": user_id,
        "company_id": company.get("id"),
        "email": company.get("email"),
        "subject": subject,
        "body": body,
        "provider": provider,
        "provider_status": provider_status,
        "error_message": error_message,
    }).execute()


def _mark_company(company_id: str, user_id: str, updates: Dict[str, Any]) -> None:
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    get_admin_client().table("companies").update(updates).eq("id", company_id).eq("user_id", user_id).execute()


def send_batch_for_user(user_id: str, limit_override: Optional[int] = None) -> Dict[str, int]:
    settings = get_user_settings(user_id)
    limit = int(limit_override or settings.get("daily_limit") or 30)
    dry_run = bool(settings.get("dry_run", True))

    if not settings.get("sender_name"):
        raise RuntimeError("Configure o nome do candidato antes de disparar.")

    platform_from_email = PLATFORM_FROM_EMAIL or settings.get("sender_email")
    platform_from_name = PLATFORM_FROM_NAME or "Curriculumy"
    if not platform_from_email:
        raise RuntimeError("Configure PLATFORM_FROM_EMAIL nos Secrets do Streamlit ou o e-mail remetente verificado.")

    if not settings.get("resume_storage_path"):
        raise RuntimeError("Envie um currículo em PDF antes de disparar.")

    resume_bytes, resume_filename = download_resume(user_id)
    if not resume_bytes:
        raise RuntimeError("Não foi possível baixar o currículo no Supabase Storage.")

    companies = list_companies(
        user_id,
        filters={"only_eligible": True},
        limit=limit,
    )

    sent = 0
    skipped = 0
    errors = 0

    for company in companies:
        company_id = company["id"]
        source = (company.get("source") or "").strip().lower()

        subject = build_subject(company, settings)
        body = build_email_body(company, settings)

        if source not in ALLOWED_SOURCES:
            _mark_company(company_id, user_id, {"status": "bloqueado_origem_invalida", "blocked": True})
            skipped += 1
            continue

        try:
            if dry_run:
                provider = "dry_run"
                provider_status = "DRY_RUN"
            else:
                result = send_email_sendgrid(
                    from_email=platform_from_email,
                    from_name=platform_from_name,
                    to_email=company["email"],
                    subject=subject,
                    html_body=body,
                    reply_to_email=settings.get("reply_to_email") or settings.get("sender_email") or platform_from_email,
                    attachment_bytes=resume_bytes,
                    attachment_filename=resume_filename or "curriculo.pdf",
                )
                provider = "sendgrid"
                provider_status = str(result["status_code"])

            _log_send(user_id, company, subject, body, provider, provider_status)
            _mark_company(company_id, user_id, {
                "status": "enviado",
                "last_sent_at": datetime.now(timezone.utc).isoformat(),
            })
            sent += 1

        except Exception as exc:
            _log_send(user_id, company, subject, body, "sendgrid", "ERROR", str(exc))
            _mark_company(company_id, user_id, {"status": "erro"})
            errors += 1

    return {"sent": sent, "skipped": skipped, "errors": errors, "loaded": len(companies)}
