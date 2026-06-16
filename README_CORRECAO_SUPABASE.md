# Correcao do erro: column "user_id" does not exist

Esse erro acontece quando o projeto Supabase ja possui tabelas da versao anterior single-user, principalmente `public.companies` e `public.send_log`, criadas sem a coluna `user_id`.

Na versao SaaS/multiusuario, todas as tabelas precisam ter `user_id` para separar os dados de cada conta.

## Opcao recomendada se voce ainda nao tem dados importantes

Execute no SQL Editor do Supabase:

```sql
-- Abra e rode o arquivo inteiro:
schema_supabase_clean_install.sql
```

Esse script apaga as tabelas antigas do app e recria tudo corretamente para multiusuario.
Ele nao apaga usuarios em `auth.users`.

## Opcao se voce quer preservar dados antigos

1. Crie um usuario em `Authentication > Users`.
2. Copie o UUID desse usuario.
3. Abra `migration_single_user_to_saas.sql`.
4. Substitua:

```sql
owner_user_id uuid := '00000000-0000-0000-0000-000000000000';
```

pelo UUID real do usuario.

5. Execute o arquivo no SQL Editor.

Essa migracao atribui as empresas/logs antigos para esse usuario.

## Depois da correcao

Rode o app novamente:

```bash
streamlit run app.py
```

Se estiver em deploy, reinicie o servico web e o worker.
