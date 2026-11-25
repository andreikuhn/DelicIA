"""Vídeo de alguém fazendo a receita, para o Modo Pro (decisão D71).

Com a YOUTUBE_API_KEY (YouTube Data API v3), busca o vídeo mais relevante em português que pode ser
mostrado dentro de outro site. Sem a chave (ou se a busca falhar), o site oferece o link da busca no
YouTube. As receitas são escritas pela IA: o vídeo é de uma receita com o mesmo nome, não da mesma
receita palavra por palavra, e a tela avisa isso.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

BUSCA_API = "https://www.googleapis.com/youtube/v3/search"


def search_terms(nome: str) -> str:
    return f"{nome.strip()} receita"


def search_link(nome: str) -> str:
    """Busca no YouTube, para abrir numa aba nova (funciona sem chave)."""
    return "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": search_terms(nome)})


def _baixar(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as resposta:  # noqa: S310 - endereço fixo da API do YouTube
        return json.load(resposta)


def find_video(nome: str, chave: str | None, baixar=_baixar) -> dict | None:
    """{"id", "titulo", "canal", "url"} do vídeo mais relevante, ou None (sem chave, sem resultado ou
    falha da API). `baixar` vem de fora nos testes."""
    if not chave or not nome.strip():
        return None
    url = BUSCA_API + "?" + urllib.parse.urlencode({
        "part": "snippet", "type": "video", "maxResults": 1, "q": search_terms(nome), "key": chave,
        "relevanceLanguage": "pt", "regionCode": "BR", "videoEmbeddable": "true", "safeSearch": "strict"})
    try:
        itens = baixar(url).get("items") or []
    except Exception:  # noqa: BLE001 - cota esgotada, chave inválida ou rede: o site mostra o link da busca
        return None
    if not itens or not itens[0].get("id", {}).get("videoId"):
        return None
    video_id, info = itens[0]["id"]["videoId"], itens[0].get("snippet") or {}
    return {"id": video_id, "titulo": info.get("title", ""), "canal": info.get("channelTitle", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}"}
