"""Testes da busca de vídeo do Modo Pro (D71), sem chamar o YouTube."""
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from nutrimesa.videos import find_video, search_link  # noqa: E402


class TestVideos(unittest.TestCase):
    def test_acha_o_primeiro_video(self):
        pedidos = []

        def baixar(url):
            pedidos.append(url)
            return {"items": [{"id": {"videoId": "abc123"},
                               "snippet": {"title": "Bolo de cenoura fofinho", "channelTitle": "Cozinha da Vó"}}]}

        video = find_video("Bolo de cenoura", "chave1", baixar)
        self.assertEqual(video, {"id": "abc123", "titulo": "Bolo de cenoura fofinho", "canal": "Cozinha da Vó",
                                 "url": "https://www.youtube.com/watch?v=abc123"})
        q = parse_qs(urlparse(pedidos[0]).query)
        self.assertEqual((q["q"], q["videoEmbeddable"], q["key"]), (["Bolo de cenoura receita"], ["true"], ["chave1"]))

    def test_sem_chave_ou_com_falha_nao_quebra(self):
        self.assertIsNone(find_video("Bolo", None))

        def falha(url):
            raise OSError("cota esgotada")

        self.assertIsNone(find_video("Bolo", "chave1", falha))
        self.assertIsNone(find_video("Bolo", "chave1", lambda url: {"items": []}))

    def test_link_da_busca(self):
        self.assertEqual(search_link("Frango assado"),
                         "https://www.youtube.com/results?search_query=Frango+assado+receita")


if __name__ == "__main__":
    unittest.main()
