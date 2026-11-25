"""Testes da conversa (D56), com clientes falsos: não chamam a API nem gastam cota."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa import chat as chat_mod  # noqa: E402
from nutrimesa.chat import MARCA_DETALHES, MARCA_RECEITA, Chat, load_env, provider, split_details, split_suggestions  # noqa: E402
from nutrimesa.restrictions import load_restrictions  # noqa: E402
from nutrimesa.vocabulary import load_vocabulary  # noqa: E402


class Sobrecarga(Exception):
    code = 503


def pedaco(texto):
    return SimpleNamespace(text=texto)


class GeminiFalso:
    """Cada chamada consome a próxima resposta da fila: uma lista de pedaços (stream), um texto
    (generate_content) ou uma exceção. Guarda o que foi pedido."""

    def __init__(self, *respostas):
        self.fila, self.pedidos = list(respostas), []
        self.models = SimpleNamespace(generate_content=self._gerar, generate_content_stream=self._stream)

    def _proxima(self, kwargs):
        self.pedidos.append(kwargs)
        item = self.fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def _gerar(self, **kwargs):
        return SimpleNamespace(text=self._proxima(kwargs))

    def _stream(self, **kwargs):
        item = self._proxima(kwargs)
        yield from (pedaco(t) for t in item)


class TestConversa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()
        cls.res = load_restrictions()

    def _chat(self, *respostas):
        cliente = GeminiFalso(*respostas)
        return Chat(cliente, self.vocab, self.res, "gemini", modelo="m"), cliente

    def test_cumprimento_responde_sem_chamar_o_modelo(self):
        chat, cliente = self._chat()
        self.assertIn("DelícIA", chat.send("oi"))
        self.assertEqual(cliente.pedidos, [])
        self.assertEqual([m["role"] for m in chat.mensagens], ["user", "assistant"])

    def test_resposta_aos_pedacos_e_historico(self):
        chat, cliente = self._chat(["Com frango ", "dá strogonoff."], ["Para 2 pessoas: ..."])
        self.assertEqual(list(chat.send_stream("tenho frango e batata")), ["Com frango ", "dá strogonoff."])
        chat.send("quero a receita para 2 pessoas")
        enviado = cliente.pedidos[1]["contents"]  # a segunda pergunta leva o histórico inteiro
        self.assertEqual([c.role for c in enviado], ["user", "model", "user"])
        self.assertEqual(enviado[1].parts[0].text, "Com frango dá strogonoff.")
        self.assertIn("DelícIA", cliente.pedidos[0]["config"].system_instruction)

    def test_perfil_vai_nas_instrucoes(self):
        chat, cliente = self._chat(["ok"])
        chat.set_profile(["intolerancia_lactose"], "ganhar", 2680)
        chat.send("tenho frango")
        instrucoes = cliente.pedidos[0]["config"].system_instruction
        self.assertIn("Intolerância à lactose", instrucoes)
        self.assertIn("ganhar peso", instrucoes)
        self.assertIn("fonte de proteína em todas as refeições", instrucoes)
        self.assertIn("2680 kcal", instrucoes)

    def test_preferencias_e_corpo_nas_instrucoes(self):
        chat, cliente = self._chat(["ok"])
        chat.set_profile([], None, 2100, nao_gosta="Fígado, coentro e jiló", outros=["Idade: 25 anos", "Peso: 70 kg"])
        chat.send("tenho carne")
        instrucoes = cliente.pedidos[0]["config"].system_instruction
        for trecho in ("Não gosta de: Fígado, coentro e jiló", "Idade: 25 anos", "Peso: 70 kg", "2100 kcal"):
            self.assertIn(trecho, instrucoes)
        self.assertEqual(chat.alerts("Finalize com coentro picado. Sirva sem jiló. Não use fígado."),
                         ["coentro: você marcou que não gosta"])

    def test_metas_do_nutricionista_nas_instrucoes(self):
        chat, cliente = self._chat(["ok"])
        chat.set_profile([], None, 1800, proteina_g=110, nutricionista=True)
        chat.send("tenho frango")
        instrucoes = cliente.pedidos[0]["config"].system_instruction
        for trecho in ("1800 kcal", "110 g por dia", "passadas pelo nutricionista", "quanto da meta"):
            self.assertIn(trecho, instrucoes)

    def test_modos_do_chat(self):
        chat, cliente = self._chat(["ok"], ["ok"])
        chat.modo = "bebidas"
        chat.send("tenho laranja")
        self.assertIn("SOMENTE bebidas", cliente.pedidos[0]["config"].system_instruction)
        chat.modo = None
        chat.send("tenho arroz")
        self.assertNotIn("MODO ATUAL", cliente.pedidos[1]["config"].system_instruction)
        self.assertNotIn("MODO ATUAL", chat.system_prompt)  # pedidos avulsos (cardápio) não levam o modo

    def test_modo_vegano_avisa_ingrediente_animal(self):
        chat, _ = self._chat()
        texto = "Misture com queijo mussarela e ovos."
        self.assertEqual(chat.alerts(texto, com_modo=True), [])  # sem o modo, perfil sem restrição
        chat.modo = "vegano"
        self.assertEqual(chat.alerts(texto), [])  # cardápio: sem o modo
        self.assertTrue(chat.alerts(texto, com_modo=True))
        self.assertEqual(chat.alerts("No modo vegano, ignorei o frango e usei só o feijão.", com_modo=True), [])

    def test_confere_restricoes_no_texto(self):
        chat, _ = self._chat()
        chat.set_profile(["intolerancia_lactose"])
        self.assertEqual(chat.alerts("Leve ao forno com queijo mussarela."), ["queijo mussarela: contém lactose"])

    def test_modo_de_preparo_aos_pedacos(self):
        chat, cliente = self._chat(["1. Tempere ", "o frango."], [])
        self.assertEqual(list(chat.stream_text("receita de frango assado")), ["1. Tempere ", "o frango."])
        self.assertEqual(cliente.pedidos[0]["contents"], "receita de frango assado")
        self.assertEqual(list(chat.stream_text("outra")), [chat_mod.RESPOSTA_SEM_TEXTO])  # resposta vazia
        self.assertEqual(chat.mensagens, [])  # pedido avulso não entra na conversa

    def test_resposta_interrompida_desfaz_a_pergunta(self):
        chat, _ = self._chat(["Com ovos ", "dá omelete."])
        pedacos = chat.send_stream("tenho ovos")
        next(pedacos)
        pedacos.close()  # o site foi executado de novo no meio da resposta
        self.assertEqual(chat.mensagens, [])

    def test_erro_do_servico_desfaz_a_pergunta(self):
        chat, _ = self._chat(ValueError("caiu"))
        with self.assertRaises(ValueError):
            chat.send("tenho ovos")
        self.assertEqual(chat.mensagens, [])

    def test_resposta_vazia(self):
        chat, _ = self._chat(["   "])
        self.assertIn("repetir", chat.send("tenho ovos"))

    def test_classificador_pede_json(self):
        chat, cliente = self._chat('{"intencao": "fora_do_escopo"}')
        self.assertIn("foge do que eu sei fazer", chat.send("quem ganhou o jogo?"))
        self.assertEqual(cliente.pedidos[0]["config"].response_mime_type, "application/json")

    def test_json_avulso(self):
        chat, cliente = self._chat('{"dias": []}', "isso não é json")
        self.assertEqual(chat.generate_json("monte", {"type": "object"}), {"dias": []})
        self.assertEqual(cliente.pedidos[0]["config"].response_json_schema, {"type": "object"})
        with self.assertRaises(ValueError):
            chat.generate_json("monte", {"type": "object"})


class TestModelosReserva(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()
        cls.res = load_restrictions()

    def setUp(self):
        self.espera, chat_mod.ESPERA_GEMINI_S = chat_mod.ESPERA_GEMINI_S, 0

    def tearDown(self):
        chat_mod.ESPERA_GEMINI_S = self.espera

    def test_sobrecarga_passa_para_os_reservas_e_da_mais_uma_volta(self):
        cliente = GeminiFalso(Sobrecarga(), Sobrecarga(), Sobrecarga(), ["Claro!"])
        chat = Chat(cliente, self.vocab, self.res, "gemini", modelo="m")
        self.assertEqual(chat.send("tenho ovos"), "Claro!")
        r1, r2 = chat_mod.MODELOS_RESERVA_GEMINI
        self.assertEqual([p["model"] for p in cliente.pedidos], ["m", r1, r2, "m"])

    def test_json_tambem_usa_os_reservas(self):
        cliente = GeminiFalso(Sobrecarga(), '{"ok": 1}')
        chat = Chat(cliente, self.vocab, self.res, "gemini", modelo="m")
        self.assertEqual(chat.generate_json("x", {"type": "object"}), {"ok": 1})
        self.assertEqual(cliente.pedidos[1]["model"], chat_mod.MODELOS_RESERVA_GEMINI[0])

    def test_erros_do_servidor_trocam_de_modelo_e_os_do_pedido_nao(self):
        for codigo in (429, 500, 502, 503, 504):
            self.assertTrue(chat_mod._vale_tentar_outro(type("E", (Exception,), {"code": codigo})()), codigo)
        for codigo in (400, 401, 404):
            self.assertFalse(chat_mod._vale_tentar_outro(type("E", (Exception,), {"code": codigo})()), codigo)
        import httpx
        self.assertTrue(chat_mod._vale_tentar_outro(httpx.ReadTimeout("parado")))

    def test_limite_no_primeiro_pedaco(self):
        def lento():
            time.sleep(0.5)
            yield "tarde"

        def com_erro():
            yield "a"
            raise ValueError("quebrou")
        with self.assertRaises(TimeoutError):
            list(chat_mod._com_limite_no_primeiro(lento(), 0.05))
        self.assertEqual(list(chat_mod._com_limite_no_primeiro(iter(["a", "b"]), 1)), ["a", "b"])
        with self.assertRaises(ValueError):
            list(chat_mod._com_limite_no_primeiro(com_erro(), 1))


class TestDetalhes(unittest.TestCase):
    def test_separa_resumo_e_detalhes(self):
        texto = f"Sugiro omelete.\n{MARCA_DETALHES}\n## Receita\n1. Bata os ovos."
        self.assertEqual(split_details(texto), ("Sugiro omelete.", "## Receita\n1. Bata os ovos."))
        self.assertEqual(split_details("Só isso."), ("Só isso.", ""))

    def test_separa_sugestoes(self):
        texto = (f"Com frango dá para fazer:\n{MARCA_RECEITA} Frango assado | 45 min | falta azeite\n"
                 f"2. **{MARCA_RECEITA} Escondidinho** | 1 h\nQual prefere?")
        self.assertEqual(split_suggestions(texto), ("Com frango dá para fazer:",
                         [("Frango assado", "45 min · falta azeite"), ("Escondidinho", "1 h")], "Qual prefere?"))
        self.assertEqual(split_suggestions("Olá!"), ("Olá!", [], ""))


class TestOllama(unittest.TestCase):
    def test_conversa_e_json_pelo_ollama(self):
        class OllamaFalso:
            def __init__(self):
                self.pedidos = []

            def chat(self, **kwargs):
                self.pedidos.append(kwargs)
                if kwargs.get("stream"):
                    return iter([SimpleNamespace(message=SimpleNamespace(content="Omelete"))])
                return SimpleNamespace(message=SimpleNamespace(content=json.dumps({"ok": True})))
        cliente = OllamaFalso()
        chat = Chat(cliente, load_vocabulary(), load_restrictions(), "ollama", modelo="m")
        self.assertEqual(chat.send("tenho ovos"), "Omelete")
        self.assertEqual(cliente.pedidos[0]["messages"][0]["role"], "system")
        self.assertEqual(chat.generate_json("x", {"type": "object"}), {"ok": True})


class TestProvider(unittest.TestCase):
    def setUp(self):
        self.antes = os.environ.pop("LLM_PROVIDER", None)

    def tearDown(self):
        os.environ.pop("LLM_PROVIDER", None)
        if self.antes is not None:
            os.environ["LLM_PROVIDER"] = self.antes

    def test_padrao_e_ollama(self):
        self.assertEqual(provider(), "ollama")

    def test_gemini_e_maiusculas(self):
        os.environ["LLM_PROVIDER"] = " Gemini "
        self.assertEqual(provider(), "gemini")

    def test_invalido(self):
        os.environ["LLM_PROVIDER"] = "gpt"
        with self.assertRaises(ValueError):
            provider()


class TestLoadEnv(unittest.TestCase):
    def test_le_valores_e_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as pasta:
            env = Path(pasta) / ".env"
            env.write_text("# comentário\nNM_TESTE_A=um\nNM_TESTE_B='dois'\nNM_TESTE_C=\n", encoding="utf-8")
            os.environ["NM_TESTE_A"] = "já definido"
            try:
                load_env(env)
                self.assertEqual(os.environ["NM_TESTE_A"], "já definido")
                self.assertEqual(os.environ["NM_TESTE_B"], "dois")
                self.assertNotIn("NM_TESTE_C", os.environ)
            finally:
                for chave in ("NM_TESTE_A", "NM_TESTE_B", "NM_TESTE_C"):
                    os.environ.pop(chave, None)


if __name__ == "__main__":
    unittest.main()
