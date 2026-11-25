-- Atualização 6 (2026-10-27): preferências no perfil (decisão D59): o que a pessoa não gosta de comer
-- e o orçamento. Rode uma vez no SQL Editor de um projeto que já tem o schema.sql. Pode rodar de novo.

alter table public.perfis add column if not exists nao_gosta text not null default ''
  check (char_length(nao_gosta) <= 200);
alter table public.perfis add column if not exists orcamento text
  check (orcamento in ('economico', 'normal'));

-- faz o Supabase enxergar as colunas novas na hora
notify pgrst, 'reload schema';
