-- Atualização 3 (2026-10-26): cardápio da semana salvo na conta (decisão D48).
-- Rode uma vez no SQL Editor de um projeto que já tem o schema.sql. Pode rodar de novo sem problema.
-- Um cardápio por pessoa: o mais recente substitui o anterior. Some junto com a conta (on delete cascade).

create table if not exists public.cardapios (
  id uuid primary key references auth.users (id) on delete cascade,
  -- receitas e porções de cada refeição; nomes e totais são recalculados pelo site ao carregar
  dados jsonb not null,
  atualizado_em timestamptz not null default now()
);

alter table public.cardapios enable row level security;

grant select, insert, update, delete on public.cardapios to authenticated;
-- quem não entrou (anon) não precisa nem enxergar a tabela
revoke all on public.cardapios from anon;

drop policy if exists "ler o próprio cardápio" on public.cardapios;
create policy "ler o próprio cardápio" on public.cardapios
  for select to authenticated using ((select auth.uid()) = id);

drop policy if exists "criar o próprio cardápio" on public.cardapios;
create policy "criar o próprio cardápio" on public.cardapios
  for insert to authenticated with check ((select auth.uid()) = id);

drop policy if exists "alterar o próprio cardápio" on public.cardapios;
create policy "alterar o próprio cardápio" on public.cardapios
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

drop policy if exists "apagar o próprio cardápio" on public.cardapios;
create policy "apagar o próprio cardápio" on public.cardapios
  for delete to authenticated using ((select auth.uid()) = id);

-- faz o Supabase enxergar a tabela nova na hora
notify pgrst, 'reload schema';
