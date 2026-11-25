"""Cardápio da semana gerado pelo Gemini (decisões D37, D51 e D56).

A pessoa escolhe as refeições (tirar, renomear, adicionar; leve ou completa). O modelo monta os 7
dias de uma vez, em JSON com formato fixo (ESQUEMA_SEMANA), respeitando as restrições do perfil e a
metas de calorias e de proteína (D61), divididas entre as refeições pelos pesos de cada uma. O código valida o formato,
soma os totais de cada dia e confere os ingredientes de cada prato contra as restrições.

O plano é um dict pronto para salvar (JSON):
  {"versao": 3, "meta_kcal": 2000, "meta_e_referencia": bool, "meta_proteina_g": 90 ou None,
   "fonte_meta": "nutricionista" | "formula" | None (referência), "refeicoes": {chave: [rótulo, peso, tipo]},
   "dias": [{"dia": "Segunda", "refeicoes": [{"chave", "prato", "porcao", "ingredientes": [...],
             "kcal", "proteina_g", "carboidrato_g", "gordura_g", "receita"?}]}]}
Os números são estimativas do modelo, avisadas como tal na tela.
"""
from __future__ import annotations



DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
TIPOS = {"leve": "leve (café, lanche ou ceia: um prato simples)",
         "completa": "completa (prato principal com acompanhamento)"}
PESO_NOVA = {"leve": 0.15, "completa": 0.30}  # parte da meta de uma refeição que a pessoa adiciona
REFEICOES = {  # padrão. chave -> (rótulo, parte das calorias do dia, tipo)
    "cafe": ("Café da manhã", 0.20, "leve"),
    "almoco": ("Almoço", 0.35, "completa"),
    "lanche": ("Lanche da tarde", 0.15, "leve"),
    "jantar": ("Jantar", 0.30, "completa"),
}
REFERENCIA_KCAL = 2000  # valor diário de referência da Anvisa (IN 75/2020), sem meta no perfil
REFERENCIA_PROTEINA_G = 50  # idem, para a proteína
TOLERANCIA_KCAL = 0.10  # o dia "bate a meta" com kcal a até 10% da meta e proteína em pelo menos 90%
MINIMO_PROTEINA = 0.90
NUMEROS = ("kcal", "proteina_g", "carboidrato_g", "gordura_g")

_PRATO = {
    "type": "object",
    "properties": {
        "chave": {"type": "string"},
        "prato": {"type": "string", "description": "nome do prato"},
        "porcao": {"type": "string", "description": "quanto comer, ex.: 1 prato raso, 2 fatias"},
        "ingredientes": {"type": "array", "items": {"type": "string"}},
        "kcal": {"type": "number"}, "proteina_g": {"type": "number"},
        "carboidrato_g": {"type": "number"}, "gordura_g": {"type": "number"},
    },
    "required": ["chave", "prato", "porcao", "ingredientes", *NUMEROS],
}
ESQUEMA_SEMANA = {
    "type": "object",
    "properties": {"dias": {"type": "array", "items": {
        "type": "object",
        "properties": {"dia": {"type": "string"}, "refeicoes": {"type": "array", "items": _PRATO}},
        "required": ["dia", "refeicoes"]}}},
    "required": ["dias"],
}


def config_to_json(refeicoes: dict) -> list:
    """Lista [[chave, rótulo, peso, tipo], ...]: o Supabase guarda em jsonb, que reordena as chaves de um
    objeto (o Jantar ia para antes do Lanche); numa lista a ordem das refeições fica."""
    return [[k, *v] for k, v in refeicoes.items()]


def config_from_json(dados: dict | list | None) -> dict:
    """Refeições salvas -> formato de REFEICOES. ValueError se estiver estragado. Aceita o formato antigo
    (objeto, com a ordem embaralhada pelo jsonb): as refeições padrão voltam na ordem do dia e as
    adicionadas vão depois."""
    if not dados:
        return dict(REFEICOES)
    if isinstance(dados, dict):
        ordem = list(REFEICOES)
        itens = sorted(dados.items(), key=lambda kv: ordem.index(kv[0]) if kv[0] in ordem else len(ordem))
    else:
        itens = [(linha[0], linha[1:]) for linha in dados]
    refeicoes = {}
    for chave, (rotulo, peso, tipo) in itens:
        if isinstance(tipo, list):  # versão 2 salvava as categorias da base antiga
            tipo = "completa" if "prato_principal" in tipo else "leve"
        if tipo not in TIPOS or not str(rotulo).strip() or float(peso) <= 0:
            raise ValueError(f"Refeição inválida: {chave}")
        refeicoes[str(chave)] = (str(rotulo), float(peso), tipo)
    return refeicoes


def meal_targets(meta_kcal: float, refeicoes: dict) -> dict[str, int]:
    """Meta de cada refeição: a meta do dia dividida pelos pesos das refeições que existem."""
    soma = sum(peso for _, peso, _ in refeicoes.values())
    return {chave: round(meta_kcal * peso / soma) for chave, (_, peso, _) in refeicoes.items()}


def _alvo(kcal: int, proteina: int | None) -> str:
    return f"cerca de {kcal} kcal" + (f" e {proteina} g de proteína" if proteina else "")


def _pedido_semana(meta: int, refeicoes: dict, proteina: int | None = None) -> str:
    alvos = meal_targets(meta, refeicoes)
    proteinas = meal_targets(proteina, refeicoes) if proteina else {}
    linhas = "\n".join(f'- chave "{c}": {r}, {TIPOS[t]}, {_alvo(alvos[c], proteinas.get(c))}'
                       for c, (r, _, t) in refeicoes.items())
    return (f"Monte um cardápio de 7 dias ({', '.join(DIAS)}) para UMA pessoa, com {_alvo(meta, proteina)} "
            f"por dia (as metas valem: acerte as porções para chegar perto delas), só com estas refeições, "
            f"nesta ordem, em todos os dias:\n{linhas}\n"
            "Pratos brasileiros do dia a dia, variados (não repita o mesmo prato na semana, exceto no "
            "café, que pode repetir no máximo 2 vezes), com ingredientes fáceis de achar. Respeite as "
            "restrições do perfil. Para cada prato: nome, porção para 1 pessoa, lista de ingredientes "
            "principais e a estimativa de kcal, proteína, carboidratos e gorduras da porção.")


def _numero(valor) -> float:
    try:
        return max(0.0, round(float(valor), 1))
    except (TypeError, ValueError):
        return 0.0


def _prato_valido(dados: dict, chave: str) -> dict:
    prato = str(dados.get("prato") or "").strip()
    if not prato:
        raise ValueError("Prato sem nome")
    return {"chave": chave, "prato": prato, "porcao": str(dados.get("porcao") or "1 porção").strip(),
            "ingredientes": [str(i).strip() for i in dados.get("ingredientes") or [] if str(i).strip()],
            **{n: _numero(dados.get(n)) for n in NUMEROS}}


def build_week(chat, meta_kcal: int | None, refeicoes: dict | None = None, proteina_g: int | None = None,
               fonte: str | None = None) -> dict:
    """Pede a semana ao modelo e valida. ValueError se a resposta não servir. Sem meta de calorias, usa as
    referências da Anvisa (energia e proteína); com meta de calorias e sem a de proteína, fica sem proteína."""
    config = dict(refeicoes or REFEICOES)
    if not config:
        raise ValueError("Escolha pelo menos uma refeição.")
    meta = meta_kcal or REFERENCIA_KCAL
    proteina = proteina_g or (REFERENCIA_PROTEINA_G if meta_kcal is None else None)
    dados = chat.generate_json(_pedido_semana(meta, config, proteina), ESQUEMA_SEMANA)
    dias_modelo = dados.get("dias") or [] if isinstance(dados, dict) else []
    if len(dias_modelo) < len(DIAS):
        raise ValueError("O modelo não devolveu os 7 dias. Tente gerar de novo.")
    dias = []
    for nome, dia in zip(DIAS, dias_modelo):
        por_chave = {str(r.get("chave")): r for r in dia.get("refeicoes") or [] if isinstance(r, dict)}
        sobra = [r for r in dia.get("refeicoes") or [] if isinstance(r, dict)]
        pratos = []
        for i, chave in enumerate(config):
            # o modelo às vezes troca a chave; aí vale a posição
            bruto = por_chave.get(chave) or (sobra[i] if i < len(sobra) else None)
            if bruto is None:
                raise ValueError(f"Faltou a refeição {config[chave][0]} na {nome}. Tente gerar de novo.")
            pratos.append(_prato_valido(bruto, chave))
        dias.append({"dia": nome, "refeicoes": pratos})
    return {"versao": 3, "meta_kcal": meta, "meta_e_referencia": meta_kcal is None, "meta_proteina_g": proteina,
            "fonte_meta": fonte if meta_kcal else None, "refeicoes": config_to_json(config), "dias": dias}


def meal_goals(plano: dict) -> dict[str, tuple[int, int | None]]:
    """Meta de cada refeição do plano: (kcal, proteína em g ou None). Planos antigos não têm proteína."""
    config = config_from_json(plano["refeicoes"])
    kcal = meal_targets(plano["meta_kcal"], config)
    proteina = meal_targets(plano["meta_proteina_g"], config) if plano.get("meta_proteina_g") else {}
    return {c: (kcal[c], proteina.get(c)) for c in config}


def day_check(plano: dict, dia: dict) -> list[str]:
    """O que o dia erra das metas (lista vazia = dentro da meta)."""
    totais, problemas = day_totals(dia), []
    diferenca = totais["kcal"] - plano["meta_kcal"]
    if abs(diferenca) > TOLERANCIA_KCAL * plano["meta_kcal"]:
        problemas.append(f"{abs(diferenca):.0f} kcal {'acima' if diferenca > 0 else 'abaixo'} da meta")
    proteina = plano.get("meta_proteina_g")
    if proteina and totais["proteina_g"] < MINIMO_PROTEINA * proteina:
        problemas.append(f"{proteina - totais['proteina_g']:.0f} g de proteína abaixo da meta")
    return problemas


def swap_meal(chat, plano: dict, dia: int, chave: str) -> None:
    """Troca um prato por outro, gerado pelo modelo, mantendo a meta daquela refeição."""
    config = config_from_json(plano["refeicoes"])
    rotulo, _, tipo = config[chave]
    alvo = _alvo(*meal_goals(plano)[chave])
    usados = sorted({p["prato"] for d in plano["dias"] for p in d["refeicoes"]})
    pedido = (f"Sugira UM prato para {rotulo} ({TIPOS[tipo]}), {alvo}, para 1 pessoa. "
              f"Não repita nenhum destes: {'; '.join(usados)}. Respeite as restrições do perfil. "
              f'Use "chave": "{chave}".')
    _substituir(plano, dia, chave, _prato_valido(chat.generate_json(pedido, _PRATO), chave))


def choose_meal(chat, plano: dict, dia: int, chave: str, nome: str) -> None:
    """A pessoa escolhe o prato da refeição (D72): o modelo monta esse prato (porção e nutrientes) na meta
    daquela refeição, com as restrições do perfil. ValueError se o nome vier vazio."""
    nome = " ".join(nome.split())[:80]
    if not nome:
        raise ValueError("Escreva o nome do prato que você quer.")
    config = config_from_json(plano["refeicoes"])
    rotulo, _, tipo = config[chave]
    alvo = _alvo(*meal_goals(plano)[chave])
    pedido = (f'A pessoa escolheu comer "{nome}" no {rotulo} ({TIPOS[tipo]}). Monte esse prato para 1 pessoa, '
              f"{alvo}: ajuste a porção para chegar perto da meta. Mantenha o prato que ela pediu (pode corrigir a "
              "grafia do nome); se ele levar algo que as restrições do perfil proíbem, use o substituto e diga no "
              f'nome (ex.: "com leite sem lactose"). Use "chave": "{chave}".')
    _substituir(plano, dia, chave, _prato_valido(chat.generate_json(pedido, _PRATO), chave))


def _substituir(plano: dict, dia: int, chave: str, novo: dict) -> None:
    plano["dias"][dia]["refeicoes"] = [novo if p["chave"] == chave else p for p in plano["dias"][dia]["refeicoes"]]


def restore(dados: dict | None) -> dict | None:
    """Plano salvo -> plano, ou None se for do formato antigo (base de receitas) ou estiver estragado."""
    try:
        if not dados or dados.get("versao") != 3:
            return None
        config = config_from_json(dados["refeicoes"])
        for dia in dados["dias"]:
            for p in dia["refeicoes"]:
                if p["chave"] not in config or not p["prato"]:
                    return None
            dia["refeicoes"].sort(key=lambda p: list(config).index(p["chave"]))  # na ordem do dia
        dados["refeicoes"] = config_to_json(config)
        return dados
    except (KeyError, TypeError, ValueError):
        return None


def day_totals(dia: dict) -> dict[str, float]:
    return {n: round(sum(p[n] for p in dia["refeicoes"]), 1) for n in NUMEROS}
