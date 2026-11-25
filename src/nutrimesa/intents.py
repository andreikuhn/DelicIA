"""Intenção da mensagem do usuário: cumprimento, agradecimento, despedida, culinária ou fora do escopo.

Decidida em duas camadas (decisão D25):
  1. regras em código (rápidas e testáveis): mensagens que são só cumprimento/agradecimento/despedida,
     e mensagens com sinal claro de cozinha (um ingrediente conhecido ou palavras como "receita");
  2. quando as regras não decidem, um classificador (o próprio LLM, com saída restrita a
     "culinaria" ou "fora_do_escopo") olha a mensagem e a última resposta do assistente.
Na dúvida, a mensagem segue como culinária: o prompt principal também recusa assuntos fora do tema.

As respostas para cumprimento, agradecimento, despedida e fora do escopo são textos fixos daqui,
iguais para qualquer modelo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from nutrimesa.search import TERMOS_AMBIGUOS, resolve_terms, split_terms
from nutrimesa.vocabulary import normalize_text

CUMPRIMENTO, AGRADECIMENTO, DESPEDIDA = "cumprimento", "agradecimento", "despedida"
CULINARIA, FORA_DO_ESCOPO = "culinaria", "fora_do_escopo"
INTENCOES_DO_CLASSIFICADOR = (CULINARIA, FORA_DO_ESCOPO)

# Frases sociais, já normalizadas (sem acento, minúsculas). As mais longas vêm primeiro.
_FRASES = {
    CUMPRIMENTO: ["bom dia", "boa tarde", "boa noite", "tudo bem", "tudo bom", "tudo certo",
                  "tudo joia", "como vai", "como voce esta", "como vc esta", "e ai", "e ae", "eai",
                  "eae", "ola", "oi", "oie", "opa", "salve", "fala", "hey", "hello", "hi", "beleza",
                  "blz", "nutrimesa", "delicia"],
    AGRADECIMENTO: ["muito obrigado", "muito obrigada", "obrigado", "obrigada", "brigado",
                    "brigada", "valeu", "vlw", "agradeco", "obg", "thanks"],
    DESPEDIDA: ["ate mais", "ate logo", "ate amanha", "ate a proxima", "tchau", "falou", "flw",
                "fui", "bye"],
}
# Palavras que podem sobrar numa mensagem social sem mudar o sentido ("oi, tudo bem com você?")
_ENCHIMENTO = {"e", "com", "voce", "vc", "ce", "ai", "ae", "por", "a", "o", "pra", "para",
               "ajuda", "tudo", "mesmo", "muito", "demais", "gente", "amigo", "amiga", "querido",
               "querida", "sim", "td", "bem", "ok", "certo", "entao", "bot", "ne", "hein"}
# Sinais de assunto de cozinha, além dos ingredientes do vocabulário
_PALAVRAS_DE_COZINHA = {
    "receita", "receitas", "cozinhar", "cozinho", "cozinha", "comida", "comer", "almoco", "almocar",
    "jantar", "janta", "cafe", "lanche", "lanchinho", "sobremesa", "doce", "prato", "pratos",
    "porcao", "porcoes", "pessoa", "pessoas", "preparo", "preparar", "ingrediente", "ingredientes",
    "geladeira", "despensa", "armario", "fome", "assar", "assado", "fritar", "frito", "refogar",
    "cozido", "forno", "panela", "frigideira", "airfryer", "microondas", "rende", "substituir",
    "substituto", "trocar", "alergia", "alergico", "alergica", "intolerancia", "lactose", "gluten",
    "dieta", "caloria", "calorias", "nutricional", "vegetariano", "vegetariana", "vegano", "vegana",
    "marmita", "cardapio", "modo", "passo",
    # nomes de pratos comuns
    "bolo", "bolos", "torta", "tortas", "sopa", "sopas", "caldo", "salgado", "salgados", "suco",
    "vitamina", "panqueca", "omelete", "pudim", "brigadeiro", "feijoada", "lasanha", "pizza",
    "hamburguer", "sanduiche", "macarronada", "risoto", "farofa", "pure", "strogonoff",
    "estrogonofe", "escondidinho", "mingau", "cuscuz", "moqueca", "galinhada", "tropeiro",
}
# Respostas curtas que, no meio de uma conversa, costumam ser continuação ("sim", "a segunda")
_CONTINUACAO = {"sim", "nao", "pode", "ser", "quero", "essa", "esse", "isso", "a", "o", "primeira",
                "segunda", "terceira", "quarta", "quinta", "ultima", "outra", "outro", "mais",
                "menos", "manda", "mostra", "ok", "okay", "beleza", "bora", "vamos", "claro",
                "uhum", "aham", "por", "favor", "pf", "pfv", "prefiro", "melhor", "opcao", "numero",
                "e", "pra", "para", "de", "um", "uma", "dois", "duas", "tres", "quatro", "cinco",
                "seis", "sete", "oito", "nove", "dez"}

APRESENTACAO = (
    "Eu sou a DelícIA, sua assistente de cozinha. Eu posso:\n"
    "- sugerir receitas com os ingredientes que você já tem em casa;\n"
    "- ajustar as quantidades para o número de pessoas;\n"
    "- explicar o preparo passo a passo."
)
CONVITE = "Me conta: o que você tem aí na geladeira ou na despensa?"

RESPOSTA_FORA_DO_ESCOPO = (
    "Essa pergunta foge do que eu sei fazer, então não consigo responder sobre esse assunto.\n\n"
    f"{APRESENTACAO}\n\nSe quiser, me diga o que você tem em casa que eu sugiro uma receita."
)
RESPOSTA_AGRADECIMENTO = ("Por nada! Se quiser outra receita ou ajustar as quantidades, "
                          "é só me dizer o que você tem em casa.")
RESPOSTA_DESPEDIDA = "Até mais! Bom apetite."

PROMPT_CLASSIFICADOR = """Você classifica mensagens enviadas a um assistente de cozinha.
O assistente só trata de: receitas, ingredientes que a pessoa tem, quantidades e porções,
modo de preparo, substituições, compras de ingredientes e dúvidas de cozinha em geral.

Responda "culinaria" se a mensagem for sobre esses temas OU for continuação da conversa
(por exemplo "sim", "a segunda", "para 4 pessoas", "e sem cebola?").
Responda "fora_do_escopo" se a mensagem for sobre outro assunto (esportes, política, notícias,
tarefas escolares, programação, celebridades, etc.).
Na dúvida, responda "culinaria"."""

ESQUEMA_CLASSIFICADOR = {
    "type": "object",
    "properties": {"intencao": {"type": "string", "enum": list(INTENCOES_DO_CLASSIFICADOR)}},
    "required": ["intencao"],
    "additionalProperties": False,
}


@dataclass
class Intencao:
    tipo: str
    origem: str  # "regra" ou "classificador"


def _tira_frases(texto: str, frases: list[str]) -> tuple[str, list[str]]:
    """Remove as frases encontradas (palavra inteira) e devolve o que sobrou e o que foi achado."""
    achadas = []
    for frase in frases:
        padrao = rf"\b{re.escape(frase)}\b"
        if re.search(padrao, texto):
            achadas.append(frase)
            texto = re.sub(padrao, " ", texto)
    return " ".join(texto.split()), achadas


def _so_social(chave: str) -> tuple[str | None, list[str]]:
    """Se a mensagem é só cumprimento/agradecimento/despedida, diz qual (e as frases achadas)."""
    resto, achadas_por_tipo = chave, {}
    for tipo, frases in _FRASES.items():
        resto, achadas = _tira_frases(resto, frases)
        if achadas:
            achadas_por_tipo[tipo] = achadas
    if not achadas_por_tipo or any(p not in _ENCHIMENTO for p in resto.split()):
        return None, []
    # despedida e agradecimento valem mais que um "oi" junto ("valeu, tchau")
    for tipo in (DESPEDIDA, AGRADECIMENTO, CUMPRIMENTO):
        if tipo in achadas_por_tipo:
            return tipo, achadas_por_tipo[tipo]
    return None, []


def _tem_sinal_de_cozinha(texto: str, vocab: dict[str, pd.DataFrame]) -> bool:
    chave = normalize_text(texto)
    palavras = set(chave.split())
    if palavras & _PALAVRAS_DE_COZINHA:
        return True
    if any(f" {normalize_text(t)} " in f" {chave} " for t in TERMOS_AMBIGUOS):
        return True
    # cada pedaço e cada palavra passam pelo reconhecimento de ingredientes, sem correção de
    # digitação: aqui um falso positivo ("flamengo" virando "frango") atrapalharia mais que ajudaria
    pedacos = split_terms(texto) + chave.split()
    return bool(resolve_terms(pedacos, vocab, aproximado=False).encontrados)


def _e_continuacao(chave: str) -> bool:
    palavras = chave.split()
    return bool(palavras) and len(palavras) <= 6 and all(
        p in _CONTINUACAO or p.isdigit() for p in palavras)


def classify_intent(texto: str, vocab: dict[str, pd.DataFrame],
                    classificador: Callable[[str, str], str] | None = None,
                    contexto: str = "") -> Intencao:
    """Decide a intenção. 'contexto' é a última resposta do assistente (vazia no começo)."""
    chave = normalize_text(texto)
    tipo, _ = _so_social(chave)
    if tipo:
        return Intencao(tipo, "regra")
    if _tem_sinal_de_cozinha(texto, vocab):
        return Intencao(CULINARIA, "regra")
    if contexto and _e_continuacao(chave):
        return Intencao(CULINARIA, "regra")
    if classificador is None:
        return Intencao(CULINARIA, "regra")
    try:
        decidido = classificador(texto, contexto)
    except Exception:  # noqa: BLE001 - se o classificador falhar, segue a conversa normal
        decidido = CULINARIA
    return Intencao(decidido if decidido in INTENCOES_DO_CLASSIFICADOR else CULINARIA, "classificador")


def classifier_message(texto: str, contexto: str) -> str:
    """Texto enviado ao classificador."""
    anterior = contexto.strip()[:600] or "(início da conversa)"
    return f"Última resposta do assistente:\n{anterior}\n\nMensagem do usuário:\n{texto}"


def social_reply(tipo: str, texto: str) -> str:
    """Resposta fixa para cumprimento, agradecimento e despedida."""
    if tipo == AGRADECIMENTO:
        return RESPOSTA_AGRADECIMENTO
    if tipo == DESPEDIDA:
        return RESPOSTA_DESPEDIDA
    chave = normalize_text(texto)
    saudacao = "Olá!"
    for frase, resposta in (("bom dia", "Bom dia!"), ("boa tarde", "Boa tarde!"),
                            ("boa noite", "Boa noite!")):
        if re.search(rf"\b{frase}\b", chave):
            saudacao = resposta
            break
    if re.search(r"\b(tudo (bem|bom|certo|joia)|como (vai|voce esta|vc esta)|beleza|blz)\b", chave):
        saudacao += " Tudo ótimo por aqui, obrigado por perguntar."
    return f"{saudacao}\n\n{APRESENTACAO}\n\n{CONVITE}"
