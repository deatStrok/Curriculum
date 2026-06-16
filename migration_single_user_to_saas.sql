-- Agente de Candidatura SaaS - MIGRACAO NAO DESTRUTIVA DO MVP SINGLE-USER
-- Use este arquivo SOMENTE se voce ja importou empresas/logs no schema antigo e quer preservar dados.
-- Antes de rodar:
-- 1) Crie pelo menos um usuario em Authentication > Users.
-- 2) Copie o UUID desse usuario.
-- 3) Substitua abaixo o valor de owner_user_id pelo UUID real.
--
-- Observacao: esta migracao preserva IDs bigint antigos de companies/send_log.
-- O app funciona porque trata o ID como valor retornado pelo Supabase.

create extension if not exists pgcrypto;

do $$
declare
  owner_user_id uuid := '00000000-0000-0000-0000-000000000000'; -- TROQUE PELO UUID DO USUARIO DONO DOS DADOS ANTIGOS
begin
  if owner_user_id = '00000000-0000-0000-0000-000000000000'::uuid then
    raise exception 'Substitua owner_user_id pelo UUID real de um usuario em auth.users antes de executar.';
  end if;

  if not exists (select 1 from auth.users where id = owner_user_id) then
    raise exception 'O owner_user_id informado nao existe em auth.users.';
  end if;

  -- profiles
  create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text not null,
    full_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  insert into public.profiles (id, email)
  select id, email from auth.users where id = owner_user_id
  on conflict (id) do nothing;

  -- user_settings novo
  create table if not exists public.user_settings (
    user_id uuid primary key references auth.users(id) on delete cascade,
    sender_name text not null default '',
    sender_email text not null default '',
    reply_to_email text not null default '',
    target_role text not null default 'Desenvolvedor Python',
    resume_storage_path text,
    resume_filename text,
    daily_limit integer not null default 30 check (daily_limit >= 1 and daily_limit <= 10000),
    dry_run boolean not null default true,
    schedule_enabled boolean not null default false,
    schedule_hour integer not null default 9 check (schedule_hour >= 0 and schedule_hour <= 23),
    timezone text not null default 'America/Bahia',
    provider text not null default 'sendgrid',
    email_signature text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
  );

  insert into public.user_settings (user_id, sender_name, sender_email, target_role, daily_limit, dry_run)
  values (
    owner_user_id,
    coalesce((select value from public.settings where key = 'sender_name'), ''),
    coalesce((select value from public.settings where key = 'sender_email'), ''),
    coalesce((select value from public.settings where key = 'target_role'), 'Desenvolvedor Python'),
    coalesce((select value::int from public.settings where key = 'daily_limit'), 30),
    coalesce((select value::boolean from public.settings where key = 'dry_run'), true)
  )
  on conflict (user_id) do nothing;

  -- companies: adiciona colunas multiusuario sem destruir dados.
  alter table public.companies add column if not exists user_id uuid references auth.users(id) on delete cascade;
  alter table public.companies add column if not exists tags text;
  update public.companies set user_id = owner_user_id where user_id is null;
  alter table public.companies alter column user_id set not null;

  -- Remove unique global antigo de email, se existir, e cria unique por usuario.
  alter table public.companies drop constraint if exists companies_email_key;
  alter table public.companies drop constraint if exists companies_user_email_unique;
  alter table public.companies add constraint companies_user_email_unique unique (user_id, email);

  -- send_log: adiciona user_id preservando logs antigos.
  alter table public.send_log add column if not exists user_id uuid references auth.users(id) on delete cascade;
  update public.send_log set user_id = owner_user_id where user_id is null;
  alter table public.send_log alter column user_id set not null;
end $$;

create index if not exists idx_companies_user_id on public.companies(user_id);
create index if not exists idx_companies_user_status on public.companies(user_id, status);
create index if not exists idx_companies_user_approved on public.companies(user_id, approved, blocked, last_sent_at);
create index if not exists idx_companies_user_filters on public.companies(user_id, sector, city, state, source);
create index if not exists idx_send_log_user_id on public.send_log(user_id);
create index if not exists idx_send_log_company_id on public.send_log(company_id);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes', 'resumes', false, 10485760, array['application/pdf'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

alter table public.profiles enable row level security;
alter table public.user_settings enable row level security;
alter table public.companies enable row level security;
alter table public.send_log enable row level security;

-- Recria policies publicas.
drop policy if exists profiles_own_select on public.profiles;
drop policy if exists profiles_own_insert on public.profiles;
drop policy if exists profiles_own_update on public.profiles;
drop policy if exists settings_own_all on public.user_settings;
drop policy if exists companies_own_all on public.companies;
drop policy if exists send_log_own_all on public.send_log;

create policy profiles_own_select on public.profiles for select to authenticated using ((select auth.uid()) = id);
create policy profiles_own_insert on public.profiles for insert to authenticated with check ((select auth.uid()) = id);
create policy profiles_own_update on public.profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy settings_own_all on public.user_settings for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy companies_own_all on public.companies for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy send_log_own_all on public.send_log for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

-- Recria policies de Storage.
drop policy if exists resumes_own_select on storage.objects;
drop policy if exists resumes_own_insert on storage.objects;
drop policy if exists resumes_own_update on storage.objects;
drop policy if exists resumes_own_delete on storage.objects;

create policy resumes_own_select on storage.objects for select to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy resumes_own_insert on storage.objects for insert to authenticated
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy resumes_own_update on storage.objects for update to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text)
with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);

create policy resumes_own_delete on storage.objects for delete to authenticated
using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
