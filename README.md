# Agente de Candidatura SaaS - Multiusuario

## Correcao importante para Supabase

Se aparecer o erro `column "user_id" does not exist`, voce provavelmente ja tinha tabelas antigas da versao single-user no projeto Supabase.

- Para ambiente novo/teste, rode `schema_supabase_clean_install.sql`.
- Para preservar dados antigos, rode `migration_single_user_to_saas.sql` depois de substituir o UUID do usuario dono dos dados.

Veja tambem `README_CORRECAO_SUPABASE.md`.

# Agente de Candidatura SaaS com Streamlit + Supabase

Sistema multiusuário para envio controlado de currículos:

- Cadastro e login de usuários via Supabase Auth.
- Cada usuário possui suas próprias empresas, currículo, configurações, logs e agendamento.
- Importação de CSV com até milhares de empresas.
- Filtros por status, fonte, setor, cidade, estado, texto, bloqueio e elegibilidade.
- Aprovação visual antes do envio.
- Botão **Enviar lote agora** pelo próprio sistema.
- Agendamento diário por usuário, executado por um processo `worker` no servidor.
- Envio via SendGrid com currículo em anexo.
- Supabase Storage para guardar currículos em PDF.
- RLS configurada no banco para isolamento por `user_id`.

> Importante: o usuário final não precisa mexer no terminal. O terminal é usado apenas por quem implanta o sistema. Depois do deploy, o usuário usa tudo pela interface.

---

## 1. Criar projeto no Supabase

1. Crie um projeto no Supabase.
2. Vá em **SQL Editor**.
3. Execute o arquivo `schema_supabase.sql`.
4. Confira se foram criadas as tabelas:
   - `profiles`
   - `user_settings`
   - `companies`
   - `send_log`
5. Confira se o bucket `resumes` foi criado no Storage.

---

## 2. Configurar autenticação

No Supabase:

1. Vá em **Authentication > Providers**.
2. Ative **Email**.
3. Decida se quer confirmação de e-mail.
   - Se a confirmação estiver ativada, o usuário precisa confirmar o e-mail antes de entrar.
   - Se estiver desativada, ele já entra após criar conta.

---

## 3. Configurar variáveis de ambiente

Copie `.env.example` para `.env` no ambiente local:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_anon_key_aqui
SUPABASE_SERVICE_ROLE_KEY=sua_service_role_key_aqui
SENDGRID_API_KEY=sua_sendgrid_api_key_aqui
APP_TIMEZONE=America/Bahia
```

Em deploy, configure essas mesmas variáveis no painel da plataforma.

Nunca exponha `SUPABASE_SERVICE_ROLE_KEY` no navegador, GitHub ou frontend público. Neste projeto ela fica apenas no servidor Streamlit/worker.

---

## 4. Rodar localmente como administrador/desenvolvedor

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

No Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

---

## 5. Como o usuário final usa

1. Acessa a URL do sistema.
2. Cria conta ou faz login.
3. Vai em **Configurações**.
4. Configura:
   - nome do remetente;
   - e-mail remetente verificado;
   - e-mail de resposta;
   - cargo-alvo;
   - limite diário;
   - currículo em PDF;
   - modo teste ligado/desligado.
5. Vai em **Importar CSV**.
6. Importa empresas com o modelo `companies_sample.csv`.
7. Vai em **Empresas**.
8. Filtra e aprova empresas.
9. Vai em **Disparos**.
10. Clica em **Enviar lote agora** ou ativa o agendamento diário.

---

## 6. Envio diário sem terminal para o usuário

O usuário ativa o agendamento pelo painel. Para que ele funcione automaticamente, o deploy precisa rodar dois processos:

- `web`: roda o Streamlit.
- `worker`: roda o agendador diário.

O arquivo `Procfile` já vem com:

```Procfile
web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
worker: python worker.py
```

O arquivo `render.yaml` também inclui um serviço web e um worker.

---

## 7. Fontes válidas para envio

O sistema só envia para empresas aprovadas e com uma destas fontes:

- `vaga_publica`
- `pagina_carreiras`
- `email_institucional`
- `indicacao`
- `opt_in`

Qualquer outra fonte é bloqueada pelo motor de envio.

---

## 8. Campos do CSV

Colunas mínimas:

```csv
company_name,email
```

Colunas recomendadas:

```csv
company_name,email,website,city,state,country,sector,desired_role,source,priority,tags,notes
```

Veja `companies_sample.csv`.

---

## 9. Produção

Recomendações:

1. Use domínio próprio autenticado no SendGrid.
2. Configure SPF, DKIM e DMARC.
3. Comece com limite diário baixo por usuário.
4. Mantenha `dry_run` ativo durante testes.
5. Monitore erros no SendGrid e na tabela `send_log`.
6. Use HTTPS no deploy.
7. Não permita envio sem aprovação visual.
8. Mantenha RLS ativada no Supabase.
9. Não exponha a service role key ao cliente.

---

## 10. Observação de conformidade

Currículos contêm dados pessoais. O sistema foi desenhado com isolamento por usuário, logs e controle de fonte, mas você ainda deve ajustar política de privacidade, termos de uso, retenção de dados e base legal antes de comercializar como SaaS.
