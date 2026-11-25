"""Contas e perfis no Supabase: cadastro, login, recuperação de senha, perfil e exclusão (LGPD).

Cada sessão do site usa o próprio cliente do Supabase (o login fica guardado nele), e o banco
só deixa cada pessoa ler e alterar o próprio perfil (RLS, ver supabase/schema.sql).

Recuperação de senha por código (decisão D32): o Supabase manda um e-mail com um código de 6
dígitos, que a pessoa digita no site. Link de redefinição não funciona bem no Streamlit, que não
lê o pedaço da URL depois do "#". Para o e-mail trazer o código, o modelo "Reset Password" do
Supabase precisa conter {{ .Token }} (passo a passo em docs/publicar_site.md).
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nutrimesa.energy import ATIVIDADES, SEXOS, validate_body
from nutrimesa.restrictions import OPCOES_PERFIL

TABELA = "perfis"
SENHA_MINIMA = 8

# Códigos de erro do Supabase Auth -> mensagem para a pessoa
_MENSAGENS = {
    "invalid_credentials": "E-mail ou senha incorretos.",
    "email_not_confirmed": "Confirme seu e-mail antes de entrar: procure a mensagem da DelícIA "
                           "na sua caixa de entrada (e no spam).",
    "user_already_exists": "Já existe uma conta com esse e-mail. Tente entrar ou recuperar a senha.",
    "email_exists": "Já existe uma conta com esse e-mail. Tente entrar ou recuperar a senha.",
    "weak_password": f"Senha fraca. Use pelo menos {SENHA_MINIMA} caracteres, misturando letras e números.",
    "over_email_send_rate_limit": "Muitos e-mails enviados em pouco tempo. Espere alguns minutos.",
    "over_request_rate_limit": "Muitas tentativas em pouco tempo. Espere alguns minutos.",
    "otp_expired": "Código inválido ou vencido. Peça um novo código.",
    "same_password": "A nova senha precisa ser diferente da anterior.",
    "email_address_invalid": "E-mail inválido.",
    "validation_failed": "Confira o e-mail e a senha.",
    # o e-mail padrão do Supabase só entrega para a equipe do projeto (precisa de SMTP próprio)
    "email_address_not_authorized": "O site ainda não consegue mandar e-mails para esse endereço. "
                                    "Avise o responsável pela DelícIA.",
}


class AccountError(Exception):
    """Erro com mensagem pronta para mostrar na tela."""


@dataclass
class Perfil:
    id: str
    nome: str = ""
    objetivo: str | None = None
    restricoes: list[str] = field(default_factory=list)
    # dados do corpo (opcionais), para IMC e meta de calorias (energy.py)
    ano_nascimento: int | None = None
    sexo: str | None = None
    altura_cm: float | None = None
    peso_kg: float | None = None
    atividade: str | None = None
    # preferências (atualização 006): o que não gosta de comer (texto livre) e orçamento
    nao_gosta: str = ""
    orcamento: str | None = None
    # metas passadas pelo nutricionista (atualização 007): valem no lugar da fórmula (energy.daily_targets)
    kcal_nutricionista: int | None = None
    proteina_nutricionista: int | None = None
    # Modo Pro (atualização 008, D71): grátis por enquanto, ligado pela própria pessoa em Configurações
    pro: bool = False


_CAMPOS_CORPO = ("ano_nascimento", "sexo", "altura_cm", "peso_kg", "atividade")
_CAMPOS_PREFERENCIAS = ("nao_gosta", "orcamento")
ORCAMENTOS = {"economico": "Econômico", "normal": "Sem preocupação"}
MAX_NAO_GOSTA = 200
KCAL_NUTRICIONISTA = (800, 6000)  # mesmas faixas do check em supabase/007_prescricao.sql
PROTEINA_NUTRICIONISTA = (20, 400)


SEM_CONEXAO = ("Não foi possível falar com o servidor de contas (Supabase). Tente de novo em instantes. "
               "Se continuar, confira a internet e se o projeto no Supabase está pausado (reative no painel).")


def _sem_conexao(erro: Exception) -> bool:
    """Falha de rede (endereço que não existe, projeto pausado, sem internet), não um erro do cadastro."""
    nomes = {type(e).__name__ for e in (erro, erro.__cause__, erro.__context__) if e is not None}
    return bool(nomes & {"ConnectError", "ConnectTimeout", "ReadTimeout", "gaierror", "ConnectionError"})


def _mensagem(erro: Exception) -> str:
    codigo = getattr(erro, "code", None)
    if codigo in _MENSAGENS:
        return _MENSAGENS[codigo]
    if type(erro).__name__ == "AuthWeakPasswordError":
        return _MENSAGENS["weak_password"]
    if _sem_conexao(erro):
        return SEM_CONEXAO
    return "Não foi possível concluir agora. Tente de novo em instantes."


def _chamar(funcao, *args, **kwargs):
    """Roda uma chamada do Supabase e troca qualquer erro por AccountError (mensagem em português)."""
    try:
        return funcao(*args, **kwargs)
    except AccountError:
        raise
    except Exception as erro:  # noqa: BLE001 - os erros do Supabase viram mensagem em português
        # falhas de rede ou do banco também: sem isso o site mostraria um erro técnico em inglês
        # o erro original vai para o terminal, para dar para descobrir a causa
        print(f"[contas] {type(erro).__name__}: {erro}", file=sys.stderr, flush=True)
        raise AccountError(_mensagem(erro)) from erro


def _confere_senha(senha: str) -> None:
    if len(senha) < SENHA_MINIMA:
        raise AccountError(f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.")


def sign_up(client, email: str, senha: str, nome: str, consentiu: bool) -> bool:
    """Cria a conta. Retorna True se já entrou; False se precisa confirmar o e-mail antes."""
    if not consentiu:
        raise AccountError("Para criar a conta, é preciso concordar com o uso dos dados.")
    _confere_senha(senha)
    agora = datetime.now(timezone.utc).isoformat()
    resposta = _chamar(client.auth.sign_up, {
        "email": email.strip(), "password": senha,
        # o consentimento fica guardado na conta desde o cadastro e passa para o perfil no 1º login
        "options": {"data": {"nome": nome.strip(), "consentimento_em": agora}},
    })
    return getattr(resposta, "session", None) is not None


def sign_in(client, email: str, senha: str) -> Perfil:
    """Entra e devolve o perfil (criado na hora, se for o primeiro login)."""
    resposta = _chamar(client.auth.sign_in_with_password, {"email": email.strip(), "password": senha})
    return _perfil_do_usuario(client, resposta.user)


# erros em que o próprio Supabase recusou o código (vencido, já usado, sessão encerrada)
_SESSAO_INVALIDA = ("AuthApiError", "AuthSessionMissingError", "AuthInvalidJwtError")


def restore_session(client, refresh_token: str) -> Perfil | None:
    """Retoma a sessão guardada no navegador (D55). None se o código não vale mais (o site o apaga);
    AccountError se não deu agora (rede, Supabase fora): o código fica guardado para a próxima vez."""
    try:
        resposta = client.auth.refresh_session(refresh_token)
    except Exception as erro:  # noqa: BLE001
        if type(erro).__name__ in _SESSAO_INVALIDA:
            return None
        raise AccountError(_mensagem(erro)) from erro
    return _perfil_do_usuario(client, resposta.user) if getattr(resposta, "user", None) else None


def browser_value(chave: str, token: str) -> str:
    """O que o navegador guarda (D66): a chave da sessão na memória do servidor e o código do Supabase."""
    return json.dumps({"c": chave, "t": token})


def read_browser_value(valor: str) -> tuple[str | None, str]:
    """(chave da memória do servidor, código do Supabase). O formato antigo guardava só o código."""
    try:
        dados = json.loads(valor)
        return dados.get("c"), dados.get("t") or ""
    except (ValueError, AttributeError):
        return None, valor


def session_token(client) -> str | None:
    """Código para retomar a sessão; o Supabase troca por outro quando renova o acesso."""
    try:
        sessao = client.auth.get_session()  # renova o acesso se estiver vencendo
    except Exception:  # noqa: BLE001 - sem sessão válida: o navegador deixa de guardar
        return None
    return sessao.refresh_token if sessao else None


# ---------------------------------------------------------------- entrar com o Google (D70)
# O Supabase faz o login com o Google (OAuth, fluxo PKCE). O site gera o par verificador/desafio: o
# verificador fica guardado no servidor até a pessoa voltar do Google (a volta abre uma sessão nova do
# Streamlit, e o cliente do Supabase daquela sessão não o teria).

def google_login_url(client, volta: str) -> tuple[str, str]:
    """(endereço da página do Google, verificador para guardar até a volta)."""
    verificador = secrets.token_urlsafe(48)
    desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
    resposta = _chamar(client.auth.sign_in_with_oauth, {"provider": "google", "options": {
        "redirect_to": volta, "query_params": {"code_challenge": desafio, "code_challenge_method": "s256"}}})
    return resposta.url, verificador


def google_sign_in(client, codigo: str, verificador: str):
    """Troca o código da volta do Google por uma sessão. Devolve (perfil, usuário); perfil None na
    primeira vez: falta o aceite do uso dos dados (LGPD) antes de criar o perfil (accept_terms)."""
    resposta = _chamar(client.auth.exchange_code_for_session, {"auth_code": codigo, "code_verifier": verificador})
    if not getattr(resposta, "user", None):
        raise AccountError("Não foi possível entrar com o Google. Tente de novo.")
    return _chamar(load_profile, client, resposta.user.id), resposta.user


def accept_terms(client, usuario) -> Perfil:
    """Primeiro login com o Google: a pessoa concordou com o texto de consentimento; cria o perfil."""
    dados = usuario.user_metadata or {}
    nome = str(dados.get("full_name") or dados.get("name") or "").strip()[:80]
    _chamar(client.table(TABELA).insert({
        "id": usuario.id, "nome": nome, "restricoes": [],
        "consentimento_em": datetime.now(timezone.utc).isoformat(),
    }).execute)
    return Perfil(id=usuario.id, nome=nome)


def _perfil_do_usuario(client, usuario) -> Perfil:
    perfil = _chamar(load_profile, client, usuario.id)
    if perfil is None:
        dados = usuario.user_metadata or {}
        if not dados.get("consentimento_em"):
            raise AccountError("Conta sem registro de consentimento. Crie a conta de novo pelo site.")
        _chamar(client.table(TABELA).insert({
            "id": usuario.id, "nome": dados.get("nome", ""), "restricoes": [],
            "consentimento_em": dados["consentimento_em"],
        }).execute)
        perfil = Perfil(id=usuario.id, nome=dados.get("nome", ""))
    return perfil


def send_reset_code(client, email: str) -> None:
    """Manda o e-mail com o código de recuperação (o Supabase não diz se o e-mail existe)."""
    _chamar(client.auth.reset_password_for_email, email.strip())


def reset_with_code(client, email: str, codigo: str, nova_senha: str) -> None:
    """Confere o código do e-mail e troca a senha. A pessoa fica logada."""
    _confere_senha(nova_senha)
    _chamar(client.auth.verify_otp, {"email": email.strip(), "token": codigo.strip(), "type": "recovery"})
    _chamar(client.auth.update_user, {"password": nova_senha})


def sign_out(client) -> None:
    _chamar(client.auth.sign_out)


def _numero(valor) -> float | None:
    return None if valor in (None, "") else float(valor)


def load_profile(client, user_id: str) -> Perfil | None:
    # select("*"): funciona antes e depois da atualização 002 (colunas do corpo) no banco
    linhas = client.table(TABELA).select("*").eq("id", user_id).execute().data
    if not linhas:
        return None
    linha = linhas[0]
    ano = linha.get("ano_nascimento")
    return Perfil(id=linha["id"], nome=linha.get("nome") or "", objetivo=linha.get("objetivo"),
                  restricoes=list(linha.get("restricoes") or []),
                  ano_nascimento=int(ano) if ano else None, sexo=linha.get("sexo"),
                  altura_cm=_numero(linha.get("altura_cm")), peso_kg=_numero(linha.get("peso_kg")),
                  atividade=linha.get("atividade"), nao_gosta=linha.get("nao_gosta") or "",
                  orcamento=linha.get("orcamento"), kcal_nutricionista=_inteiro(linha.get("kcal_nutricionista")),
                  proteina_nutricionista=_inteiro(linha.get("proteina_nutricionista")), pro=bool(linha.get("pro")))


def _inteiro(valor) -> int | None:
    return None if valor in (None, "") else int(valor)


AVISO_SEM_COLUNA_PRO = ("O Modo Pro ficou ligado só até você sair: o banco precisa da atualização "
                        "supabase/008_pro.sql (rodar uma vez no SQL Editor do Supabase).")


def set_pro(client, user_id: str, ligado: bool) -> list[str]:
    """Liga ou desliga o Modo Pro. Avisos (lista vazia = salvo); AccountError se não deu."""
    try:
        client.table(TABELA).update({"pro": ligado}).eq("id", user_id).execute()
    except Exception as erro:  # noqa: BLE001
        if _falta_coluna(erro):
            return [AVISO_SEM_COLUNA_PRO]
        if _sessao_expirou(erro):
            raise AccountError("Sua sessão expirou. Saia e entre de novo para salvar.") from erro
        raise AccountError("Não foi possível salvar agora. Tente de novo em instantes.") from erro
    return []


def _falta_coluna(erro: Exception) -> bool:
    texto = str(erro)
    return any(sinal in texto for sinal in ("PGRST204", "42703", "does not exist", "Could not find"))


def _sessao_expirou(erro: Exception) -> bool:
    texto = str(erro)
    return any(sinal in texto for sinal in ("PGRST301", "PGRST303", "JWT expired", "jwt expired"))


def save_profile(client, perfil: Perfil) -> list[str]:
    """Salva o perfil. Devolve avisos (lista vazia = tudo salvo).

    Se o banco ainda não tiver os campos do corpo (atualização 002 não rodada), salva o resto
    e avisa, em vez de não salvar nada. Erro de verdade vira AccountError.
    """
    desconhecidas = [r for r in perfil.restricoes if r not in OPCOES_PERFIL]
    if desconhecidas:
        raise AccountError(f"Restrição desconhecida: {', '.join(desconhecidas)}")
    if perfil.objetivo not in (None, "perder", "manter", "ganhar"):
        raise AccountError("Objetivo inválido.")
    if perfil.sexo not in (None, *SEXOS):
        raise AccountError("Sexo inválido.")
    if perfil.atividade not in (None, *ATIVIDADES):
        raise AccountError("Nível de atividade inválido.")
    if perfil.orcamento not in (None, *ORCAMENTOS):
        raise AccountError("Orçamento inválido.")
    if len(perfil.nao_gosta) > MAX_NAO_GOSTA:
        raise AccountError(f'"Não gosto de" aceita até {MAX_NAO_GOSTA} caracteres.')
    for valor, (minimo, maximo), nome in ((perfil.kcal_nutricionista, KCAL_NUTRICIONISTA, "Energia (kcal por dia)"),
                                          (perfil.proteina_nutricionista, PROTEINA_NUTRICIONISTA,
                                           "Proteína (g por dia)")):
        if valor is not None and not minimo <= valor <= maximo:
            raise AccountError(f"{nome} do nutricionista deve estar entre {minimo} e {maximo}.")
    problemas = validate_body(perfil.peso_kg, perfil.altura_cm, perfil.ano_nascimento)
    if problemas:
        raise AccountError(" ".join(problemas))
    base = {"nome": perfil.nome.strip(), "objetivo": perfil.objetivo, "restricoes": perfil.restricoes,
            "atualizado_em": datetime.now(timezone.utc).isoformat()}
    corpo = {c: getattr(perfil, c) for c in _CAMPOS_CORPO}
    preferencias = {"nao_gosta": perfil.nao_gosta.strip(), "orcamento": perfil.orcamento}
    nutricionista = {"kcal_nutricionista": perfil.kcal_nutricionista,
                     "proteina_nutricionista": perfil.proteina_nutricionista}
    # do mais completo ao mais simples: o banco pode ainda não ter as colunas das atualizações 002, 006 e 007
    tentativas = [({**base, **corpo, **preferencias, **nutricionista}, []),
                  ({**base, **corpo, **preferencias},
                   ["As metas do nutricionista ainda não puderam ser salvas: o banco precisa da atualização "
                    "supabase/007_prescricao.sql (rodar uma vez no SQL Editor do Supabase)."]),
                  ({**base, **corpo}, ['"Não gosto de" e orçamento ainda não puderam ser salvos: o banco precisa '
                                       "da atualização supabase/006_preferencias.sql (rodar uma vez no SQL Editor "
                                       "do Supabase)."]),
                  (base, ["Salvamos nome, objetivo e restrições. Idade, sexo, altura, peso e atividade "
                          "ainda não puderam ser salvos: o banco precisa da atualização "
                          "supabase/002_perfil_corpo.sql (rodar uma vez no SQL Editor do Supabase)."])]
    for i, (dados, avisos) in enumerate(tentativas):
        try:
            resposta = client.table(TABELA).update(dados).eq("id", perfil.id).execute()
            break
        except Exception as erro:  # noqa: BLE001
            if _sessao_expirou(erro):
                raise AccountError("Sua sessão expirou. Saia e entre de novo para salvar.") from erro
            if not _falta_coluna(erro) or i == len(tentativas) - 1:
                raise AccountError("Não foi possível salvar agora. Tente de novo em instantes.") from erro
    if not getattr(resposta, "data", None):
        # o banco não achou a linha deste usuário (ou a sessão não vale mais): nada foi salvo
        raise AccountError("Não encontramos seu perfil para salvar. Saia e entre de novo.")
    return avisos


TABELA_CARDAPIOS = "cardapios"
AVISO_SEM_TABELA_CARDAPIO = ("O cardápio não foi salvo na sua conta: o banco precisa da atualização "
                             "supabase/003_cardapio.sql (rodar uma vez no SQL Editor do Supabase).")


def _falta_tabela(erro: Exception) -> bool:
    texto = str(erro)
    return any(sinal in texto for sinal in ("PGRST205", "42P01", "Could not find the table"))


def save_menu(client, user_id: str, dados: dict) -> list[str]:
    """Guarda o cardápio da pessoa (um por conta; o novo substitui o anterior). Devolve avisos."""
    linha = {"id": user_id, "dados": dados, "atualizado_em": datetime.now(timezone.utc).isoformat()}
    try:
        client.table(TABELA_CARDAPIOS).upsert(linha).execute()
    except Exception as erro:  # noqa: BLE001
        if _falta_tabela(erro):
            return [AVISO_SEM_TABELA_CARDAPIO]
        if _sessao_expirou(erro):
            raise AccountError("Sua sessão expirou. Saia e entre de novo para salvar o cardápio.") from erro
        raise AccountError("Não foi possível salvar o cardápio agora. Tente de novo em instantes.") from erro
    return []


def load_menu(client, user_id: str) -> dict | None:
    """O cardápio salvo, ou None (sem cardápio, tabela ainda não criada ou falha de conexão)."""
    try:
        linhas = client.table(TABELA_CARDAPIOS).select("dados").eq("id", user_id).execute().data
    except Exception:  # noqa: BLE001 - sem o salvo, a pessoa só monta outro
        return None
    return linhas[0]["dados"] if linhas else None


TABELA_CONVERSAS = "conversas"
MAX_CONVERSAS_LISTADAS = 50
AVISO_SEM_TABELA_CONVERSAS = ("O histórico de conversas ainda não está sendo salvo: o banco precisa da "
                              "atualização supabase/004_conversas.sql (rodar uma vez no SQL Editor do Supabase).")


def list_conversations(client, user_id: str) -> list[dict] | None:
    """Conversas da pessoa, da mais recente para a mais antiga: [{"id", "titulo", "atualizado_em"}].
    None se a tabela ainda não existe ou o banco não respondeu (o site segue sem histórico)."""
    try:
        return (client.table(TABELA_CONVERSAS).select("id, titulo, atualizado_em").eq("usuario_id", user_id)
                .order("atualizado_em", desc=True).limit(MAX_CONVERSAS_LISTADAS).execute().data) or []
    except Exception:  # noqa: BLE001
        return None


def last_conversation(client, user_id: str) -> dict | None:
    """A conversa mais recente, já com as mensagens ({"id", "mensagens"}), numa consulta só; None se não
    houver ou o banco não responder (o site começa uma conversa nova)."""
    try:
        linhas = (client.table(TABELA_CONVERSAS).select("id, mensagens").eq("usuario_id", user_id)
                  .order("atualizado_em", desc=True).limit(1).execute().data)
    except Exception:  # noqa: BLE001
        return None
    return {"id": linhas[0]["id"], "mensagens": list(linhas[0]["mensagens"] or [])} if linhas else None


def load_conversation(client, conversa_id: str) -> list[dict]:
    """Mensagens de uma conversa ([{"role", "content"}]); lista vazia se não achar."""
    try:
        linhas = client.table(TABELA_CONVERSAS).select("mensagens").eq("id", conversa_id).execute().data
    except Exception as erro:  # noqa: BLE001
        raise AccountError("Não foi possível abrir a conversa agora. Tente de novo em instantes.") from erro
    return list(linhas[0]["mensagens"]) if linhas else []


def save_conversation(client, user_id: str, conversa_id: str, titulo: str, mensagens: list[dict]) -> list[str]:
    """Guarda (ou atualiza) a conversa. Devolve avisos; erro de conexão vira AccountError."""
    linha = {"id": conversa_id, "usuario_id": user_id, "titulo": titulo[:80], "mensagens": mensagens,
             "atualizado_em": datetime.now(timezone.utc).isoformat()}
    try:
        client.table(TABELA_CONVERSAS).upsert(linha).execute()
    except Exception as erro:  # noqa: BLE001
        if _falta_tabela(erro):
            return [AVISO_SEM_TABELA_CONVERSAS]
        if _sessao_expirou(erro):
            raise AccountError("Sua sessão expirou. Saia e entre de novo para salvar a conversa.") from erro
        raise AccountError("Não foi possível salvar a conversa agora.") from erro
    return []


def delete_conversation(client, conversa_id: str) -> None:
    try:
        client.table(TABELA_CONVERSAS).delete().eq("id", conversa_id).execute()
    except Exception as erro:  # noqa: BLE001
        raise AccountError("Não foi possível apagar a conversa agora.") from erro


TABELA_CONSUMO = "consumo"
AVISO_SEM_TABELA_CONSUMO = ("O que você comeu ainda não está sendo guardado: o banco precisa da atualização "
                            "supabase/005_consumo.sql (rodar uma vez no SQL Editor do Supabase).")


def add_consumption(client, user_id: str, dia: str, receita: str, nutrientes: dict) -> str:
    """Registra 1 porção comida (a maçã). Devolve o id do registro; AccountError se não deu."""
    linha = {"id": str(uuid.uuid4()), "usuario_id": user_id, "dia": dia, "receita": receita[:120],
             "nutrientes": nutrientes}
    try:
        client.table(TABELA_CONSUMO).insert(linha).execute()
    except Exception as erro:  # noqa: BLE001
        if _falta_tabela(erro):
            raise AccountError(AVISO_SEM_TABELA_CONSUMO) from erro
        if _sessao_expirou(erro):
            raise AccountError("Sua sessão expirou. Saia e entre de novo para registrar.") from erro
        raise AccountError("Não foi possível registrar agora. Tente de novo em instantes.") from erro
    return linha["id"]


def list_consumption(client, user_id: str, desde: str) -> list[dict] | None:
    """Registros a partir do dia `desde` (AAAA-MM-DD): [{"id", "dia", "receita", "nutrientes"}].
    None se a tabela ainda não existe ou o banco não respondeu."""
    try:
        return (client.table(TABELA_CONSUMO).select("id, dia, receita, nutrientes").eq("usuario_id", user_id)
                .gte("dia", desde).order("criado_em").execute().data) or []
    except Exception:  # noqa: BLE001
        return None


def delete_consumption(client, registro_id: str) -> None:
    try:
        client.table(TABELA_CONSUMO).delete().eq("id", registro_id).execute()
    except Exception as erro:  # noqa: BLE001
        raise AccountError("Não foi possível desfazer agora. Tente de novo em instantes.") from erro


def delete_account(client) -> None:
    """Apaga a conta e o perfil (função apagar_minha_conta no banco) e encerra a sessão."""
    client.rpc("apagar_minha_conta").execute()
    try:
        client.auth.sign_out()
    except Exception:  # noqa: BLE001 - a conta já não existe; sair é só limpeza
        pass
