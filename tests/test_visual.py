"""Testes das ilustrações e do estilo (só conferem que o HTML/SVG sai bem formado)."""
import base64
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa import visual  # noqa: E402


class TestVisual(unittest.TestCase):
    def test_desenhos_sao_svg_validos_nos_dois_modos(self):
        for tema in ("light", "dark", None):
            for desenho in (visual.hero_illustration, visual.logo_mark, visual.sprig):
                with self.subTest(tema=tema, desenho=desenho.__name__):
                    ET.fromstring(desenho(tema))
            for nome in visual.ICONES:
                ET.fromstring(visual.icon(nome, tema))

    def test_modos_usam_cores_diferentes(self):
        self.assertNotEqual(visual.hero_illustration("light"), visual.hero_illustration("dark"))

    def test_textura_de_papel_e_svg_valido(self):
        css = visual.page_css("light")
        dado = re.search(r"data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)", css).group(1)
        ET.fromstring(base64.b64decode(dado))

    def test_marca_tem_o_nome_e_ingredientes_nas_letras(self):
        html = visual.wordmark("light")
        self.assertIn('aria-label="DelícIA"', html)
        self.assertIn("<em>IA</em>", html)  # o "IA" final fica como letra
        for classe in ("dl-letra-e", "dl-letra-l", "dl-acento"):
            self.assertIn(classe, html)
        for desenho in re.findall(r"<svg.*?</svg>", html, flags=re.S):
            ET.fromstring(desenho.replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" ', 1)
                          if "xmlns" not in desenho else desenho)

    def test_cartoes(self):
        html = visual.feature_cards("light", [("escudo", "Título", "Texto")])
        self.assertIn("Título", html)
        self.assertIn("<svg", html)


if __name__ == "__main__":
    unittest.main()
