"""Testes do cardápio gerado pelo modelo (D56), com um chat falso."""
import json
import sys
import unittest
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.planner import (  # noqa: E402
    DIAS, PESO_NOVA, REFEICOES, build_week, config_from_json, config_to_json, day_check, day_totals, meal_goals, meal_targets,
    choose_meal, restore, swap_meal,
)


def prato(chave, nome, kcal=500):
    return {"chave": chave, "prato": nome, "porcao": "1 prato", "ingredientes": ["arroz", "feijão"],
            "kcal": kcal, "proteina_g": 20, "carboidrato_g": 60, "gordura_g": 10}


class ChatFalso:
    def __init__(self, *respostas):
        self.respostas, self.pedidos = list(respostas), []

    def generate_json(self, pedido, esquema):
        self.pedidos.append(pedido)
        return self.respostas.pop(0)


def semana(chaves):
    return {"dias": [{"dia": d, "refeicoes": [prato(c, f"{c} {d}") for c in chaves]} for d in DIAS]}


class TestCardapio(unittest.TestCase):
    def test_monta_a_semana_com_as_refeicoes_pedidas(self):
        config = {"almoco": REFEICOES["almoco"], "extra": ("Ceia", PESO_NOVA["leve"], "leve")}
        chat = ChatFalso(semana(["almoco", "extra"]))
        plano = build_week(chat, 2000, config)
        self.assertEqual(len(plano["dias"]), 7)
        self.assertEqual([p["chave"] for p in plano["dias"][0]["refeicoes"]], ["almoco", "extra"])
        self.assertIn("Ceia", chat.pedidos[0])
        self.assertIn("2000 kcal", chat.pedidos[0])
        self.assertEqual(day_totals(plano["dias"][0])["kcal"], 1000)

    def test_metas_do_nutricionista_por_refeicao(self):
        chat = ChatFalso(semana(REFEICOES), prato("jantar", "Peixe assado"))
        plano = build_week(chat, 1800, None, 100, "nutricionista")
        self.assertIn("1800 kcal e 100 g de proteína", chat.pedidos[0])
        self.assertIn("cerca de 630 kcal e 35 g de proteína", chat.pedidos[0])  # almoço: 35%
        self.assertEqual((plano["meta_proteina_g"], plano["fonte_meta"]), (100, "nutricionista"))
        self.assertEqual(meal_goals(plano)["jantar"], (540, 30))
        swap_meal(chat, plano, 0, "jantar")
        self.assertIn("cerca de 540 kcal e 30 g de proteína", chat.pedidos[1])

    def test_dia_dentro_e_fora_da_meta(self):
        plano = build_week(ChatFalso(semana(REFEICOES)), 2000, None, 80)  # cada dia: 2000 kcal e 80 g
        self.assertEqual(day_check(plano, plano["dias"][0]), [])
        plano["meta_proteina_g"] = 100
        plano["meta_kcal"] = 2500
        self.assertEqual(day_check(plano, plano["dias"][0]),
                         ["500 kcal abaixo da meta", "20 g de proteína abaixo da meta"])

    def test_plano_antigo_sem_proteina(self):
        plano = build_week(ChatFalso(semana(REFEICOES)), 2000)
        del plano["meta_proteina_g"], plano["fonte_meta"]
        self.assertEqual(meal_goals(restore(plano))["almoco"], (700, None))
        self.assertEqual(day_check(plano, plano["dias"][0]), [])

    def test_ordem_das_refeicoes_sobrevive_ao_banco(self):
        config = {**REFEICOES, "extra_1": ("Ceia", PESO_NOVA["leve"], "leve")}
        self.assertEqual(list(config_from_json(config_to_json(config))), [*REFEICOES, "extra_1"])
        # formato antigo, com as chaves na ordem do jsonb (tamanho e depois alfabética)
        antigo = {k: list(config[k]) for k in ("cafe", "almoco", "jantar", "lanche", "extra_1")}
        self.assertEqual(list(config_from_json(antigo)), ["cafe", "almoco", "lanche", "jantar", "extra_1"])
        plano = build_week(ChatFalso(semana(REFEICOES)), 2000)
        plano["refeicoes"] = {k: list(REFEICOES[k]) for k in ("cafe", "almoco", "jantar", "lanche")}
        plano["dias"][0]["refeicoes"].reverse()
        plano = restore(plano)
        self.assertEqual([p["chave"] for p in plano["dias"][0]["refeicoes"]], list(REFEICOES))

    def test_pessoa_escolhe_o_prato(self):
        chat = ChatFalso(semana(REFEICOES), prato("jantar", "Lasanha de berinjela", 560))
        plano = build_week(chat, 2000)
        choose_meal(chat, plano, 1, "jantar", "  lasanha   de berinjela ")
        self.assertIn('escolheu comer "lasanha de berinjela" no Jantar', chat.pedidos[1])
        self.assertIn("cerca de 600 kcal", chat.pedidos[1])  # meta do jantar: 30% de 2000
        jantar = next(p for p in plano["dias"][1]["refeicoes"] if p["chave"] == "jantar")
        self.assertEqual((jantar["prato"], jantar["kcal"]), ("Lasanha de berinjela", 560))
        self.assertEqual(plano["dias"][0]["refeicoes"][3]["prato"], "jantar Segunda")  # outros dias iguais
        with self.assertRaises(ValueError):
            choose_meal(chat, plano, 1, "jantar", "   ")

    def test_meta_dividida_pelos_pesos(self):
        alvos = meal_targets(2000, REFEICOES)
        self.assertEqual(alvos["almoco"], 700)
        self.assertAlmostEqual(sum(alvos.values()), 2000, delta=2)

    def test_sem_meta_usa_a_referencia(self):
        plano = build_week(ChatFalso(semana(REFEICOES)), None)
        self.assertEqual((plano["meta_kcal"], plano["meta_e_referencia"], plano["meta_proteina_g"]), (2000, True, 50))

    def test_chave_trocada_pelo_modelo_vale_a_posicao(self):
        resposta = semana(["x1", "x2", "x3", "x4"])
        plano = build_week(ChatFalso(resposta), 2000)
        self.assertEqual([p["chave"] for p in plano["dias"][0]["refeicoes"]], list(REFEICOES))

    def test_resposta_incompleta_vira_erro(self):
        with self.assertRaises(ValueError):
            build_week(ChatFalso({"dias": semana(REFEICOES)["dias"][:3]}), 2000)
        sem_jantar = semana(["cafe", "almoco", "lanche"])
        with self.assertRaises(ValueError):
            build_week(ChatFalso(sem_jantar), 2000)

    def test_numeros_estranhos_viram_zero(self):
        resposta = semana(REFEICOES)
        resposta["dias"][0]["refeicoes"][0]["kcal"] = "muito"
        plano = build_week(ChatFalso(resposta), 2000)
        self.assertEqual(plano["dias"][0]["refeicoes"][0]["kcal"], 0)

    def test_troca_um_prato(self):
        chat = ChatFalso(semana(REFEICOES), prato("jantar", "Sopa de legumes", 400))
        plano = build_week(chat, 2000)
        swap_meal(chat, plano, 2, "jantar")
        self.assertEqual(plano["dias"][2]["refeicoes"][3]["prato"], "Sopa de legumes")
        self.assertIn("Não repita", chat.pedidos[1])

    def test_salvo_volta_igual_e_formato_antigo_e_descartado(self):
        plano = build_week(ChatFalso(semana(REFEICOES)), 2000)
        self.assertEqual(restore(json.loads(json.dumps(plano))), plano)
        self.assertIsNone(restore({"versao": 1, "dias": []}))
        self.assertIsNone(restore(None))

    def test_refeicoes_da_versao_antiga_viram_tipo(self):
        antigo = {"almoco": ["Almoço", 0.35, ["prato_principal", "acompanhamento"]], "cafe": ["Café", 0.2, ["lanche"]]}
        self.assertEqual(config_from_json(antigo)["almoco"][2], "completa")
        self.assertEqual(config_from_json(antigo)["cafe"][2], "leve")
        with self.assertRaises(ValueError):
            config_from_json({"x": ["  ", 0.1, "leve"]})


if __name__ == "__main__":
    unittest.main()
