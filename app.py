from __future__ import annotations

import pandas as pd
import streamlit as st

from database import (
    create_company,
    ensure_profile,
    get_auth_client,
    get_user_settings,
    import_companies,
    list_companies,
    list_logs,
    metrics,
    update_companies,
    update_user_settings,
    upload_resume,
)
from send_engine import send_batch_for_user
from settings import ALLOWED_SOURCES
from templates import build_email_body, build_subject

st.set_page_config(
    page_title="Agente de Candidatura SaaS",
    page_icon="📨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
    .metric-card {border:1px solid rgba(128,128,128,.18); border-radius:16px; padding:14px;}
    @media (max-width: 768px) {
        .main .block-container {padding-left: .8rem; padding-right: .8rem;}
        div[data-testid="stHorizontalBlock"] {gap: .4rem;}
        div[data-testid="stMetric"] {background: rgba(128,128,128,.05); border-radius: 12px; padding: 10px;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

STATUS_OPTIONS = [
    "novo",
    "aprovado",
    "enviado",
    "erro",
    "bloqueado_origem_invalida",
]
SOURCE_OPTIONS = ["", *sorted(ALLOWED_SOURCES), "outra"]


def logout() -> None:
    for key in ["user", "session"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def auth_screen() -> None:
    st.title("📨 Agente de Candidatura")
    st.caption("Sistema multiusuário para gerenciar empresas e enviar currículos pelo próprio painel.")

    tab_login, tab_signup = st.tabs(["Entrar", "Criar conta"])
    auth = get_auth_client()

    with tab_login:
        email = st.text_input("E-mail", key="login_email")
        password = st.text_input("Senha", type="password", key="login_password")
        if st.button("Entrar", use_container_width=True):
            try:
                response = auth.auth.sign_in_with_password({"email": email, "password": password})
                if not response.user:
                    st.error("Não foi possível autenticar.")
                    return
                st.session_state.user = {
                    "id": response.user.id,
                    "email": response.user.email,
                }
                st.session_state.session = response.session
                ensure_profile(response.user.id, response.user.email or email)
                st.rerun()
            except Exception as exc:
                st.error(f"Erro ao entrar: {exc}")

    with tab_signup:
        full_name = st.text_input("Nome", key="signup_name")
        email_new = st.text_input("E-mail", key="signup_email")
        password_new = st.text_input("Senha", type="password", key="signup_password")
        if st.button("Criar conta", use_container_width=True):
            try:
                response = auth.auth.sign_up({"email": email_new, "password": password_new})
                if response.user:
                    ensure_profile(response.user.id, response.user.email or email_new, full_name)
                    if response.session:
                        st.session_state.user = {"id": response.user.id, "email": response.user.email}
                        st.session_state.session = response.session
                        st.rerun()
                    else:
                        st.success("Conta criada. Confirme seu e-mail antes de entrar, se a confirmação estiver ativa no Supabase.")
                else:
                    st.warning("Conta solicitada. Verifique seu e-mail.")
            except Exception as exc:
                st.error(f"Erro ao criar conta: {exc}")


if "user" not in st.session_state:
    auth_screen()
    st.stop()

user_id = st.session_state.user["id"]
user_email = st.session_state.user["email"]
ensure_profile(user_id, user_email)
settings = get_user_settings(user_id)

with st.sidebar:
    st.subheader("Conta")
    st.write(user_email)
    st.divider()
    st.caption("Envios são sempre isolados por usuário.")
    if st.button("Sair", use_container_width=True):
        logout()

st.title("📨 Agente de Candidatura")
st.caption("Importe empresas, filtre, aprove, envie lotes e acompanhe logs sem mexer no terminal.")

page = st.sidebar.radio(
    "Navegação",
    ["Dashboard", "Empresas", "Importar CSV", "Disparos", "Prévia", "Logs", "Configurações"],
)

if page == "Dashboard":
    m = metrics(user_id)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Empresas", m["total"])
    c2.metric("Aprovadas", m["approved"])
    c3.metric("Enviadas", m["sent"])
    c4.metric("Elegíveis", m["eligible"])

    st.info(
        "Elegível = empresa aprovada, não bloqueada, sem envio anterior e com origem válida no momento do disparo."
    )

    st.subheader("Checklist de operação")
    st.write("1. Configure remetente e currículo em **Configurações**.")
    st.write("2. Importe empresas em **Importar CSV**.")
    st.write("3. Use **Empresas** para filtrar e aprovar contatos.")
    st.write("4. Use **Disparos** para enviar um lote agora ou ativar o agendamento diário.")

elif page == "Importar CSV":
    st.subheader("Importar empresas")
    st.write("Use o modelo `companies_sample.csv`. As colunas mínimas são `company_name` e `email`.")
    uploaded = st.file_uploader("Arquivo CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df.head(50), use_container_width=True, hide_index=True)
        if st.button("Importar para minha conta", type="primary", use_container_width=True):
            try:
                inserted, skipped = import_companies(user_id, df)
                st.success(f"Importação finalizada. Inseridas: {inserted}. Ignoradas/duplicadas: {skipped}.")
            except Exception as exc:
                st.error(str(exc))

elif page == "Empresas":
    st.subheader("Filtragem e aprovação")

    with st.expander("Filtros", expanded=True):
        f1, f2, f3 = st.columns(3)
        status_filter = f1.selectbox("Status", ["Todos", *STATUS_OPTIONS])
        source_filter = f2.selectbox("Fonte", ["Todas", *SOURCE_OPTIONS])
        approved_filter = f3.selectbox("Aprovação", ["Todos", "Aprovadas", "Não aprovadas"])

        f4, f5, f6 = st.columns(3)
        blocked_filter = f4.selectbox("Bloqueio", ["Todos", "Bloqueadas", "Não bloqueadas"])
        sector_filter = f5.text_input("Setor contém")
        city_filter = f6.text_input("Cidade contém")

        f7, f8, f9 = st.columns(3)
        state_filter = f7.text_input("Estado contém")
        text_filter = f8.text_input("Busca geral")
        only_eligible = f9.checkbox("Somente elegíveis")

    rows = list_companies(
        user_id,
        filters={
            "status": status_filter,
            "source": source_filter,
            "approved": approved_filter,
            "blocked": blocked_filter,
            "sector": sector_filter,
            "city": city_filter,
            "state": state_filter,
            "text": text_filter,
            "only_eligible": only_eligible,
        },
        limit=1000,
    )

    st.caption("A tabela mostra até 1000 registros por filtro. Refine os filtros para bases grandes.")
    df = pd.DataFrame(rows)

    if df.empty:
        st.warning("Nenhuma empresa encontrada.")
    else:
        visible_cols = [
            "id", "company_name", "email", "website", "city", "state", "country", "sector",
            "desired_role", "source", "priority", "tags", "status", "approved", "blocked", "last_sent_at", "notes"
        ]
        df = df[[c for c in visible_cols if c in df.columns]]
        edited = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "id": st.column_config.TextColumn("ID", disabled=True),
                "website": st.column_config.LinkColumn("Site"),
                "priority": st.column_config.NumberColumn("Prioridade", min_value=1, max_value=5),
                "approved": st.column_config.CheckboxColumn("Aprovada"),
                "blocked": st.column_config.CheckboxColumn("Bloqueada"),
                "status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
                "source": st.column_config.SelectboxColumn("Fonte", options=SOURCE_OPTIONS),
                "last_sent_at": st.column_config.TextColumn("Último envio", disabled=True),
            },
        )

        b1, b2, b3 = st.columns(3)
        if b1.button("Salvar alterações", type="primary", use_container_width=True):
            update_companies(user_id, edited.to_dict(orient="records"))
            st.success("Alterações salvas.")
            st.rerun()
        if b2.button("Aprovar empresas filtradas", use_container_width=True):
            edited["approved"] = True
            edited["status"] = edited["status"].replace("novo", "aprovado")
            update_companies(user_id, edited.to_dict(orient="records"))
            st.success("Empresas filtradas aprovadas.")
            st.rerun()
        if b3.button("Bloquear empresas filtradas", use_container_width=True):
            edited["blocked"] = True
            update_companies(user_id, edited.to_dict(orient="records"))
            st.success("Empresas filtradas bloqueadas.")
            st.rerun()

    st.divider()
    with st.expander("Adicionar empresa manualmente"):
        with st.form("new_company"):
            c1, c2 = st.columns(2)
            company_name = c1.text_input("Empresa")
            email = c2.text_input("E-mail")
            c3, c4, c5 = st.columns(3)
            website = c3.text_input("Site")
            city = c4.text_input("Cidade")
            state = c5.text_input("Estado")
            c6, c7, c8 = st.columns(3)
            sector = c6.text_input("Setor")
            desired_role = c7.text_input("Cargo desejado")
            source = c8.selectbox("Fonte", SOURCE_OPTIONS)
            notes = st.text_area("Observações")
            approved = st.checkbox("Já aprovar para envio")
            submitted = st.form_submit_button("Adicionar")
            if submitted:
                try:
                    create_company(user_id, {
                        "company_name": company_name,
                        "email": email,
                        "website": website,
                        "city": city,
                        "state": state,
                        "sector": sector,
                        "desired_role": desired_role,
                        "source": source,
                        "priority": 3,
                        "status": "aprovado" if approved else "novo",
                        "approved": approved,
                        "notes": notes,
                    })
                    st.success("Empresa adicionada.")
                except Exception as exc:
                    st.error(str(exc))

elif page == "Disparos":
    st.subheader("Disparar pelo próprio sistema")

    m = metrics(user_id)
    st.metric("Empresas elegíveis para envio", m["eligible"])

    current_limit = int(settings.get("daily_limit") or 30)
    limit_now = st.number_input("Quantidade máxima neste disparo", min_value=1, max_value=10000, value=current_limit)

    if settings.get("dry_run"):
        st.warning("Modo teste está ativo. O sistema vai registrar logs, mas não enviará e-mails reais.")
    else:
        st.error("Modo teste desativado: os e-mails serão enviados de verdade pelo provedor configurado.")

    confirm = st.checkbox("Confirmo que as empresas aprovadas têm fonte válida e que desejo iniciar o lote.")
    if st.button("Enviar lote agora", type="primary", disabled=not confirm, use_container_width=True):
        try:
            result = send_batch_for_user(user_id, int(limit_now))
            st.success(f"Lote concluído. Enviados: {result['sent']}. Ignorados: {result['skipped']}. Erros: {result['errors']}.")
        except Exception as exc:
            st.error(str(exc))

    st.divider()
    st.subheader("Agendamento diário")
    st.write("O usuário ativa o agendamento aqui. O servidor precisa estar com o processo `worker` rodando no deploy.")
    schedule_enabled = st.toggle("Ativar envio diário", value=bool(settings.get("schedule_enabled")))
    schedule_hour = st.slider("Hora local do envio", min_value=0, max_value=23, value=int(settings.get("schedule_hour") or 9))
    timezone = st.text_input("Timezone", value=settings.get("timezone") or "America/Bahia")

    if st.button("Salvar agendamento", use_container_width=True):
        update_user_settings(user_id, {
            "schedule_enabled": schedule_enabled,
            "schedule_hour": int(schedule_hour),
            "timezone": timezone,
        })
        st.success("Agendamento salvo.")
        st.rerun()

elif page == "Prévia":
    st.subheader("Prévia do e-mail")
    rows = list_companies(user_id, filters={}, limit=500)
    if not rows:
        st.warning("Cadastre ou importe empresas primeiro.")
    else:
        options = {f"{r['company_name']} <{r['email']}>": r for r in rows}
        selected_label = st.selectbox("Empresa", list(options.keys()))
        company = options[selected_label]
        subject = build_subject(company, settings)
        body = build_email_body(company, settings)
        st.text_input("Assunto", value=subject)
        st.markdown(body, unsafe_allow_html=True)

elif page == "Logs":
    st.subheader("Histórico de envios")
    logs = list_logs(user_id, limit=1000)
    if logs:
        st.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum envio registrado ainda.")

elif page == "Configurações":
    st.subheader("Configurações individuais")

    with st.form("settings_form"):
        c1, c2 = st.columns(2)
        sender_name = c1.text_input("Nome do remetente", value=settings.get("sender_name") or "")
        sender_email = c2.text_input("E-mail remetente verificado", value=settings.get("sender_email") or "")
        c3, c4 = st.columns(2)
        reply_to_email = c3.text_input("Responder para", value=settings.get("reply_to_email") or sender_email)
        target_role = c4.text_input("Cargo-alvo padrão", value=settings.get("target_role") or "")
        daily_limit = st.number_input("Limite diário", min_value=1, max_value=10000, value=int(settings.get("daily_limit") or 30))
        dry_run = st.checkbox("Modo teste: registrar sem enviar e-mail real", value=bool(settings.get("dry_run", True)))
        email_signature = st.text_area("Assinatura", value=settings.get("email_signature") or sender_name)
        save = st.form_submit_button("Salvar configurações", type="primary")
        if save:
            update_user_settings(user_id, {
                "sender_name": sender_name,
                "sender_email": sender_email,
                "reply_to_email": reply_to_email,
                "target_role": target_role,
                "daily_limit": int(daily_limit),
                "dry_run": dry_run,
                "email_signature": email_signature,
            })
            st.success("Configurações salvas.")
            st.rerun()

    st.divider()
    st.subheader("Currículo")
    if settings.get("resume_filename"):
        st.success(f"Currículo atual: {settings['resume_filename']}")
    resume = st.file_uploader("Enviar currículo em PDF", type=["pdf"])
    if resume and st.button("Salvar currículo", use_container_width=True):
        content = resume.read()
        try:
            upload_resume(user_id, resume.name, content)
            st.success("Currículo salvo no Supabase Storage.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
