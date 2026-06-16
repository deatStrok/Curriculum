from __future__ import annotations

import html
from typing import Any, Dict


DEFAULT_SUBJECT_TEMPLATE = "Candidatura para {role}"

DEFAULT_EMAIL_TEMPLATE = """Olá, equipe {company_name}, tudo bem?

Meu nome é {candidate_name} e gostaria de me apresentar para oportunidades relacionadas a {role}.

Tenho interesse em contribuir com projetos que envolvam tecnologia, desenvolvimento, dados, automação, sistemas e melhoria de processos.

{company_notes}

Estou enviando meu currículo em anexo para avaliação. Caso exista alguma oportunidade compatível, fico à disposição para uma conversa.

Atenciosamente,
{signature}"""

TEMPLATE_PRESETS = {
    "Direto e profissional": {
        "subject": "Candidatura para {role}",
        "body": DEFAULT_EMAIL_TEMPLATE,
    },
    "Curto e objetivo": {
        "subject": "Currículo - {role}",
        "body": """Olá, equipe {company_name}.

Meu nome é {candidate_name} e estou buscando oportunidades como {role}.

Envio meu currículo em anexo para avaliação. Caso haja alguma vaga compatível, fico à disposição para conversar.

Atenciosamente,
{signature}""",
    },
    "Com foco em disponibilidade": {
        "subject": "Disponível para oportunidades em {role}",
        "body": """Olá, equipe {company_name}, tudo bem?

Sou {candidate_name} e gostaria de me colocar à disposição para oportunidades relacionadas a {role}.

Tenho interesse em contribuir com projetos da empresa e envio meu currículo em anexo para análise.

{company_notes}

Caso faça sentido, fico à disposição para uma conversa inicial.

Atenciosamente,
{signature}""",
    },
    "Mais humano/networking": {
        "subject": "Apresentação profissional - {role}",
        "body": """Olá, equipe {company_name}, tudo bem?

Meu nome é {candidate_name}. Estou entrando em contato para me apresentar profissionalmente e compartilhar meu currículo para possíveis oportunidades em {role}.

Acredito que minha experiência e interesse na área podem ser úteis em projetos da empresa.

{company_notes}

Fico à disposição caso exista alguma oportunidade atual ou futura compatível.

Atenciosamente,
{signature}""",
    },
}


def _context(company: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, str]:
    company_name = company.get("company_name") or "empresa"
    candidate_name = settings.get("sender_name") or ""
    role = company.get("desired_role") or settings.get("target_role") or "oportunidades profissionais"
    notes = (company.get("notes") or "").strip()
    signature = settings.get("email_signature") or candidate_name
    reply_to = settings.get("reply_to_email") or settings.get("sender_email") or ""
    return {
        "company_name": str(company_name),
        "candidate_name": str(candidate_name),
        "role": str(role),
        "company_notes": str(notes),
        "signature": str(signature),
        "reply_to_email": str(reply_to),
    }


def render_text_template(template: str, context: Dict[str, str]) -> str:
    if not template:
        template = DEFAULT_EMAIL_TEMPLATE
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace("{" + key + "}", value)
    return rendered


def text_to_html(text: str) -> str:
    escaped = html.escape(text or "")
    paragraphs = []
    for block in escaped.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        paragraphs.append("<p>" + block.replace("\n", "<br>") + "</p>")
    return "\n".join(paragraphs)


def build_subject(company: Dict[str, Any], settings: Dict[str, Any]) -> str:
    ctx = _context(company, settings)
    template = settings.get("subject_template") or DEFAULT_SUBJECT_TEMPLATE
    return render_text_template(template, ctx).strip()


def build_email_text(company: Dict[str, Any], settings: Dict[str, Any]) -> str:
    ctx = _context(company, settings)
    template = settings.get("email_body_template") or DEFAULT_EMAIL_TEMPLATE
    return render_text_template(template, ctx).strip()


def build_email_body(company: Dict[str, Any], settings: Dict[str, Any]) -> str:
    text = build_email_text(company, settings)
    footer = """
    <hr>
    <p style="font-size:12px;color:#666;">
    Esta mensagem foi enviada para um contato institucional, página de carreiras, vaga pública,
    indicação ou canal informado para oportunidades profissionais. Para responder ao candidato,
    use o botão responder do seu e-mail.
    </p>
    """
    return text_to_html(text) + footer
