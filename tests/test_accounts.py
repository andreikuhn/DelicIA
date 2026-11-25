"""Testes de contas e perfis com um Supabase falso (não acessam a internet)."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa import accounts  # noqa: E402


class AuthApiError(Exception):
    """Imita o erro do Supabase Auth (mesmo nome de classe e atributo 'code')."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Consulta:
    def __init__(self, banco, tabela):
        self.banco, self.tabela, self.acao, self.dados, self.filtro = banco, tabela, None, None, None

    def select(self, _colunas):
        self.acao = "select"
        return self

    def insert(self, dados):
        self.acao, self.dados = "insert", dados
        return self

    def update(self, dados):
        self.acao, self.dados = "update", dados
        return self

    def upsert(self, dados):
        self.acao, self.dados = "upsert", dados
        return self

    def delete(self):
        self.acao = "delete"
        return self

    def eq(self, coluna, valor):
        self.filtro = (coluna, valor)
        return self

    def gte(self, coluna, valor):
        self.minimo = (coluna, valor)
        return self

    def order(self, coluna, desc=False):
        self.ordem = (coluna, desc)
        return self

    def limit(self, n):
        return self

    def execute(self):
        if self.tabela in self.banco.get("_tabelas_ausentes", set()):  # imita o PostgREST sem a tabela
            raise Exception({"code": "PGRST205", "message": f"Could not find the table 'public.{self.tabela}'"})
        linhas = self.banco.setdefault(self.tabela, {})
        if self.acao == "upsert":
            linhas[self.dados["id"]] = dict(self.dados)
            return SimpleNamespace(data=[self.dados])
        if self.acao == "insert":
            linhas[self.dados["id"]] = dict(self.dados)
            return SimpleNamespace(data=[self.dados])
        if self.acao == "update":
            ausentes = self.banco.get("_colunas_ausentes", set()) & set(self.dados)
            if ausentes:  # imita o PostgREST quando a coluna não existe no banco
                raise Exception({"code": "PGRST204", "message": f"Could not find the '{sorted(ausentes)[0]}' column"})
            if self.filtro[1] not in linhas:
                return SimpleNamespace(data=[])  # o banco não achou a linha: nada atualizado
            linhas[self.filtro[1]].update(self.dados)
            return SimpleNamespace(data=[linhas[self.filtro[1]]])
        coluna, valor = self.filtro
        achadas = [v for v in linhas.values() if v.get(coluna) == valor]
        if getattr(self, "minimo", None):
            achadas = [v for v in achadas if v.get(self.minimo[0]) >= self.minimo[1]]
        if self.acao == "delete":
            for v in achadas:
                del linhas[v["id"]]
            return SimpleNamespace(data=achadas)
        if getattr(self, "ordem", None):
            achadas.sort(key=lambda v: v.get(self.ordem[0]) or "", reverse=self.ordem[1])
        return SimpleNamespace(data=achadas)


class SupabaseFalso:
    def __init__(self):
        self.banco = {}
        self.chamadas = []
        self.erro = None
        self.metadados = {"nome": "Ana", "consentimento_em": "2026-10-25T00:00:00+00:00"}
        self.usuario = SimpleNamespace(id="u1", user_metadata=self.metadados)
        self.sessao = None  # como no Supabase: cada renovação troca o refresh token por outro
        self.renovacoes = 0
        entrar = self._registra("sign_in", SimpleNamespace(user=self.usuario))
        sair = self._registra("sign_out", None)
        self.auth = SimpleNamespace(
            sign_up=self._registra("sign_up", SimpleNamespace(session=None)),
            sign_in_with_password=lambda *a: (self._nova_sessao(), entrar(*a))[1],
            reset_password_for_email=self._registra("reset", None),
            verify_otp=self._registra("verify_otp", None),
            update_user=self._registra("update_user", None),
            sign_out=lambda *a: (setattr(self, "sessao", None), sair(*a))[1],
            get_session=lambda: self.sessao,
            refresh_session=self._renovar,
            sign_in_with_oauth=lambda cred: (self.chamadas.append(("oauth", cred)),
                                             SimpleNamespace(url="https://x.supabase.co/auth/v1/authorize?provider=google"))[1],
            exchange_code_for_session=lambda params: (self.chamadas.append(("troca", params)),
                                                      SimpleNamespace(user=self.usuario))[1],
        )

    def _nova_sessao(self):
        self.renovacoes += 1
        self.sessao = SimpleNamespace(refresh_token=f"rt{self.renovacoes}")

    def _renovar(self, token):
        if self.erro:
            raise self.erro
        if self.sessao is None or token != self.sessao.refresh_token:
            raise AuthApiError("refresh_token_not_found")  # token velho ou de sessão encerrada
        self._nova_sessao()
        return SimpleNamespace(user=self.usuario, session=self.sessao)

    def _registra(self, nome, retorno):
        def funcao(*args):
            self.chamadas.append((nome, args))
            if self.erro:
                raise self.erro
            return retorno
        return funcao

    def table(self, tabela):
        return Consulta(self.banco, tabela)

    def rpc(self, nome):
        self.chamadas.append(("rpc", (nome,)))
        return SimpleNamespace(execute=lambda: None)


class TestContas(unittest.TestCase):
    def setUp(self):
        self.sb = SupabaseFalso()

    def test_cadastro_exige_consentimento_e_senha_minima(self):
        with self.assertRaises(accounts.AccountError):
            accounts.sign_up(self.sb, "a@b.com", "senhaforte1", "Ana", consentiu=False)
        with self.assertRaises(accounts.AccountError):
            accounts.sign_up(self.sb, "a@b.com", "curta", "Ana", consentiu=True)
        self.assertEqual(self.sb.chamadas, [])

    def test_cadastro_guarda_consentimento_na_conta(self):
        ja_entrou = accounts.sign_up(self.sb, " a@b.com ", "senhaforte1", "Ana", consentiu=True)
        self.assertFalse(ja_entrou)  # precisa confirmar o e-mail
        dados = self.sb.chamadas[0][1][0]
        self.assertEqual(dados["email"], "a@b.com")
        self.assertIn("consentimento_em", dados["options"]["data"])

    def test_primeiro_login_cria_perfil(self):
        perfil = accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.assertEqual((perfil.id, perfil.nome, perfil.restricoes), ("u1", "Ana", []))
        self.assertEqual(self.sb.banco["perfis"]["u1"]["consentimento_em"], self.sb.metadados["consentimento_em"])
        # segundo login lê o perfil existente
        self.sb.banco["perfis"]["u1"]["restricoes"] = ["vegano"]
        self.assertEqual(accounts.sign_in(self.sb, "a@b.com", "senhaforte1").restricoes, ["vegano"])

    def test_login_sem_consentimento_registrado(self):
        self.sb.metadados.clear()
        with self.assertRaises(accounts.AccountError):
            accounts.sign_in(self.sb, "a@b.com", "senhaforte1")

    def test_erros_viram_mensagem_em_portugues(self):
        self.sb.erro = AuthApiError("invalid_credentials")
        with self.assertRaises(accounts.AccountError) as ctx:
            accounts.sign_in(self.sb, "a@b.com", "errada123")
        self.assertEqual(str(ctx.exception), "E-mail ou senha incorretos.")
        self.sb.erro = AuthApiError("codigo_novo_qualquer")
        with self.assertRaises(accounts.AccountError) as ctx:
            accounts.send_reset_code(self.sb, "a@b.com")
        self.assertIn("Tente de novo", str(ctx.exception))

    def test_falha_de_rede_vira_mensagem_e_nao_erro_tecnico(self):
        self.sb.erro = ConnectionError("sem internet")
        for chamada in (lambda: accounts.sign_in(self.sb, "a@b.com", "senhaforte1"),
                        lambda: accounts.sign_out(self.sb)):
            with self.assertRaises(accounts.AccountError) as ctx:
                chamada()
            self.assertIn("Tente de novo", str(ctx.exception))

    def test_recuperacao_confere_codigo_e_troca_senha(self):
        accounts.reset_with_code(self.sb, "a@b.com", " 123456 ", "novasenha1")
        nomes = [n for n, _ in self.sb.chamadas]
        self.assertEqual(nomes, ["verify_otp", "update_user"])
        self.assertEqual(self.sb.chamadas[0][1][0], {"email": "a@b.com", "token": "123456", "type": "recovery"})

    def test_salvar_perfil_valida_dados(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", "perder", ["doenca_celiaca"]))
        self.assertEqual(self.sb.banco["perfis"]["u1"]["restricoes"], ["doenca_celiaca"])
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", None, ["inventada"]))
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", "emagrecer", []))

    def test_salvar_tudo_sem_avisos(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        avisos = accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", "manter", [], 1996, "feminino",
                                                                165.0, 60.0, "leve"))
        self.assertEqual(avisos, [])
        self.assertEqual(self.sb.banco["perfis"]["u1"]["altura_cm"], 165.0)

    def test_banco_sem_colunas_do_corpo_salva_o_resto_e_avisa(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.sb.banco["_colunas_ausentes"] = {"ano_nascimento", "sexo", "altura_cm", "peso_kg", "atividade"}
        avisos = accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", "perder", ["vegano"], 1996))
        self.assertEqual(self.sb.banco["perfis"]["u1"]["restricoes"], ["vegano"])
        self.assertEqual(self.sb.banco["perfis"]["u1"]["objetivo"], "perder")
        self.assertIn("002_perfil_corpo.sql", avisos[0])

    def test_preferencias_salvas_e_validadas(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.assertEqual(accounts.save_profile(self.sb, accounts.Perfil(
            "u1", "Ana", nao_gosta=" fígado, coentro ", orcamento="economico")), [])
        perfil = accounts.load_profile(self.sb, "u1")
        self.assertEqual((perfil.nao_gosta, perfil.orcamento), ("fígado, coentro", "economico"))
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", orcamento="caro"))
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", nao_gosta="x" * 201))

    def test_banco_sem_colunas_de_preferencias_salva_o_resto_e_avisa(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.sb.banco["_colunas_ausentes"] = {"nao_gosta", "orcamento"}
        avisos = accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", "perder", [], 1996, nao_gosta="fígado"))
        self.assertEqual(self.sb.banco["perfis"]["u1"]["ano_nascimento"], 1996)
        self.assertIn("006_preferencias.sql", avisos[0])

    def test_metas_do_nutricionista_salvas_e_validadas(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.assertEqual(accounts.save_profile(self.sb, accounts.Perfil(
            "u1", "Ana", kcal_nutricionista=1800, proteina_nutricionista=90)), [])
        perfil = accounts.load_profile(self.sb, "u1")
        self.assertEqual((perfil.kcal_nutricionista, perfil.proteina_nutricionista), (1800, 90))
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", kcal_nutricionista=500))
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", proteina_nutricionista=401))

    def test_banco_sem_colunas_do_nutricionista_salva_o_resto_e_avisa(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.sb.banco["_colunas_ausentes"] = {"kcal_nutricionista", "proteina_nutricionista"}
        avisos = accounts.save_profile(self.sb, accounts.Perfil("u1", "Ana", nao_gosta="fígado", kcal_nutricionista=1800))
        self.assertEqual(self.sb.banco["perfis"]["u1"]["nao_gosta"], "fígado")
        self.assertIn("007_prescricao.sql", avisos[0])

    def test_modo_pro_liga_e_volta_no_perfil(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        self.assertFalse(accounts.load_profile(self.sb, "u1").pro)
        self.assertEqual(accounts.set_pro(self.sb, "u1", True), [])
        self.assertTrue(accounts.load_profile(self.sb, "u1").pro)
        self.sb.banco["_colunas_ausentes"] = {"pro"}
        self.assertIn("008_pro.sql", accounts.set_pro(self.sb, "u1", False)[0])

    def test_nenhuma_linha_atualizada_e_erro(self):
        with self.assertRaises(accounts.AccountError):
            accounts.save_profile(self.sb, accounts.Perfil("ninguem", "Ana"))

    def test_entrar_com_google_primeira_vez_pede_aceite(self):
        import base64
        import hashlib
        url, verificador = accounts.google_login_url(self.sb, "https://delicia.streamlit.app/?google=abc")
        self.assertIn("provider=google", url)
        opcoes = self.sb.chamadas[-1][1]["options"]
        self.assertEqual(opcoes["redirect_to"], "https://delicia.streamlit.app/?google=abc")
        desafio = base64.urlsafe_b64encode(hashlib.sha256(verificador.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(opcoes["query_params"], {"code_challenge": desafio, "code_challenge_method": "s256"})
        self.sb.usuario.user_metadata = {"full_name": "Ana Souza"}  # vindo do Google, sem consentimento
        perfil, usuario = accounts.google_sign_in(self.sb, "codigo1", verificador)
        self.assertIsNone(perfil)  # sem perfil: o site mostra o texto de consentimento antes
        self.assertEqual(self.sb.chamadas[-1], ("troca", {"auth_code": "codigo1", "code_verifier": verificador}))
        perfil = accounts.accept_terms(self.sb, usuario)
        self.assertEqual(perfil.nome, "Ana Souza")
        self.assertTrue(self.sb.banco["perfis"]["u1"]["consentimento_em"])
        self.assertEqual(accounts.google_sign_in(self.sb, "codigo2", verificador)[0].nome, "Ana Souza")

    def test_retoma_sessao_guardada_no_navegador(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        token = accounts.session_token(self.sb)
        perfil = accounts.restore_session(self.sb, token)
        self.assertEqual((perfil.id, perfil.nome), ("u1", "Ana"))
        novo = accounts.session_token(self.sb)
        self.assertNotEqual(novo, token)  # o token muda: o site precisa guardar o novo
        self.assertIsNone(accounts.restore_session(self.sb, token))  # o velho não vale mais
        accounts.sign_out(self.sb)
        self.assertIsNone(accounts.restore_session(self.sb, novo))
        self.assertIsNone(accounts.session_token(self.sb))

    def test_valor_guardado_no_navegador(self):
        valor = accounts.browser_value("chave1", "rt9")
        self.assertEqual(accounts.read_browser_value(valor), ("chave1", "rt9"))
        self.assertEqual(accounts.read_browser_value("rt-antigo"), (None, "rt-antigo"))  # formato de antes
        self.assertEqual(accounts.read_browser_value("12345"), (None, "12345"))

    def test_falha_de_rede_na_retomada_nao_perde_a_sessao(self):
        accounts.sign_in(self.sb, "a@b.com", "senhaforte1")
        token = accounts.session_token(self.sb)
        self.sb.erro = ConnectionError("sem internet")
        with self.assertRaises(accounts.AccountError):  # o site não apaga o código: tenta de novo depois
            accounts.restore_session(self.sb, token)
        self.sb.erro = None
        self.assertEqual(accounts.restore_session(self.sb, token).id, "u1")

    def test_cardapio_salvo_volta_igual_e_o_novo_substitui(self):
        self.assertIsNone(accounts.load_menu(self.sb, "u1"))
        self.assertEqual(accounts.save_menu(self.sb, "u1", {"versao": 1, "dias": [1]}), [])
        accounts.save_menu(self.sb, "u1", {"versao": 1, "dias": [2]})
        self.assertEqual(accounts.load_menu(self.sb, "u1"), {"versao": 1, "dias": [2]})
        self.assertIsNone(accounts.load_menu(self.sb, "outra_pessoa"))

    def test_banco_sem_tabela_de_cardapio_avisa_sem_quebrar(self):
        self.sb.banco["_tabelas_ausentes"] = {"cardapios"}
        avisos = accounts.save_menu(self.sb, "u1", {"versao": 1})
        self.assertIn("003_cardapio.sql", avisos[0])
        self.assertIsNone(accounts.load_menu(self.sb, "u1"))

    def test_historico_de_conversas(self):
        msgs = [{"role": "user", "content": "tenho ovos"}, {"role": "assistant", "content": "Omelete!"}]
        self.assertEqual(accounts.list_conversations(self.sb, "u1"), [])
        self.assertEqual(accounts.save_conversation(self.sb, "u1", "c1", "tenho ovos", msgs), [])
        accounts.save_conversation(self.sb, "u1", "c2", "x" * 200, msgs[:1])
        self.sb.banco["conversas"]["c1"]["atualizado_em"] = "2099-01-01"  # c1 vira a mais recente
        lista = accounts.list_conversations(self.sb, "u1")
        self.assertEqual([c["id"] for c in lista], ["c1", "c2"])
        self.assertEqual(len(self.sb.banco["conversas"]["c2"]["titulo"]), 80)
        self.assertEqual(accounts.load_conversation(self.sb, "c1"), msgs)
        self.assertEqual(accounts.last_conversation(self.sb, "u1"), {"id": "c1", "mensagens": msgs})
        self.assertIsNone(accounts.last_conversation(self.sb, "outra_pessoa"))
        self.assertEqual(accounts.list_conversations(self.sb, "outra_pessoa"), [])
        accounts.delete_conversation(self.sb, "c1")
        self.assertEqual([c["id"] for c in accounts.list_conversations(self.sb, "u1")], ["c2"])

    def test_consumo_registra_lista_e_desfaz(self):
        a = accounts.add_consumption(self.sb, "u1", "2026-10-27", "Omelete", {"kcal": 300})
        accounts.add_consumption(self.sb, "u1", "2026-10-01", "Arroz", {"kcal": 200})
        accounts.add_consumption(self.sb, "outra", "2026-10-27", "Bolo", {"kcal": 500})
        self.assertEqual([r["receita"] for r in accounts.list_consumption(self.sb, "u1", "2026-10-20")], ["Omelete"])
        self.assertEqual(len(accounts.list_consumption(self.sb, "u1", "2026-10-01")), 2)
        accounts.delete_consumption(self.sb, a)
        self.assertEqual([r["receita"] for r in accounts.list_consumption(self.sb, "u1", "2026-10-01")], ["Arroz"])

    def test_banco_sem_tabela_de_consumo(self):
        self.sb.banco["_tabelas_ausentes"] = {"consumo"}
        self.assertIsNone(accounts.list_consumption(self.sb, "u1", "2026-10-01"))
        with self.assertRaisesRegex(accounts.AccountError, "005_consumo.sql"):
            accounts.add_consumption(self.sb, "u1", "2026-10-27", "Omelete", {})

    def test_banco_sem_tabela_de_conversas(self):
        self.sb.banco["_tabelas_ausentes"] = {"conversas"}
        self.assertIsNone(accounts.list_conversations(self.sb, "u1"))
        self.assertIsNone(accounts.last_conversation(self.sb, "u1"))
        self.assertIn("004_conversas.sql", accounts.save_conversation(self.sb, "u1", "c1", "t", [])[0])

    def test_apagar_conta_chama_funcao_do_banco_e_sai(self):
        accounts.delete_account(self.sb)
        self.assertEqual([n for n, _ in self.sb.chamadas], ["rpc", "sign_out"])
        self.assertEqual(self.sb.chamadas[0][1], ("apagar_minha_conta",))


if __name__ == "__main__":
    unittest.main()
