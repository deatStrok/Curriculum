-- Adiciona modelos editáveis de assunto e corpo do e-mail por usuário.
-- Rode este arquivo no SQL Editor do Supabase se você já tem o banco criado.

alter table public.user_settings
  add column if not exists subject_template text not null default 'Candidatura para {role}',
  add column if not exists email_body_template text;

update public.user_settings
set subject_template = coalesce(nullif(subject_template, ''), 'Candidatura para {role}');
