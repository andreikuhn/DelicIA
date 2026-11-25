"""Testes do vocabulário (não precisam do Excel da TACO).

Rodam com:  python -m pytest   ou   python -m unittest discover -s tests -v
"""
import copy
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite importar 'nutrimesa' sem instalar o projeto

from nutrimesa.vocabulary import (  # noqa: E402
    build_synonym_index, load_vocabulary, normalize_text, validate_vocabulary,
)


class TestNormalizeText(unittest.TestCase):
    def test_remove_acento_e_cedilha(self):
        self.assertEqual(normalize_text("Muçarela"), "mucarela")
        self.assertEqual(normalize_text("feijão"), "feijao")

    def test_hifen_e_pontuacao_viram_espaco(self):
        self.assertEqual(normalize_text("batata-doce"), "batata doce")
        self.assertEqual(normalize_text("Pimenta-do-Reino!"), "pimenta do reino")

    def test_espacos_extras(self):
        self.assertEqual(normalize_text("  Feijão   Carioca "), "feijao carioca")

    def test_texto_vazio(self):
        self.assertEqual(normalize_text("   "), "")


class TestVocabularioReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()
        cls.indice = build_synonym_index(cls.vocab["sinonimos"])

    def test_sem_problemas(self):
        problemas = validate_vocabulary(self.vocab)
        self.assertEqual(problemas, [], "\n" + "\n".join(problemas))

    def test_frases_dos_exemplos_do_projeto(self):
        # termos usados nos exemplos da especificação (cenários A, B e testes A e C)
        esperado = {
            "arroz": "arroz", "frango": "frango", "ovo": "ovo", "ovos": "ovo",
            "cenoura": "cenoura", "batata": "batata",
            "creme de leite": "creme_de_leite", "molho de tomate": "molho_de_tomate",
            "aipim": "mandioca", "muçarela": "queijo_mussarela",
            "milho em lata": "milho_verde", "carne moída": "carne_bovina_moida",
        }
        for termo, ingrediente in esperado.items():
            with self.subTest(termo=termo):
                self.assertEqual(self.indice.get(normalize_text(termo)), ingrediente)

    def test_termos_ambiguos_ficam_de_fora_de_proposito(self):
        # decisão D04: estes termos devem gerar pergunta ao usuário, não palpite
        for termo in ["massa", "farinha", "carne", "molho", "queijo"]:
            with self.subTest(termo=termo):
                self.assertNotIn(normalize_text(termo), self.indice)

    def test_cortes_de_frango_tem_o_generico_como_pai(self):
        ing = self.vocab["ingredientes"].set_index("ingrediente_id")
        for corte in ["peito_de_frango", "coxa_de_frango", "sobrecoxa_de_frango"]:
            self.assertEqual(ing.loc[corte, "ingrediente_pai"], "frango")


class TestValidadorDetectaErros(unittest.TestCase):
    """O validador precisa reprovar dados ruins; senão 'sem problemas' não significaria nada."""

    @classmethod
    def setUpClass(cls):
        cls.base = load_vocabulary()

    def _copia(self):
        return copy.deepcopy(self.base)

    def _tem(self, problemas, trecho):
        return any(trecho in p for p in problemas)

    def test_base_original_continua_valida(self):
        self.assertEqual(validate_vocabulary(self._copia()), [])

    def test_id_de_ingrediente_duplicado(self):
        v = self._copia()
        v["ingredientes"].loc[1, "ingrediente_id"] = v["ingredientes"].loc[0, "ingrediente_id"]
        self.assertTrue(self._tem(validate_vocabulary(v), "duplicado"))

    def test_sinonimo_para_ingrediente_inexistente(self):
        v = self._copia()
        v["sinonimos"].loc[0, "ingrediente_id"] = "ingrediente_que_nao_existe"
        self.assertTrue(self._tem(validate_vocabulary(v), "inexistente"))

    def test_sinonimo_ambiguo_apos_normalizar(self):
        v = self._copia()
        # 'Muçarela' e 'mucarela' são o mesmo termo normalizado, mas apontam para ingredientes distintos
        # (ordem das colunas: termo, ingrediente_id, tipo, status)
        v["sinonimos"].loc[len(v["sinonimos"])] = ["MUCARELA", "arroz", "grafia", "proposto"]
        self.assertTrue(self._tem(validate_vocabulary(v), "ambíguo"))
        with self.assertRaises(ValueError):
            build_synonym_index(v["sinonimos"])

    def test_tipo_de_ajuste_invalido(self):
        v = self._copia()
        v["ingredientes"].loc[0, "tipo_ajuste"] = "qualquer_coisa"
        self.assertTrue(self._tem(validate_vocabulary(v), "tipo_ajuste"))

    def test_ingrediente_sem_termo_canonico(self):
        v = self._copia()
        alvo = v["sinonimos"].loc[v["sinonimos"]["tipo"] == "canonico", "ingrediente_id"].iloc[0]
        v["sinonimos"].loc[(v["sinonimos"]["ingrediente_id"] == alvo)
                           & (v["sinonimos"]["tipo"] == "canonico"), "tipo"] = "variante"
        self.assertTrue(self._tem(validate_vocabulary(v), "canonico"))

    def test_coluna_ausente(self):
        v = self._copia()
        v["sinonimos"] = v["sinonimos"].drop(columns=["status"])
        self.assertTrue(self._tem(validate_vocabulary(v), "colunas ausentes"))

    def test_pai_inexistente(self):
        v = self._copia()
        v["ingredientes"].loc[0, "ingrediente_pai"] = "pai_que_nao_existe"
        self.assertTrue(self._tem(validate_vocabulary(v), "pai inexistente"))


if __name__ == "__main__":
    unittest.main()
