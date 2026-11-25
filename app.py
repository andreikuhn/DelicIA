"""Site da DelícIA (Streamlit). Rodar localmente:  python -m streamlit run app.py

Configuração (veja docs/publicar_site.md): SUPABASE_URL, SUPABASE_KEY, LLM_PROVIDER, GEMINI_API_KEY
e, opcionalmente, LLM_MODEL. No Streamlit Cloud ficam em "Secrets"; no computador, em
.streamlit/secrets.toml ou no .env. Nenhum desses arquivos vai para o Git.
Cores do tema (claro e escuro): .streamlit/config.toml. Ilustrações e estilo: src/nutrimesa/visual.py.

Layout (D57), no jeito dos assistentes conhecidos: barra lateral com "Nova conversa", o histórico
de conversas e o menu (cardápio, perfil, configurações); no centro, a conversa, com a caixa de texto
sempre embaixo e as mensagens subindo.
"""
import dataclasses
import os
import secrets
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))


def _recarregar_se_o_codigo_mudou() -> None:
    """O Streamlit Cloud às vezes atualiza o app.py sem recarregar src/ (ImportError depois de um
    git push). Se algum arquivo de src/nutrimesa mudou desde a última execução, descarta as
    versões antigas da memória para que sejam importadas de novo."""
    versao = tuple(sorted((p.name, p.stat().st_mtime_ns) for p in (RAIZ / "src" / "nutrimesa").glob("*.py")))
    if getattr(sys, "_delicia_versao", None) == versao:
        return
    for nome in [m for m in sys.modules if m == "nutrimesa" or m.startswith("nutrimesa.")]:
        del sys.modules[nome]
    st.cache_resource.clear()  # guarda objetos das classes antigas
    sys._delicia_versao = versao


_recarregar_se_o_codigo_mudou()

from nutrimesa import accounts, consumo, videos, visual  # noqa: E402
from nutrimesa.chat import MARCA_DETALHES, MODOS, MARCA_RECEITA, create_chat, load_env, split_details, split_suggestions  # noqa: E402
from nutrimesa.energy import ATIVIDADES, AVISO, FONTES, SEXOS, Metas, age_from_year, daily_targets, estimate, water_goal  # noqa: E402
from nutrimesa.planner import (  # noqa: E402
    DIAS, NUMEROS, PESO_NOVA, REFEICOES, TIPOS, build_week, config_from_json, config_to_json,
    choose_meal, day_check, day_totals, meal_goals, restore, swap_meal,
)
from nutrimesa.restrictions import OPCOES_PERFIL, load_restrictions  # noqa: E402
from nutrimesa.vocabulary import load_vocabulary  # noqa: E402

CONFIGURACOES = ("SUPABASE_URL", "SUPABASE_KEY", "LLM_PROVIDER", "LLM_MODEL", "GEMINI_API_KEY", "LOGIN_GOOGLE",
                 "SITE_URL", "YOUTUBE_API_KEY")
OBJETIVOS = {"": "Prefiro não informar", "perder": "Perder peso", "manter": "Manter o peso",
             "ganhar": "Ganhar peso"}
ESCOLHA = "Escolha uma opção"  # no lugar do texto padrão do Streamlit, em inglês

TEXTO_CONSENTIMENTO = """
**Como a DelícIA usa seus dados**

- Guardamos seu **nome e e-mail** (se entrar com o Google, recebemos dele só esses dois) e, se você preencher, **objetivo, restrições alimentares**
  (alergias, intolerâncias, dieta) e **dados do corpo** (ano de nascimento, sexo, altura, peso e
  nível de atividade), além do que você **não gosta de comer**, do seu **orçamento** e das **metas de
  energia e proteína** que um nutricionista tenha passado para você. Dados de
  saúde são **dados sensíveis** pela LGPD.
- Usamos esses dados **só para adaptar as receitas e estimar IMC e calorias** para você.
- Os dados ficam no Supabase (serviço de banco de dados). Só você acessa o seu perfil, as suas
  conversas e os seus cardápios.
- As receitas e os nutrientes são criados pelo **Gemini (Google)**, que recebe suas **mensagens e o
  seu perfil** (restrições, objetivo, metas de calorias e proteína, dados do corpo, o que não gosta e
  orçamento),
  para acertar as porções e as escolhas. Seu nome e e-mail **não** são enviados. Na versão
  gratuita, o Google pode usar o conteúdo das conversas para melhorar os modelos dele: não escreva
  no chat informações pessoais que não sejam necessárias.
- O **histórico das conversas** fica salvo na sua conta, para você continuar depois. Você pode
  apagar cada conversa.
- Quando você toca na **maçã** de uma receita, guardamos que comeu 1 porção naquele dia, com os
  nutrientes estimados, para somar no seu perfil. Tocar de novo apaga o registro.
- Para você não precisar entrar de novo a cada vez que abrir o site, este navegador guarda um
  código de acesso. Ao clicar em **Sair**, ele é apagado.
- Você pode **apagar sua conta e todos os dados** a qualquer momento, em **Configurações**.
- Este é um projeto acadêmico. As receitas e os nutrientes são **estimativas da IA** e podem ter
  erros: confira os rótulos e procure um profissional de saúde para orientação. Todos os cálculos de
  gasto energético e de consumo de proteínas são aproximados e não substituem a consulta com um nutricionista.
"""


def _configurar_ambiente() -> None:
    """Traz as configurações dos Secrets do Streamlit (ou do .env) para variáveis de ambiente."""
    load_env(RAIZ / ".env")
    st.session_state.pop("erro_secrets", None)
    try:
        segredos = dict(st.secrets)
    except Exception as erro:  # noqa: BLE001 - sem Secrets (segue com o .env) ou Secrets inválidos
        segredos = {}
        # o Streamlit avisa erro de formato (TOML) com a mesma classe de "arquivo não encontrado"
        if not isinstance(erro, FileNotFoundError) or "pars" in str(erro).lower():
            st.session_state.erro_secrets = type(erro).__name__
    # nomes iguais aos do .env, mesmo que digitados em minúsculas
    segredos = {str(k).strip().upper(): v for k, v in segredos.items()}
    # só os NOMES (nunca os valores), para a mensagem de configuração incompleta
    st.session_state.nomes_secrets = sorted(segredos)
    for chave in CONFIGURACOES:
        if segredos.get(chave):
            os.environ[chave] = str(segredos[chave]).strip()
    os.environ.setdefault("LLM_PROVIDER", "gemini")


def _tema() -> str:
    """'light' ou 'dark', conforme o modo que a pessoa escolheu no menu do Streamlit."""
    try:
        return st.context.theme.type or "light"
    except Exception:  # noqa: BLE001 - versões sem st.context.theme: usa o claro
        return "light"


@st.cache_resource
def _carregar_dados(versao: int):  # sem "_" no nome: o Streamlit ignora argumentos com "_" na chave
    return load_vocabulary(), load_restrictions()


def _dados():
    """Vocabulário e restrições (só leitura, compartilhados entre as sessões). A chave é a versão do
    código carregada agora: nunca volta da memória um objeto criado pelo código antigo."""
    return _carregar_dados(id(load_vocabulary))


def _cliente_supabase():
    """Um cliente por sessão do navegador: o login de cada pessoa fica guardado no próprio cliente."""
    if "supabase" not in st.session_state and os.environ.get("BANCO", "local").strip().lower() != "supabase":
        # modo local (padrão): contas e dados num SQLite no próprio PC, sem Supabase (banco_local.py)
        from nutrimesa.banco_local import ClienteLocal
        st.session_state.supabase = ClienteLocal()
    if "supabase" not in st.session_state:
        from supabase import create_client
        url, chave = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
        if not url or not chave:
            faltam = " e ".join(n for n, v in (("SUPABASE_URL", url), ("SUPABASE_KEY", chave)) if not v)
            if st.session_state.get("erro_secrets"):
                st.error("Os Secrets do site têm um erro de formato e não puderam ser lidos. Cada linha "
                         'precisa estar assim, com espaços e aspas: SUPABASE_URL = "https://xxxx.supabase.co"')
            else:
                nomes = st.session_state.get("nomes_secrets") or []
                achados = ", ".join(nomes) if nomes else "nenhum (os Secrets estão vazios)"
                st.error(f"O site ainda não foi configurado: falta {faltam} (veja os Secrets). "
                         f"Nomes encontrados nos Secrets: {achados}.")
            st.stop()
        if "supabase.com/dashboard" in url:
            st.error("SUPABASE_URL está com o endereço do painel. Use a Project URL, no formato "
                     "https://xxxx.supabase.co (Project Settings > API).")
            st.stop()
        from supabase import ClientOptions
        # sem renovação em segundo plano: a sessão é renovada nas execuções do site, que guardam o
        # código novo no navegador (D55); renovada escondida, ficaria guardado um código que não vale
        opcoes = ClientOptions(auto_refresh_token=False, persist_session=False)
        st.session_state.supabase = create_client(url, chave, options=opcoes)
    return st.session_state.supabase


def _metas(perfil: accounts.Perfil) -> Metas:
    """Metas do dia: as do nutricionista, se houver; senão, as da fórmula (D60)."""
    est = estimate(perfil.peso_kg, perfil.altura_cm, perfil.ano_nascimento, perfil.sexo,
                   perfil.atividade, perfil.objetivo)
    return daily_targets(est, perfil.peso_kg, perfil.kcal_nutricionista, perfil.proteina_nutricionista)


def _dados_do_perfil(perfil: accounts.Perfil) -> list[str]:
    """Linhas do perfil que vão nas instruções do modelo (D59). Nome e e-mail nunca vão."""
    dados = [
        f"Idade: {age_from_year(perfil.ano_nascimento)} anos" if perfil.ano_nascimento else "",
        f"Sexo biológico: {SEXOS[perfil.sexo].lower()}" if perfil.sexo else "",
        f"Altura: {perfil.altura_cm:.0f} cm" if perfil.altura_cm else "",
        f"Peso: {perfil.peso_kg:.1f} kg".replace(".", ",") if perfil.peso_kg else "",
        f"Atividade física: {ATIVIDADES[perfil.atividade][0].lower()}" if perfil.atividade else "",
        f"Orçamento: {accounts.ORCAMENTOS[perfil.orcamento].lower()}" if perfil.orcamento else "",
    ]
    return [d for d in dados if d]


def _novo_chat(mensagens: list[dict] | None = None):
    """Chat com o perfil atual (restrições, objetivo, meta) e, se vier, o histórico de uma conversa."""
    perfil: accounts.Perfil = st.session_state.perfil
    chat, metas = create_chat(*_dados()), _metas(perfil)
    chat.set_profile(perfil.restricoes, perfil.objetivo, metas.kcal, perfil.nao_gosta, _dados_do_perfil(perfil),
                     metas.proteina_g, "nutricionista" in (metas.fonte_kcal, metas.fonte_proteina))
    chat.mensagens = list(mensagens or [])
    return chat


def _perfil_vazio(perfil: accounts.Perfil) -> bool:
    return not (perfil.restricoes or perfil.objetivo or perfil.ano_nascimento or perfil.sexo
                or perfil.altura_cm or perfil.peso_kg or perfil.atividade or perfil.nao_gosta or perfil.orcamento
                or perfil.kcal_nutricionista or perfil.proteina_nutricionista)


def _iniciar_sessao(perfil: accounts.Perfil) -> None:
    st.session_state.perfil = perfil
    st.session_state.pagina = "chat"
    # ao entrar (ou no F5), volta para a última conversa, do jeito que estava. A lista da barra lateral e a
    # última conversa são buscadas ao mesmo tempo: uma ida ao Supabase a menos antes de a página aparecer
    cliente = _cliente_supabase()
    with ThreadPoolExecutor(max_workers=2) as fila:
        lista = fila.submit(accounts.list_conversations, cliente, perfil.id)
        ultima = fila.submit(accounts.last_conversation, cliente, perfil.id)
    st.session_state.conversas, ultima = lista.result(), ultima.result()
    st.session_state.chat = _novo_chat(ultima["mensagens"] if ultima else None)
    st.session_state.conversa_id = ultima["id"] if ultima else None


def _encerrar_sessao() -> None:
    _memoria_do_servidor().pop(st.session_state.pop("chave_servidor", None), None)
    # tudo o que é da pessoa: senão quem entrar depois neste navegador veria conversas e cardápios dela
    for chave in ("perfil", "chat", "conversa_id", "conversas", "pagina", "supabase", "recuperacao_email",
                  "cardapios", "cardapio_carregado", "sessao_gravada", "cadastro_inicial"):
        st.session_state.pop(chave, None)
    st.session_state.apagar_sessao_navegador = True  # apagado na próxima execução (esta termina num rerun)


def _mensagem_de_erro_do_modelo(erro: Exception) -> str:
    codigo = getattr(erro, "code", None) or getattr(erro, "status_code", None)
    if codigo == 429:
        return ("O limite gratuito de uso do modelo foi atingido. Espere um pouco (ou até amanhã) "
                "e tente de novo.")
    if codigo in (500, 502, 503, 504) or isinstance(erro, TimeoutError):
        return "O serviço do modelo está sobrecarregado agora. Tente de novo em alguns instantes."
    return "O assistente não conseguiu responder agora. Tente de novo em instantes."


# ---------------------------------------------------------------- manter conectado (D55)

# O código fica no localStorage do navegador, lido e gravado por um componente com JavaScript.
# Cookie não serve: o Streamlit Community Cloud filtra os cookies antes de chegarem ao site.
_JS_SESSAO = """
export default function(component) {
  const { setStateValue, data } = component;
  const CHAVE = "delicia_sessao";
  try {
    if (data.acao === "gravar") localStorage.setItem(CHAVE, data.valor);
    else if (data.acao === "apagar") localStorage.removeItem(CHAVE);
    else setStateValue("token", localStorage.getItem(CHAVE) || "");
  } catch (e) {
    if (data.acao === "ler") setStateValue("token", "");  // navegador sem localStorage
  }
}
"""
_sessao_navegador = st.components.v2.component("sessao_navegador", js=_JS_SESSAO)


# Troca de claro/escuro no menu ⋮ (D65): este componente olha a cor de fundo do Streamlit e, quando muda,
# marca <html data-dl-tema> na hora (as cores do nosso CSS são variáveis e trocam junto, sem esperar o
# Python) e depois pede uma nova execução, só para redesenhar as ilustrações com a paleta nova.
_JS_TEMA = """
export default function(component) {
  const app = document.querySelector('[data-testid="stApp"]');
  if (!app) return;
  const tema = () => {
    const c = (getComputedStyle(app).backgroundColor.match(/\\d+/g) || [255, 255, 255]).map(Number);
    return c[0] + c[1] + c[2] < 384 ? "dark" : "light";
  };
  let atual = tema();
  document.documentElement.dataset.dlTema = atual;
  const id = setInterval(() => {
    const t = tema();
    if (t !== atual) {
      atual = t;
      document.documentElement.dataset.dlTema = t;
      component.setTriggerValue("tema", t);
    }
  }, 120);
  return () => clearInterval(id);
}
"""
_observa_tema = st.components.v2.component("observa_tema", js=_JS_TEMA)

# No celular a barra lateral cobre a tela: ao tocar numa conversa ou numa página do menu, ela se fecha.
_JS_MENU_CELULAR = """
export default function(component) {
  // no documento, não na barra: o componente monta antes do login, quando a barra ainda não existe
  const fecha = (e) => {
    const botao = e.target.closest('[data-testid="stSidebarUserContent"] button');
    if (innerWidth > 640 || !botao || botao.innerText.includes("delete")) return;  // apagar conversa: continua aberta
    setTimeout(() => document.querySelector('[data-testid="stSidebarHeader"] button')?.click(), 150);
  };
  document.addEventListener("click", fecha);
  return () => document.removeEventListener("click", fecha);
}
"""
_menu_celular = st.components.v2.component("menu_celular", js=_JS_MENU_CELULAR)


def _gravar_no_navegador(valor: str | None) -> None:
    """Grava (ou apaga, com None) o código da sessão no navegador, para o F5 não pedir login."""
    acao = "gravar" if valor else "apagar"
    # chave nova a cada valor: o componente monta de novo e o JavaScript roda com o dado novo
    _sessao_navegador(key=f"sessao_{acao}_{abs(hash(valor))}", data={"acao": acao, "valor": valor or ""})


def _retomar_sessao() -> bool:
    """Ao abrir o site (F5, celular), entra com o código guardado no navegador, se ainda valer.
    Devolve True enquanto ainda decide: nesse meio-tempo aparece a tela de carregamento, não o login."""
    if st.session_state.pop("apagar_sessao_navegador", False):
        _gravar_no_navegador(None)
        return False
    if st.session_state.get("tentou_retomar"):
        return False
    lido = _sessao_navegador(key="sessao_ler", data={"acao": "ler", "valor": ""},
                             on_token_change=lambda: None)
    if lido.token is None:
        return True  # o navegador ainda não respondeu; a resposta roda o site de novo
    chave, token = accounts.read_browser_value(lido.token)
    if _voltar_da_memoria(chave):
        st.session_state.sessao_gravada = lido.token
        st.session_state.tentou_retomar = True
        return False
    if not token:
        st.session_state.tentou_retomar = True
        return False
    # "tentou" só depois do resultado: se esta execução for interrompida no meio, a próxima tenta de novo
    # (o Supabase aceita o mesmo código por alguns segundos depois de trocá-lo)
    try:
        perfil = accounts.restore_session(_cliente_supabase(), token)
    except accounts.AccountError:
        st.session_state.tentou_retomar = True
        st.session_state.aviso = "Não deu para reconectar agora. Atualize a página em instantes ou entre com a senha."
        return False  # o código continua guardado
    st.session_state.tentou_retomar = True
    if perfil is None:
        _gravar_no_navegador(None)  # vencido ou já usado: só limpa; a pessoa entra com a senha
        return False
    _atualizar_sessao_navegador()  # o código novo vai para o navegador antes de qualquer outra coisa
    _iniciar_sessao(perfil)
    return False


def tela_carregando() -> None:
    """Enquanto o navegador diz se há sessão guardada (uma fração de segundo): só a marca, sem o login."""
    st.markdown(f'<div class="dl-carregando"><div class="dl-guardanapo">{visual.wordmark(_tema(), "2.2rem")}'
                '<p>Abrindo sua cozinha...</p></div></div>',
                unsafe_allow_html=True)
    # se o navegador não responder (JavaScript bloqueado), o botão aparece depois de uns segundos
    if st.button("Entrar com e-mail e senha", key="pular_retomada", type="tertiary"):
        st.session_state.tentou_retomar = True
        st.rerun()


def _atualizar_sessao_navegador() -> None:
    """O Supabase troca o código quando renova o acesso: guarda sempre o mais novo, junto com a chave da
    memória do servidor."""
    _lembrar_no_servidor()
    token = accounts.session_token(_cliente_supabase())
    valor = accounts.browser_value(st.session_state.chave_servidor, token) if token else None
    if valor != st.session_state.get("sessao_gravada"):
        _gravar_no_navegador(valor)
        st.session_state.sessao_gravada = valor


# ---------------------------------------------------------------- F5 na hora (D66)

# O F5 abre uma sessão nova do Streamlit, e retomar pelo Supabase custa três idas em sequência (renovar,
# perfil, conversas). Enquanto o servidor está de pé, cada sessão logada fica também na memória dele, sob
# uma chave aleatória que só aquele navegador conhece (guardada junto com o código do Supabase): o F5 volta
# dali na hora, na mesma página. Se o servidor reiniciou, vale o caminho pelo Supabase.
DURACAO_MEMORIA = 24 * 3600  # segundos sem uso até a memória esquecer a sessão
GUARDADOS = ("perfil", "supabase", "conversas", "conversa_id", "chat", "pagina", "cardapios")


@st.cache_resource
def _memoria_do_servidor() -> dict:
    return {}  # chave -> {"expira": instante, "estado": {nome: valor da sessão}}


def _lembrar_no_servidor() -> None:
    chave = st.session_state.setdefault("chave_servidor", secrets.token_urlsafe(24))
    memoria, agora = _memoria_do_servidor(), time.time()
    for velha in [k for k, v in list(memoria.items()) if v["expira"] < agora]:
        memoria.pop(velha, None)
    # guarda as referências: o que muda depois nesses objetos (mensagens, cardápios) já vale para o F5
    memoria[chave] = {"expira": agora + DURACAO_MEMORIA,
                      "estado": {k: st.session_state[k] for k in GUARDADOS if k in st.session_state}}


def _voltar_da_memoria(chave: str | None) -> bool:
    entrada = _memoria_do_servidor().get(chave) if chave else None
    if not entrada or entrada["expira"] < time.time() or "perfil" not in entrada["estado"]:
        return False
    st.session_state.update(entrada["estado"])
    _perfil_da_versao_atual()
    st.session_state.chave_servidor = chave
    if "chat" in entrada["estado"]:  # cópia: outra aba aberta com a mesma conta não escreve nesta conversa
        st.session_state.chat = _novo_chat(list(entrada["estado"]["chat"].mensagens))
    return True


# ---------------------------------------------------------------- entrada (sem login)

def tela_entrada() -> None:
    """Mesa posta (D63): a tigela servida num prato e o acesso num cartão de receita, sobre a toalha."""
    tema = _tema()
    # sem a folha das outras páginas e sem rolar: o CSS reconhece a entrada pela marca .dl-topo-centro
    # (visual.page_css), em vez de um <style> próprio que podia ficar na página depois do login
    st.markdown(f'<div class="dl-topo-centro">{visual.wordmark(tema, "2rem")}</div>', unsafe_allow_html=True)
    prato, acesso = st.columns([1, 0.9], gap="large", vertical_alignment="center")
    with prato:
        st.markdown(
            f'<div class="dl-prato"><div class="dl-disco">{visual.hero_illustration(tema)}</div>'
            '<div class="dl-guardanapo"><h1 class="dl-titulo">Cozinhe com o que você já tem em casa.</h1>'
            '<p class="dl-sub">A DelícIA olha sua geladeira com você e cria receitas na medida da sua dieta.</p>'
            '</div></div>', unsafe_allow_html=True)
    with acesso, st.container(key="cartao_acesso"):
        titulo, subtitulo = TITULOS_ACESSO[st.session_state.get("acesso", "entrar")]
        st.markdown(f'<h2 class="dl-cartao-titulo">{titulo}</h2>', unsafe_allow_html=True)
        st.caption(subtitulo)
        if "aviso" in st.session_state:
            st.success(st.session_state.pop("aviso"))
        if "aviso_erro" in st.session_state:
            st.error(st.session_state.pop("aviso_erro"))
        if st.session_state.get("acesso", "entrar") != "recuperar":
            _botao_google()
        _acesso(_cliente_supabase())


# em Criar conta não vai: o texto de consentimento já avisa (e assim a entrada cabe sem rolar)
_RODAPE_ACESSO = "Projeto acadêmico. Receitas e nutrientes são estimativas da IA. " + AVISO


# ---------------------------------------------------------------- entrar com o Google (D70)
# Só aparece com LOGIN_GOOGLE = "sim" nos Secrets, depois de ligar o Google no Supabase (docs/login_google.md).

_LOGO_GOOGLE = ('<svg viewBox="0 0 48 48" width="20" height="20" aria-hidden="true">'
                '<path fill="#EA4335" d="M24 9.5c3.5 0 6.7 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 '
                '13.2l7.9 6.2C12.5 13.6 17.8 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4'
                'c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.8c4.3-4 6.9-9.9 6.9-17.2z"/><path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-2.9'
                '-.8-4.6s.3-3.2.8-4.6l-7.9-6.2C1 16.6 0 20.2 0 24s1 7.4 2.7 10.8l7.9-6.2z"/><path fill="#34A853" d="M24 48'
                'c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.8c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.2C6.6 42.6 14.6 '
                '48 24 48z"/></svg>')


@st.cache_resource
def _google_pendentes() -> dict:
    return {}  # estado -> (verificador, expira): quem saiu para o Google e ainda não voltou


def _google_ligado() -> bool:
    return os.environ.get("LOGIN_GOOGLE", "").strip().lower() in ("sim", "1", "true")


def _botao_google() -> None:
    """Botão "Entrar com o Google": um link que troca a janela inteira (o Google não abre dentro do quadro
    do Streamlit Cloud). O endereço é montado uma vez por sessão."""
    if not _google_ligado():
        return
    if "google_url" not in st.session_state:
        estado = secrets.token_urlsafe(16)
        volta = os.environ.get("SITE_URL", "https://delicia.streamlit.app").rstrip("/") + f"/?google={estado}"
        try:
            url, verificador = accounts.google_login_url(_cliente_supabase(), volta)
        except accounts.AccountError:
            return  # sem o botão agora; e-mail e senha continuam
        pendentes, agora = _google_pendentes(), time.time()
        for velho in [k for k, (_, expira) in list(pendentes.items()) if expira < agora]:
            pendentes.pop(velho, None)
        pendentes[estado] = (verificador, agora + 15 * 60)
        st.session_state.google_url = url
    st.markdown(f'<a class="dl-google" href="{st.session_state.google_url}" target="_top">{_LOGO_GOOGLE}'
                '<span>Entrar com o Google</span></a><div class="dl-ou"><span>ou</span></div>', unsafe_allow_html=True)


def _voltar_do_google() -> bool:
    """Volta do Google (?google=estado&code=...): entra, ou pede o aceite na primeira vez. True se tratou."""
    estado, codigo = st.query_params.get("google"), st.query_params.get("code")
    if not estado:
        return False
    st.query_params.clear()  # o código vale uma vez: um F5 depois não tenta de novo
    st.session_state.tentou_retomar = True
    pendente = _google_pendentes().pop(estado, None)
    if not codigo or not pendente or pendente[1] < time.time():
        st.session_state.aviso_erro = "Não deu para entrar com o Google (o pedido venceu). Tente de novo."
        return True
    try:
        perfil, usuario = accounts.google_sign_in(_cliente_supabase(), codigo, pendente[0])
    except accounts.AccountError as erro:
        st.session_state.aviso_erro = str(erro)
        return True
    if perfil is None:
        st.session_state.google_usuario = usuario  # primeira vez: falta o aceite (tela_aceite)
        return True
    _atualizar_sessao_navegador()
    _iniciar_sessao(perfil)
    if _perfil_vazio(perfil):
        st.session_state.pagina, st.session_state.cadastro_inicial = "perfil", True
    return True


def tela_aceite() -> None:
    """Primeiro login com o Google: antes de criar o perfil, a pessoa lê e concorda com o uso dos dados."""
    usuario = st.session_state.google_usuario
    st.markdown(f'<div class="dl-topo-centro">{visual.wordmark(_tema(), "2rem")}</div>', unsafe_allow_html=True)
    _, meio, _ = st.columns([1, 2, 1])
    with meio, st.container(key="cartao_acesso"):
        st.markdown('<h2 class="dl-cartao-titulo">Falta só uma coisa</h2>', unsafe_allow_html=True)
        st.caption(f"Você entrou com o Google ({usuario.email}). Antes de começar, leia como a DelícIA usa seus dados.")
        with st.container(height=260):
            st.markdown(TEXTO_CONSENTIMENTO)
        concordo, nao = st.columns(2)
        if concordo.button("Concordo e quero entrar", type="primary", width="stretch"):
            try:
                perfil = accounts.accept_terms(_cliente_supabase(), usuario)
            except accounts.AccountError as erro:
                st.error(str(erro))
                return
            del st.session_state.google_usuario
            _atualizar_sessao_navegador()
            _iniciar_sessao(perfil)
            st.session_state.pagina, st.session_state.cadastro_inicial = "perfil", True
            st.rerun()
        if nao.button("Não concordo", width="stretch"):
            try:
                accounts.sign_out(_cliente_supabase())
            except accounts.AccountError:
                pass
            del st.session_state.google_usuario
            st.session_state.aviso_erro = "Sem o aceite, a conta não é criada. Nenhum dado foi guardado."
            st.rerun()


# Acesso como nos chats conhecidos (D74): o cartão mostra uma coisa por vez. Entrar é o padrão; "Esqueci a
# senha" fica num link discreto embaixo da senha e "Criar conta" num link no pé do cartão.
TITULOS_ACESSO = {
    "entrar": ("Que bom te ver", "Entre para continuar suas receitas."),
    "criar": ("Crie sua conta", "Leva menos de um minuto."),
    "recuperar": ("Recuperar a senha", "Mandamos um código de 6 dígitos para o seu e-mail."),
}


def _ir_para(modo: str) -> None:
    st.session_state.acesso = modo


def _link(rotulo: str, modo: str, chave: str) -> None:
    st.button(rotulo, key=chave, type="tertiary", on_click=_ir_para, args=(modo,))


def _acesso(cliente) -> None:
    modo = st.session_state.get("acesso", "entrar")
    {"entrar": _form_entrar, "criar": _form_criar, "recuperar": _form_recuperar}[modo](cliente)


def _form_entrar(cliente) -> None:
    with st.form("entrar", border=False):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary", width="stretch"):
            try:
                perfil = accounts.sign_in(cliente, email, senha)
            except accounts.AccountError as erro:
                st.error(str(erro))
            else:
                _iniciar_sessao(perfil)
                if _perfil_vazio(perfil):  # primeira vez (ou ainda sem dados): começa pelo cadastro
                    st.session_state.pagina, st.session_state.cadastro_inicial = "perfil", True
                st.rerun()
    _link("Esqueci a senha", "recuperar", "ir_recuperar")
    _link("Não tem conta? **Criar conta**", "criar", "ir_criar")
    st.caption(_RODAPE_ACESSO)


def _form_criar(cliente) -> None:
    with st.form("criar", border=False):
        # dois campos por linha: a entrada cabe na tela sem rolar
        c1, c2 = st.columns(2)
        nome = c1.text_input("Como podemos te chamar?")
        email = c2.text_input("E-mail", key="email_cadastro")
        c3, c4 = st.columns(2)
        senha = c3.text_input(f"Senha (mín. {accounts.SENHA_MINIMA} caracteres)", type="password",
                              key="senha_cadastro")
        confirmacao = c4.text_input("Repita a senha", type="password")
        with st.expander("Como usamos seus dados (leia antes de concordar)", expanded=False):
            st.markdown(TEXTO_CONSENTIMENTO)
        consentiu = st.checkbox("Li e concordo com o uso dos meus dados descrito acima.")
        if st.form_submit_button("Criar conta", type="primary", width="stretch"):
            if senha != confirmacao:
                st.error("As senhas não são iguais.")
            else:
                try:
                    ja_entrou = accounts.sign_up(cliente, email, senha, nome, consentiu)
                except accounts.AccountError as erro:
                    st.error(str(erro))
                else:
                    st.session_state.aviso = ("Conta criada! Agora é só entrar." if ja_entrou else
                                              "Conta criada! Enviamos um e-mail de confirmação. Confirme e depois entre.")
                    _ir_para("entrar")
                    st.rerun()
    _link("Já tem conta? **Entrar**", "entrar", "ir_entrar_criar")


def _form_recuperar(cliente) -> None:
    if "recuperacao_email" not in st.session_state:
        with st.form("pedir_codigo", border=False):
            email = st.text_input("E-mail da conta", key="email_recuperacao")
            if st.form_submit_button("Enviar código", type="primary", width="stretch"):
                try:
                    accounts.send_reset_code(cliente, email)
                except accounts.AccountError as erro:
                    st.error(str(erro))
                else:
                    st.session_state.recuperacao_email = email
                    st.rerun()
    else:
        st.info(f"Se existir uma conta com {st.session_state.recuperacao_email}, enviamos um "
                "código de 6 dígitos para esse e-mail.")
        with st.form("trocar_senha", border=False):
            codigo = st.text_input("Código recebido")
            nova = st.text_input("Nova senha", type="password")
            if st.form_submit_button("Trocar senha", type="primary", width="stretch"):
                try:
                    accounts.reset_with_code(cliente, st.session_state.recuperacao_email, codigo, nova)
                except accounts.AccountError as erro:
                    st.error(str(erro))
                else:
                    st.session_state.pop("recuperacao_email")
                    st.session_state.aviso = "Senha trocada! Entre com a nova senha."
                    _ir_para("entrar")
                    st.rerun()
        if st.button("Usar outro e-mail", type="tertiary"):
            st.session_state.pop("recuperacao_email")
            st.rerun()
    _link("Lembrou a senha? **Entrar**", "entrar", "ir_entrar_recuperar")


# ---------------------------------------------------------------- conversas e barra lateral (D57)

def _conversas() -> list[dict] | None:
    """Lista da barra lateral, buscada uma vez por sessão e mantida em dia localmente."""
    if "conversas" not in st.session_state:
        st.session_state.conversas = accounts.list_conversations(_cliente_supabase(), st.session_state.perfil.id)
    return st.session_state.conversas


def _abrir_conversa(conversa_id: str | None) -> None:
    mensagens = accounts.load_conversation(_cliente_supabase(), conversa_id) if conversa_id else []
    st.session_state.chat = _novo_chat(mensagens)
    st.session_state.conversa_id = conversa_id
    st.session_state.pagina = "chat"


def _salvar_conversa(pergunta: str | None = None) -> None:
    """Guarda a conversa atual na conta e põe no topo da lista da barra lateral. Com `pergunta`, guarda
    também a pergunta que ainda está sendo respondida (não se perde com F5 ou saída no meio)."""
    chat = st.session_state.chat
    mensagens = chat.mensagens + ([{"role": "user", "content": pergunta}] if pergunta else [])
    # título: a última receita que a pessoa abriu (setinha); antes disso, a primeira pergunta
    escolhidas = [nome for m in mensagens for nome in m.get("receitas", {})]
    primeira = next((m["content"] for m in mensagens if m["role"] == "user"), "Conversa")
    titulo = " ".join((escolhidas[-1] if escolhidas else primeira).split())[:60]
    if st.session_state.conversa_id is None:
        st.session_state.conversa_id = str(uuid.uuid4())
    conversa_id = st.session_state.conversa_id
    try:
        avisos = accounts.save_conversation(_cliente_supabase(), st.session_state.perfil.id, conversa_id,
                                            titulo, mensagens)
    except accounts.AccountError as erro:
        avisos = [str(erro)]
    st.session_state.aviso_historico = avisos[0] if avisos else None
    lista = [c for c in (_conversas() or []) if c["id"] != conversa_id]
    st.session_state.conversas = [{"id": conversa_id, "titulo": titulo}] + lista


def barra_lateral() -> None:
    tema = _tema()
    pagina = st.session_state.get("pagina", "chat")
    with st.sidebar:
        st.markdown(visual.wordmark(tema, "1.5rem"), unsafe_allow_html=True)
        if st.button("Nova conversa", icon=":material/edit_square:", type="primary", width="stretch"):
            _abrir_conversa(None)
            st.rerun()
        st.markdown('<p class="dl-rotulo">Conversas</p>', unsafe_allow_html=True)
        conversas = _conversas()
        if conversas is None:
            st.caption("O histórico ainda não está disponível.")
        elif not conversas:
            st.caption("Suas conversas aparecem aqui.")
        for c in conversas or []:
            ativa = pagina == "chat" and c["id"] == st.session_state.get("conversa_id")
            titulo, apagar = st.columns([6, 1], gap=None, vertical_alignment="center")
            if titulo.button(c["titulo"] or "Conversa", key=f"conv_{c['id']}", width="stretch",
                             type="secondary" if ativa else "tertiary"):
                try:
                    _abrir_conversa(c["id"])
                except accounts.AccountError as erro:
                    st.session_state.aviso_historico = str(erro)
                st.rerun()
            if apagar.button("", icon=":material/delete:", key=f"apagar_{c['id']}", type="tertiary",
                             help="Apagar esta conversa"):
                try:
                    accounts.delete_conversation(_cliente_supabase(), c["id"])
                except accounts.AccountError as erro:
                    st.session_state.aviso_historico = str(erro)
                else:
                    st.session_state.conversas = [x for x in conversas if x["id"] != c["id"]]
                    if c["id"] == st.session_state.get("conversa_id"):
                        _abrir_conversa(None)
                st.rerun()
        st.divider()
        for chave, rotulo, icone in (("cardapio", "Cardápio da semana", ":material/calendar_month:"),
                                     ("perfil", "Meu perfil", ":material/person:"),
                                     ("calculos", "Como calculamos", ":material/calculate:"),
                                     ("config", "Configurações", ":material/settings:")):
            if st.button(rotulo, icon=icone, key=f"menu_{chave}", width="stretch",
                         type="secondary" if pagina == chave else "tertiary"):
                st.session_state.pagina = chave
                st.session_state.pop("cadastro_inicial", None)  # saiu do cadastro inicial pelo menu
                st.rerun()


# ---------------------------------------------------------------- página: conversa

def _so_o_resumo(pedacos, guardado: list):
    """Repassa o texto até a marca de detalhes (o resto fica em "ver detalhes"), com as marcas de
    sugestão virando itens de lista. Segura o fim de cada pedaço que pode ser o começo de uma marca,
    para ela nunca aparecer pela metade na tela."""
    texto, mostrado = "", 0
    for pedaco in pedacos:
        guardado.append(pedaco)
        texto += pedaco
        corte = texto.find(MARCA_DETALHES)
        fim = corte if corte >= 0 else max(mostrado, len(texto) - len(MARCA_DETALHES))
        if fim > mostrado:
            yield texto[mostrado:fim].replace(MARCA_RECEITA, "- ")
            mostrado = fim
    corte = texto.find(MARCA_DETALHES)
    fim = corte if corte >= 0 else len(texto)
    if fim > mostrado:
        yield texto[mostrado:fim].replace(MARCA_RECEITA, "- ")


def _resposta(indice: int) -> None:
    """Resposta do assistente: texto curto e cada sugestão com uma setinha que abre o modo de preparo.
    O preparo é pedido ao modelo só quando a pessoa abre, e fica guardado na própria mensagem."""
    chat = st.session_state.chat
    m = chat.mensagens[indice]
    intro, sugestoes, fim = split_suggestions(split_details(m["content"])[0])
    st.markdown(intro)
    pergunta = chat.mensagens[indice - 1]["content"] if indice else ""
    for i, (nome, info) in enumerate(sugestoes):
        chave = f"receita_{st.session_state.get('conversa_id')}_{indice}_{i}"
        rotulo = f"**{nome}**" + (f" · {info}" if info else "")
        with st.expander(rotulo, key=chave, on_change="rerun"):
            receitas = m.setdefault("receitas", {})
            if nome not in receitas and st.session_state.get(chave):
                pedido = (f'A pessoa escolheu a receita "{nome}" ({info}). Contexto, o que ela disse antes: '
                          f'"{pergunta}". Escreva SOMENTE essa receita: ingredientes com quantidades (para o '
                          "número de pessoas da conversa; se não souber, 2 pessoas, e diga), modo de preparo "
                          "numerado, tempo e a estimativa de nutrientes por porção. Comece direto pelo nome da "
                          "receita, sem cumprimentar e sem listar outras sugestões. "
                          f"Não use as marcas {MARCA_DETALHES} nem {MARCA_RECEITA}.")
                try:
                    with st.spinner("Escrevendo o modo de preparo..."):
                        pedacos = chat.stream_text(pedido)
                        primeiro = next(pedacos, "")
                    receitas[nome] = st.write_stream(_junta(primeiro, pedacos)).strip()
                except Exception as erro:  # noqa: BLE001
                    st.error(_mensagem_de_erro_do_modelo(erro))
                    continue
                _salvar_conversa()
                st.rerun()  # a barra lateral mostra o título novo (o nome da receita)
            elif nome in receitas:
                st.markdown(receitas[nome])
                _video_da_receita(nome, chave)
            if nome in receitas:
                alertas = chat.alerts(receitas[nome], com_modo=True)
                if alertas:
                    st.warning("Atenção ao seu perfil: " + "; ".join(alertas) + ". Confira os rótulos.",
                               icon=":material/warning:")
                _maca(m, nome, f"{st.session_state.get('conversa_id')}_{indice}_{i}")
    if fim:
        st.markdown(fim)
    _rodape_da_resposta(m["content"])


# ---------------------------------------------------------------- Modo Pro: vídeo da receita (D71)

@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def _buscar_video(nome: str, chave: str | None) -> dict | None:
    """Uma busca por nome de receita a cada 7 dias, para todo mundo: a cota grátis do YouTube é de ~100
    buscas por dia."""
    return videos.find_video(nome, chave)


def _video_da_receita(nome: str, sufixo: str) -> None:
    """No Modo Pro, um vídeo de alguém fazendo a receita (o mais relevante do YouTube com o mesmo nome).
    Sem a chave do YouTube ou sem resultado, o link da busca. Fora do Pro, um convite discreto."""
    if not st.session_state.perfil.pro:
        st.caption(":material/smart_display: Com o **Modo Pro** (em Configurações, grátis por enquanto) aparece um "
                   "vídeo de alguém fazendo esta receita.")
        return
    video = _buscar_video(nome, os.environ.get("YOUTUBE_API_KEY"))
    with st.container(key=f"video_{sufixo}"):
        st.markdown("**:material/smart_display: Veja alguém fazendo**")
        if video:
            st.video(video["url"])
            st.caption(f"{video['titulo']} · {video['canal']}. Vídeo do YouTube de uma receita com o mesmo nome: "
                       "quantidades e passos podem ser diferentes dos de cima.")
        else:
            st.link_button("Ver vídeos desta receita no YouTube", videos.search_link(nome),
                           icon=":material/open_in_new:")


def _maca(m: dict, nome: str, sufixo: str) -> None:
    """Maçã no fim da receita (D58): tocar registra 1 porção no dia (a maçã fica mordida); tocar de
    novo desfaz. Os nutrientes da porção são pedidos ao modelo uma vez e guardados na mensagem."""
    comidas = m.setdefault("comidas", {})  # nome da receita -> id do registro na tabela consumo
    nutrientes = m.setdefault("nutrientes", {})
    comeu = nome in comidas
    maca, texto = st.columns([1, 7], vertical_alignment="center")
    tocou = maca.button("", key=f"{'mordida' if comeu else 'maca'}_{sufixo}",
                        help="Desfazer: não comi" if comeu else "Comi 1 porção")
    aviso = st.session_state.pop(f"aviso_maca_{sufixo}", None)
    if aviso:
        texto.success(aviso, icon=":material/check_circle:")
    elif comeu:
        kcal = nutrientes.get(nome, {}).get("kcal")
        texto.caption(f"Você comeu 1 porção{f' (cerca de {kcal:.0f} kcal)' if kcal else ''}. "
                      "Está no seu perfil. Toque na maçã para desfazer.")
    else:
        texto.caption("Comeu? Toque na maçã para registrar 1 porção no seu perfil.")
    if not tocou:
        return
    perfil: accounts.Perfil = st.session_state.perfil
    try:
        if comeu:
            accounts.delete_consumption(_cliente_supabase(), comidas[nome])
            del comidas[nome]
        else:
            if nome not in nutrientes:
                with st.spinner("Calculando os nutrientes da porção..."):
                    nutrientes[nome] = consumo.estimate(st.session_state.chat, nome, m["receitas"][nome])
            comidas[nome] = accounts.add_consumption(_cliente_supabase(), perfil.id, consumo.today().isoformat(),
                                                     nome, nutrientes[nome])
    except (accounts.AccountError, ValueError) as erro:
        st.error(str(erro))
        return
    except Exception as erro:  # noqa: BLE001 - falha do modelo
        st.error(_mensagem_de_erro_do_modelo(erro))
        return
    kcal = nutrientes.get(nome, {}).get("kcal")
    st.session_state[f"aviso_maca_{sufixo}"] = (
        f"Registrado no seu perfil: 1 porção de {nome}{f' ({kcal:.0f} kcal)' if kcal else ''}. Veja em Meu perfil."
        if nome in comidas else "Registro desfeito: tiramos essa porção do seu perfil.")
    _salvar_conversa()
    st.rerun()


def _rodape_da_resposta(texto: str) -> None:
    """Detalhes recolhidos e avisos do perfil (conferidos pelo código, D56)."""
    _, detalhes = split_details(texto)
    if detalhes:
        with st.expander("Ver detalhes"):
            st.markdown(detalhes)
    alertas = st.session_state.chat.alerts(texto, com_modo=True)
    if alertas:
        st.warning("Atenção ao seu perfil: " + "; ".join(alertas) + ". Confira os rótulos.",
                   icon=":material/warning:")


# categorias que a pessoa marca acima da caixa de texto (D73); vão junto com a mensagem, no fim ("Só: ...")
CATEGORIAS = ("Doce", "Salgado", "Lanche", "Refeição completa", "Sopa", "Rápida (até 30 min)", "Brasileira",
              "Japonesa", "Italiana", "Vegetariana")


def com_categorias(pedido: str, categorias: list[str] | None) -> str:
    return f"{pedido}\n\n*Só: {', '.join(categorias)}*" if categorias else pedido


# os dois jeitos de pedir: (título, exemplo que vai para a caixa de texto ao tocar, ícone)
JEITOS_DE_PEDIR = (
    ("Tenho estes ingredientes", "Tenho frango, batata e cebola. O que dá para fazer?", ":material/kitchen:"),
    ("Quero uma receita", "Me passa a receita de bolo de cenoura.", ":material/menu_book:"),
)


def _boas_vindas(perfil: accounts.Perfil) -> None:
    """Conversa vazia: a tigela, a pergunta e os dois jeitos de começar (cada um com um exemplo que dá
    para tocar)."""
    nome = f", {perfil.nome.split()[0]}" if perfil.nome else ""
    st.markdown(f'<div class="dl-boasvindas"><div class="dl-boasvindas-tigela">{visual.hero_illustration(_tema())}</div>'
                f'<h2>O que vamos cozinhar hoje{nome}?</h2>'
                '<p>Conte o que tem em casa e eu sugiro receitas, ou diga o nome de um prato e eu passo a receita '
                'completa, na medida da sua dieta.</p></div>', unsafe_allow_html=True)
    for i, (coluna, (titulo, exemplo, icone)) in enumerate(zip(st.columns(2), JEITOS_DE_PEDIR)):
        # só põe o exemplo na caixa de texto, para a pessoa mudar o que quiser antes de enviar
        coluna.button(f"**{titulo}**  \n{exemplo}", icon=icone, key=f"inicio_{i}", width="stretch",
                      on_click=lambda texto=exemplo: st.session_state.update(caixa_chat=texto))


def pagina_chat() -> None:
    chat = st.session_state.chat
    perfil: accounts.Perfil = st.session_state.perfil
    with st.container():  # sempre ocupa o mesmo lugar, com ou sem aviso (ver main)
        if st.session_state.get("aviso_historico"):
            st.warning(st.session_state.aviso_historico, icon=":material/history:")
        if "aviso_perfil" in st.session_state:  # vindo do cadastro inicial
            st.success(st.session_state.pop("aviso_perfil"))
    if not chat.mensagens:
        _boas_vindas(perfil)
    for indice, m in enumerate(chat.mensagens):
        with st.chat_message(m["role"], avatar="🥗" if m["role"] == "assistant" else ":material/person:"):
            if m["role"] == "assistant":
                _resposta(indice)
            else:
                st.markdown(m["content"])
    # um toque num dos exemplos da tela inicial vale como se a pessoa tivesse escrito
    with st.bottom:  # logo acima da caixa de texto, sempre à vista
        # filtros numa caixa só: o botão "Filtros" abre as opções; ao lado, os que estão marcados.
        # O rótulo do botão não muda: se mudasse, a caixa fecharia a cada opção marcada.
        with st.container(key="filtros_chat", horizontal=True, vertical_alignment="center"):
            with st.popover("Filtros", icon=":material/tune:"):
                modo = st.pills("Mostrar só", [titulo for titulo, _ in MODOS.values()], key="modo_chat")
                categorias = st.pills("Categorias", CATEGORIAS, selection_mode="multi", key="categorias_chat")
            ativos = ([modo] if modo else []) + list(categorias or [])
            if ativos:
                st.caption(", ".join(ativos))
    chat.modo = next((chave for chave, (titulo, _) in MODOS.items() if titulo == modo), None)
    pedido = st.chat_input("Diga o que tem em casa ou o nome de uma receita", key="caixa_chat")         or st.session_state.pop("pedido_pendente", None)  # ex.: o botão de sucos da hidratação
    if pedido:
        pedido = com_categorias(pedido, categorias)
    if not pedido:
        return
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(pedido)
    _salvar_conversa(pedido)
    with st.chat_message("assistant", avatar="🥗"):
        guardado = []
        try:
            with st.spinner("Pensando..."):
                pedacos = _so_o_resumo(chat.send_stream(pedido), guardado)
                primeiro = next(pedacos, "")
            st.write_stream(_junta(primeiro, pedacos))
        except Exception as erro:  # noqa: BLE001 - qualquer falha do modelo vira aviso na tela
            st.markdown(_mensagem_de_erro_do_modelo(erro))
            return
        _rodape_da_resposta(chat.mensagens[-1]["content"])
    _salvar_conversa()
    st.rerun()  # a barra lateral mostra a conversa nova no topo


def _junta(primeiro: str, resto):
    yield primeiro
    yield from resto


# ---------------------------------------------------------------- página: perfil

def _painel_estimativa(perfil: accounts.Perfil) -> None:
    est = estimate(perfil.peso_kg, perfil.altura_cm, perfil.ano_nascimento, perfil.sexo,
                   perfil.atividade, perfil.objetivo)
    metas = daily_targets(est, perfil.peso_kg, perfil.kcal_nutricionista, perfil.proteina_nutricionista)
    st.markdown("#### Suas metas do dia")
    a, b, c, d = st.columns(4)
    a.metric("IMC", f"{est.imc:.1f}".replace(".", ",") if est.imc else "—",
             help="Índice de massa corporal: peso ÷ altura². Classificação da OMS para adultos.")
    if est.classificacao_imc:
        a.caption(est.classificacao_imc.capitalize())
    b.metric("Gasto diário", f"{est.gasto_diario} kcal" if est.gasto_diario else "—",
             help="Equação de Mifflin-St Jeor multiplicada pelo nível de atividade.")
    c.metric("Meta de energia", f"{metas.kcal} kcal" if metas.kcal else "—",
             help="A do seu nutricionista, se você preencheu. Senão, pela fórmula: perder, 500 kcal a menos "
                  "por dia, com piso mínimo; ganhar, 300 kcal a mais.")
    d.metric("Meta de proteína", f"{metas.proteina_g} g" if metas.proteina_g else "—",
             help="A do seu nutricionista, se você preencheu. Senão, 0,8 g por kg de peso por dia.")
    agua, agua_referencia = water_goal(perfil.peso_kg, perfil.atividade)
    e = st.columns(4)[0]  # segunda linha: com 5 colunas os números ficavam cortados
    e.metric("Meta de água", f"{agua / 1000:.2f} L".replace(".", ","),
             help="35 ml por kg de peso por dia, mais um extra pela atividade física. Sem o peso, 2 litros.")
    e.caption("Referência de 2 litros" if agua_referencia else "Estimada por fórmula")
    for coluna, fonte in ((c, metas.fonte_kcal), (d, metas.fonte_proteina)):
        if fonte:
            coluna.caption(FONTES[fonte].capitalize())
    if metas.fonte_kcal == "nutricionista" and est.meta_kcal and est.meta_kcal != metas.kcal:
        st.caption(f"Pela fórmula, a meta seria de cerca de {est.meta_kcal} kcal. Vale a do nutricionista.")
    for aviso in est.avisos if metas.fonte_kcal != "nutricionista" else []:
        st.info(aviso)
    if "nutricionista" not in (metas.fonte_kcal, metas.fonte_proteina):
        st.caption("Tem metas passadas por um nutricionista? Preencha em **Metas do seu nutricionista**, "
                   "no fim do formulário: elas passam a valer no lugar da fórmula.")
    st.caption(AVISO + " Veja **Como calculamos**, no menu.")


COPOS_ML = (("Copo", 200), ("Grande", 300), ("Garrafa", 500))


def _painel_agua(perfil: accounts.Perfil) -> None:
    """Hidratação (D60): meta de água do dia (peso e atividade), o quanto já bebeu e botões para registrar.
    A água fica na tabela `consumo` (receita "Água"), então não precisa de SQL novo."""
    st.markdown("#### Hidratação")
    meta, referencia = water_goal(perfil.peso_kg, perfil.atividade)
    registros = accounts.list_consumption(_cliente_supabase(), perfil.id, consumo.today().isoformat())
    if registros is None:
        st.info(accounts.AVISO_SEM_TABELA_CONSUMO)
        return
    copos = [r for r in registros if consumo.is_water(r)]
    bebeu = consumo.water_ml(copos)
    st.progress(min(bebeu / meta, 1.0), text=f"{bebeu:.0f} de {meta} ml hoje"
                + (" · meta batida!" if bebeu >= meta else ""))
    colunas = st.columns(len(COPOS_ML) + 1)
    for coluna, (nome, ml) in zip(colunas, COPOS_ML):
        if coluna.button(f"{nome} {ml} ml", key=f"agua_{ml}", icon=":material/water_drop:", width="stretch"):
            try:
                accounts.add_consumption(_cliente_supabase(), perfil.id, consumo.today().isoformat(),
                                         consumo.AGUA, {"agua_ml": ml})
            except accounts.AccountError as erro:
                st.error(str(erro))
            else:
                st.rerun()
    if colunas[-1].button("Desfazer", key="agua_desfazer", icon=":material/undo:", width="stretch",
                          disabled=not copos):
        try:
            accounts.delete_consumption(_cliente_supabase(), copos[-1]["id"])
        except accounts.AccountError as erro:
            st.error(str(erro))
        else:
            st.rerun()
    st.caption(("Meta de referência (2 litros): preencha o peso no perfil para uma meta sua. "
                if referencia else f"Meta pelo seu peso ({perfil.peso_kg:.0f} kg: 35 ml por kg) e pela atividade. ")
               + "Estimativa geral; quem tem doença nos rins ou no coração deve seguir o médico.")
    if st.button("Sugerir sucos e bebidas", key="sugerir_sucos", icon=":material/local_drink:"):
        st.session_state.modo_chat = MODOS["bebidas"][0]
        st.session_state.pedido_pendente = "Sugira sucos e bebidas para eu me hidratar hoje."
        st.session_state.pagina = "chat"
        st.rerun()


def _painel_consumo(perfil: accounts.Perfil) -> None:
    """O que a pessoa comeu (maçãs das receitas, D58): hoje, últimos 7 e 30 dias."""
    st.markdown("#### O que você comeu")
    if "aviso_consumo" in st.session_state:
        st.success(st.session_state.pop("aviso_consumo"))
    periodo = st.segmented_control("Período", list(consumo.PERIODOS), format_func=lambda p: consumo.PERIODOS[p][0],
                                   default="hoje", key="periodo_consumo", label_visibility="collapsed") or "hoje"
    registros = accounts.list_consumption(_cliente_supabase(), perfil.id,
                                          consumo.period_start(periodo).isoformat())
    if registros is None:
        st.info(accounts.AVISO_SEM_TABELA_CONSUMO)
        return
    registros = [r for r in registros if not consumo.is_water(r)]  # a água tem painel próprio
    if not registros:
        st.caption("Nada registrado neste período. Ao abrir uma receita no chat, toque na maçã quando comer.")
        return
    soma = consumo.totals(registros)
    dias = len({r["dia"] for r in registros})
    metas = _metas(perfil)
    for coluna, chave in zip(st.columns(len(consumo.PRINCIPAIS)), consumo.PRINCIPAIS):
        rotulo, unidade = consumo.NUTRIENTES[chave]
        meta = {"kcal": metas.kcal, "proteina_g": metas.proteina_g}.get(chave) if periodo == "hoje" else None
        coluna.metric(f"{rotulo} ({unidade})", consumo.format_value(soma[chave]), delta_color="off",
                      delta=f"meta {meta}" if meta else None, delta_arrow="off")  # mesmo jeito do cardápio
        if periodo != "hoje":
            coluna.caption(f"média de {consumo.format_value(soma[chave] / dias)} {unidade} por dia")
    if periodo != "hoje":
        st.caption(f"Médias dos {dias} dia(s) com registro.")
    with st.expander("Vitaminas, minerais e fibras"):
        st.dataframe([{"Nutriente": rotulo, "Total": f"{consumo.format_value(soma[chave])} {unidade}",
                       **({"Média por dia": f"{consumo.format_value(soma[chave] / dias)} {unidade}"}
                          if periodo != "hoje" else {})}
                      for chave, (rotulo, unidade) in consumo.NUTRIENTES.items() if chave not in consumo.PRINCIPAIS],
                     hide_index=True, width="stretch")
    with st.expander(f"Receitas registradas ({len(registros)})"):
        for r in reversed(registros):
            dia = date.fromisoformat(r["dia"]).strftime("%d/%m")
            kcal = (r.get("nutrientes") or {}).get("kcal") or 0
            texto, repetir = st.columns([6, 1], vertical_alignment="center")
            texto.markdown(f"{dia} · {r['receita']} · {kcal:.0f} kcal")
            if repetir.button("", icon=":material/replay:", key=f"repetir_{r['id']}", type="tertiary",
                              help="Comi de novo hoje (registra mais 1 porção)"):
                try:  # mesma receita e mesmos nutrientes, com a data de hoje
                    accounts.add_consumption(_cliente_supabase(), perfil.id, consumo.today().isoformat(),
                                             r["receita"], r.get("nutrientes") or {})
                except accounts.AccountError as erro:
                    st.error(str(erro))
                else:
                    st.session_state.aviso_consumo = f"{r['receita']}: mais 1 porção registrada hoje."
                    st.rerun()
    st.caption("Nutrientes estimados pela IA para 1 porção de cada receita.")


def pagina_perfil() -> None:
    perfil: accounts.Perfil = st.session_state.perfil
    inicial = st.session_state.get("cadastro_inicial")
    if inicial:
        st.subheader(f"Boas-vindas{', ' + perfil.nome.split()[0] if perfil.nome else ''}!")
        st.markdown("Antes de começar, conte um pouco sobre você. Com esses dados a DelícIA evita o que "
                    "você não pode comer e calcula sua meta de calorias. Tudo é opcional e dá para mudar "
                    "depois em **Meu perfil**.")
        if st.button("Pular por agora", icon=":material/skip_next:"):
            st.session_state.pop("cadastro_inicial")
            st.session_state.pagina = "chat"
            st.rerun()
    else:
        st.subheader("Meu perfil")
        _painel_agua(perfil)
        st.divider()
        _painel_consumo(perfil)
        st.divider()
        _painel_estimativa(perfil)
    with st.form("form_perfil"):  # a chave "perfil" já é usada na sessão
        st.markdown("**Sobre você**")
        c1, c2, c3 = st.columns(3)
        nome = c1.text_input("Nome", value=perfil.nome)
        ano = c2.number_input("Ano de nascimento", min_value=1900, max_value=date.today().year,
                              value=perfil.ano_nascimento, step=1, placeholder="Ex.: 2000")
        # "" (e não None) é o "Prefiro não informar": None em opções atrapalha o Streamlit
        sexos = ["", *SEXOS]
        sexo = c3.selectbox("Sexo biológico", sexos, index=sexos.index(perfil.sexo or ""),
                            format_func=lambda s: SEXOS.get(s, "Prefiro não informar"), placeholder=ESCOLHA,
                            help="Usado só na fórmula de gasto de energia.")
        st.markdown("**Corpo e rotina**")
        c4, c5, c6 = st.columns(3)
        # float(): o Streamlit recusa misturar inteiro (ex.: 178) com limites decimais
        altura = c4.number_input("Altura (cm)", min_value=100.0, max_value=250.0, step=0.5,
                                 value=None if perfil.altura_cm is None else float(perfil.altura_cm),
                                 placeholder="Ex.: 170")
        peso = c5.number_input("Peso (kg)", min_value=30.0, max_value=300.0, step=0.1,
                               value=None if perfil.peso_kg is None else float(perfil.peso_kg),
                               placeholder="Ex.: 68,5")
        atividades = ["", *ATIVIDADES]
        atividade = c6.selectbox("Nível de atividade", atividades, index=atividades.index(perfil.atividade or ""),
                                 format_func=lambda a: ATIVIDADES[a][0] if a else "Prefiro não informar",
                                 placeholder=ESCOLHA)
        st.markdown("**Objetivo e restrições**")
        objetivo = st.radio("Objetivo", options=list(OBJETIVOS), format_func=OBJETIVOS.get,
                            index=list(OBJETIVOS).index(perfil.objetivo or ""), horizontal=True)
        restricoes = st.multiselect(
            "Alergias, intolerâncias e dieta", options=list(OPCOES_PERFIL),
            default=perfil.restricoes, format_func=lambda o: OPCOES_PERFIL[o][0],
            placeholder="Escolha uma ou mais", select_all=False,  # sem os textos padrão em inglês
            help="A IA evita esses itens, e cada resposta é conferida: o que aparecer vem com aviso.")
        st.markdown("**Preferências**")
        p1, p2 = st.columns([2, 1])
        nao_gosta = p1.text_input("Não gosto de", value=perfil.nao_gosta, max_chars=accounts.MAX_NAO_GOSTA,
                                  placeholder="Ex.: fígado, coentro, jiló",
                                  help="Separe por vírgula. A IA evita, e o que aparecer vem com aviso.")
        orcamentos = ["", *accounts.ORCAMENTOS]
        orcamento = p2.selectbox("Orçamento", orcamentos, index=orcamentos.index(perfil.orcamento or ""),
                                 format_func=lambda o: accounts.ORCAMENTOS.get(o, "Prefiro não informar"),
                                 placeholder=ESCOLHA)
        st.markdown("**Metas do seu nutricionista (opcional)**")
        st.caption("Se um nutricionista passou metas para você, preencha: os pratos e os cardápios passam a "
                   "seguir esses números, no lugar da estimativa por fórmula.")
        n1, n2 = st.columns(2)
        kcal_nutri = n1.number_input("Energia (kcal por dia)", min_value=accounts.KCAL_NUTRICIONISTA[0],
                                     max_value=accounts.KCAL_NUTRICIONISTA[1], step=50,
                                     value=perfil.kcal_nutricionista, placeholder="Ex.: 1800")
        proteina_nutri = n2.number_input("Proteína (g por dia)", min_value=accounts.PROTEINA_NUTRICIONISTA[0],
                                         max_value=accounts.PROTEINA_NUTRICIONISTA[1], step=5,
                                         value=perfil.proteina_nutricionista, placeholder="Ex.: 90")
        if st.form_submit_button("Salvar perfil", type="primary"):
            novo = accounts.Perfil(
                id=perfil.id, nome=nome, objetivo=objetivo or None, restricoes=restricoes,
                ano_nascimento=int(ano) if ano else None, sexo=sexo or None,
                altura_cm=float(altura) if altura else None, peso_kg=float(peso) if peso else None,
                atividade=atividade or None, nao_gosta=nao_gosta.strip(), orcamento=orcamento or None,
                kcal_nutricionista=int(kcal_nutri) if kcal_nutri else None,
                proteina_nutricionista=int(proteina_nutri) if proteina_nutri else None, pro=perfil.pro)
            try:
                avisos = accounts.save_profile(_cliente_supabase(), novo)
            except accounts.AccountError as erro:
                st.error(str(erro))
            else:
                st.session_state.perfil = novo
                st.session_state.chat = _novo_chat(st.session_state.chat.mensagens)
                st.session_state.aviso_perfil = "Perfil salvo. As próximas sugestões já seguem o perfil."
                if st.session_state.pop("cadastro_inicial", None):
                    st.session_state.pagina = "chat"  # cadastro feito: vai direto para a conversa
                st.session_state.alertas_perfil = avisos
                st.rerun()
    if "aviso_perfil" in st.session_state:
        st.success(st.session_state.pop("aviso_perfil"))
    for alerta in st.session_state.pop("alertas_perfil", []):
        st.warning(alerta)


# ---------------------------------------------------------------- página: como calculamos

TEXTO_CALCULOS = """
#### De onde vêm as suas metas

1. **Do seu nutricionista.** Se você preencheu em **Meu perfil** a energia (kcal por dia) e a proteína
   (g por dia) que ele passou, a DelícIA usa esses números em tudo: nas receitas do chat, no cardápio
   da semana e no que você comeu. Eles valem no lugar das fórmulas abaixo.
2. **De fórmulas**, quando não há metas do nutricionista e os dados do corpo estão completos:
   - **Gasto em repouso:** equação de Mifflin-St Jeor (1990): 10 × peso (kg) + 6,25 × altura (cm)
     − 5 × idade, + 5 para homens ou − 161 para mulheres.
   - **Gasto do dia:** o gasto em repouso vezes o fator do nível de atividade (1,2 a 1,9).
   - **Meta para o objetivo:** perder peso, 500 kcal a menos por dia, nunca abaixo de 1.200 kcal
     (mulheres) ou 1.500 kcal (homens); ganhar peso, 300 kcal a mais (convenção moderada, sem
     diretriz oficial).
   - **Proteína:** 0,8 g por kg de peso por dia, a recomendação para adultos (Institute of Medicine,
     2005).
   - **Água:** 35 ml por kg de peso por dia, mais 0 a 800 ml conforme a atividade física (entre 1,5 e
     5 litros); sem o peso, a referência de 2 litros. Altura e idade não mudam essa conta.
   - **IMC:** peso ÷ altura², com a classificação da OMS para adultos.
   - Só calculamos para maiores de 18 anos.
3. **Da referência da Anvisa** (2.000 kcal e 50 g de proteína por dia), quando faltam dados.

#### Como as metas viram pratos

A meta do dia é dividida entre as refeições do cardápio (por exemplo, almoço 35% e jantar 30%). Cada
prato é pedido à IA com a meta da refeição dele. Um dia fica **dentro da meta** quando a energia está
a até 10% da meta e a proteína chega a pelo menos 90% dela.

#### Os nutrientes são estimativas

Os nutrientes dos pratos e das receitas são calculados pela IA (Gemini) e podem ter erros. As quantidades reais
dependem dos ingredientes, das marcas e do preparo.
"""


def pagina_calculos() -> None:
    st.subheader("Como calculamos")
    st.warning(AVISO, icon=":material/info:")
    metas = _metas(st.session_state.perfil)
    if metas.kcal or metas.proteina_g:
        partes = [f"**{metas.kcal} kcal** ({FONTES[metas.fonte_kcal]})" if metas.kcal else "",
                  f"**{metas.proteina_g} g de proteína** ({FONTES[metas.fonte_proteina]})" if metas.proteina_g else ""]
        st.markdown("Suas metas agora: " + " e ".join(x for x in partes if x) + ".")
    st.markdown(TEXTO_CALCULOS)


# ---------------------------------------------------------------- página: configurações

def pagina_config() -> None:
    st.subheader("Configurações")
    perfil: accounts.Perfil = st.session_state.perfil
    with st.container(key="painel_pro"):
        ligado = st.toggle("**Modo Pro**", value=perfil.pro, key="toggle_pro",
                           help="Grátis por enquanto. No futuro, o Modo Pro será pago.")
        st.caption("Mostra um vídeo de alguém fazendo cada receita que você abre, no chat e no cardápio. "
                   "Grátis por enquanto; no futuro será um plano pago.")
        if ligado != perfil.pro:
            try:
                avisos = accounts.set_pro(_cliente_supabase(), perfil.id, ligado)
            except accounts.AccountError as erro:
                st.error(str(erro))
            else:
                perfil.pro = ligado
                for aviso in avisos:
                    st.warning(aviso)
                if not avisos:
                    st.toast("Modo Pro ligado." if ligado else "Modo Pro desligado.", icon=":material/check_circle:")
    st.caption("Modo claro ou escuro: menu ⋮ no canto superior direito, Light (claro) ou Dark (escuro).")
    if st.button("Sair da conta", icon=":material/logout:"):
        try:
            accounts.sign_out(_cliente_supabase())
        except accounts.AccountError:
            pass  # mesmo sem resposta do Supabase, a sessão some deste navegador
        finally:
            _encerrar_sessao()
        st.rerun()
    st.divider()
    with st.expander("Apagar minha conta"):
        st.write("Apaga sua conta e todos os seus dados: perfil, conversas e cardápios. Não dá para desfazer.")
        confirmacao = st.text_input("Para confirmar, digite APAGAR")
        if st.button("Apagar conta e dados", disabled=confirmacao.strip() != "APAGAR"):
            try:
                accounts.delete_account(_cliente_supabase())
            except Exception:  # noqa: BLE001
                st.error("Não foi possível apagar agora. Tente de novo em instantes.")
            else:
                _encerrar_sessao()
                st.session_state.aviso = "Sua conta e todos os seus dados foram apagados."
                st.rerun()


# ---------------------------------------------------------------- página: cardápio (D51, D56)

# Cada cardápio da conta: {"id", "nome", "refeicoes" (formato de REFEICOES), "plano" (dict ou None)}.
# Todos ficam numa linha só da tabela cardapios.

def _novo_cardapio(nome: str) -> dict:
    return {"id": uuid.uuid4().hex[:8], "nome": nome, "refeicoes": dict(REFEICOES), "plano": None}


def _salvar_cardapios() -> None:
    """Guarda todos os cardápios na conta; avisos e erros aparecem na próxima exibição da página."""
    dados = {"versao": 3, "cardapios": [
        {"id": c["id"], "nome": c["nome"], "refeicoes": config_to_json(c["refeicoes"]), "plano": c["plano"]}
        for c in st.session_state.cardapios]}
    try:
        st.session_state.alertas_cardapio = accounts.save_menu(_cliente_supabase(), st.session_state.perfil.id,
                                                               dados)
    except accounts.AccountError as erro:
        st.session_state.alertas_cardapio = [str(erro)]


def _carregar_cardapios() -> None:
    if st.session_state.get("cardapios"):
        return
    dados = accounts.load_menu(_cliente_supabase(), st.session_state.perfil.id) or {}
    # versão 1 (um cardápio só) vira o "Cardápio 1"; planos da base antiga (versões 1 e 2) são descartados
    salvos = dados.get("cardapios", []) if "cardapios" in dados else \
        ([{"nome": "Cardápio 1", "refeicoes": dados.get("refeicoes"), "plano": dados}] if dados else [])
    lista = []
    for n, salvo in enumerate(salvos, start=1):
        c = _novo_cardapio(str(salvo.get("nome") or f"Cardápio {n}"))
        c["id"] = salvo.get("id") or c["id"]
        try:
            c["refeicoes"] = config_from_json(salvo.get("refeicoes"))
        except (ValueError, TypeError):
            pass  # refeições estragadas: volta ao padrão
        c["plano"] = restore(salvo.get("plano"))
        lista.append(c)
    st.session_state.cardapios = lista or [_novo_cardapio("Cardápio 1")]


TIPO_ROTULO = {"leve": "Leve (café, lanche, ceia)", "completa": "Completa (prato principal + acompanhamento)"}


def _editar_cardapio(c: dict, lugar=None) -> None:
    """Nome do cardápio e refeições: renomear, tirar e adicionar. Com `lugar`, abre num botão (popover) ali,
    para não ocupar uma linha da página."""
    caixa = (lugar.popover("Refeições", icon=":material/tune:", width="stretch") if lugar is not None else
             st.expander("Nome e refeições deste cardápio", icon=":material/tune:", expanded=True))
    with caixa, st.form(f"refeicoes_{c['id']}", clear_on_submit=True):
        nome = st.text_input("Nome do cardápio", value=c["nome"], max_chars=40)
        editadas = {}
        for chave, (rotulo, peso, tipo) in c["refeicoes"].items():
            a, b, t = st.columns([3, 3, 1], vertical_alignment="bottom")
            novo = a.text_input("Refeição", value=rotulo, max_chars=30, key=f"rot_{c['id']}_{chave}")
            b.caption(TIPO_ROTULO[tipo])
            if not t.checkbox("Tirar", key=f"tirar_{c['id']}_{chave}"):
                editadas[chave] = (novo.strip(), peso, tipo)
        a, b = st.columns([3, 3])
        nova = a.text_input("Adicionar refeição (deixe vazio para não adicionar)", placeholder="Ex.: Ceia",
                            max_chars=30, key=f"nova_{c['id']}")
        tipo = b.selectbox("Tipo", list(TIPOS), format_func=TIPO_ROTULO.get, key=f"tipo_{c['id']}")
        if not st.form_submit_button("Salvar mudanças"):
            return
        if nova.strip():
            editadas[f"extra_{uuid.uuid4().hex[:6]}"] = (nova.strip(), PESO_NOVA[tipo], tipo)
        rotulos = [r for r, _, _ in editadas.values()]
        if not nome.strip():
            st.error("Dê um nome ao cardápio.")
        elif not editadas:
            st.error("O cardápio precisa de pelo menos uma refeição.")
        elif not all(rotulos) or len({r.casefold() for r in rotulos}) != len(rotulos):
            st.error("Cada refeição precisa de um nome, sem repetir.")
        else:
            c["nome"] = nome.strip()
            if c["plano"] and editadas.keys() != c["refeicoes"].keys():
                c["plano"] = None  # outras refeições: o cardápio precisa ser gerado de novo
                st.session_state.aviso_cardapio = "Refeições mudaram: clique em Gerar cardápio de novo."
            elif c["plano"]:  # só nomes: troca no cardápio gerado
                c["plano"]["refeicoes"] = config_to_json(editadas)
            c["refeicoes"] = editadas
            _salvar_cardapios()
            st.rerun()


def _receita_do_prato(c: dict, dia: int, prato: dict) -> None:
    """Receita completa, pedida ao modelo só quando a pessoa abre (e guardada no cardápio)."""
    if not prato.get("receita"):
        kcal, proteina = meal_goals(c["plano"])[prato["chave"]]
        meta = f"cerca de {kcal} kcal" + (f" e {proteina} g de proteína" if proteina else "")
        pedido = (f'Receita completa de "{prato["prato"]}" para 1 pessoa (porção: {prato["porcao"]}, '
                  f"meta da refeição: {meta}; acerte as quantidades para chegar perto dela): "
                  "ingredientes com quantidades, modo de preparo numerado, tempo e a estimativa de "
                  f"nutrientes da porção. Não use a marca {MARCA_DETALHES}.")
        try:
            with st.spinner("Escrevendo a receita..."):
                prato["receita"] = st.session_state.chat.generate_text(pedido)
        except Exception as erro:  # noqa: BLE001
            st.error(_mensagem_de_erro_do_modelo(erro))
            return
        _salvar_cardapios()
    st.markdown(prato["receita"].replace(MARCA_DETALHES, ""))
    _video_da_receita(prato["prato"], f"cardapio_{c['id']}_{dia}_{prato['chave']}")


@st.dialog("Escolher o prato")
def _janela_escolher(cardapio_id: str, dia: int, chave: str) -> None:
    """A pessoa escreve o prato que quer nesta refeição (D72); a IA monta a porção na meta da refeição."""
    c = next(x for x in st.session_state.cardapios if x["id"] == cardapio_id)
    config = config_from_json(c["plano"]["refeicoes"])
    kcal, proteina = meal_goals(c["plano"])[chave]
    st.markdown(f"**{config[chave][0]}** de {DIAS[dia].lower()}")
    st.caption(f"A DelícIA ajusta a porção para a meta desta refeição: cerca de {kcal} kcal"
               + (f" e {proteina} g de proteína." if proteina else "."))
    with st.form(f"form_escolher_{cardapio_id}_{dia}_{chave}", border=False):
        nome = st.text_input("Qual prato você quer?", max_chars=80, placeholder="Ex.: lasanha de berinjela")
        if st.form_submit_button("Colocar no cardápio", type="primary", width="stretch"):
            try:
                with st.spinner("Montando o prato..."):
                    choose_meal(st.session_state.chat, c["plano"], dia, chave, nome)
            except ValueError as erro:
                st.error(str(erro))
            except Exception as erro:  # noqa: BLE001
                st.error(_mensagem_de_erro_do_modelo(erro))
            else:
                _salvar_cardapios()
                st.session_state.aviso_cardapio_toast = f"Prato trocado: {nome.strip()}."
                st.rerun()


@st.dialog("Receita", width="large")
def _janela_receita(cardapio_id: str, dia: int, chave: str) -> None:
    c = next(x for x in st.session_state.cardapios if x["id"] == cardapio_id)
    prato = next(p for p in c["plano"]["dias"][dia]["refeicoes"] if p["chave"] == chave)
    st.subheader(prato["prato"])
    _receita_do_prato(c, dia, prato)
    if prato.get("receita"):
        _maca_do_prato(c, prato, f"{cardapio_id}_{dia}_{chave}")


def _comido_na_semana(prato: dict) -> str | None:
    """Dia (aaaa-mm-dd) em que a pessoa registrou este prato nesta semana, ou None. O cardápio é da semana:
    na semana seguinte o prato volta a ficar sem marca."""
    semana = consumo.today().isocalendar()[:2]
    return next((dia for dia in prato.get("comido", {}) if date.fromisoformat(dia).isocalendar()[:2] == semana), None)


def _alternar_comido(prato: dict) -> str:
    """Maçã do cardápio (D67, D69): registra 1 porção hoje no perfil, com os números do próprio prato (sem
    pedir nada ao modelo), ou desfaz o registro desta semana. Devolve o aviso. AccountError se não deu."""
    comidas = prato.setdefault("comido", {})  # dia -> id do registro na tabela consumo
    dia = _comido_na_semana(prato)
    if dia:
        accounts.delete_consumption(_cliente_supabase(), comidas[dia])
        del comidas[dia]
        aviso = "Registro desfeito: tiramos essa porção do seu perfil."
    else:
        hoje = consumo.today().isoformat()
        comidas[hoje] = accounts.add_consumption(_cliente_supabase(), st.session_state.perfil.id, hoje,
                                                 prato["prato"], {n: prato[n] for n in NUMEROS})
        aviso = (f"Registrado no seu perfil: 1 porção de {prato['prato']} ({prato['kcal']:.0f} kcal, "
                 f"{prato['proteina_g']:.0f} g de proteína). Veja em Meu perfil.")
    _salvar_cardapios()
    return aviso


def _maca_do_prato(c: dict, prato: dict, sufixo: str) -> None:
    """Maçã no fim da receita aberta no cardápio, com o aviso ao lado."""
    comeu = _comido_na_semana(prato)
    maca, texto = st.columns([1, 7], vertical_alignment="center")
    tocou = maca.button("", key=f"{'mordida' if comeu else 'maca'}_cardapio_{sufixo}",
                        help="Desfazer: não comi" if comeu else "Comi 1 porção")
    aviso = st.session_state.pop(f"aviso_maca_{sufixo}", None)
    if aviso:
        texto.success(aviso, icon=":material/check_circle:")
    elif comeu:
        texto.caption(f"Você comeu 1 porção desta receita esta semana ({prato['kcal']:.0f} kcal). Está no seu "
                      "perfil. Toque na maçã para desfazer.")
    else:
        texto.caption("Comeu? Toque na maçã para registrar 1 porção no seu perfil.")
    if not tocou:
        return
    try:
        st.session_state[f"aviso_maca_{sufixo}"] = _alternar_comido(prato)
    except accounts.AccountError as erro:
        st.error(str(erro))
        return
    st.rerun(scope="fragment")  # só a janela da receita roda de novo; ela continua aberta


def _dia(c: dict, indice: int) -> None:
    """Um dia do cardápio, compacto: o resumo do dia numa linha e cada prato numa linha só, com os botões
    de receita e de troca ao lado (D68)."""
    plano, chat = c["plano"], st.session_state.chat
    config = config_from_json(plano["refeicoes"])
    alvos = meal_goals(plano)
    dia = plano["dias"][indice]
    totais, problemas = day_totals(dia), day_check(plano, dia)
    proteina = (f" · {totais['proteina_g']:.0f} de {plano['meta_proteina_g']} g de proteína"
                if plano.get("meta_proteina_g") else f" · {totais['proteina_g']:.0f} g de proteína")
    resumo = f"{totais['kcal']:.0f} de {plano['meta_kcal']} kcal{proteina}"
    if problemas:  # antes dos pratos: é o primeiro que a pessoa precisa saber do dia
        st.warning(f"**Fora da meta:** {'; '.join(problemas)} · {resumo}", icon=":material/warning:")
    else:
        st.success(f"**Dentro da meta** · {resumo}", icon=":material/check_circle:")
    # os pratos num bloco só, sem o espaço entre elementos do Streamlit: as linhas se separam por um fio
    lista = st.container(key=f"pratos_{c['id']}_{indice}")
    for prato in dia["refeicoes"]:
        comeu = _comido_na_semana(prato)
        # "prato_comido_" pinta a linha de verde (visual.page_css)
        with lista.container(key=f"prato_{'comido_' if comeu else ''}{c['id']}_{indice}_{prato['chave']}"):
            info, escolher, receita, trocar, maca = st.columns([8, 1, 1, 1, 1], vertical_alignment="center",
                                                             gap="small")
            kcal, meta_proteina = alvos[prato["chave"]]
            info.markdown(f"<span class='dl-refeicao'>{config[prato['chave']][0]}</span> **{prato['prato']}**",
                          unsafe_allow_html=True)
            alertas = chat.alerts(" ".join([prato["prato"], *prato["ingredientes"]]))
            info.caption(f"{prato['porcao']} · {prato['kcal']:.0f} kcal (meta {kcal}) · {prato['proteina_g']:.0f} g "
                         "de proteína" + (f" (meta {meta_proteina} g)" if meta_proteina else "")
                         + (" · :material/warning: " + "; ".join(alertas) if alertas else ""))
            if escolher.button("", icon=":material/edit:", key=f"escolher_{c['id']}_{indice}_{prato['chave']}",
                               help="Escolher o prato que eu quero"):
                _janela_escolher(c["id"], indice, prato["chave"])
            if receita.button("", icon=":material/menu_book:", key=f"ver_{c['id']}_{indice}_{prato['chave']}",
                              help="Ver a receita"):
                _janela_receita(c["id"], indice, prato["chave"])
            if trocar.button("", icon=":material/autorenew:", key=f"trocar_{c['id']}_{indice}_{prato['chave']}",
                             help="Trocar por outro prato"):
                try:
                    with st.spinner("Pensando em outro prato..."):
                        swap_meal(chat, plano, indice, prato["chave"])
                except Exception as erro:  # noqa: BLE001
                    st.error(_mensagem_de_erro_do_modelo(erro) if not isinstance(erro, ValueError) else str(erro))
                else:
                    _salvar_cardapios()
                    st.rerun()
            if maca.button("", key=f"{'mordida' if comeu else 'maca'}_linha_{c['id']}_{indice}_{prato['chave']}",
                           help="Desfazer: não comi" if comeu else "Comi 1 porção (registra no perfil)"):
                try:
                    st.session_state.aviso_cardapio_toast = _alternar_comido(prato)
                except accounts.AccountError as erro:
                    st.error(str(erro))
                else:
                    st.rerun()
    if "aviso_cardapio_toast" in st.session_state:
        st.toast(st.session_state.pop("aviso_cardapio_toast"), icon=":material/check_circle:")


def _semana(c: dict) -> None:
    """Os 7 dias numa fileira de botões (abre no dia de hoje) e o dia escolhido embaixo."""
    hoje = consumo.today().weekday()  # 0 = segunda, como em DIAS
    chave = f"dia_{c['id']}"
    if st.session_state.get(chave) is None:  # primeira vez ou botão desmarcado: volta para hoje
        st.session_state[chave] = hoje
    st.segmented_control("Dia da semana", list(range(len(DIAS))), key=chave, label_visibility="collapsed",
                         format_func=lambda i: "Hoje" if i == hoje else DIAS[i][:3])
    _dia(c, st.session_state[chave] if st.session_state[chave] is not None else hoje)


def _apagar_cardapio(c: dict, lugar) -> None:
    """Botão "Apagar" com confirmação num balão (popover): apaga o cardápio da conta. Se era o único, fica um
    cardápio vazio no lugar, pronto para gerar de novo."""
    with lugar.popover("Apagar", icon=":material/delete:", width="stretch"):
        st.markdown(f"Apagar **{c['nome']}**? A semana inteira some da sua conta e não dá para desfazer.")
        st.caption("O que você já registrou como comido (maçã) continua no seu perfil.")
        if st.button("Sim, apagar cardápio", type="primary", key=f"apagar_{c['id']}", width="stretch"):
            st.session_state.cardapios.remove(c)
            if not st.session_state.cardapios:
                st.session_state.cardapios.append(_novo_cardapio("Cardápio 1"))
            _salvar_cardapios()
            st.session_state.aviso_cardapio = f"Cardápio \"{c['nome']}\" apagado."
            st.rerun()


def _um_cardapio(c: dict, metas: Metas) -> None:
    rotulo = "Gerar outro cardápio" if c["plano"] else "Gerar cardápio"
    if c["plano"]:
        refeicoes, gerar, apagar = st.columns([1, 1, 0.7])
        _editar_cardapio(c, refeicoes)
        _apagar_cardapio(c, apagar)
    else:
        _editar_cardapio(c)
        gerar = st.container()
    # com cardápio pronto, gerar de novo substitui a semana: vira ação secundária
    if gerar.button(rotulo, type="secondary" if c["plano"] else "primary", key=f"gerar_{c['id']}",
                    icon=":material/auto_awesome:", width="stretch"):
        try:
            with st.spinner("Montando a semana (leva uns segundos)..."):
                c["plano"] = build_week(st.session_state.chat, metas.kcal, c["refeicoes"], metas.proteina_g,
                                        metas.fonte_kcal)
        except Exception as erro:  # noqa: BLE001
            st.error(str(erro) if isinstance(erro, ValueError) else _mensagem_de_erro_do_modelo(erro))
        else:
            _salvar_cardapios()
            st.rerun()
    plano = c["plano"]
    if plano is None:
        return
    proteina = f" e {plano['meta_proteina_g']} g de proteína" if plano.get("meta_proteina_g") else ""
    fonte = ("referência da Anvisa" if plano["meta_e_referencia"] else
             "do seu nutricionista" if plano.get("fonte_meta") == "nutricionista" else "estimada pelo seu perfil")
    st.caption(f"Meta do dia: **{plano['meta_kcal']} kcal{proteina}** ({fonte}) · valores aproximados, que não "
               "substituem o nutricionista.")
    _semana(c)


def pagina_cardapio() -> None:
    # sem título: o menu ao lado já mostra a página, e assim a semana cabe na tela sem rolar (D69)
    perfil: accounts.Perfil = st.session_state.perfil
    _carregar_cardapios()
    for alerta in st.session_state.pop("alertas_cardapio", []):
        st.warning(alerta)
    if "aviso_cardapio" in st.session_state:
        st.success(st.session_state.pop("aviso_cardapio"))
    cardapios = st.session_state.cardapios
    abas = st.tabs([c["nome"] for c in cardapios] + ["Novo cardápio"])
    for aba, c in zip(abas, cardapios):
        with aba:
            _um_cardapio(c, _metas(perfil))
    with abas[-1], st.form("novo_cardapio", clear_on_submit=True):
        nome = st.text_input("Nome do novo cardápio", value=f"Cardápio {len(cardapios) + 1}", max_chars=40)
        if st.form_submit_button("Criar cardápio", type="primary"):
            if not nome.strip():
                st.error("Dê um nome ao cardápio.")
            else:
                cardapios.append(_novo_cardapio(nome.strip()))
                _salvar_cardapios()
                st.session_state.aviso_cardapio = f"Cardápio \"{nome.strip()}\" criado: abra a aba dele."
                st.rerun()


# ---------------------------------------------------------------- montagem

def _perfil_da_versao_atual() -> None:
    """Depois de publicar uma versão nova, a sessão aberta (ou a da memória do servidor, D66) ainda guarda o
    perfil feito pela classe antiga, sem os campos novos (ex.: `pro`): recria com os valores padrão."""
    antigo = st.session_state.perfil
    if isinstance(antigo, accounts.Perfil):
        return
    valores = {}
    for campo in dataclasses.fields(accounts.Perfil):
        if hasattr(antigo, campo.name):
            valores[campo.name] = getattr(antigo, campo.name)
        elif campo.default_factory is not dataclasses.MISSING:
            valores[campo.name] = campo.default_factory()
        elif campo.default is not dataclasses.MISSING:
            valores[campo.name] = campo.default
    st.session_state.perfil = accounts.Perfil(**valores)


def tela_logada() -> None:
    _perfil_da_versao_atual()
    barra_lateral()
    {"chat": pagina_chat, "perfil": pagina_perfil, "config": pagina_config,
     "cardapio": pagina_cardapio, "calculos": pagina_calculos}.get(st.session_state.get("pagina", "chat"), pagina_chat)()


def main() -> None:
    st.set_page_config(page_title="DelícIA", page_icon="🥗", layout="wide", initial_sidebar_state="expanded")
    _configurar_ambiente()
    st.markdown(visual.page_css(_tema()), unsafe_allow_html=True)
    # Componentes invisíveis num lugar fixo: se aparecessem só em algumas execuções, tudo abaixo
    # mudaria de posição e o Streamlit mostraria cópias esmaecidas das mensagens no lugar errado.
    with st.container(key="ocultos"):
        _observa_tema(key="observa_tema", on_tema_change=lambda: None)
        _menu_celular(key="menu_celular")
        if "perfil" not in st.session_state:
            _voltar_do_google()
        decidindo = "perfil" not in st.session_state and "google_usuario" not in st.session_state and _retomar_sessao()
        if "perfil" in st.session_state:
            _atualizar_sessao_navegador()
    if "perfil" in st.session_state:
        tela_logada()
    elif "google_usuario" in st.session_state:
        tela_aceite()
    elif decidindo:
        tela_carregando()
    else:
        tela_entrada()


main()
