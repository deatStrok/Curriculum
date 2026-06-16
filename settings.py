import os
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


SUPABASE_URL = get_secret("SUPABASE_URL", "")
SUPABASE_ANON_KEY = get_secret("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = get_secret("SUPABASE_SERVICE_ROLE_KEY", "")
SENDGRID_API_KEY = get_secret("SENDGRID_API_KEY", "")
APP_TIMEZONE = get_secret("APP_TIMEZONE", "America/Bahia")
PLATFORM_FROM_EMAIL = get_secret("PLATFORM_FROM_EMAIL", "")
PLATFORM_FROM_NAME = get_secret("PLATFORM_FROM_NAME", "Curriculumy")

ALLOWED_SOURCES = {
    "vaga_publica",
    "pagina_carreiras",
    "email_institucional",
    "indicacao",
    "opt_in",
}

DEFAULT_SETTINGS = {
    "sender_name": "",
    "sender_email": "",
    "reply_to_email": "",
    "target_role": "Desenvolvedor Python",
    "daily_limit": 30,
    "dry_run": True,
    "schedule_enabled": False,
    "schedule_hour": 9,
    "timezone": APP_TIMEZONE,
    "provider": "sendgrid",
    "email_signature": "",
    "subject_template": "Candidatura para {role}",
    "email_body_template": "",
}

