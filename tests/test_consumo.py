import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nutrimesa import consumo  # noqa: E402


class ChatFalso:
    def __init__(self, resposta):
        self.resposta, self.pedidos = resposta, []

    def generate_json(self, pedido, esquema, temperatura=0.6):
        self.pedidos.append((pedido, esquema, temperatura))
        return self.resposta


class TestConsumo(unittest.TestCase):
    def test_estima_uma_porcao(self):
        chat = ChatFalso({**{k: 1 for k in consumo.NUTRIENTES}, "kcal": 412.34, "sodio_mg": -3})
        valores = consumo.estimate(chat, "Omelete", "2 ovos, sal")
        self.assertEqual(valores["kcal"], 412.3)
        self.assertEqual(valores["sodio_mg"], 0)  # negativo vira 0
        self.assertIn("UMA porção", chat.pedidos[0][0])
        self.assertEqual(chat.pedidos[0][1]["required"], list(consumo.NUTRIENTES))

    def test_recusa_resposta_sem_sentido(self):
        with self.assertRaises(ValueError):
            consumo.estimate(ChatFalso({"kcal": 300}), "Omelete", "...")  # faltam campos
        with self.assertRaises(ValueError):
            consumo.estimate(ChatFalso({k: 0 for k in consumo.NUTRIENTES}), "Omelete", "...")  # 0 kcal

    def test_soma_e_periodos(self):
        registros = [{"nutrientes": {"kcal": 300, "proteina_g": 20}}, {"nutrientes": {"kcal": 150.5}}]
        soma = consumo.totals(registros)
        self.assertEqual((soma["kcal"], soma["proteina_g"], soma["ferro_mg"]), (450.5, 20, 0))
        hoje = date(2026, 10, 27)
        self.assertEqual(consumo.period_start("hoje", hoje), hoje)
        self.assertEqual(consumo.period_start("semana", hoje), date(2026, 10, 21))
        self.assertEqual(consumo.period_start("mes", hoje), date(2026, 9, 28))
        self.assertEqual((consumo.format_value(450.5), consumo.format_value(2.25)), ("450", "2,2"))

    def test_agua_separada_da_comida(self):
        registros = [{"nutrientes": {"kcal": 300}}, {"nutrientes": {"agua_ml": 250}}, {"nutrientes": {"agua_ml": 500}}]
        self.assertEqual([consumo.is_water(r) for r in registros], [False, True, True])
        self.assertEqual(consumo.water_ml(registros), 750)


if __name__ == "__main__":
    unittest.main()
