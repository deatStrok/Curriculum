-- Agente de Candidatura SaaS - Supabase/Postgres
-- Execute este arquivo no SQL Editor do Supabase.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

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
  subject_template text not null default 'Candidatura para {role}',
  email_body_template text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.companies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  company_name text not null,
  email text not null,
  website text,
  city text,
  state text,
  country text default 'Brasil',
  sector text,
  desired_role text,
  source text,
  priority integer not null default 3 check (priority >= 1 and priority <= 5),
  tags text,
  status text not null default 'novo',
  approved boolean not null default false,
  blocked boolean not null default false,
  last_sent_at timestamptz,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint companies_user_email_unique unique (user_id, email)
);

create index if not exists idx_companies_user_id on public.companies(user_id);
create index if not exists idx_companies_user_status on public.companies(user_id, status);
create index if not exists idx_companies_user_approved on public.companies(user_id, approved, blocked, last_sent_at);
create index if not exists idx_companies_user_filters on public.companies(user_id, sector, city, state, source);

create table if not exists public.send_log (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  company_id uuid references public.companies(id) on delete set null,
  email text not null,
  subject text not null,
  body text not null,
  provider text,
  provider_status text,
  error_message text,
  sent_at timestamptz not null default now()
);

create index if not exists idx_send_log_user_id on public.send_log(user_id);
create index if not exists idx_send_log_company_id on public.send_log(company_id);

-- Bucket privado para currículos em PDF.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes', 'resumes', false, 10485760, array['application/pdf'])
on conflict (id) do nothing;

-- RLS: defesa em profundidade para uso com clientes anon/authenticated.
alter table public.profiles enable row level security;
alter table public.user_settings enable row level security;
alter table public.companies enable row level security;
alter table public.send_log enable row level security;

-- Evita erro se as policies já existirem.
do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'profiles' and policyname = 'profiles_own_select') then
    create policy profiles_own_select on public.profiles for select to authenticated using ((select auth.uid()) = id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'profiles' and policyname = 'profiles_own_insert') then
    create policy profiles_own_insert on public.profiles for insert to authenticated with check ((select auth.uid()) = id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'profiles' and policyname = 'profiles_own_update') then
    create policy profiles_own_update on public.profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
  end if;

  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'user_settings' and policyname = 'settings_own_all') then
    create policy settings_own_all on public.user_settings for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
  end if;

  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'companies' and policyname = 'companies_own_all') then
    create policy companies_own_all on public.companies for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
  end if;

  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'send_log' and policyname = 'send_log_own_all') then
    create policy send_log_own_all on public.send_log for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
  end if;
end $$;

-- Policies do Storage para clientes autenticados. O app também usa service role no servidor para upload/download.
do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'resumes_own_select') then
    create policy resumes_own_select on storage.objects for select to authenticated
    using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'resumes_own_insert') then
    create policy resumes_own_insert on storage.objects for insert to authenticated
    with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'resumes_own_update') then
    create policy resumes_own_update on storage.objects for update to authenticated
    using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text)
    with check (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'resumes_own_delete') then
    create policy resumes_own_delete on storage.objects for delete to authenticated
    using (bucket_id = 'resumes' and (storage.foldername(name))[1] = (select auth.uid())::text);
  end if;
end $$;
