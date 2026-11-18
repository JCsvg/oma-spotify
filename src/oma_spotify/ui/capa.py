"""Capa: o ponto único onde a interface desenha capas e fotos.

Com imagem (0.5.0): `PROVEDOR` (o serviço `services/capas.py`) devolve a capa de verdade em meio-blocos.
Sem imagem, com capas desligadas, sem ImageMagick, sem rede ou enquanto carrega: um bloco na cor do item,
tirada das cores do tema, com a inicial no meio (em letra grande quando cabe). A foto de artista é redonda
(os cantos ficam na cor do fundo).
"""

from __future__ import annotations

import zlib

from rich.text import Text
from textual.widget import Widget

from oma_spotify.tema import misturar
from oma_spotify.ui.fonte import GLIFOS, _sem_acento

CORES = ("red", "yellow", "green", "cyan", "blue", "magenta", "orange")
PROVEDOR = None  # services.capas.Capas, posto pela app


def cor_do_item(uri: str, tipo: str, paleta: dict) -> str:
    if tipo == "curtidas":
        return paleta["accent"]
    return paleta.get(CORES[zlib.crc32(uri.encode()) % len(CORES)], paleta["accent"])


def inicial(nome: str) -> str:
    for c in _sem_acento(nome or "").upper():
        if c.isalnum():
            return c
    return "♪"


def _elipse(w: int, h: int, y: int) -> tuple[int, int]:
    """Colunas [a, b) dentro do círculo na linha y (células têm o dobro da altura da largura)."""
    cy = (h - 1) / 2
    ry = h / 2
    dy = (y - cy) / ry
    meia = (w / 2) * max(0.0, 1 - dy * dy) ** 0.5
    a = round(w / 2 - meia)
    return max(0, a), min(w, w - a)


def linhas_capa(uri: str, tipo: str, nome: str, w: int, h: int, paleta: dict, redonda: bool | None = None,
                glifo: str = "", imagem: str = "") -> list[Text]:
    """h linhas de w colunas: a imagem, se já estiver pronta; senão o bloco na cor do item com a inicial."""
    w, h = max(1, w), max(1, h)
    if imagem and PROVEDOR is not None:
        r = PROVEDOR.obter(imagem, w, h, tipo == "artist" if redonda is None else redonda, paleta["background"])
        if r is not None:
            return [t.copy() for t in r]
    cor = cor_do_item(uri, tipo, paleta)
    bg = paleta["background"]
    fundo = misturar(cor, bg, 0.22)
    redonda = tipo == "artist" if redonda is None else redonda
    letra = glifo or ("♥" if tipo == "curtidas" else inicial(nome))
    # conteúdo central: letra grande (3x3) quando cabe, senão uma letra só
    centro: list[str]
    g = GLIFOS.get(letra)
    if g is not None and h >= 5 and w >= 9:
        centro = list(g)
    else:
        centro = [letra]
    topo = (h - len(centro)) // 2
    saida = []
    for y in range(h):
        a, b = _elipse(w, h, y) if redonda and h >= 3 else (0, w)
        miolo = [" "] * w
        if topo <= y < topo + len(centro):
            s = centro[y - topo]
            x0 = (w - len(s)) // 2
            for i, ch in enumerate(s):
                if 0 <= x0 + i < w:
                    miolo[x0 + i] = ch
        t = Text()
        if a:
            t.append(" " * a, style=f"on {bg}")
        t.append("".join(miolo[a:b]), style=f"bold {cor} on {fundo}")
        if w - b:
            t.append(" " * (w - b), style=f"on {bg}")
        saida.append(t)
    return saida


class Capa(Widget):
    """Bloco de capa. Tamanho vem do CSS (width e height)."""

    DEFAULT_CSS = "Capa { width: 14; height: 7; }"

    def __init__(self, uri: str = "", tipo: str = "", nome: str = "", redonda: bool | None = None, imagem: str = "", **kw) -> None:
        super().__init__(**kw)
        self.uri, self.tipo, self.nome, self.redonda, self.imagem = uri, tipo, nome, redonda, imagem

    def definir(self, uri: str, tipo: str, nome: str, imagem: str = "") -> None:
        if (uri, tipo, nome, imagem) != (self.uri, self.tipo, self.nome, self.imagem):
            self.uri, self.tipo, self.nome, self.imagem = uri, tipo, nome, imagem
            self.refresh()

    def render(self):
        w, h = self.size
        if not self.uri and not self.nome:
            return Text("\n".join(t.plain for t in linhas_capa("", "", "", w, h, self.app.paleta, glifo="♪")),
                        style=f"{self.app.cor('mudo')} on {self.app.cor('painel')}", justify="left")
        return Text("\n").join(linhas_capa(self.uri, self.tipo, self.nome, w, h, self.app.paleta, self.redonda,
                                            imagem=self.imagem))
