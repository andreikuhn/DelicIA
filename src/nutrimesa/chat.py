"""Conversa com o LLM (decisão D56): o próprio modelo cria as receitas, as quantidades e a estimativa
de nutrientes, sem base fixa de receitas; o código cuida do que precisa ser confiável.

Provedores, escolhidos por LLM_PROVIDER:
  gemini  (usado no site) API do Google, camada gratuita com limite diário; GEMINI_API_KEY;
  ollama  modelo local e gratuito, para o terminal; precisa do Ollama rodando.

Fluxo de cada mensagem:
  0. decide a intenção (intents.py): cumprimento e assunto fora do tema recebem resposta fixa;
  1. envia o histórico ao modelo, com as instruções e o perfil (restrições, objetivo, meta de calorias);
  2. a resposta chega aos pedaços (streaming); a parte depois de MARCA_DETALHES fica em "ver detalhes"
     e cada sugestão (linha com MARCA_RECEITA) ganha uma setinha que abre o modo de preparo;
  3. o site confere a resposta com alerts(): ingredientes que contêm o que o perfil evita viram aviso.
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd

from nutrimesa.intents import (
    AGRADECIMENTO, CULINARIA, CUMPRIMENTO, DESPEDIDA, ESQUEMA_CLASSIFICADOR, FORA_DO_ESCOPO,
    PROMPT_CLASSIFICADOR, RESPOSTA_FORA_DO_ESCOPO, classifier_message, classify_intent, social_reply,
)
from nutrimesa.restrictions import OPCOES_PERFIL, PALAVRAS_DE_NEGACAO, components_for, text_alerts
from nutrimesa.vocabulary import normalize_text

PROVEDOR_PADRAO = "ollama"
# Gemini: confira em AI Studio quais modelos a sua chave gratuita pode usar e troque em LLM_MODEL
MODELO_PADRAO = {"ollama": "qwen2.5:7b", "gemini": "gemini-3.1-flash-lite"}
OPCOES_OLLAMA = {"temperature": 0.4, "num_ctx": 8192}
# Gemini: quando o Google responde 503 (sobrecarga) ou 429 (limite gratuito), passa na hora para os
# modelos reserva, nesta ordem (2026-10-26: o preview do flash-lite respondeu em 2 a 4 s com cota própria;
# o 3-flash-preview é rápido, mas a camada gratuita dele só dá 20 pedidos por dia); se todos falharem,
# espera 2 s e dá mais uma volta. A biblioteca do Google não tenta de novo sozinha: as tentativas dela
# chegavam a 39 s.
MODELOS_RESERVA_GEMINI = ("gemini-3.1-flash-lite-preview", "gemini-3-flash-preview")
TENTATIVAS_GEMINI = 2
ESPERA_GEMINI_S = 2
# Sem limite, uma conexão presa chegou a 48 s. 60 s cobre um cardápio inteiro gerado de uma vez.
LIMITE_GEMINI_MS = 60_000
# O Google às vezes segura a conexão sem mandar nada (28 a 47 s medidos), e o limite acima não pega
# isso. Normal até o 1º pedaço: 1 a 12 s; passou de 15 s, vai para o reserva.
LIMITE_PRIMEIRO_PEDACO_S = 15

MARCA_DETALHES = "[[DETALHES]]"
MARCA_RECEITA = "[[RECEITA]]"  # começa cada sugestão; no site vira uma linha com setinha (modo de preparo)
RESPOSTA_SEM_TEXTO = "Desculpe, não consegui montar uma resposta. Pode repetir o pedido?"
# como o objetivo muda as receitas e o cardápio (vai junto nas instruções)
OBJETIVOS = {
    "perder": "perder peso: prefira pratos com mais verduras, fibras e proteína magra, que dão saciedade, "
              "e menos açúcar, fritura e farinha branca",
    "manter": "manter o peso: equilíbrio entre proteína, carboidratos, verduras e frutas",
    "ganhar": "ganhar peso: inclua uma boa fonte de proteína em todas as refeições e lanches mais "
              "nutritivos (ex.: ovos, iogurte, castanhas, pasta de amendoim)",
}

SYSTEM_PROMPT = f"""Você é a DelícIA, uma assistente de cozinha que conversa em português do Brasil.
Ajuda a pessoa a descobrir o que cozinhar com o que ela já tem em casa, dá a receita completa para o
número de pessoas pedido e estima os nutrientes.

Como responder:
- Quando a pessoa disser o que tem, sugira de 3 a 6 receitas reais e conhecidas que usem esses
  ingredientes. Cada sugestão numa linha sozinha, exatamente assim, sem negrito nem numeração:
  {MARCA_RECEITA} Nome da receita | tempo aproximado | o que falta comprar (ou "não falta nada")
  Não escreva o modo de preparo das sugestões: a pessoa abre a que quiser. Se ela errou a
  digitação de um ingrediente, diga como entendeu (ex.: "entendi 'frngo' como frango").
- Quando a pessoa pedir um prato pelo nome (ex.: "receita de bolo de cenoura", "quero fazer lasanha"),
  passe direto a receita completa desse prato, sem a lista de sugestões e sem a marca de detalhes:
  uma frase curta, ingredientes, modo de preparo, tempo e nutrientes por porção.
- Se a mensagem da pessoa terminar com "Só: ..." (categorias que ela marcou, ex.: "Só: Doce, Sopa"),
  todas as sugestões e receitas precisam ser dessas categorias. Se nada do que ela tem servir, diga e
  sugira o mínimo para comprar.
- Receita completa: ingredientes com quantidades para o número de pessoas (se não souber, use 2 e
  diga), modo de preparo numerado e tempo.
- Nutrientes: estimativa POR PORÇÃO de calorias, proteína, carboidratos e gorduras, e as principais
  vitaminas e minerais. Sempre diga que é uma estimativa.
- Formato: comece com uma resposta curta e direta, de no máximo 6 linhas, fácil de ler no celular.
  Se houver mais conteúdo (receita completa, modo de preparo, nutrientes, dicas), escreva numa linha
  sozinha exatamente {MARCA_DETALHES} e coloque esse conteúdo depois dela. A pessoa vê o começo e
  abre os detalhes se quiser.
- Você só trata de cozinha e alimentação. Se a pergunta for de outro assunto, diga que não pode
  ajudar com isso e lembre o que você faz.
- Não dê orientação médica nem de dieta. Para questões de saúde, indique um profissional."""

# Filtro que a pessoa escolhe no chat (D60): vale só para as respostas do chat, não para o cardápio
MODOS = {
    "bebidas": ("Só sucos e bebidas",
                "\n\nMODO ATUAL: sugira SOMENTE bebidas saudáveis (sucos naturais, vitaminas, smoothies, "
                "águas saborizadas, chás gelados), nunca pratos. Use os ingredientes que a pessoa tem. Cada "
                "sugestão no mesmo formato de linha com a marca de receita. Prefira bebidas sem açúcar adicionado."),
    "vegano": ("Só comida vegana",
               "\n\nMODO ATUAL: sugira SOMENTE receitas 100% veganas: nada de carne, peixe, ovos, leite, queijo, "
               "mel ou qualquer ingrediente de origem animal. Se a pessoa tiver ingredientes animais, "
               "ignore-os e sugira com os vegetais, grãos e leguminosas que ela tem, ou diga o que falta."),
}


SEM_PERFIL = """

Perfil: sem restrições cadastradas. Se a pessoa mencionar uma alergia ou intolerância, respeite e
lembre que ela pode cadastrá-la em "Meu perfil", para todas as sugestões já virem filtradas."""

COM_PERFIL = """

Perfil da pessoa (cadastrado por ela):
- Restrições: {restricoes}.
- Objetivo: {objetivo}.{meta}{outros}
NUNCA sugira um ingrediente que as restrições proíbem; se a receita normalmente leva, já ofereça
o substituto (ex.: leite sem lactose, bebida vegetal). Lembre que é preciso conferir os rótulos.
Evite também o que a pessoa não gosta, e use os outros dados para acertar porções e escolhas."""


def _metas(kcal: int | None, proteina: int | None, nutricionista: bool) -> str:
    if not kcal and not proteina:
        return ""
    linhas = (f"\n- Meta de energia: cerca de {kcal} kcal por dia." if kcal else "") \
        + (f"\n- Meta de proteína: cerca de {proteina} g por dia." if proteina else "")
    fonte = " Essas metas foram passadas pelo nutricionista da pessoa: siga-as." if nutricionista else ""
    return (linhas + "\n- Ao dar uma receita, acerte a porção para caber nessas metas e diga quanto da meta "
            "do dia 1 porção cobre (ex.: cerca de 30% da energia e 35% da proteína)." + fonte)


def _vale_tentar_outro(erro: Exception) -> bool:
    """Sobrecarga (503), limite do modelo (429), erro ou demora do servidor (500, 502, 504), tempo
    esgotado ou falha de rede: vale tentar o outro modelo."""
    import httpx
    return (getattr(erro, "code", None) in (429, 500, 502, 503, 504)
            or isinstance(erro, (httpx.TransportError, TimeoutError)))


def _com_limite_no_primeiro(pedacos, limite_s: float):
    """Repassa os pedaços; TimeoutError se o primeiro não chegar a tempo. A leitura roda numa thread
    à parte, porque a conexão presa não devolve o controle; abandonada, ela termina sozinha."""
    fila = queue.Queue()

    def ler():
        try:
            for pedaco in pedacos:
                fila.put((True, pedaco))
            fila.put((False, None))
        except Exception as erro:  # noqa: BLE001 - o erro é entregue a quem lê
            fila.put((False, erro))

    threading.Thread(target=ler, daemon=True).start()
    try:
        tem, valor = fila.get(timeout=limite_s)
    except queue.Empty:
        raise TimeoutError(f"o Google não respondeu em {limite_s} s") from None
    while tem:
        yield valor
        tem, valor = fila.get()
    if valor is not None:
        raise valor


def split_suggestions(texto: str) -> tuple[str, list[tuple[str, str]], str]:
    """(texto antes das sugestões, [(nome, "tempo · o que falta")], texto depois) das linhas que começam
    com MARCA_RECEITA."""
    antes, sugestoes, depois = [], [], []
    for linha in texto.splitlines():
        sem_lista = linha.strip().lstrip("-*0123456789. ").strip()  # o modelo às vezes põe numeração
        if not sem_lista.startswith(MARCA_RECEITA):
            (depois if sugestoes else antes).append(linha)
            continue
        partes = [p.strip(" *") for p in sem_lista[len(MARCA_RECEITA):].split("|")]
        if partes[0]:
            sugestoes.append((partes[0], " · ".join(p for p in partes[1:] if p)))
    return "\n".join(antes).strip(), sugestoes, "\n".join(depois).strip()


def split_details(texto: str) -> tuple[str, str]:
    """(resposta curta, detalhes): o que vem depois de MARCA_DETALHES fica em "ver detalhes"."""
    resumo, _, detalhes = texto.partition(MARCA_DETALHES)
    return resumo.strip(), detalhes.strip()


def load_env(caminho: str | Path) -> None:
    """Lê um arquivo .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    caminho = Path(caminho)
    if not caminho.exists():
        return
    # utf-8-sig: o Bloco de Notas pode salvar com BOM, que grudaria no nome da primeira chave
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valor = valor.strip().strip('"').strip("'")
        if valor:
            os.environ.setdefault(chave.strip(), valor)


def provider() -> str:
    """Provedor escolhido em LLM_PROVIDER (ollama ou gemini). ValueError se for outro."""
    nome = (os.environ.get("LLM_PROVIDER") or PROVEDOR_PADRAO).strip().lower()
    if nome not in MODELO_PADRAO:
        raise ValueError(f"LLM_PROVIDER inválido: '{nome}'. Use 'ollama' ou 'gemini'.")
    return nome


@lru_cache(maxsize=2)
def _cliente(nome: str, chave: str | None):
    """Um cliente oficial por processo, compartilhado pelos chats (D66): criar um custava meio segundo
    (conexão segura) a cada F5, login ou perfil salvo. `chave` entra só para trocar de cliente se a
    GEMINI_API_KEY mudar. A conversa de cada pessoa fica no Chat, não no cliente."""
    if nome == "gemini":
        from google import genai
        from google.genai import types
        opcoes = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1), timeout=LIMITE_GEMINI_MS)
        return genai.Client(http_options=opcoes)  # chave: GEMINI_API_KEY
    import ollama
    return ollama.Client()  # endereço: OLLAMA_HOST


def create_chat(vocab: dict[str, pd.DataFrame], restricoes: pd.DataFrame) -> Chat:
    """Cria o chat do provedor configurado, com o cliente oficial."""
    nome = provider()
    return Chat(_cliente(nome, os.environ.get("GEMINI_API_KEY")), vocab, restricoes, nome)


class Chat:
    """Uma conversa. `mensagens` ([{"role": "user"|"assistant", "content": texto}]) é o que o site
    mostra, salva no histórico e manda ao modelo. O cliente vem de fora, para os testes usarem um falso."""

    def __init__(self, client, vocab: dict[str, pd.DataFrame], restricoes: pd.DataFrame,
                 provedor: str = "gemini", modelo: str | None = None):
        self.client, self.vocab, self.restricoes, self.provedor = client, vocab, restricoes, provedor
        self.modelo = modelo or os.environ.get("LLM_MODEL") or MODELO_PADRAO[provedor]
        self.evitar: set[str] = set()
        self.nao_gosta: list[str] = []
        self.modo: str | None = None  # chave de MODOS (filtro do chat)
        self.system_prompt = SYSTEM_PROMPT + SEM_PERFIL
        self.mensagens: list[dict] = []

    def set_profile(self, opcoes: list[str] | None = None, objetivo: str | None = None,
                    meta_kcal: int | None = None, nao_gosta: str = "", outros: list[str] | None = None,
                    proteina_g: int | None = None, nutricionista: bool = False) -> None:
        """`nao_gosta`: texto livre ("fígado, coentro"); `outros`: linhas prontas do perfil (idade, peso,
        atividade, orçamento...), que vão como estão nas instruções (D59). `nutricionista`: as metas de
        kcal e proteína vieram do nutricionista da pessoa (D60, D61)."""
        opcoes, outros = list(opcoes or []), list(outros or [])
        self.evitar = components_for(opcoes)
        self.nao_gosta = [t for t in (normalize_text(p) for p in re.split(r"[,;]|\be\b", nao_gosta or "")) if t]
        if (nao_gosta or "").strip():
            outros.insert(0, f"Não gosta de: {nao_gosta.strip()}")
        if not opcoes and not objetivo and not meta_kcal and not proteina_g and not outros:
            self.system_prompt = SYSTEM_PROMPT + SEM_PERFIL
            return
        self.system_prompt = SYSTEM_PROMPT + COM_PERFIL.format(
            restricoes=", ".join(OPCOES_PERFIL[o][0] for o in opcoes) or "nenhuma",
            objetivo=OBJETIVOS.get(objetivo, "não informado"),
            meta=_metas(meta_kcal, proteina_g, nutricionista),
            outros="".join(f"\n- {linha}." for linha in outros))

    def _prompt_do_chat(self) -> str:
        return self.system_prompt + (MODOS[self.modo][1] if self.modo in MODOS else "")

    def alerts(self, texto: str, com_modo: bool = False) -> list[str]:
        """Ingredientes citados no texto que o perfil evita (conferência pelo código, D56) e o que a
        pessoa marcou que não gosta (busca simples das palavras, fora de frases como "sem coentro")."""
        evitar = self.evitar | (components_for(["vegano"]) if com_modo and self.modo == "vegano" else set())
        alertas = text_alerts(texto, evitar, self.vocab, self.restricoes)
        trechos = [f" {normalize_text(t)} " for t in re.split(r"[.!?;:\n]+", texto or "")]
        trechos = [t for t in trechos if not set(t.split()) & PALAVRAS_DE_NEGACAO]
        return alertas + [f"{t}: você marcou que não gosta" for t in self.nao_gosta
                          if any(f" {t} " in trecho and f" sem {t} " not in trecho for trecho in trechos)]

    # ------------------------------------------------------------- conversa

    def send(self, texto_usuario: str) -> str:
        return "".join(self.send_stream(texto_usuario))

    def send_stream(self, texto_usuario: str):
        """Devolve a resposta aos pedaços, enquanto o modelo escreve."""
        ultima = next((m["content"] for m in reversed(self.mensagens) if m["role"] == "assistant"), "")
        intencao = classify_intent(texto_usuario, self.vocab, self._classificar, ultima)
        self.mensagens.append({"role": "user", "content": texto_usuario})
        if intencao.tipo in (CUMPRIMENTO, AGRADECIMENTO, DESPEDIDA, FORA_DO_ESCOPO):
            resposta = (RESPOSTA_FORA_DO_ESCOPO if intencao.tipo == FORA_DO_ESCOPO
                        else social_reply(intencao.tipo, texto_usuario))
            yield resposta
        else:
            pedacos = []
            try:
                for pedaco in self._stream():
                    pedacos.append(pedaco)
                    yield pedaco
            except BaseException:  # inclui o GeneratorExit de quando o site é interrompido no meio
                del self.mensagens[-1]  # erro no meio: a pergunta sem resposta não fica no histórico
                raise
            resposta = "".join(pedacos).strip()
            if not resposta:  # bloqueada pelo filtro do Google ou vazia
                resposta = RESPOSTA_SEM_TEXTO
                yield resposta
        self.mensagens.append({"role": "assistant", "content": resposta})

    def _stream(self):
        if self.provedor == "ollama":
            msgs = [{"role": "system", "content": self._prompt_do_chat()}] + [
                {"role": m["role"], "content": m["content"]} for m in self.mensagens]
            for parte in self.client.chat(model=self.modelo, messages=msgs, stream=True, options=OPCOES_OLLAMA):
                if parte.message.content:
                    yield parte.message.content
            return
        from google.genai import types
        conteudo = [types.Content(role="model" if m["role"] == "assistant" else "user",
                                  parts=[types.Part(text=m["content"])]) for m in self.mensagens]
        config = types.GenerateContentConfig(system_instruction=self._prompt_do_chat(), temperature=0.5)
        for pedaco in self._gerar_stream(model=self.modelo, contents=conteudo, config=config):
            if pedaco.text:
                yield pedaco.text

    def _classificar(self, texto: str, contexto: str) -> str:
        dados = self.generate_json(classifier_message(texto, contexto), ESQUEMA_CLASSIFICADOR,
                                   PROMPT_CLASSIFICADOR, temperatura=0)
        return dados.get("intencao", CULINARIA) if isinstance(dados, dict) else CULINARIA

    # ------------------------------------------------------------- pedidos avulsos (cardápio, receita)

    def generate_json(self, pedido: str, esquema: dict, sistema: str | None = None,
                      temperatura: float = 0.6) -> dict:
        """Pedido com resposta em JSON no formato do esquema. ValueError se vier fora do formato."""
        sistema = sistema or self.system_prompt
        if self.provedor == "ollama":
            resposta = self.client.chat(model=self.modelo, format=esquema,
                                        messages=[{"role": "system", "content": sistema},
                                                  {"role": "user", "content": pedido}],
                                        options={**OPCOES_OLLAMA, "temperature": temperatura})
            texto = resposta.message.content
        else:
            from google.genai import types
            texto = self._gerar(model=self.modelo, contents=pedido, config=types.GenerateContentConfig(
                system_instruction=sistema, response_mime_type="application/json",
                response_json_schema=esquema, temperature=temperatura)).text
        try:
            return json.loads(texto or "")
        except json.JSONDecodeError as erro:
            raise ValueError("O modelo respondeu fora do formato esperado.") from erro

    def generate_text(self, pedido: str) -> str:
        """Pedido avulso em texto (ex.: a receita completa de um prato do cardápio), com o perfil."""
        if self.provedor == "ollama":
            resposta = self.client.chat(model=self.modelo, options=OPCOES_OLLAMA,
                                        messages=[{"role": "system", "content": self.system_prompt},
                                                  {"role": "user", "content": pedido}])
            return resposta.message.content or RESPOSTA_SEM_TEXTO
        from google.genai import types
        resposta = self._gerar(model=self.modelo, contents=pedido, config=types.GenerateContentConfig(
            system_instruction=self.system_prompt, temperature=0.5))
        return (resposta.text or "").strip() or RESPOSTA_SEM_TEXTO

    def stream_text(self, pedido: str):
        """Como generate_text, mas aos pedaços (o modo de preparo aparece enquanto é escrito)."""
        if self.provedor == "ollama":
            yield self.generate_text(pedido)
            return
        from google.genai import types
        config = types.GenerateContentConfig(system_instruction=self.system_prompt, temperature=0.5)
        vazio = True
        for pedaco in self._gerar_stream(model=self.modelo, contents=pedido, config=config):
            if pedaco.text:
                vazio = False
                yield pedaco.text
        if vazio:
            yield RESPOSTA_SEM_TEXTO

    # ------------------------------------------------------------- Gemini com modelos reserva

    def _tentativas(self, primeiro: str):
        """(é a última?, modelo): o pedido, os outros (principal e reservas) e, após 2 s, mais uma volta."""
        modelos = [primeiro] + [m for m in dict.fromkeys((self.modelo, *MODELOS_RESERVA_GEMINI)) if m != primeiro]
        ordem = modelos * TENTATIVAS_GEMINI
        for i, modelo in enumerate(ordem):
            if i and i % len(modelos) == 0:
                time.sleep(ESPERA_GEMINI_S)
            yield i == len(ordem) - 1, modelo

    def _gerar(self, **kwargs):
        """generate_content; em sobrecarga, cota ou rede passa para outro modelo."""
        for ultima, modelo in self._tentativas(kwargs["model"]):
            try:
                return self.client.models.generate_content(**{**kwargs, "model": modelo})
            except Exception as erro:  # noqa: BLE001 - só sobrecarga e rede trocam de modelo; o resto sobe
                if not _vale_tentar_outro(erro) or ultima:
                    raise

    def _gerar_stream(self, **kwargs):
        """generate_content_stream; troca de modelo só se ainda não chegou nenhum pedaço."""
        for ultima, modelo in self._tentativas(kwargs["model"]):
            chegou = False
            try:
                pedacos = self.client.models.generate_content_stream(**{**kwargs, "model": modelo})
                for pedaco in _com_limite_no_primeiro(pedacos, LIMITE_PRIMEIRO_PEDACO_S):
                    chegou = True
                    yield pedaco
                return
            except Exception as erro:  # noqa: BLE001 - só sobrecarga e rede trocam de modelo; o resto sobe
                if chegou or not _vale_tentar_outro(erro) or ultima:
                    raise
