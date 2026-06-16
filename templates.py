from __future__ import annotations

from typing import Dict, Any


def build_subject(company: Dict[str, Any], settings: Dict[str, Any]) -> str:
    role = company.get("desired_role") or settings.get("target_role") or "oportunidades profissionais"
    return f"Candidatura para {role}"


def build_email_body(company: Dict[str, Any], settings: Dict[str, Any]) -> str:
    company_name = company.get("company_name") or "equipe"
    sender_name = settings.get("sender_name") or ""
    role = company.get("desired_role") or settings.get("target_role") or "oportunidades profissionais"
    notes = company.get("notes") or ""
    signature = settings.get("email_signature") or sender_name

    context = f"<p>{notes}</p>" if notes else ""

    return f"""
    <p>Olá, equipe {company_name}, tudo bem?</p>

    <p>Meu nome é {sender_name} e gostaria de me apresentar para oportunidades relacionadas a
    <strong>{role}</strong>.</p>

    <p>Tenho interesse em contribuir com projetos que envolvam tecnologia, desenvolvimento,
    dados, automação, sistemas e melhoria de processos.</p>

    {context}

    <p>Estou enviando meu currículo em anexo para avaliação. Caso exista alguma oportunidade compatível,
    fico à disposição para uma conversa.</p>

    <p>Atenciosamente,<br>{signature}</p>

    <hr>
    <p style="font-size:12px;color:#666;">
    Esta mensagem foi enviada para um contato institucional, página de carreiras, vaga pública,
    indicação ou canal informado para oportunidades profissionais.
    </p>
    """
