"""O que a pessoa comeu (decisão D58): a maçã de cada receita registra 1 porção; o perfil soma o dia,
os últimos 7 dias e os últimos 30 dias.

Os nutrientes da porção são estimados pelo modelo, em JSON com campos fixos (para poder somar), a
partir do texto da receita que a pessoa abriu. São estimativas da IA, como o resto do conteúdo (D56).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# chave -> (rótulo, unidade). Os 4 primeiros aparecem logo; o resto fica em "Vitaminas e minerais".
NUTRIENTES = {
    "kcal": ("Energia", "kcal"),
    "proteina_g": ("Proteína", "g"),
    "carboidrato_g": ("Carboidratos", "g"),
    "gordura_g": ("Gorduras", "g"),
    "fibra_g": ("Fibras", "g"),
    "sodio_mg": ("Sódio", "mg"),
    "calcio_mg": ("Cálcio", "mg"),
    "ferro_mg": ("Ferro", "mg"),
    "potassio_mg": ("Potássio", "mg"),
    "magnesio_mg": ("Magnésio", "mg"),
    "zinco_mg": ("Zinco", "mg"),
    "vitamina_a_mcg": ("Vitamina A", "mcg"),
    "vitamina_c_mg": ("Vitamina C", "mg"),
    "vitamina_d_mcg": ("Vitamina D", "mcg"),
    "vitamina_e_mg": ("Vitamina E", "mg"),
    "vitamina_b12_mcg": ("Vitamina B12", "mcg"),
    "folato_mcg": ("Folato", "mcg"),
}
PRINCIPAIS = ("kcal", "proteina_g", "carboidrato_g", "gordura_g")
PERIODOS = {"hoje": ("Hoje", 1), "semana": ("Últimos 7 dias", 7), "mes": ("Últimos 30 dias", 30)}
BRASILIA = timezone(timedelta(hours=-3))  # sem horário de verão desde 2019

ESQUEMA = {
    "type": "object",
    "properties": {chave: {"type": "number"} for chave in NUTRIENTES},
    "required": list(NUTRIENTES),
}


def today() -> date:
    return datetime.now(BRASILIA).date()


def period_start(periodo: str, hoje: date | None = None) -> date:
    """Primeiro dia do período: hoje, 7 ou 30 dias contando hoje."""
    return (hoje or today()) - timedelta(days=PERIODOS[periodo][1] - 1)


def estimate(chat, receita: str, texto: str) -> dict[str, float]:
    """Nutrientes de 1 porção da receita, pedidos ao modelo. ValueError se vierem sem sentido."""
    pedido = (f'Estime os nutrientes de UMA porção (a de 1 pessoa) da receita "{receita}" abaixo. '
              "Use 0 para o que a receita praticamente não tem.\n\n" + texto)
    dados = chat.generate_json(pedido, ESQUEMA, temperatura=0)
    try:
        valores = {chave: round(max(float(dados[chave]), 0.0), 1) for chave in NUTRIENTES}
    except (KeyError, TypeError, ValueError) as erro:
        raise ValueError("O modelo não devolveu os nutrientes no formato esperado.") from erro
    if not 0 < valores["kcal"] < 5000:
        raise ValueError("O modelo devolveu uma estimativa de calorias sem sentido. Tente de novo.")
    return valores


def totals(registros: list[dict]) -> dict[str, float]:
    """Soma de cada nutriente; registros antigos sem algum campo contam 0 nele."""
    return {chave: sum(float((r.get("nutrientes") or {}).get(chave) or 0) for r in registros)
            for chave in NUTRIENTES}


def format_value(valor: float) -> str:
    return (f"{valor:.0f}" if valor >= 10 else f"{valor:.1f}").replace(".", ",")


# Água bebida: registros na mesma tabela `consumo`, com receita "Água" e {"agua_ml": ml} (sem SQL novo).
AGUA = "Água"


def is_water(registro: dict) -> bool:
    return "agua_ml" in (registro.get("nutrientes") or {})


def water_ml(registros: list[dict]) -> float:
    return sum(float((r.get("nutrientes") or {}).get("agua_ml") or 0) for r in registros if is_water(r))
