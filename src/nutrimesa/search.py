"""Entende os ingredientes que a pessoa escreveu ("ovos", "aipim", "frnago").

resolve_terms transforma o texto em ingrediente_id, tolerando plural, quantidades e erros de
digitação (decisão D26), e separa termos ambíguos (decisão D04) e desconhecidos. Usado pela detecção
de intenção. As receitas em si vêm do Gemini (D56), não de uma base.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from nutrimesa.vocabulary import build_synonym_index, normalize_text

# Decisão D04: termos que não estão nos sinônimos porque podem ser mais de um ingrediente.
# Os candidatos servem para o chatbot montar a pergunta ("Que tipo de farinha?").
_CORTES_BOVINOS = ["carne_bovina_moida", "carne_bovina_patinho", "carne_bovina_acem",
                   "carne_bovina_alcatra"]
TERMOS_AMBIGUOS = {
    "massa": ["macarrao"],
    "farinha": ["farinha_de_trigo", "farinha_de_mandioca", "fuba"],
    "carne": _CORTES_BOVINOS + ["frango"],
    "carne de boi": _CORTES_BOVINOS,
    "carne bovina": _CORTES_BOVINOS,
    "carne vermelha": _CORTES_BOVINOS,
    "bife": ["carne_bovina_alcatra", "carne_bovina_patinho"],
    "molho": ["molho_de_tomate", "extrato_de_tomate"],
    "queijo": ["queijo_mussarela", "queijo_parmesao", "queijo_minas"],
    "pao": ["pao_frances", "pao_de_forma"],
    "salada": ["alface", "tomate", "repolho"],
    "verdura": ["alface", "couve", "espinafre", "repolho"],
    "legumes": ["batata", "cenoura", "abobrinha", "chuchu", "brocolis"],
    "pimenta": ["pimenta_do_reino", "pimentao"],
    "chocolate": ["chocolate_em_po"],
}

# Palavras que podem vir antes do ingrediente e não mudam qual ele é ("2 kg de", "um pouco de")
_PREFIXOS_DESCARTAVEIS = {
    "tenho", "eu", "tem", "temos", "aqui", "ainda", "so", "apenas", "tambem", "sobrou", "sobraram",
    "um", "uma", "uns", "umas", "o", "a", "os", "as", "meio", "meia", "pouco", "pouquinho", "resto",
    "algum", "alguma", "alguns", "algumas", "bastante", "muito", "muita", "muitos", "muitas", "mais",
    "de", "do", "da", "dos", "das", "kg", "g", "gr", "grama", "gramas", "quilo", "quilos", "kilo",
    "kilos", "l", "litro", "litros", "ml", "xicara", "xicaras", "colher", "colheres", "lata",
    "latas", "pacote", "pacotes", "caixa", "caixas", "caixinha", "unidade", "unidades", "duzia",
    "pote", "potes", "vidro", "dente", "dentes", "pe", "pes", "maco", "macos", "cabeca", "fatia",
    "fatias", "pedaco", "pedacos", "bandeja", "saco", "sache", "copo", "copos",
}
_SUFIXOS_DESCARTAVEIS = ["em casa", "na geladeira", "no freezer", "na despensa", "no armario",
                         "sobrando", "sobrou"]


@dataclass
class TermosResolvidos:
    encontrados: dict[str, str] = field(default_factory=dict)      # termo original -> ingrediente_id
    ambiguos: dict[str, list[str]] = field(default_factory=dict)   # termo original -> candidatos
    desconhecidos: list[str] = field(default_factory=list)
    # termos entendidos por aproximação (erro de digitação ou parte do nome): termo -> como foi lido
    corrigidos: dict[str, str] = field(default_factory=dict)

    @property
    def ids(self) -> set[str]:
        return set(self.encontrados.values())


def split_terms(texto: str) -> list[str]:
    """Separa uma lista escrita livremente: "ovos, tomate e cebola" -> ["ovos", "tomate", "cebola"].

    Números soltos ("3 ovos") são descartados; quantidades não importam para a busca.
    """
    partes = re.split(r"[,;\n+/]|\s+e\s+|\s+com\s+", texto)
    termos = []
    for parte in partes:
        limpo = re.sub(r"^\s*\d+([.,]\d+)?\s*", "", parte).strip()
        if limpo:
            termos.append(limpo)
    return termos


def clean_term(chave: str) -> str:
    """Tira de um termo já normalizado o que não identifica o ingrediente.

    >>> clean_term("2 kg de peito de frango na geladeira")
    'peito de frango'
    """
    palavras = chave.split()
    while palavras and (palavras[0] in _PREFIXOS_DESCARTAVEIS or palavras[0].isdigit()):
        palavras.pop(0)
    texto = " ".join(palavras)
    for sufixo in _SUFIXOS_DESCARTAVEIS:
        if texto.endswith(" " + sufixo):
            texto = texto[: -len(sufixo) - 1]
    return texto.strip()


def _singular(palavra: str, tira_es: bool) -> str:
    if len(palavra) <= 3:
        return palavra
    for fim, troca in (("oes", "ao"), ("aes", "ao"), ("ais", "al")):
        if palavra.endswith(fim):
            return palavra[: -len(fim)] + troca
    if tira_es and palavra.endswith("es"):
        return palavra[:-2]
    if palavra.endswith("s"):
        return palavra[:-1]
    return palavra


def _sem_diminutivo(palavra: str) -> str:
    """"franguinho" -> "frango", "paozinho" -> "pao", "cebolinha" -> "cebola"."""
    for fim, troca in (("zinhos", ""), ("zinhas", ""), ("zinho", ""), ("zinha", ""),
                       ("guinho", "go"), ("quinho", "co"), ("inhos", "o"), ("inhas", "a"),
                       ("inho", "o"), ("inha", "a")):
        if palavra.endswith(fim) and len(palavra) - len(fim) >= 3:
            return palavra[: -len(fim)] + troca
    return palavra


def _variantes(chave: str) -> list[str]:
    """O próprio termo, duas formas no singular ("tomates" -> "tomate"; "paes franceses" ->
    "pao frances") e a forma sem diminutivo ("tomatinhos" -> "tomate" fica para a correção)."""
    palavras = chave.split()
    formas = [chave] + [" ".join(_singular(p, tira_es) for p in palavras) for tira_es in (False, True)]
    formas.append(" ".join(_sem_diminutivo(p) for p in palavras))
    return list(dict.fromkeys(formas))


def _busca_exata(chave: str, indice: dict[str, str]) -> str | None:
    for forma in _variantes(chave):
        if forma in indice:
            return indice[forma]
    return None


def _distancia(a: str, b: str) -> int:
    """Quantas letras trocar, tirar, pôr ou inverter de lugar para ir de 'a' a 'b'.

    Distância de Damerau-Levenshtein (versão "alinhamento ótimo"): "frnago" -> "frango" = 1.
    """
    anterior2, anterior = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            atual[j] = min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (ca != cb))
            if anterior2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                atual[j] = min(atual[j], anterior2[j - 2] + 1)
        anterior2, anterior = anterior, atual
    return anterior[-1]


def _erros_tolerados(chave: str) -> int:
    """Quantos erros aceitar, pelo tamanho. Termos de 1 ou 2 letras não são corrigidos."""
    tamanho = len(chave.replace(" ", ""))
    if tamanho <= 2:
        return 0
    if tamanho <= 6:
        return 1
    return 2 if tamanho <= 11 else 3


def _busca_aproximada(chave: str, opcoes: dict[str, object]) -> tuple[list[object], str] | None:
    """Termo mais próximo entre as chaves de 'opcoes'. Empate entre alvos diferentes = ambíguo.

    Só compara termos que começam pela mesma letra: erro na primeira letra é raro, e sem essa
    regra "sardinha" viraria "farinha". Retorna (alvos, chave reconhecida) ou None.
    """
    tolerancia = _erros_tolerados(chave)
    if tolerancia == 0:
        return None
    notas = sorted((_distancia(chave, k), k) for k in opcoes if k[:1] == chave[:1])
    if not notas or notas[0][0] > tolerancia:
        return None
    menor, melhor = notas[0]
    alvos = [opcoes[melhor]]
    for nota, k in notas[1:]:
        if nota > menor:
            break
        if opcoes[k] not in alvos:
            alvos.append(opcoes[k])
    return alvos, melhor


def resolve_terms(termos: list[str], vocab: dict[str, pd.DataFrame],
                  aproximado: bool = True) -> TermosResolvidos:
    """Converte termos do usuário em ingrediente_id usando o dicionário de sinônimos.

    Ordem: nome exato (ou plural) -> termo ambíguo -> correção de digitação -> início do nome
    ("frango congelado" vira "frango"). As duas últimas só com aproximado=True e ficam
    registradas em 'corrigidos', para o chatbot confirmar com o usuário.
    """
    indice = build_synonym_index(vocab["sinonimos"])
    nomes = vocab["ingredientes"].set_index("ingrediente_id")["nome_canonico"].to_dict()
    ambiguos = {normalize_text(t): c for t, c in TERMOS_AMBIGUOS.items()}
    resultado = TermosResolvidos()
    for termo in termos:
        chave = clean_term(normalize_text(termo))
        if not chave:
            continue
        achado = _busca_exata(chave, indice)
        if achado:
            resultado.encontrados[termo] = achado
            continue
        ambiguo = next((ambiguos[f] for f in _variantes(chave) if f in ambiguos), None)
        if ambiguo:
            resultado.ambiguos[termo] = list(ambiguo)
            continue
        if aproximado and _resolve_aproximado(termo, chave, indice, ambiguos, nomes, resultado):
            continue
        resultado.desconhecidos.append(termo)
    return resultado


def _resolve_aproximado(termo: str, chave: str, indice: dict[str, str],
                        ambiguos: dict[str, list[str]], nomes: dict[str, str],
                        resultado: TermosResolvidos) -> bool:
    # 1) erro de digitação no termo inteiro (ou no termo sem diminutivo: "tomatinho" -> "tomato")
    opcoes = {**indice, **{k: tuple(v) for k, v in ambiguos.items()}}
    # também sem o "de" do meio, para "peito frango" achar "peito de frango"
    for k, v in list(indice.items()):
        opcoes.setdefault(k.replace(" de ", " "), v)
    parecido = _busca_aproximada(chave, opcoes)
    sem_diminutivo = " ".join(_sem_diminutivo(p) for p in chave.split())
    if not parecido and sem_diminutivo != chave:
        parecido = _busca_aproximada(sem_diminutivo, opcoes)
    if parecido:
        alvos, reconhecido = parecido
        if len(alvos) == 1 and isinstance(alvos[0], str):
            resultado.encontrados[termo] = alvos[0]
            resultado.corrigidos[termo] = nomes[alvos[0]]
        else:  # empate, ou o termo parecido já era ambíguo ("farinah" -> "farinha")
            candidatos = []
            for alvo in alvos:
                for c in (alvo if isinstance(alvo, tuple) else [alvo]):
                    if c not in candidatos:
                        candidatos.append(c)
            resultado.ambiguos[termo] = candidatos
        return True
    # 2) só o começo do nome ("frango congelado", "cebola roxa", "carne moida de primeira")
    palavras = chave.split()
    for fim in range(len(palavras) - 1, 0, -1):
        achado = _busca_exata(" ".join(palavras[:fim]), indice)
        if achado:
            resultado.encontrados[termo] = achado
            resultado.corrigidos[termo] = nomes[achado]
            return True
    return False
