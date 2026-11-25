"""Testes da detecção de intenção (não chamam nenhum modelo)."""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.intents import (  # noqa: E402
    AGRADECIMENTO, CULINARIA, CUMPRIMENTO, DESPEDIDA, FORA_DO_ESCOPO, classify_intent, social_reply,
)
from nutrimesa.vocabulary import load_vocabulary  # noqa: E402

CONTEXTO = "Sugiro omelete ou ovos mexidos. Qual você prefere?"


class TestIntencaoPorRegra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()

    def _tipo(self, texto, contexto=""):
        def nao_deveria_ser_chamado(_texto, _contexto):
            raise AssertionError(f"classificador chamado para {texto!r}")
        return classify_intent(texto, self.vocab, nao_deveria_ser_chamado, contexto).tipo

    def test_cumprimentos(self):
        for texto in ("Bom dia", "oi, tudo bem?", "Olá DelícIA!", "boa noite, tudo bom com você?",
                      "e aí", "Boa tarde!!", "opa, beleza?"):
            with self.subTest(texto=texto):
                self.assertEqual(self._tipo(texto), CUMPRIMENTO)

    def test_agradecimento_e_despedida(self):
        self.assertEqual(self._tipo("valeu!"), AGRADECIMENTO)
        self.assertEqual(self._tipo("muito obrigada"), AGRADECIMENTO)
        self.assertEqual(self._tipo("tchau"), DESPEDIDA)
        self.assertEqual(self._tipo("obrigado, tchau"), DESPEDIDA)

    def test_pedidos_de_cozinha(self):
        for texto in ("tenho frango e batata", "bom dia, tenho ovos", "o que eu faço pro jantar?",
                      "quero uma receita", "oi, quero fazer um bolo", "estou com fome",
                      "tem alguma coisa com queijo?", "sou alérgico a camarão", "tenho aipim"):
            with self.subTest(texto=texto):
                self.assertEqual(self._tipo(texto), CULINARIA)

    def test_continuacao_da_conversa(self):
        for texto in ("sim", "a segunda", "para 4 pessoas", "pode ser", "quero essa", "3"):
            with self.subTest(texto=texto):
                self.assertEqual(self._tipo(texto, CONTEXTO), CULINARIA)

    def test_flamengo_nao_vira_frango(self):
        # sem correção de digitação na detecção de intenção
        chamado = []
        classify_intent("o flamengo ganhou?", self.vocab, lambda t, c: chamado.append(t) or FORA_DO_ESCOPO)
        self.assertEqual(chamado, ["o flamengo ganhou?"])


class TestIntencaoPeloClassificador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()

    def test_assunto_de_fora_vai_para_o_classificador(self):
        for texto in ("Quem ganhou o jogo do Flamengo ontem?", "qual a capital da França",
                      "me ajuda com meu dever de matemática", "conta uma piada"):
            with self.subTest(texto=texto):
                intencao = classify_intent(texto, self.vocab, lambda t, c: FORA_DO_ESCOPO)
                self.assertEqual((intencao.tipo, intencao.origem), (FORA_DO_ESCOPO, "classificador"))

    def test_classificador_recebe_o_contexto(self):
        recebido = []
        classify_intent("e o preço?", self.vocab, lambda t, c: recebido.append(c) or CULINARIA, CONTEXTO)
        self.assertEqual(recebido, [CONTEXTO])

    def test_resposta_estranha_ou_erro_viram_culinaria(self):
        def quebra(_t, _c):
            raise RuntimeError("sem conexão")
        self.assertEqual(classify_intent("conta uma piada", self.vocab, lambda t, c: "talvez").tipo, CULINARIA)
        self.assertEqual(classify_intent("conta uma piada", self.vocab, quebra).tipo, CULINARIA)

    def test_sem_classificador_segue_como_culinaria(self):
        self.assertEqual(classify_intent("conta uma piada", self.vocab).tipo, CULINARIA)


class TestRespostasFixas(unittest.TestCase):
    def test_saudacao_acompanha_o_horario_e_explica_o_que_faz(self):
        resposta = social_reply(CUMPRIMENTO, "Boa noite, tudo bem?")
        self.assertTrue(resposta.startswith("Boa noite! Tudo ótimo"))
        self.assertIn("sugerir receitas", resposta)
        self.assertIn("geladeira", resposta)

    def test_oi_simples(self):
        self.assertTrue(social_reply(CUMPRIMENTO, "oi").startswith("Olá!\n"))


if __name__ == "__main__":
    unittest.main()
