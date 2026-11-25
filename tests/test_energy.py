"""Testes do IMC e da meta de calorias."""
import sys
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.energy import bmi, bmi_class, daily_targets, estimate, resting_energy, validate_body, water_goal  # noqa: E402

HOJE = date(2026, 10, 25)


class TestEnergia(unittest.TestCase):
    def test_metas_do_nutricionista_vencem_a_formula(self):
        est = estimate(70, 175, 1996, "masculino", "moderado", "manter", HOJE)
        formula = daily_targets(est, 70)
        self.assertEqual((formula.kcal, formula.proteina_g, formula.fonte_kcal), (est.meta_kcal, 56, "formula"))
        nutri = daily_targets(est, 70, 1800, 110)
        self.assertEqual((nutri.kcal, nutri.proteina_g, nutri.fonte_proteina), (1800, 110, "nutricionista"))
        # só a proteína do nutricionista: a energia continua pela fórmula
        mista = daily_targets(est, 70, None, 110)
        self.assertEqual((mista.fonte_kcal, mista.fonte_proteina), ("formula", "nutricionista"))

    def test_nutricionista_vale_mesmo_sem_dados_ou_com_imc_baixo(self):
        vazio = daily_targets(estimate(None, None, None, None, None, None, HOJE), None)
        self.assertEqual((vazio.kcal, vazio.proteina_g, vazio.fonte_kcal), (None, None, None))
        baixo = estimate(45, 175, 1996, "feminino", "leve", "perder", HOJE)  # IMC 14,7: sem meta pela fórmula
        self.assertIsNone(baixo.meta_kcal)
        self.assertEqual(daily_targets(baixo, 45, 1100, 60).kcal, 1100)  # abaixo do piso de 1.200: vale

    def test_imc(self):
        self.assertEqual(bmi(70, 175), 22.9)
        self.assertEqual(bmi_class(18.4), "abaixo do peso")
        self.assertEqual(bmi_class(24.9), "peso adequado")
        self.assertEqual(bmi_class(29.9), "sobrepeso")
        self.assertEqual(bmi_class(30), "obesidade")

    def test_mifflin_st_jeor(self):
        # 10*70 + 6,25*175 - 5*30 = 1643,75
        self.assertAlmostEqual(resting_energy(70, 175, 30, "masculino"), 1648.75)
        self.assertAlmostEqual(resting_energy(70, 175, 30, "feminino"), 1482.75)

    def test_meta_manter_e_perder(self):
        manter = estimate(70, 175, 1996, "masculino", "moderado", "manter", HOJE)
        self.assertEqual(manter.gasto_diario, round(1648.75 * 1.55))
        perder = estimate(70, 175, 1996, "masculino", "moderado", "perder", HOJE)
        self.assertEqual(perder.meta_kcal, round((1648.75 * 1.55 - 500) / 10) * 10)

    def test_piso_de_calorias(self):
        est = estimate(48, 150, 1970, "feminino", "sedentario", "perder", HOJE)
        self.assertEqual(est.meta_kcal, 1200)
        self.assertTrue(any("limitada" in a for a in est.avisos))

    def test_ganhar_tem_aviso_de_convencao(self):
        est = estimate(60, 180, 2000, "masculino", "leve", "ganhar", HOJE)
        self.assertTrue(any("convenção" in a for a in est.avisos))

    def test_menor_de_idade_nao_recebe_meta(self):
        est = estimate(60, 170, 2012, "feminino", "leve", "perder", HOJE)
        self.assertIsNone(est.meta_kcal)
        self.assertTrue(any("18 anos" in a for a in est.avisos))

    def test_imc_baixo_nao_recebe_meta_para_perder(self):
        est = estimate(50, 180, 1995, "masculino", "leve", "perder", HOJE)
        self.assertIsNone(est.meta_kcal)
        self.assertEqual(est.classificacao_imc, "abaixo do peso")

    def test_dados_faltando(self):
        est = estimate(70, 175, None, None, None, "manter", HOJE)
        self.assertEqual(est.imc, 22.9)
        self.assertIsNone(est.meta_kcal)
        self.assertIn("ano de nascimento", est.avisos[0])

    def test_validacao(self):
        self.assertEqual(validate_body(70, 175, 1996, HOJE), [])
        self.assertEqual(len(validate_body(500, 20, 1800, HOJE)), 3)
        self.assertEqual(validate_body(None, None, None, HOJE), [])

    def test_meta_de_agua(self):
        self.assertEqual(water_goal(70, "sedentario"), (2450, False))   # 70 x 35
        self.assertEqual(water_goal(70, "intenso"), (3050, False))      # + 600 pela atividade
        self.assertEqual(water_goal(None, "leve"), (2000, True))        # sem peso: referência
        self.assertEqual(water_goal(35, None), (1500, False))           # piso
        self.assertEqual(water_goal(150, "muito_intenso"), (5000, False))  # teto


if __name__ == "__main__":
    unittest.main()
