-- Atualização 2 (2026-10-25): dados do corpo no perfil, para IMC e meta de calorias.
-- Rode uma vez no SQL Editor de um projeto que já tem o schema.sql. Pode rodar de novo sem problema.

alter table public.perfis add column if not exists ano_nascimento integer
  check (ano_nascimento between 1900 and 2100);
alter table public.perfis add column if not exists sexo text
  check (sexo in ('feminino', 'masculino'));
alter table public.perfis add column if not exists altura_cm numeric(5, 1)
  check (altura_cm between 100 and 250);
alter table public.perfis add column if not exists peso_kg numeric(5, 1)
  check (peso_kg between 30 and 300);
alter table public.perfis add column if not exists atividade text
  check (atividade in ('sedentario', 'leve', 'moderado', 'intenso', 'muito_intenso'));

-- quem não entrou (anon) não precisa nem enxergar a tabela
revoke all on public.perfis from anon;
