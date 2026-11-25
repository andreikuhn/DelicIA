-- Banco do site DelícIA (Supabase). Rode uma vez no SQL Editor do projeto.
-- Cria a tabela de perfis, protege cada linha para só o dono ler e alterar (RLS),
-- e a função que apaga a conta inteira a pedido do usuário (LGPD).

create table if not exists public.perfis (
  id uuid primary key references auth.users (id) on delete cascade,
  nome text,
  objetivo text check (objetivo in ('perder', 'manter', 'ganhar')),
  -- os valores aceitos são as chaves de OPCOES_PERFIL em src/nutrimesa/restrictions.py
  restricoes text[] not null default '{}' check (restricoes <@ array[
    'intolerancia_lactose', 'doenca_celiaca', 'alergia_leite', 'alergia_ovo', 'alergia_trigo',
    'alergia_soja', 'alergia_peixe', 'alergia_crustaceos', 'alergia_amendoim',
    'alergia_castanhas', 'vegetariano', 'vegano'
  ]::text[]),
  consentimento_em timestamptz not null,
  atualizado_em timestamptz not null default now()
);
-- Colunas do corpo (IMC e meta de calorias): ficam em 002_perfil_corpo.sql, que também serve
-- para projetos criados antes delas. Num projeto novo, rode este arquivo e depois o 002.

alter table public.perfis enable row level security;

grant select, insert, update, delete on public.perfis to authenticated;
-- quem não entrou (anon) não precisa nem enxergar a tabela
revoke all on public.perfis from anon;

drop policy if exists "ler o próprio perfil" on public.perfis;
create policy "ler o próprio perfil" on public.perfis
  for select to authenticated using ((select auth.uid()) = id);

drop policy if exists "criar o próprio perfil" on public.perfis;
create policy "criar o próprio perfil" on public.perfis
  for insert to authenticated with check ((select auth.uid()) = id);

drop policy if exists "alterar o próprio perfil" on public.perfis;
create policy "alterar o próprio perfil" on public.perfis
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

drop policy if exists "apagar o próprio perfil" on public.perfis;
create policy "apagar o próprio perfil" on public.perfis
  for delete to authenticated using ((select auth.uid()) = id);

-- Apaga o usuário logado. O perfil some junto (on delete cascade).
-- "security definer" porque usuários comuns não podem mexer em auth.users diretamente.
create or replace function public.apagar_minha_conta()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'não autenticado';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.apagar_minha_conta() from public, anon;
grant execute on function public.apagar_minha_conta() to authenticated;
