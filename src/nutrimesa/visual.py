"""Identidade visual da DelícIA (decisão D43): ilustrações próprias em SVG e estilo da página.

Conceito: "caderno de receitas da horta". Papel creme com textura, verde-folha, tinta quase preta
e terracota de destaque; títulos em Fraunces (serifa macia, com personalidade) e texto em Nunito
(arredondada e fácil de ler). As ilustrações são desenhadas aqui, à mão em código, sem imagens de
terceiros. Cada desenho tem uma versão para o modo claro e outra para o escuro.
"""
from __future__ import annotations

import base64
import re
from functools import lru_cache

FONTES = ("https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500;"
          "0,9..144,700;1,9..144,500;1,9..144,700&family=Nunito:wght@400;600;700;800&display=swap")

PALETA = {
    "light": {
        "papel": "#FBF7EF", "papel2": "#F2ECDD", "tinta": "#1E2A20", "suave": "#5B6B5C",
        "folha": "#2F6B3B", "folha2": "#5E9A5C", "salvia": "#A9C4A0", "salvia2": "#D8E5CF",
        "terracota": "#C2552D", "tomate": "#D9462F", "mostarda": "#E2A93B", "cenoura": "#E8833A",
        "lima": "#4F8F2A", "polpa": "#D9EDA8",
        "creme": "#FFFDF8", "sombra": "rgba(46, 60, 40, 0.10)", "grao": 0.05, "linha": "#E3DAC6",
        "bolha_ia": "#FFFDF8", "bolha_eu": "#EFEBE1", "xadrez": "rgba(169, 196, 160, 0.22)",
    },
    "dark": {
        "papel": "#111811", "papel2": "#1A241B", "tinta": "#EFE9DA", "suave": "#A9B5A6",
        "folha": "#8BC79A", "folha2": "#5E9A5C", "salvia": "#3E5A43", "salvia2": "#22311F",
        "terracota": "#F0956A", "tomate": "#D86A55", "mostarda": "#D9B25A", "cenoura": "#E0915A",
        "lima": "#8FC45A", "polpa": "#3B5226",
        "creme": "#1D2A1E", "sombra": "rgba(0, 0, 0, 0.40)", "grao": 0.07, "linha": "#2C3A2D",
        "bolha_ia": "#1D2A1E", "bolha_eu": "#243025", "xadrez": "rgba(62, 90, 67, 0.30)",
    },
}


def _p(tema: str | None) -> dict:
    return PALETA["dark" if tema == "dark" else "light"]


def _compacta(svg: str) -> str:
    """SVG numa linha só, sem comentários: o markdown do Streamlit corta HTML com linhas em branco
    ou comentários no meio."""
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    return " ".join(svg.split())


def _b64(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


# ------------------------------------------------------------------ peças de desenho

def _folha(x, y, giro, cor, escala=1.0, nervura="#ffffff", opacidade_nervura=0.35):
    return (f'<g transform="translate({x} {y}) rotate({giro}) scale({escala})">'
            f'<path d="M0 0 C 14 -20, 40 -20, 54 0 C 40 20, 14 20, 0 0 Z" fill="{cor}"/>'
            f'<path d="M3 0 Q 27 -2 51 0" stroke="{nervura}" stroke-opacity="{opacidade_nervura}" '
            f'stroke-width="1.6" fill="none"/></g>')


def _brilho(x, y, tamanho, cor):
    """Estrelinha de quatro pontas: o "IA" da DelícIA."""
    t = tamanho
    return (f'<path d="M{x} {y - t} Q {x + t * 0.18} {y - t * 0.18} {x + t} {y} '
            f'Q {x + t * 0.18} {y + t * 0.18} {x} {y + t} Q {x - t * 0.18} {y + t * 0.18} {x - t} {y} '
            f'Q {x - t * 0.18} {y - t * 0.18} {x} {y - t} Z" fill="{cor}"/>')


def logo_mark(tema: str | None = None, tamanho: int = 44) -> str:
    """Selo: tigela com uma folha brotando e um brilho (a IA)."""
    p = _p(tema)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{tamanho}" '
            f'height="{tamanho}" role="img" aria-label="Selo da DelícIA">'
            f'<circle cx="32" cy="32" r="31" fill="{p["salvia2"]}"/>'
            f'<path d="M12 33 H52 A20 20 0 0 1 12 33 Z" fill="{p["folha"]}"/>'
            f'<path d="M15 33 H49" stroke="{p["papel"]}" stroke-width="2.5" stroke-linecap="round"/>'
            f'<path d="M32 33 C 31 26, 30 21, 26 16" stroke="{p["folha"]}" stroke-width="2.4" '
            f'fill="none" stroke-linecap="round"/>'
            f'<path d="M27 17 C 20 15, 17 20, 18 25 C 24 25, 28 22, 27 17 Z" fill="{p["folha2"]}"/>'
            f'<path d="M31 24 C 35 17, 42 17, 44 21 C 40 26, 34 26, 31 24 Z" fill="{p["folha"]}"/>'
            + _brilho(47, 12, 5.5, p["terracota"]) + '</svg>')


def _letra_e_limao(p: dict) -> str:
    """O "e" como rodela de limão: gomos, o traço do meio e a abertura embaixo à direita."""
    gomos = "".join(f'<path d="M25 25 L{25 + 17 * dx:.1f} {25 + 17 * dy:.1f}" stroke="{p["lima"]}" '
                    f'stroke-width="1.6"/>'
                    for dx, dy in ((0, -1), (0.87, -0.5), (-0.87, -0.5), (-0.87, 0.5), (0, 1)))
    # abertura do "e": fatia que falta entre 0° (o traço) e 40°, embaixo à direita
    return (f'<svg class="dl-letra dl-letra-e" viewBox="0 0 50 50" aria-hidden="true">'
            f'<path d="M25 25 L42.62 39.78 A23 23 0 1 1 48 25 Z" fill="{p["lima"]}"/>'
            f'<path d="M25 25 L39.17 36.89 A18.5 18.5 0 1 1 43.5 25 Z" fill="{p["polpa"]}"/>{gomos}'
            f'<circle cx="25" cy="25" r="2.4" fill="{p["lima"]}"/>'
            f'<rect x="2" y="21.8" width="46" height="6.4" rx="3.2" fill="{p["tinta"]}"/></svg>')


def _letra_l_cenoura(p: dict) -> str:
    """O "l" como cenoura em pé, com rama no topo."""
    return (f'<svg class="dl-letra dl-letra-l" viewBox="0 0 30 84" aria-hidden="true">'
            f'<path d="M15 22 C 10 12, 6 8, 3 2" stroke="{p["folha"]}" stroke-width="3.4" fill="none" '
            f'stroke-linecap="round"/>'
            f'<path d="M15 22 C 15 12, 16 6, 15 0" stroke="{p["folha2"]}" stroke-width="3.4" fill="none" '
            f'stroke-linecap="round"/>'
            f'<path d="M15 22 C 20 12, 24 8, 27 3" stroke="{p["folha"]}" stroke-width="3.4" fill="none" '
            f'stroke-linecap="round"/>'
            f'<path d="M6 24 C 6 19, 24 19, 24 24 L 16.5 81 C 16 84, 14 84, 13.5 81 Z" fill="{p["cenoura"]}"/>'
            f'<path d="M9 36 H14 M17 47 H21 M10 57 H14.5 M16.5 66 H19" stroke="{p["tinta"]}" '
            f'stroke-opacity="0.35" stroke-width="2" stroke-linecap="round"/></svg>')


def _acento_folha(p: dict) -> str:
    """O acento do "í" como folhinha."""
    return (f'<svg class="dl-acento" viewBox="0 0 34 26" aria-hidden="true">'
            f'<path d="M3 23 C 6 10, 18 2, 31 3 C 29 15, 17 24, 3 23 Z" fill="{p["folha"]}"/>'
            f'<path d="M5 21 C 13 15, 21 9, 28 5" stroke="{p["papel"]}" stroke-opacity="0.6" '
            f'stroke-width="1.6" fill="none" stroke-linecap="round"/></svg>')


def wordmark(tema: str | None = None, tamanho: str = "2.4rem") -> str:
    """Selo + nome (decisão D44): "D", "e" de limão, "l" de cenoura, "í" com acento de folha, "c"
    e o "IA" em itálico terracota. Os desenhos ficam no lugar das letras, no fluxo do texto."""
    p = _p(tema)
    nome = (f'D{_letra_e_limao(p)}{_letra_l_cenoura(p)}'
            f'<span class="dl-i">ı{_acento_folha(p)}</span>c<em>IA</em>')
    return (f'<div class="dl-marca">{logo_mark(tema, 52)}'
            f'<span class="dl-nome" role="img" aria-label="DelícIA" style="font-size:{tamanho}">{nome}</span></div>')


def hero_illustration(tema: str | None = None) -> str:
    """Ilustração principal: tigela de salada com vapor que vira brilho, sobre um borrão de horta."""
    p = _p(tema)
    sementes = "".join(f'<ellipse cx="{cx}" cy="{cy}" rx="2" ry="3.4" fill="{p["mostarda"]}" '
                       f'transform="rotate({g} {cx} {cy})"/>'
                       for cx, cy, g in ((214, 138, 20), (226, 146, -30), (206, 150, 60), (220, 128, -70)))
    return _compacta(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 330" width="100%" role="img"
 aria-label="Ilustração de uma tigela de salada fresca" class="dl-hero-svg">
 <path d="M60 210 C 20 140, 70 50, 170 46 C 260 40, 360 70, 382 150 C 404 236, 330 300, 220 300
  C 130 300, 92 268, 60 210 Z" fill="{p["salvia2"]}"/>
 <path d="M84 96 C 120 40, 230 24, 300 60" stroke="{p["salvia"]}" stroke-width="2" fill="none"
  stroke-dasharray="2 9" stroke-linecap="round"/>
 <!-- vapor que vira brilho -->
 <path d="M178 98 C 168 80, 190 70, 180 50" stroke="{p["suave"]}" stroke-width="3" fill="none"
  stroke-linecap="round" opacity="0.55"/>
 <path d="M214 92 C 204 72, 228 62, 216 38" stroke="{p["suave"]}" stroke-width="3" fill="none"
  stroke-linecap="round" opacity="0.55"/>
 {_brilho(182, 40, 10, p["terracota"])}{_brilho(222, 26, 6, p["mostarda"])}{_brilho(250, 54, 4, p["terracota"])}
 <!-- folhas saindo da tigela -->
 {_folha(110, 150, -40, p["folha2"], 1.25)}{_folha(150, 128, -70, p["folha"], 1.2)}
 {_folha(250, 112, -110, p["folha"], 1.25)}{_folha(282, 140, -140, p["folha2"], 1.2)}
 {_folha(190, 118, -95, p["salvia"], 1.0)}
 <!-- tomate em rodela -->
 <circle cx="218" cy="140" r="27" fill="{p["tomate"]}"/>
 <circle cx="218" cy="140" r="20" fill="none" stroke="#ffffff" stroke-opacity="0.35" stroke-width="2"/>
 {sementes}
 <!-- limão em rodela -->
 <circle cx="152" cy="150" r="22" fill="{p["mostarda"]}"/>
 <circle cx="152" cy="150" r="16" fill="#FFF3C4" opacity="0.85"/>
 <path d="M152 134 V166 M136 150 H168 M141 139 L163 161 M163 139 L141 161" stroke="{p["mostarda"]}"
  stroke-width="1.6"/>
 <!-- cenoura em palitos -->
 <rect x="262" y="118" width="9" height="46" rx="4.5" fill="{p["cenoura"]}" transform="rotate(28 266 141)"/>
 <rect x="276" y="122" width="9" height="40" rx="4.5" fill="{p["cenoura"]}" transform="rotate(40 280 142)"/>
 <!-- tigela -->
 <path d="M86 160 H334 C 330 236, 278 276, 210 276 C 142 276, 90 236, 86 160 Z" fill="{p["creme"]}"
  stroke="{p["tinta"]}" stroke-width="3"/>
 <path d="M98 184 C 150 196, 270 196, 322 184" stroke="{p["folha"]}" stroke-width="5" fill="none"
  stroke-linecap="round"/>
 <path d="M104 200 C 156 212, 264 212, 316 200" stroke="{p["terracota"]}" stroke-width="2" fill="none"
  stroke-dasharray="1 8" stroke-linecap="round"/>
 <path d="M80 160 H340" stroke="{p["tinta"]}" stroke-width="3.5" stroke-linecap="round"/>
 <ellipse cx="210" cy="292" rx="70" ry="7" fill="{p["tinta"]}" opacity="0.10"/>
 <!-- raminhos soltos -->
 {_folha(44, 260, -20, p["folha2"], 0.7)}{_folha(352, 82, 30, p["folha2"], 0.6)}
</svg>""")


def sprig(tema: str | None = None, largura: int = 180) -> str:
    """Raminho em traço, para enfeitar cantos (estilo desenho de caderno)."""
    p = _p(tema)
    folhas = "".join(
        f'<path d="M{x} {y} C {x + 8 * s} {y - 14}, {x + 24 * s} {y - 12}, {x + 26 * s} {y - 2} '
        f'C {x + 14 * s} {y + 4}, {x + 4 * s} {y + 2}, {x} {y} Z" fill="none" stroke="{p["folha"]}" '
        f'stroke-width="2" stroke-linejoin="round"/>'
        for x, y, s in ((40, 70, 1), (60, 54, -1), (78, 46, 1), (96, 32, -1), (112, 26, 1)))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 90" width="{largura}" '
            f'aria-hidden="true"><path d="M10 84 C 50 70, 90 50, 140 14" stroke="{p["folha"]}" '
            f'stroke-width="2.4" fill="none" stroke-linecap="round"/>{folhas}'
            f'{_brilho(146, 10, 5, p["terracota"])}</svg>')


def divider(tema: str | None = None) -> str:
    """Linha ondulada com folhinha no meio."""
    p = _p(tema)
    return (f'<div class="dl-divisor"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 24" '
            f'width="100%" height="24" preserveAspectRatio="none" aria-hidden="true">'
            f'<path d="M0 12 Q 25 2 50 12 T 100 12 T 150 12 T 200 12 T 250 12 M350 12 Q 375 2 400 12 '
            f'T 450 12 T 500 12 T 550 12 T 600 12" stroke="{p["salvia"]}" stroke-width="2" fill="none"/>'
            f'{_folha(282, 12, -20, p["folha2"], 0.7)}</svg></div>')


ICONES = {
    "geladeira": '<rect x="7" y="3" width="18" height="26" rx="4"/><path d="M7 13 H25 M11 7 V10 M11 17 V22"/>',
    "porcoes": '<circle cx="11" cy="12" r="4"/><circle cx="22" cy="12" r="4"/><path d="M4 26 C 5 20, 17 20, 18 26 M15 26 C 16 20, 28 20, 29 26"/>',
    "escudo": '<path d="M16 3 L27 7 V15 C 27 22, 22 27, 16 29 C 10 27, 5 22, 5 15 V7 Z"/><path d="M11 16 L15 20 L22 12"/>',
    "calendario": '<rect x="4" y="6" width="24" height="22" rx="4"/><path d="M4 13 H28 M10 3 V9 M22 3 V9 M10 19 H13 M17 19 H20 M10 23 H13"/>',
}


def icon(nome: str, tema: str | None = None, tamanho: int = 30) -> str:
    p = _p(tema)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="{tamanho}" height="{tamanho}" '
            f'fill="none" stroke="{p["folha"]}" stroke-width="2.2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{ICONES[nome]}</svg>')


def feature_cards(tema: str | None, itens: list[tuple[str, str, str]]) -> str:
    """Cartões curtos (ícone, título, texto) da página de entrada."""
    cartoes = "".join(f'<div class="dl-cartao">{icon(i, tema)}<div><strong>{t}</strong><span>{d}</span></div></div>'
                      for i, t, d in itens)
    return f'<div class="dl-cartoes">{cartoes}</div>'


# ------------------------------------------------------------------ estilo da página

def _grao(tema: str | None) -> str:
    """Textura de papel (ruído bem fraco)."""
    p = _p(tema)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180">'
           '<filter id="g"><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" '
           'stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.9 0"/>'
           f'</filter><rect width="100%" height="100%" filter="url(#g)" opacity="{p["grao"]}"/></svg>')
    return _b64(svg)


_MACA = ("M32 18c-6-5-18-4-22 6-5 12 2 30 12 33 4 1 7-1 10-1s6 2 10 1"
         "c10-3 17-21 12-33-4-10-16-11-22-6z")
_CABO = ('<path d="M32 18c0-5 1-9 4-12" stroke="#6B4423" stroke-width="3" fill="none" stroke-linecap="round"/>'
         '<path d="M34 12c4-6 12-6 14-3-3 5-9 6-14 3z" fill="#5E9A5C"/>')


def apple(mordida: bool = False) -> str:
    """Maçã da receita (D58): inteira = ainda não comeu; mordida pela metade = comeu 1 porção."""
    if not mordida:
        corpo = (f'<path d="{_MACA}" fill="#D9462F"/>'
                 '<ellipse cx="20" cy="30" rx="3" ry="6" fill="#fff" opacity=".35"/>')
    else:  # as mordidas tiram a metade direita e deixam a polpa aparecendo na borda
        mordidas = ((54, 26, 13), (50, 46, 12))
        corpo = ('<defs><clipPath id="c"><path d="' + _MACA + '"/></clipPath><mask id="m">'
                 '<rect width="64" height="64" fill="#fff"/>'
                 + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#000"/>' for x, y, r in mordidas)
                 + '</mask></defs><g mask="url(#m)"><path d="' + _MACA + '" fill="#D9462F"/>'
                 '<g clip-path="url(#c)">'
                 + "".join(f'<circle cx="{x}" cy="{y}" r="{r + 3}" fill="#F6E7C8"/>' for x, y, r in mordidas)
                 + '</g></g><ellipse cx="20" cy="30" rx="3" ry="6" fill="#fff" opacity=".35"/>')
    return _b64(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{corpo}{_CABO}</svg>')


def _variaveis(tema: str) -> str:
    p = PALETA[tema]
    return ";".join(f"--dl-{k}:{v}" for k, v in p.items() if k != "grao") + f';--dl-grao:url("{_grao(tema)}")'


def page_css(tema: str | None = None) -> str:
    """CSS da página. Usa os data-testid do Streamlit, que mudam menos que as classes.

    As cores são variáveis CSS com as duas paletas (D65): trocar claro/escuro muda as cores na hora, pelo
    JavaScript que marca <html data-dl-tema>, sem esperar o Python rodar de novo. A marca escondida
    .dl-tema-escuro vale até o JavaScript marcar (primeiro carregamento)."""
    marca = '<span class="dl-tema-escuro" hidden></span>' if tema == "dark" else ""
    return _css_fixo() + marca


@lru_cache(maxsize=1)
def _css_fixo() -> str:
    """O CSS não depende do tema: montado uma vez por processo (antes era refeito a cada clique)."""
    p = {k: f"var(--dl-{k})" for k in PALETA["light"]}
    claro, escuro = _variaveis("light"), _variaveis("dark")
    return _compacta(f"""
<style>
@import url('{FONTES}');
:root {{ {claro} }}
:root:has(.dl-tema-escuro) {{ {escuro} }}
html:root[data-dl-tema="light"] {{ {claro} }}
html:root[data-dl-tema="dark"] {{ {escuro} }}
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"], button, input, textarea {{
  font-family: 'Nunito', system-ui, sans-serif;
}}
h1, h2, h3, h4, .dl-nome, .dl-titulo {{
  font-family: 'Fraunces', Georgia, serif !important; letter-spacing: -0.01em; text-wrap: balance;
}}
/* o que o navegador desenha sozinho também segue a paleta */
::selection {{ background: {p["salvia"]}; color: {p["tinta"]}; }}
:focus-visible {{ outline: 2px solid {p["folha"]} !important; outline-offset: 2px; }}
[data-testid="stMarkdownContainer"] h4 {{ font-size: 1.15rem; margin: 1.4rem 0 0.4rem 0; padding: 0; }}
/* Mesa posta (D63): o fundo é uma toalha xadrez bem clarinha e cada página é uma folha de receita
   apoiada nela. A entrada (app.tela_entrada) tira a folha e serve a tigela num prato. */
[data-testid="stAppViewContainer"] {{
  background-color: {p["papel"]};
  background-image:
    var(--dl-grao),
    linear-gradient(90deg, {p["xadrez"]} 50%, transparent 50%),
    linear-gradient({p["xadrez"]} 50%, transparent 50%);
  background-size: auto, 56px 56px, 56px 56px;
  background-attachment: fixed;
}}
[data-testid="stHeader"] {{ background: transparent; }}
/* menu ⋮: sem "Print" e "Record screen" (ficam o tema, Rerun e Clear cache) */
[data-testid="stMainMenuItem-print"], [data-testid="stMainMenuItem-recordScreencast"] {{ display: none !important; }}
/* sem Deploy, GitHub e Fork no alto (botões do Streamlit Cloud); o menu ⋮ (claro/escuro) fica */
[data-testid="stToolbarActions"], [data-testid="stToolbarActionButton"], [data-testid="stAppDeployButton"], .stAppDeployButton, .stDeployButton {{ display: none !important; }}
[data-testid="stSidebar"] {{
  background-image: var(--dl-grao);
}}
/* marca */
.dl-marca {{ display: flex; align-items: center; gap: 0.7rem; }}
.dl-nome {{ font-weight: 700; line-height: 1; color: {p["tinta"]}; white-space: nowrap; }}
.dl-letra {{ display: inline-block; vertical-align: baseline; }}
.dl-letra-e {{ width: 0.5em; height: 0.5em; margin: 0 0.02em 0 0.03em; }}
.dl-letra-l {{ width: 0.27em; height: 0.76em; margin: 0 0.03em -0.02em 0.04em; }}
.dl-i {{ position: relative; display: inline-block; }}
.dl-acento {{ position: absolute; width: 0.3em; height: 0.23em; left: -0.05em; top: 0.11em; }}
.dl-nome em {{ color: {p["terracota"]}; font-style: italic; }}
.dl-selo {{
  display: inline-block; padding: 0.25rem 0.8rem; border-radius: 999px; font-size: 0.82rem;
  font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
  color: {p["folha"]}; background: {p["salvia2"]}; border: 1px dashed {p["folha2"]};
}}
.dl-titulo {{ font-size: clamp(2.2rem, 4.6vw, 3.6rem); font-weight: 700; line-height: 1.05;
  margin: 0.8rem 0 0.6rem 0; color: {p["tinta"]}; }}
.dl-sub {{ font-size: 1.15rem; color: {p["suave"]}; max-width: 34rem; }}
.dl-hero-svg {{ max-width: 460px; display: block; margin: 0 auto; filter: drop-shadow(0 18px 24px {p["sombra"]}); }}
/* recursos: uma faixa de 4 itens soltos no papel, sem caixa em volta */
.dl-cartoes {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1.6rem;
  margin: 1.2rem 0 2rem 0; }}
@media (max-width: 900px) {{ .dl-cartoes {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 520px) {{ .dl-cartoes {{ grid-template-columns: 1fr; gap: 1rem; }} }}
.dl-cartao {{ display: flex; gap: 0.7rem; align-items: flex-start; }}
.dl-cartao strong {{ display: block; color: {p["tinta"]}; margin-bottom: 0.15rem; }}
.dl-cartao span {{ font-size: 0.92rem; color: {p["suave"]}; line-height: 1.45; }}
.dl-divisor {{ margin: 1.2rem 0 0.6rem 0; }}
/* dentro da folha, os blocos são áreas do papel (sem sombra), não cartões em cima do cartão */
[data-testid="stForm"] {{
  background: {p["papel"]}; border: 1px solid {p["linha"]} !important; border-radius: 1.4rem;
  padding: 1.4rem 1.4rem 1rem 1.4rem;
}}
[data-testid="stMetric"] {{
  background: {p["papel"]}; border: 1px solid {p["linha"]}; border-radius: 1.1rem; padding: 0.8rem 1rem;
}}
[data-testid="stMetric"] {{ min-height: 6.4rem; }}
[data-testid="stMetricValue"] {{ font-family: 'Fraunces', Georgia, serif; font-size: 1.85rem;
  font-variant-numeric: tabular-nums; }}
[data-testid="stMetricValue"] * {{ overflow: visible !important; text-overflow: clip !important; }}
/* título do quadro inteiro, quebrando linha, em vez de cortado com "..." */
[data-testid="stMetricLabel"] * {{ white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; }}
/* abas como etiquetas */
[data-testid="stTabs"] [role="tablist"] {{ gap: 0.45rem; flex-wrap: wrap; border-bottom: none !important;
  box-shadow: none !important; margin-bottom: 0.6rem; }}
[data-testid="stTab"] {{
  border-radius: 999px !important; padding: 0.3rem 1.05rem !important;
  border: 1px solid {p["linha"]} !important; background: {p["papel"]}; box-shadow: none !important;
}}
/* avisos fixos do Streamlit em inglês ("Press Enter to submit form", "Running...") */
[data-testid="InputInstructions"], [data-testid="stStatusWidget"] {{ display: none !important; }}
@media (max-width: 640px) {{ .dl-enfeite {{ display: none; }} }}
[data-testid="stTab"]::after, [data-testid="stTab"]::before,
[data-testid="stTabs"] [role="tablist"]::after, [data-testid="stTabs"] [role="tablist"]::before {{
  display: none !important; }}
[data-testid="stTab"][aria-selected="true"] {{ background: {p["folha"]}; border-color: {p["folha"]} !important; }}
[data-testid="stTab"][aria-selected="true"] p {{ color: {p["papel"]} !important; font-weight: 800; }}
/* botões */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {{
  box-shadow: 0 8px 18px {p["sombra"]}; font-weight: 800;
}}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p {{
  color: {p["papel"]} !important; font-weight: 800;
}}
/* conversa: a resposta é escrita direto na folha; a pergunta da pessoa fica num balão */
[data-testid="stChatMessage"] {{ background: transparent; padding: 0.6rem 0.2rem; }}
[data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {{
  background: {p["bolha_eu"]}; border: 1px solid {p["linha"]}; border-radius: 1.2rem 1.2rem 0.3rem 1.2rem;
  padding: 0.7rem 1rem;
}}
[data-testid="stChatInput"] {{ border-radius: 999px; }}
/* faixa da caixa de texto sem fundo próprio: o papel continua até embaixo */
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] {{
  background: transparent !important; }}
/* maçã da receita (D58): botão com o desenho; a chave do botão diz se está inteira ou mordida */
[class*="st-key-maca_"] button, [class*="st-key-mordida_"] button {{
  width: 3.2rem; height: 3.2rem; min-height: 0; padding: 0; border: none !important;
  background: url("{apple()}") center / contain no-repeat !important; box-shadow: none !important;
  transition: transform .15s;
}}
[class*="st-key-mordida_"] button {{ background-image: url("{apple(True)}") !important; }}
[class*="st-key-maca_"] button:hover, [class*="st-key-mordida_"] button:hover {{ transform: scale(1.08); }}
/* cardápio compacto (D68): cada prato numa linha, separada por um fio; botões só com ícone ao lado */
[class*="st-key-pratos_"] {{ gap: 0.25rem; }}
[class*="st-key-prato_"] {{ padding: 0.3rem 0.2rem; border-bottom: 1px solid {p["linha"]}; gap: 0; }}
[class*="st-key-prato_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; }}
[class*="st-key-prato_"] [data-testid="stColumn"] {{ min-width: 0 !important; }}
[class*="st-key-prato_"] [data-testid="stColumn"]:not(:first-child) {{ flex: 0 0 auto !important; width: auto !important; }}
[class*="st-key-prato_"] [data-testid="stCaptionContainer"] {{ margin-top: -0.7rem; }}
[class*="st-key-prato_"] [data-testid="stMarkdownContainer"] p {{ margin-bottom: 0.2rem; }}
/* prato que a pessoa já comeu esta semana (maçã): a linha fica verdinha */
[class*="st-key-prato_comido_"] {{ background: {p["salvia2"]}; border-radius: 0.9rem; border-bottom-color: transparent;
  padding-left: 0.7rem; padding-right: 0.5rem; }}
[class*="st-key-prato_comido_"] .dl-refeicao {{ background: {p["creme"]}; }}
/* maçã pequena na linha do prato, ao lado de "trocar" */
[class*="st-key-prato_"] [class*="st-key-maca_"] button, [class*="st-key-prato_"] [class*="st-key-mordida_"] button {{
  width: 2.4rem; height: 2.4rem; }}
/* celular: o nome do prato ocupa a linha toda e os botões descem para uma fileira embaixo, à direita;
   os 7 dias rolam de lado em vez de apertar */
@media (max-width: 640px) {{
  [class*="st-key-prato_"] [data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; justify-content: flex-end;
    row-gap: 0.1rem; }}
  [class*="st-key-prato_"] [data-testid="stColumn"]:first-child {{ flex: 1 0 100% !important; }}
  [class*="st-key-dia_"] [data-testid="stButtonGroup"] > div {{ flex-wrap: nowrap; overflow-x: auto; scrollbar-width: thin; }}
  [class*="st-key-dia_"] [data-testid="stButtonGroup"] button {{ flex: none; }}
}}
.dl-refeicao {{ display: inline-block; font-size: 0.78rem; font-weight: 700; color: {p["folha"]}; background: {p["salvia2"]};
  border-radius: 999px; padding: 0.05rem 0.55rem; margin-right: 0.35rem; vertical-align: 0.1em; }}
/* componentes invisíveis (sessão e tema): sem ocupar espaço */
.st-key-ocultos {{ display: none; }}
/* layout de conversa (D57): coluna central estreita, como nos assistentes conhecidos */
[data-testid="stMainBlockContainer"] {{
  max-width: 56rem; background: {p["creme"]}; border: 1px solid {p["linha"]}; border-radius: 1.6rem;
  margin-top: 2.6rem; padding-top: 2rem !important; padding-left: 2.4rem !important;
  min-height: calc(100vh - 12rem); /* conversa curta: a folha vai até perto da caixa de texto */
  padding-bottom: 2rem !important; /* o Streamlit deixa 10rem embaixo; só a conversa precisa (caixa de texto) */
  flex-shrink: 0; /* o stMain é flex: sem isto a folha encolhia à altura da tela e o texto vazava para o xadrez */
  padding-right: 2.4rem !important; box-shadow: 0 2px 0 {p["linha"]}, 0 18px 40px {p["sombra"]};
  position: relative;
}}
.stApp:has([data-testid="stChatInput"]) [data-testid="stMainBlockContainer"] {{ padding-bottom: 10rem !important; }}
/* categorias acima da caixa de texto (D73): etiquetas pequenas, numa faixa só que rola de lado no celular */
/* agora dentro da caixa "Filtros": as etiquetas quebram linha em vez de rolar de lado */
.st-key-categorias_chat [data-testid="stButtonGroup"] > div {{ flex-wrap: wrap; }}
.st-key-filtros_chat {{ gap: 0.6rem; }}
.st-key-filtros_chat button {{ min-height: 2rem; padding: 0.15rem 0.9rem; border-radius: 999px; }}
.st-key-categorias_chat button {{ min-height: 1.9rem; padding: 0.1rem 0.75rem; white-space: nowrap; flex: none; }}
.st-key-categorias_chat button p {{ font-size: 0.85rem; }}
.st-key-categorias_chat button[data-selected="true"], .st-key-categorias_chat button[aria-checked="true"] {{
  background: {p["folha"]} !important; border-color: {p["folha"]} !important; }}
.st-key-categorias_chat button[data-selected="true"] p, .st-key-categorias_chat button[aria-checked="true"] p {{
  color: {p["papel"]} !important; font-weight: 700; }}
/* o picote do cartão de receita, no alto da folha */
[data-testid="stMainBlockContainer"]::before {{
  content: ""; position: absolute; left: 2.4rem; right: 2.4rem; top: 1.1rem; border-top: 2px dashed {p["salvia"]};
}}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ margin: 3.2rem 0.5rem 0 0.5rem; padding-left: 1.1rem !important;
    padding-right: 1.1rem !important; }}
  [data-testid="stMainBlockContainer"]::before {{ left: 1.1rem; right: 1.1rem; }}
}}
/* entrada e carregamento: sem a folha, direto na toalha. Vale só enquanto a própria tela está na página
   (:has), para nunca sobrar depois do login ou do F5 */
[data-testid="stMainBlockContainer"]:has(.dl-topo-centro), [data-testid="stMainBlockContainer"]:has(.dl-carregando) {{
  background: transparent; border: none; box-shadow: none; }}
[data-testid="stMainBlockContainer"]:has(.dl-topo-centro)::before,
[data-testid="stMainBlockContainer"]:has(.dl-carregando)::before {{ display: none; }}
[data-testid="stMainBlockContainer"]:has(.dl-topo-centro) {{ max-width: 62rem; margin-top: 0; min-height: 0;
  padding-top: 1.2rem !important; padding-bottom: 1rem !important; }}
/* entrada (Mesa posta): a tigela num prato e o acesso num cartão de receita sobre a toalha */
.dl-topo-centro {{ display: flex; justify-content: center; margin-bottom: 0.4rem; }}
/* nada de texto solto no xadrez: o nome e o título ficam sobre o creme (guardanapo) */
.dl-topo-centro .dl-marca {{ background: {p["creme"]}; border: 1px solid {p["linha"]}; border-radius: 999px;
  padding: 0.3rem 1.1rem 0.3rem 0.35rem; box-shadow: 0 6px 16px {p["sombra"]}; }}
.dl-guardanapo {{ background: {p["creme"]}; border: 1px solid {p["linha"]}; border-radius: 1.2rem;
  padding: 0.9rem 1.4rem 1rem; margin: 1.1rem auto 0; max-width: 28rem; box-shadow: 0 10px 24px {p["sombra"]}; }}
.dl-prato {{ text-align: center; }}
.dl-disco {{ width: min(340px, 100%); aspect-ratio: 1; margin: 0 auto; border-radius: 50%; display: grid;
  place-items: center; background: radial-gradient(circle, {p["creme"]} 0 58%, {p["papel2"]} 58% 61%, {p["creme"]} 61%);
  max-width: 44vh; /* o prato encolhe em telas baixas: a entrada não rola */
  box-shadow: 0 2px 0 {p["linha"]}, 0 26px 50px {p["sombra"]}; }}
.dl-disco .dl-hero-svg {{ width: 78%; filter: none; }}
.dl-prato .dl-titulo {{ font-size: clamp(1.7rem, 2.8vw, 2.3rem); margin: 0 auto 0.35rem; max-width: 15em; }}
.dl-prato .dl-sub {{ margin: 0 auto; font-size: 1.02rem; }}
.st-key-cartao_acesso {{
  background: {p["creme"]}; border: 1px solid {p["linha"]}; border-radius: 1.4rem; padding: 1.8rem 1.8rem 1rem;
  box-shadow: 0 2px 0 {p["linha"]}, 0 18px 40px {p["sombra"]}; position: relative;
}}
.st-key-cartao_acesso::before {{ content: ""; position: absolute; left: 1.8rem; right: 1.8rem; top: 0.9rem;
  border-top: 2px dashed {p["salvia"]}; }}
.st-key-cartao_acesso [data-testid="stForm"] {{ background: transparent; border: none !important; padding: 0; }}
/* "Criar conta" com dois campos por linha também no celular: a entrada não rola */
.st-key-cartao_acesso [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; gap: 0.6rem; }}
.st-key-cartao_acesso [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{ min-width: 0 !important;
  width: auto !important; flex: 1 1 0 !important; }}
/* entrar com o Google (D70): botão branco com o "G", como nos outros sites, e a linha "ou" embaixo */
.dl-google {{ display: flex; align-items: center; justify-content: center; gap: 0.6rem; margin: 0.5rem 0 0;
  padding: 0.65rem 1rem; border-radius: 999px; background: #FFFFFF; color: #1F1F1F !important; font-weight: 700;
  border: 1px solid {p["linha"]}; text-decoration: none !important; box-shadow: 0 4px 12px {p["sombra"]};
  transition: border-color .15s; }}
.dl-google:hover {{ border-color: {p["folha"]}; }}
.dl-google:focus-visible {{ outline: 2px solid {p["folha"]}; outline-offset: 2px; }}
.dl-ou {{ display: flex; align-items: center; gap: 0.6rem; color: {p["suave"]}; font-size: 0.85rem; margin: 0.4rem 0 -0.4rem; }}
.dl-ou::before, .dl-ou::after {{ content: ""; flex: 1; border-top: 1px solid {p["linha"]}; }}
/* links do cartão de acesso (D74): "Esqueci a senha" discreto à direita, "Criar conta"/"Entrar" no pé */
.st-key-cartao_acesso [class*="st-key-ir_"] {{ align-self: center; }}
.st-key-cartao_acesso .st-key-ir_recuperar {{ align-self: flex-end; margin-top: -0.6rem; }}
.st-key-cartao_acesso [class*="st-key-ir_"] button {{ min-height: 0; padding: 0.1rem 0.2rem; }}
.st-key-cartao_acesso [class*="st-key-ir_"] button p {{ font-size: 0.88rem; color: {p["suave"]}; }}
.st-key-cartao_acesso [class*="st-key-ir_"] button strong {{ color: {p["folha"]}; }}
.st-key-cartao_acesso .st-key-ir_recuperar button p {{ color: {p["folha"]}; font-size: 0.82rem; }}
.dl-cartao-titulo {{ font-size: 1.6rem !important; margin: 0 !important; padding: 0 !important; }}
@media (max-width: 640px) {{
  /* no celular fica só o acesso (o prato não cabe sem rolar) */
  [data-testid="stColumn"]:has(.dl-prato) {{ display: none; }}
}}
.dl-boasvindas {{ text-align: center; margin: 0 auto 0.8rem; max-width: 34rem; }}
.dl-boasvindas h2 {{ font-size: clamp(1.5rem, 2.6vw, 1.9rem); margin: 0.3rem 0 0.3rem; padding: 0; }}
.dl-boasvindas p {{ color: {p["suave"]}; font-size: 0.98rem; line-height: 1.5; margin-bottom: 0; }}
/* a tigela acompanha a altura da tela: a conversa vazia cabe sem rolar */
.dl-boasvindas-tigela {{ width: clamp(80px, 15vh, 150px); margin: 0 auto; }}
/* conversa ainda vazia: folha só do tamanho do conteúdo (sem rolar); depois da 1ª mensagem volta ao normal */
.stApp:has(.dl-boasvindas) [data-testid="stMainBlockContainer"] {{ min-height: 0; margin-top: 1.2rem;
  padding-top: 1.8rem !important; padding-bottom: 7.5rem !important; }}
.dl-boasvindas-tigela .dl-hero-svg {{ filter: none; }}
/* os dois jeitos de começar: cartões de receita com ícone, título e um exemplo para tocar */
[class*="st-key-inicio_"] button {{ justify-content: flex-start; text-align: left; padding: 1rem 1.1rem;
  min-height: 5.2rem; border-radius: 1.2rem; background: {p["papel"]}; border: 1px solid {p["linha"]};
  transition: border-color .15s, transform .15s; }}
[class*="st-key-inicio_"] button:hover {{ border-color: {p["folha"]}; transform: translateY(-2px); }}
[class*="st-key-inicio_"] button > div {{ justify-content: flex-start; align-items: flex-start; }}
[class*="st-key-inicio_"] button p {{ color: {p["suave"]}; white-space: normal; line-height: 1.45; text-align: left; }}
[class*="st-key-inicio_"] button strong {{ color: {p["tinta"]}; }}
[class*="st-key-inicio_"] button [data-testid="stIconMaterial"] {{ color: {p["folha"]}; font-size: 1.5rem; }}
.dl-rotulo {{ font-size: 0.8rem; font-weight: 700; color: {p["suave"]}; margin: 0.8rem 0 0.2rem 0; }}
/* barra lateral: conversas e menu alinhados à esquerda, como uma lista */
[data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"],
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{ justify-content: flex-start; text-align: left; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"] > div,
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] > div {{ justify-content: flex-start; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{ background: {p["creme"]}; border-color: {p["linha"]}; }}
/* no celular o Streamlit empilha colunas: a lixeira da conversa ficava embaixo do título */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap !important; }}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
  min-width: 0 !important; width: auto !important; flex: 1 1 0 !important; }}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {{
  flex: 0 0 auto !important; }}
/* mesmo recuo do item aberto (secundário), para o texto não pular quando muda de item */
[data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"] {{ padding: 4px 12.8px !important; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-tertiary"]:hover {{ background: {p["creme"]}; }}
/* painéis com fundo de horta: st.container(key="painel...") vira a classe st-key-painel... */
[class*="st-key-painel"] {{
  background: {p["papel"]}; border: 1px solid {p["linha"]}; border-radius: 1.6rem; padding: 1.2rem 1.6rem;
}}
</style>
""")
