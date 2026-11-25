"""Vocabulário de ingredientes: carga, normalização de texto e validação.

Responsabilidade deste módulo:
  1. ler os CSVs de data/vocab/ (ingredientes e sinônimos);
  2. normalizar texto (minúsculas, sem acento, sem pontuação), para comparar termos;
  3. validar se os arquivos são coerentes entre si.

Este módulo NÃO decide se um sinônimo é "certo" (isso depende de revisão humana).
Ele só garante que os arquivos não se contradizem.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

# Pasta padrão: <raiz do projeto>/data/vocab  (este arquivo está em <raiz>/src/nutrimesa/)
PASTA_PADRAO = Path(__file__).resolve().parents[2] / "data" / "vocab"

ARQUIVOS = {
    "ingredientes": "ingredientes.csv",
    "sinonimos": "sinonimos.csv",
}

COLUNAS = {
    "ingredientes": ["ingrediente_id", "nome_canonico", "categoria", "unidade_base",
                     "tipo_ajuste", "ingrediente_pai", "observacao"],
    "sinonimos": ["termo", "ingrediente_id", "tipo", "status"],
}

# Campos que nunca podem ficar vazios
OBRIGATORIOS = {
    "ingredientes": ["ingrediente_id", "nome_canonico", "categoria", "unidade_base", "tipo_ajuste"],
    "sinonimos": ["termo", "ingrediente_id", "tipo", "status"],
}

UNIDADES_BASE = {"g", "ml", "un"}
TIPOS_AJUSTE = {"linear", "a_gosto", "nao_linear", "revisar"}
TIPOS_SINONIMO = {"canonico", "plural", "grafia", "regional", "coloquial",
                  "variante", "variante_formato", "marca_popular"}
STATUS_SINONIMO = {"proposto", "validado"}


def normalize_text(texto: str) -> str:
    """Normaliza um texto para comparação: minúsculas, sem acento, sem pontuação.

    >>> normalize_text("Muçarela")
    'mucarela'
    >>> normalize_text("batata-doce")
    'batata doce'
    """
    decomposto = unicodedata.normalize("NFKD", texto.lower())
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def load_vocabulary(pasta: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Lê os CSVs. Todas as colunas entram como texto (nada vira NaN)."""
    pasta = Path(pasta) if pasta is not None else PASTA_PADRAO
    vocab = {}
    for nome, arquivo in ARQUIVOS.items():
        caminho = pasta / arquivo
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo do vocabulário não encontrado: {caminho}")
        # utf-8-sig: os CSVs têm BOM para abrirem com acentos corretos no Excel
        vocab[nome] = pd.read_csv(caminho, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return vocab


def _colisoes_de_sinonimos(sinonimos: pd.DataFrame) -> list[str]:
    """Termos que, depois de normalizados, apontam para ingredientes diferentes."""
    visto: dict[str, str] = {}
    problemas = []
    for termo, ing in zip(sinonimos["termo"], sinonimos["ingrediente_id"]):
        chave = normalize_text(termo)
        if chave in visto and visto[chave] != ing:
            problemas.append(f"Termo ambíguo '{termo}' (normalizado: '{chave}') aponta para "
                             f"'{visto[chave]}' e para '{ing}'")
        visto.setdefault(chave, ing)
    return problemas


def build_synonym_index(sinonimos: pd.DataFrame) -> dict[str, str]:
    """Cria o índice {termo normalizado: ingrediente_id}. Falha se houver termo ambíguo."""
    problemas = _colisoes_de_sinonimos(sinonimos)
    if problemas:
        raise ValueError("; ".join(problemas))
    return {normalize_text(t): i for t, i in zip(sinonimos["termo"], sinonimos["ingrediente_id"])}


def validate_vocabulary(vocab: dict[str, pd.DataFrame]) -> list[str]:
    """Verifica a coerência dos arquivos. Retorna a lista de problemas (vazia = tudo ok)."""
    problemas: list[str] = []

    # 1) colunas e campos obrigatórios
    for nome, colunas in COLUNAS.items():
        faltam = [c for c in colunas if c not in vocab[nome].columns]
        if faltam:
            problemas.append(f"{ARQUIVOS[nome]}: colunas ausentes {faltam}")
    if problemas:  # sem as colunas não dá para continuar as outras checagens
        return problemas
    for nome, colunas in OBRIGATORIOS.items():
        for col in colunas:
            vazias = (vocab[nome][col].str.strip() == "").sum()
            if vazias:
                problemas.append(f"{ARQUIVOS[nome]}: {vazias} linha(s) com '{col}' vazio")

    ing, sin = vocab["ingredientes"], vocab["sinonimos"]

    # 2) ingredientes
    repetidos = sorted(ing.loc[ing["ingrediente_id"].duplicated(), "ingrediente_id"].unique())
    if repetidos:
        problemas.append(f"ingredientes.csv: ingrediente_id duplicado: {repetidos}")
    ids = set(ing["ingrediente_id"])
    for coluna, permitidos in (("unidade_base", UNIDADES_BASE), ("tipo_ajuste", TIPOS_AJUSTE)):
        invalidos = sorted(set(ing[coluna]) - permitidos)
        if invalidos:
            problemas.append(f"ingredientes.csv: valores inválidos em '{coluna}': {invalidos}")
    for _, linha in ing[ing["ingrediente_pai"] != ""].iterrows():
        if linha["ingrediente_pai"] not in ids:
            problemas.append(f"ingredientes.csv: pai inexistente '{linha['ingrediente_pai']}' "
                             f"em '{linha['ingrediente_id']}'")
        if linha["ingrediente_pai"] == linha["ingrediente_id"]:
            problemas.append(f"ingredientes.csv: '{linha['ingrediente_id']}' é pai de si mesmo")

    # 3) sinônimos
    desconhecidos = sorted(set(sin["ingrediente_id"]) - ids)
    if desconhecidos:
        problemas.append(f"sinonimos.csv: ingrediente_id inexistente: {desconhecidos}")
    for coluna, permitidos in (("tipo", TIPOS_SINONIMO), ("status", STATUS_SINONIMO)):
        invalidos = sorted(set(sin[coluna]) - permitidos)
        if invalidos:
            problemas.append(f"sinonimos.csv: valores inválidos em '{coluna}': {invalidos}")
    problemas += [f"sinonimos.csv: {p}" for p in _colisoes_de_sinonimos(sin)]
    com_canonico = set(sin.loc[sin["tipo"] == "canonico", "ingrediente_id"])
    for ing_id in sorted(ids - com_canonico):
        problemas.append(f"sinonimos.csv: '{ing_id}' não tem termo do tipo 'canonico'")

    return problemas
