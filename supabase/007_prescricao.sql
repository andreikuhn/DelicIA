-- Atualização 7 (2026-10-27): metas do nutricionista no perfil (decisão D60): energia (kcal por dia) e
-- proteína (g por dia). Quando preenchidas, valem no lugar da estimativa por fórmula. Rode uma vez no SQL
-- Editor de um projeto que já tem o schema.sql. Pode rodar de novo.

alter table public.perfis add column if not exists kcal_nutricionista integer
  check (kcal_nutricionista between 800 and 6000);
alter table public.perfis add column if not exists proteina_nutricionista integer
  check (proteina_nutricionista between 20 and 400);

-- faz o Supabase enxergar as colunas novas na hora
notify pgrst, 'reload schema';
