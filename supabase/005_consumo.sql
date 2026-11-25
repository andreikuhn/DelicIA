-- Atualização 5 (2026-10-27): o que a pessoa comeu (a maçã da receita, decisão D58).
-- Rode uma vez no SQL Editor de um projeto que já tem o schema.sql. Pode rodar de novo sem problema.
-- Cada clique na maçã é uma linha, com a data (horário de Brasília) e os nutrientes de 1 porção em JSON.
-- Some junto com a conta (on delete cascade).

create table if not exists public.consumo (
  id uuid primary key,
  usuario_id uuid not null references auth.users (id) on delete cascade,
  dia date not null,
  receita text not null default '',
  nutrientes jsonb not null default '{}',
  criado_em timestamptz not null default now()
);
create index if not exists consumo_usuario_dia on public.consumo (usuario_id, dia);

alter table public.consumo enable row level security;

grant select, insert, delete on public.consumo to authenticated;
-- quem não entrou (anon) não precisa nem enxergar a tabela
revoke all on public.consumo from anon;

drop policy if exists "ler o próprio consumo" on public.consumo;
create policy "ler o próprio consumo" on public.consumo
  for select to authenticated using ((select auth.uid()) = usuario_id);

drop policy if exists "registrar o próprio consumo" on public.consumo;
create policy "registrar o próprio consumo" on public.consumo
  for insert to authenticated with check ((select auth.uid()) = usuario_id);

drop policy if exists "apagar o próprio consumo" on public.consumo;
create policy "apagar o próprio consumo" on public.consumo
  for delete to authenticated using ((select auth.uid()) = usuario_id);

-- faz o Supabase enxergar a tabela nova na hora
notify pgrst, 'reload schema';
