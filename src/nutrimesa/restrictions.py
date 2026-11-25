"""Restrições alimentares do perfil: alergias, intolerâncias e dieta vegetariana/vegana.

Os dados ficam em data/vocab/restricoes_ingredientes.csv: para cada ingrediente, os componentes
que ele 'contem' com certeza ou 'pode_conter' dependendo da marca/processo (decisão D29).

As receitas vêm do Gemini (decisão D56): as restrições do perfil vão no prompt e, depois, o código
confere o texto gerado (text_alerts) e mostra um aviso para cada ingrediente citado que contém ou
pode conter o que a pessoa evita.

A lista de alergênicos segue a RDC 26/2015 da Anvisa (guia de perguntas e respostas, 5ª ed., 2017).
Isto não substitui orientação médica nem a leitura dos rótulos.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from nutrimesa.vocabulary import build_synonym_index, normalize_text

ARQUIVO_PADRAO = Path(__file__).resolve().parents[2] / "data" / "vocab" / "restricoes_ingredientes.csv"
COLUNAS = ["ingrediente_id", "componente", "nivel", "observacao"]
CONTEM, PODE_CONTER = "contem", "pode_conter"
NIVEIS = {CONTEM, PODE_CONTER}

# Componentes que um ingrediente pode ter
COMPONENTES = {
    "leite": "leite", "lactose": "lactose", "gluten": "glúten", "trigo": "trigo",
    "ovo": "ovo", "soja": "soja", "peixe": "peixe", "crustaceos": "crustáceos",
    "amendoim": "amendoim", "castanhas": "castanhas e nozes", "carne": "carne ou peixe",
    "origem_animal": "ingrediente de origem animal",
}

# Opções do perfil -> (rótulo para a tela, componentes que a pessoa evita)
OPCOES_PERFIL = {
    "intolerancia_lactose": ("Intolerância à lactose", {"lactose"}),
    "doenca_celiaca": ("Doença celíaca (sem glúten)", {"gluten"}),
    "alergia_leite": ("Alergia a leite", {"leite"}),
    "alergia_ovo": ("Alergia a ovo", {"ovo"}),
    "alergia_trigo": ("Alergia a trigo (inclui centeio, cevada e aveia)", {"trigo"}),
    "alergia_soja": ("Alergia a soja", {"soja"}),
    "alergia_peixe": ("Alergia a peixe", {"peixe"}),
    "alergia_crustaceos": ("Alergia a crustáceos", {"crustaceos"}),
    "alergia_amendoim": ("Alergia a amendoim", {"amendoim"}),
    "alergia_castanhas": ("Alergia a castanhas e nozes", {"castanhas"}),
    "vegetariano": ("Vegetariano (sem carne nem peixe)", {"carne"}),
    "vegano": ("Vegano (nada de origem animal)", {"carne", "origem_animal"}),
}


def load_restrictions(caminho: str | Path | None = None) -> pd.DataFrame:
    caminho = Path(caminho) if caminho is not None else ARQUIVO_PADRAO
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de restrições não encontrado: {caminho}")
    return pd.read_csv(caminho, encoding="utf-8-sig", dtype=str, keep_default_na=False)


def validate_restrictions(restricoes: pd.DataFrame, vocab: dict[str, pd.DataFrame]) -> list[str]:
    """Confere o arquivo de restrições. Lista vazia = tudo ok."""
    faltam = [c for c in COLUNAS if c not in restricoes.columns]
    if faltam:
        return [f"restricoes_ingredientes.csv: colunas ausentes {faltam}"]
    problemas = []
    ids = set(vocab["ingredientes"]["ingrediente_id"])
    for iid in sorted(set(restricoes["ingrediente_id"]) - ids):
        problemas.append(f"restricoes_ingredientes.csv: ingrediente inexistente '{iid}'")
    for coluna, validos in (("componente", set(COMPONENTES)), ("nivel", NIVEIS)):
        for valor in sorted(set(restricoes[coluna]) - validos):
            problemas.append(f"restricoes_ingredientes.csv: valor inválido em '{coluna}': '{valor}'")
    repetidos = restricoes[restricoes.duplicated(["ingrediente_id", "componente"])]
    for _, r in repetidos.iterrows():
        problemas.append(f"restricoes_ingredientes.csv: par repetido {r['ingrediente_id']}/{r['componente']}")
    return problemas


def components_for(opcoes: list[str] | set[str]) -> set[str]:
    """Componentes a evitar para as opções marcadas no perfil. Opção desconhecida = ValueError."""
    componentes: set[str] = set()
    for opcao in opcoes:
        if opcao not in OPCOES_PERFIL:
            raise ValueError(f"Restrição desconhecida no perfil: '{opcao}'")
        componentes |= OPCOES_PERFIL[opcao][1]
    return componentes


MAX_PALAVRAS_DO_TERMO = 4
PALAVRAS_DE_NEGACAO = {"nao", "nunca", "evite", "evitar", "livre", "isento", "isenta", "substitua",
                       "substituir", "troque", "trocar", "contenham", "alternativa", "ignorei", "ignorar",
                       "ignorando", "ignoramos", "dispensei"}
# palavras que, logo depois do ingrediente, indicam a versão vegetal (texto já normalizado)
VERSOES_VEGETAIS = ("vegetal", "vegano", "vegana", "de aveia", "de amendoa", "de soja", "de arroz",
                    "de castanha", "de coco")


def text_alerts(texto: str, componentes: set[str], vocab: dict[str, pd.DataFrame],
                restricoes: pd.DataFrame) -> list[str]:
    """Ingredientes citados num texto (resposta do Gemini) que contêm ou podem conter o que o perfil
    evita (decisão D56). Ex.: ["queijo mussarela: contém lactose"].

    O texto vem de um LLM, que pode errar: esta conferência roda no código, com a lista de
    restrições por ingrediente. Termo seguido de "sem <componente>" ("leite sem lactose") não conta.
    """
    if not componentes or not texto:
        return []
    indice = build_synonym_index(vocab["sinonimos"])
    nomes = vocab["ingredientes"].set_index("ingrediente_id")["nome_canonico"].to_dict()
    relevantes = restricoes[restricoes["componente"].isin(componentes)]
    # frases de aviso ou troca ("não use leite", "troque o queijo por...") não citam o ingrediente como uso
    trechos = [normalize_text(t) for t in re.split(r"[.!?;:\n]+", texto)]
    palavras = [p for t in trechos if not set(t.split()) & PALAVRAS_DE_NEGACAO for p in t.split()]
    alertas, vistos, i = [], set(), 0
    while i < len(palavras):
        for tamanho in range(MAX_PALAVRAS_DO_TERMO, 0, -1):  # o termo mais longo primeiro ("leite de coco")
            iid = indice.get(" ".join(palavras[i:i + tamanho]))
            if iid:
                break
        else:
            i += 1
            continue
        depois = " ".join(palavras[i + tamanho:i + tamanho + 4])
        i += tamanho
        if iid in vistos or depois.startswith(VERSOES_VEGETAIS):
            continue  # "leite vegetal", "queijo de castanha": não é o produto de origem animal
        vistos.add(iid)
        partes = []
        for _, r in relevantes[relevantes["ingrediente_id"] == iid].iterrows():
            nome_c = COMPONENTES[r["componente"]]
            if depois.startswith((f"sem {normalize_text(nome_c)}", f"zero {normalize_text(nome_c)}")):
                continue  # "leite sem lactose": não avisa lactose (mas ainda avisa origem animal)
            partes.append(f"{'pode conter' if r['nivel'] == PODE_CONTER else 'contém'} {nome_c}")
        if partes:
            alertas.append(f"{nomes.get(iid, iid)}: {', '.join(partes)}")
    return alertas
