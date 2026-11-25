"""Fluxo de contas inteiro (accounts.py) usando o banco local em SQLite, sem Supabase."""
import pytest

from nutrimesa import accounts
from nutrimesa.banco_local import ClienteLocal


@pytest.fixture
def arquivo(tmp_path):
    return tmp_path / "teste.sqlite"


def test_cria_conta_entra_e_salva_perfil(arquivo):
    c = ClienteLocal(arquivo)
    assert accounts.sign_up(c, "Ana@Exemplo.com ", "senha12345", "Ana", True) is True
    perfil = accounts.sign_in(ClienteLocal(arquivo), "ana@exemplo.com", "senha12345")
    assert perfil.nome == "Ana"
    perfil.objetivo, perfil.peso_kg, perfil.altura_cm, perfil.ano_nascimento = "manter", 70.0, 175.0, 2000
    assert accounts.save_profile(c, perfil) == []
    assert accounts.load_profile(ClienteLocal(arquivo), perfil.id).peso_kg == 70.0


def test_erros_de_cadastro_e_login_em_portugues(arquivo):
    c = ClienteLocal(arquivo)
    accounts.sign_up(c, "ana@exemplo.com", "senha12345", "Ana", True)
    with pytest.raises(accounts.AccountError, match="Já existe uma conta"):
        accounts.sign_up(c, "ana@exemplo.com", "outrasenha1", "Ana", True)
    with pytest.raises(accounts.AccountError, match="E-mail ou senha incorretos"):
        accounts.sign_in(c, "ana@exemplo.com", "errada123")
    with pytest.raises(accounts.AccountError, match="E-mail inválido"):
        accounts.sign_up(c, "sem-arroba", "senha12345", "X", True)


def test_sessao_retomada_e_encerrada(arquivo):
    c = ClienteLocal(arquivo)
    accounts.sign_in(c, *_conta(c))
    token = accounts.session_token(c)
    assert accounts.restore_session(ClienteLocal(arquivo), token).nome == "Bia"
    accounts.sign_out(c)
    assert accounts.restore_session(ClienteLocal(arquivo), token) is None


def test_conversas_cardapio_e_consumo(arquivo):
    c = ClienteLocal(arquivo)
    perfil = accounts.sign_in(c, *_conta(c))
    assert accounts.save_conversation(c, perfil.id, "c1", "Bolo", [{"role": "user", "content": "oi"}]) == []
    assert accounts.save_conversation(c, perfil.id, "c2", "Sopa", []) == []
    assert [x["id"] for x in accounts.list_conversations(c, perfil.id)] == ["c2", "c1"]
    assert accounts.load_conversation(c, "c1") == [{"role": "user", "content": "oi"}]
    assert accounts.last_conversation(c, perfil.id)["id"] == "c2"
    accounts.delete_conversation(c, "c2")
    assert [x["id"] for x in accounts.list_conversations(c, perfil.id)] == ["c1"]
    assert accounts.save_menu(c, perfil.id, {"dias": [1]}) == []
    accounts.save_menu(c, perfil.id, {"dias": [2]})
    assert accounts.load_menu(c, perfil.id) == {"dias": [2]}
    rid = accounts.add_consumption(c, perfil.id, "2026-11-23", "Maçã", {"kcal": 52})
    assert [r["receita"] for r in accounts.list_consumption(c, perfil.id, "2026-11-01")] == ["Maçã"]
    assert accounts.list_consumption(c, perfil.id, "2026-12-01") == []
    accounts.delete_consumption(c, rid)
    assert accounts.list_consumption(c, perfil.id, "2026-11-01") == []


def test_recuperacao_de_senha_com_codigo_no_terminal(arquivo, capsys):
    c = ClienteLocal(arquivo)
    email, senha = _conta(c)
    accounts.send_reset_code(c, email)
    codigo = capsys.readouterr().err.strip().split()[-1]
    accounts.reset_with_code(c, email, codigo, "novasenha99")
    assert accounts.sign_in(ClienteLocal(arquivo), email, "novasenha99").nome == "Bia"


def test_apagar_conta_some_com_tudo(arquivo):
    c = ClienteLocal(arquivo)
    perfil = accounts.sign_in(c, *_conta(c))
    accounts.save_conversation(c, perfil.id, "c1", "Bolo", [])
    accounts.save_menu(c, perfil.id, {"dias": [1]})
    accounts.delete_account(c)
    outro = ClienteLocal(arquivo)
    with pytest.raises(accounts.AccountError, match="E-mail ou senha incorretos"):
        accounts.sign_in(outro, "bia@exemplo.com", "senha12345")
    assert accounts.load_profile(outro, perfil.id) is None
    assert accounts.list_conversations(outro, perfil.id) == []
    assert accounts.load_menu(outro, perfil.id) is None


def _conta(c):
    accounts.sign_up(c, "bia@exemplo.com", "senha12345", "Bia", True)
    return "bia@exemplo.com", "senha12345"
