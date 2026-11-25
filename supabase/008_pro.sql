-- Atualização 8 (2026-10-27): Modo Pro (decisão D71). Por enquanto é grátis: a pessoa liga em Configurações.
-- No futuro será pago. Rode uma vez no SQL Editor de um projeto que já tem o schema.sql. Pode rodar de novo.

alter table public.perfis add column if not exists pro boolean not null default false;

-- faz o Supabase enxergar a coluna nova na hora
notify pgrst, 'reload schema';
