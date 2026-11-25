"""IMC e meta de calorias do perfil (decisão D36). Estimativas, não prescrição.

Fontes conferidas em 2026-10-25:
  - Gasto em repouso: equação de Mifflin-St Jeor (Am J Clin Nutr 1990;51(2):241-7):
    10 x peso (kg) + 6,25 x altura (cm) - 5 x idade + 5 (homens) ou - 161 (mulheres).
  - Fatores de atividade: os usuais das calculadoras clínicas (1,2 a 1,9).
  - Perder peso: déficit de 500 kcal/dia, uma das opções da diretriz AHA/ACC/TOS 2013; nunca
    abaixo de 1.200 kcal (mulheres) ou 1.500 kcal (homens), o piso das faixas dessa diretriz.
  - Ganhar peso: +300 kcal/dia. Não achamos diretriz oficial para esse número: é uma convenção
    moderada, marcada como tal na tela.
  - IMC: classificação da Organização Mundial da Saúde para adultos.
  - Proteína: 0,8 g por kg de peso por dia, a RDA para adultos (Institute of Medicine, Dietary
    Reference Intakes for Energy and Macronutrients, 2005).
Só calcula para maiores de 18 anos. Não recomenda perder peso com IMC abaixo de 18,5.
Metas passadas por um nutricionista (D60) valem no lugar da fórmula: veja daily_targets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

IDADE_MINIMA = 18
ALTURA_CM = (100, 250)
PESO_KG = (30, 300)

SEXOS = {"feminino": "Feminino", "masculino": "Masculino"}
ATIVIDADES = {
    "sedentario": ("Sedentário (pouco ou nenhum exercício)", 1.2),
    "leve": ("Leve (exercício 1 a 3 dias por semana)", 1.375),
    "moderado": ("Moderado (exercício 3 a 5 dias por semana)", 1.55),
    "intenso": ("Intenso (exercício 6 a 7 dias por semana)", 1.725),
    "muito_intenso": ("Muito intenso (treino pesado ou trabalho físico)", 1.9),
}
AJUSTE_OBJETIVO = {"perder": -500, "manter": 0, "ganhar": 300}
PISO_KCAL = {"feminino": 1200, "masculino": 1500}
PROTEINA_G_KG = 0.8
FONTES = {"nutricionista": "definida pelo seu nutricionista", "formula": "estimada por fórmula"}

AVISO = ("Todos os cálculos de gasto energético e de consumo de proteínas são aproximados e não "
         "substituem a consulta com um nutricionista.")


@dataclass
class Estimativa:
    imc: float | None = None
    classificacao_imc: str = ""
    gasto_repouso: int | None = None
    gasto_diario: int | None = None
    meta_kcal: int | None = None
    avisos: list[str] = field(default_factory=list)


def age_from_year(ano_nascimento: int, hoje: date | None = None) -> int:
    """Idade aproximada a partir do ano (pode errar em 1 ano antes do aniversário)."""
    return (hoje or date.today()).year - ano_nascimento


def bmi(peso_kg: float, altura_cm: float) -> float:
    return round(peso_kg / (altura_cm / 100) ** 2, 1)


def bmi_class(imc: float) -> str:
    if imc < 18.5:
        return "abaixo do peso"
    if imc < 25:
        return "peso adequado"
    if imc < 30:
        return "sobrepeso"
    return "obesidade"


def resting_energy(peso_kg: float, altura_cm: float, idade: int, sexo: str) -> float:
    """Mifflin-St Jeor, em kcal/dia."""
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * idade
    return base + (5 if sexo == "masculino" else -161)


def validate_body(peso_kg: float | None, altura_cm: float | None, ano_nascimento: int | None,
                  hoje: date | None = None) -> list[str]:
    """Problemas nos dados do corpo (lista vazia = ok). Campos vazios são permitidos."""
    problemas = []
    if altura_cm is not None and not ALTURA_CM[0] <= altura_cm <= ALTURA_CM[1]:
        problemas.append(f"Altura deve estar entre {ALTURA_CM[0]} e {ALTURA_CM[1]} cm.")
    if peso_kg is not None and not PESO_KG[0] <= peso_kg <= PESO_KG[1]:
        problemas.append(f"Peso deve estar entre {PESO_KG[0]} e {PESO_KG[1]} kg.")
    if ano_nascimento is not None:
        idade = age_from_year(ano_nascimento, hoje)
        if not 0 < idade <= 120:
            problemas.append("Ano de nascimento inválido.")
    return problemas


def estimate(peso_kg: float | None, altura_cm: float | None, ano_nascimento: int | None,
             sexo: str | None, atividade: str | None, objetivo: str | None,
             hoje: date | None = None) -> Estimativa:
    """Calcula o que der com os dados preenchidos e explica o que faltou."""
    est = Estimativa()
    if peso_kg and altura_cm:
        est.imc = bmi(peso_kg, altura_cm)
        est.classificacao_imc = bmi_class(est.imc)
    faltam = [nome for nome, valor in (("peso", peso_kg), ("altura", altura_cm),
                                       ("ano de nascimento", ano_nascimento), ("sexo", sexo),
                                       ("nível de atividade", atividade)) if not valor]
    if faltam:
        est.avisos.append("Para estimar as calorias, preencha: " + ", ".join(faltam) + ".")
        return est
    idade = age_from_year(ano_nascimento, hoje)
    if idade < IDADE_MINIMA:
        est.avisos.append("O cálculo de calorias é só para maiores de 18 anos. Para menores, "
                          "a orientação deve vir de um nutricionista ou pediatra.")
        return est
    repouso = resting_energy(peso_kg, altura_cm, idade, sexo)
    diario = repouso * ATIVIDADES[atividade][1]
    est.gasto_repouso, est.gasto_diario = round(repouso), round(diario)
    if objetivo == "perder" and est.imc is not None and est.imc < 18.5:
        est.avisos.append("Com IMC abaixo de 18,5, a DelícIA não calcula meta para perder peso. "
                          "Procure um profissional de saúde.")
        return est
    meta = diario + AJUSTE_OBJETIVO.get(objetivo or "manter", 0)
    piso = PISO_KCAL[sexo]
    if meta < piso:
        meta = piso
        est.avisos.append(f"A meta foi limitada a {piso} kcal por dia, o mínimo usado sem "
                          "acompanhamento profissional.")
    est.meta_kcal = int(round(meta / 10) * 10)
    if objetivo == "ganhar":
        est.avisos.append("O acréscimo de 300 kcal para ganhar peso é uma convenção moderada, "
                          "não um valor de diretriz oficial.")
    return est


AGUA_ML_KG = 35  # referência usual para adultos: 35 ml de líquido por kg de peso por dia
AGUA_EXTRA_ML = {"sedentario": 0, "leve": 200, "moderado": 400, "intenso": 600, "muito_intenso": 800}
AGUA_REFERENCIA_ML = 2000
AGUA_LIMITES_ML = (1500, 5000)


def water_goal(peso_kg: float | None, atividade: str | None) -> tuple[int, bool]:
    """(meta de água do dia em ml, é a referência de 2 litros?). 35 ml por kg mais um extra pela atividade,
    arredondado a 50 ml. Sem peso, usa a referência. Altura e idade não entram: não mudam a conta."""
    if not peso_kg:
        return AGUA_REFERENCIA_ML, True
    ml = peso_kg * AGUA_ML_KG + AGUA_EXTRA_ML.get(atividade or "", 0)
    return int(min(max(round(ml / 50) * 50, AGUA_LIMITES_ML[0]), AGUA_LIMITES_ML[1])), False


@dataclass
class Metas:
    """Metas do dia. Fonte: "nutricionista", "formula" ou None (sem meta: quem usa decide a referência)."""
    kcal: int | None = None
    proteina_g: int | None = None
    fonte_kcal: str | None = None
    fonte_proteina: str | None = None


def daily_targets(est: Estimativa, peso_kg: float | None, kcal_nutricionista: int | None = None,
                  proteina_nutricionista: int | None = None) -> Metas:
    """O que o nutricionista passou vence sempre a fórmula, inclusive o piso e o bloqueio por IMC.
    A proteína por fórmula só sai quando a estimativa de calorias saiu (adulto com os dados completos)."""
    metas = Metas()
    if kcal_nutricionista:
        metas.kcal, metas.fonte_kcal = kcal_nutricionista, "nutricionista"
    elif est.meta_kcal:
        metas.kcal, metas.fonte_kcal = est.meta_kcal, "formula"
    if proteina_nutricionista:
        metas.proteina_g, metas.fonte_proteina = proteina_nutricionista, "nutricionista"
    elif est.gasto_diario and peso_kg:
        metas.proteina_g, metas.fonte_proteina = round(PROTEINA_G_KG * peso_kg), "formula"
    return metas
