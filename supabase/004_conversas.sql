-- Atualização 4 (2026-10-27): histórico de conversas do chat, salvo na conta (decisão D57).
-- Rode uma vez no SQL Editor de um projeto que já tem o schema.sql. Pode rodar de novo sem problema.
-- Cada conversa é uma linha; as mensagens ficam em JSON. Some junto com a conta (on delete cascade).

create table if not exists public.conversas (
  id uuid primary key,
  usuario_id uuid not null references auth.users (id) on delete cascade,
  titulo text not null default '',
  mensagens jsonb not null default '[]',
  atualizado_em timestamptz not null default now()
);
create index if not exists conversas_usuario on public.conversas (usuario_id, atualizado_em desc);

alter table public.conversas enable row level security;

grant select, insert, update, delete on public.conversas to authenticated;
-- quem não entrou (anon) não precisa nem enxergar a tabela
revoke all on public.conversas from anon;

drop policy if exists "ler as próprias conversas" on public.conversas;
create policy "ler as próprias conversas" on public.conversas
  for select to authenticated using ((select auth.uid()) = usuario_id);

drop policy if exists "criar as próprias conversas" on public.conversas;
create policy "criar as próprias conversas" on public.conversas
  for insert to authenticated with check ((select auth.uid()) = usuario_id);

drop policy if exists "alterar as próprias conversas" on public.conversas;
create policy "alterar as próprias conversas" on public.conversas
  for update to authenticated using ((select auth.uid()) = usuario_id) with check ((select auth.uid()) = usuario_id);

drop policy if exists "apagar as próprias conversas" on public.conversas;
create policy "apagar as próprias conversas" on public.conversas
  for delete to authenticated using ((select auth.uid()) = usuario_id);

-- faz o Supabase enxergar a tabela nova na hora
notify pgrst, 'reload schema';
