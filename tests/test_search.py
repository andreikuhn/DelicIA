"""Testes do entendimento dos ingredientes que a pessoa escreve."""
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.search import (  # noqa: E402
    TERMOS_AMBIGUOS, resolve_terms, split_terms,
)
from nutrimesa.vocabulary import build_synonym_index, load_vocabulary, normalize_text  # noqa: E402


class TestSplitTerms(unittest.TestCase):
    def test_virgula_e_conjuncao(self):
        self.assertEqual(split_terms("ovos, tomate e cebola"), ["ovos", "tomate", "cebola"])

    def test_descarta_quantidades_soltas(self):
        self.assertEqual(split_terms("3 ovos; 0,5 cebola"), ["ovos", "cebola"])

    def test_nao_quebra_nomes_compostos(self):
        self.assertEqual(split_terms("creme de leite, batata-doce"), ["creme de leite", "batata-doce"])

    def test_texto_vazio(self):
        self.assertEqual(split_terms("  ,  "), [])


class TestResolveTerms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocabulary()

    def test_sinonimos_regionais_e_plural(self):
        r = resolve_terms(["Aipim", "ovos", "Muçarela"], self.vocab)
        self.assertEqual(r.encontrados, {"Aipim": "mandioca", "ovos": "ovo", "Muçarela": "queijo_mussarela"})

    def test_termo_ambiguo_vira_pergunta(self):
        r = resolve_terms(["farinha"], self.vocab)
        self.assertEqual(r.encontrados, {})
        self.assertIn("farinha_de_trigo", r.ambiguos["farinha"])

    def test_termo_desconhecido(self):
        r = resolve_terms(["abacate"], self.vocab)
        self.assertEqual(r.desconhecidos, ["abacate"])

    def test_erros_de_digitacao_sao_corrigidos_e_marcados(self):
        casos = {"frngo": "frango", "frnago": "frango", "framgo": "frango", "peito de frnago": "peito_de_frango",
                 "peito frango": "peito_de_frango", "carnemoida": "carne_bovina_moida", "tomatr": "tomate",
                 "ovs": "ovo", "macarao": "macarrao", "mussarella": "queijo_mussarela", "fejão": "feijao",
                 "salcicha": "salsicha", "cenora": "cenoura", "beterava": "beterraba", "bacom": "bacon",
                 "leite condensando": "leite_condensado", "alfase": "alface", "linguissa": "linguica_calabresa"}
        r = resolve_terms(list(casos), self.vocab)
        for termo, esperado in casos.items():
            with self.subTest(termo=termo):
                self.assertEqual(r.encontrados.get(termo), esperado)
                self.assertIn(termo, r.corrigidos)

    def test_plural_diminutivo_e_quantidade_sem_marcar_correcao(self):
        casos = {"Frangos": "frango", "tomates": "tomate", "limoes": "limao", "paes franceses": "pao_frances",
                 "franguinho": "frango", "pãozinho": "pao_frances", "2 kg de peito de frango": "peito_de_frango",
                 "uma dúzia de ovos": "ovo", "um pouco de arroz": "arroz", "3 dentes de alho": "alho"}
        r = resolve_terms(list(casos), self.vocab)
        for termo, esperado in casos.items():
            with self.subTest(termo=termo):
                self.assertEqual(r.encontrados.get(termo), esperado)
        self.assertEqual(r.corrigidos, {})

    def test_comeco_do_nome(self):
        r = resolve_terms(["cebola roxa", "frango congelado"], self.vocab)
        self.assertEqual(r.encontrados, {"cebola roxa": "cebola", "frango congelado": "frango"})
        self.assertEqual(set(r.corrigidos), {"cebola roxa", "frango congelado"})

    def test_nao_corrige_o_que_nao_e_ingrediente(self):
        r = resolve_terms(["flamengo", "jogo", "carne de porco", "oi", "time"], self.vocab)
        self.assertEqual(r.encontrados, {})
        self.assertEqual(r.ambiguos, {})

    def test_primeira_letra_diferente_nao_e_corrigida(self):
        r = resolve_terms(["sardinha"], self.vocab)
        self.assertEqual(r.encontrados, {"sardinha": "sardinha_em_conserva"})  # não vira "farinha"

    def test_erro_em_termo_ambiguo_continua_ambiguo(self):
        r = resolve_terms(["farinah", "carne de boi", "pão"], self.vocab)
        self.assertIn("farinha_de_trigo", r.ambiguos["farinah"])
        self.assertIn("carne_bovina_alcatra", r.ambiguos["carne de boi"])
        self.assertEqual(r.ambiguos["pão"], ["pao_frances", "pao_de_forma"])

    def test_sem_aproximacao(self):
        r = resolve_terms(["frngo"], self.vocab, aproximado=False)
        self.assertEqual(r.desconhecidos, ["frngo"])

    def test_ambiguos_nao_estao_no_dicionario_e_candidatos_existem(self):
        indice = build_synonym_index(self.vocab["sinonimos"])
        ids = set(self.vocab["ingredientes"]["ingrediente_id"])
        for termo, candidatos in TERMOS_AMBIGUOS.items():
            with self.subTest(termo=termo):
                self.assertNotIn(normalize_text(termo), indice)
                self.assertTrue(set(candidatos) <= ids)


if __name__ == "__main__":
    unittest.main()
