"""Testes das restrições do perfil e da conferência do texto gerado pelo modelo (D56)."""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.restrictions import (  # noqa: E402
    OPCOES_PERFIL, components_for, load_restrictions, text_alerts, validate_restrictions,
)
from nutrimesa.vocabulary import load_vocabulary  # noqa: E402


class TestRestricoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()
        cls.res = load_restrictions()

    def _alertas(self, texto, *opcoes):
        return text_alerts(texto, components_for(opcoes), self.vocab, self.res)

    def test_arquivo_valido(self):
        self.assertEqual(validate_restrictions(self.res, self.vocab), [])

    def test_opcao_desconhecida(self):
        with self.assertRaises(ValueError):
            components_for(["alergia_inventada"])

    def test_vegano_inclui_vegetariano(self):
        self.assertTrue(components_for(["vegetariano"]) <= components_for(["vegano"]))

    def test_toda_opcao_do_perfil_tem_rotulo_e_componentes(self):
        for chave, (rotulo, componentes) in OPCOES_PERFIL.items():
            with self.subTest(opcao=chave):
                self.assertTrue(rotulo and componentes)

    def test_avisa_ingrediente_que_contem(self):
        alertas = self._alertas("Faça um strogonoff com frango e creme de leite.", "intolerancia_lactose")
        self.assertEqual(alertas, ["creme de leite: contém lactose"])

    def test_pode_conter_vira_aviso_de_rotulo(self):
        self.assertEqual(self._alertas("Sirva com pão francês.", "intolerancia_lactose"),
                         ["pão francês: pode conter lactose"])

    def test_sem_o_componente_nao_avisa_so_aquele(self):
        self.assertEqual(self._alertas("Use leite sem lactose.", "intolerancia_lactose"), [])
        # para o vegano, leite sem lactose continua sendo de origem animal
        self.assertEqual(self._alertas("Use leite sem lactose.", "vegano"),
                         ["leite: contém ingrediente de origem animal"])

    def test_frases_de_aviso_ou_troca_nao_contam(self):
        texto = ("Confira os rótulos para garantir que não contenham derivados de leite. "
                 "Troque o queijo por tofu.\n* 200 g de frango\n* 1 xícara de creme de leite")
        self.assertEqual(self._alertas(texto, "intolerancia_lactose"), ["creme de leite: contém lactose"])

    def test_versao_vegetal_e_zero_lactose_nao_avisam(self):
        self.assertEqual(self._alertas("Troque por leite vegetal ou leite de aveia.", "vegano"), [])
        self.assertEqual(self._alertas("Use leite zero lactose.", "intolerancia_lactose"), [])

    def test_termo_mais_longo_primeiro_e_sem_repetir(self):
        alertas = self._alertas("Leite de coco, leite de coco e mais leite de coco.", "intolerancia_lactose")
        self.assertEqual(alertas, [])  # leite de coco não é o leite de vaca
        alertas = self._alertas("Frango, frango e frango.", "vegetariano")
        self.assertEqual(alertas, ["frango: contém carne ou peixe"])

    def test_sem_restricao_ou_sem_texto_nao_avisa(self):
        self.assertEqual(text_alerts("queijo", set(), self.vocab, self.res), [])
        self.assertEqual(self._alertas("", "vegano"), [])


if __name__ == "__main__":
    unittest.main()
