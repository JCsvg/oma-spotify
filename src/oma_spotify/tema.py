"""Cores do tema ativo do Omarchy (colors.toml), convertidas num tema do Textual.

Os tons que o tema não traz saem da mistura do texto com o fundo, então qualquer
tema funciona, inclusive os claros.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from textual.theme import Theme

PADRAO = {"background": "#1a1b26", "foreground": "#a9b1d6", "accent": "#7aa2f7", "muted": "#565f89",
          "red": "#f7768e", "green": "#9ece6a", "yellow": "#e0af68", "blue": "#7aa2f7", "selection": "#2f3b54",
          "cyan": "#449dab", "magenta": "#ad8ee6", "orange": "#eb927b"}


def arquivo_do_tema() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return base / "omarchy" / "current" / "theme" / "colors.toml"


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def misturar(a: str, b: str, t: float) -> str:
    """t de `a` sobre `b` (0 = b, 1 = a)."""
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x * t + y * (1 - t)):02x}" for x, y in zip(ra, rb))


def ler() -> dict:
    cores = dict(PADRAO)
    escuro = True
    try:
        dados = tomllib.loads(arquivo_do_tema().read_text())
        escuro = str(dados.get("mode", "dark")).lower() != "light"
        for k, v in dados.items():
            if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7):
                cores[k] = v
    except (OSError, ValueError):
        pass
    fg, bg = cores["foreground"], cores["background"]
    cores["escuro"] = escuro
    # papéis da tabela de cores do design
    cores["fundo"] = bg
    cores["fundo_escuro"] = cores.get("dark_background") or misturar("#000000" if escuro else "#ffffff", bg, 0.2)
    cores["campo"] = cores.get("lighter_background") or misturar(fg, bg, 0.13)
    cores["painel"] = misturar(fg, bg, 0.06)
    cores["hover"] = misturar(fg, bg, 0.045)
    cores["texto"] = fg
    cores["forte"] = cores.get("bright_foreground") or cores.get("light_foreground") or fg
    cores["mudo"] = cores.get("dark_foreground") or cores["muted"]
    cores["linha"] = misturar(fg, bg, 0.24)
    cores["selecao"] = cores["selection"]
    return cores


def tema_textual(nome: str = "omarchy", c: dict | None = None) -> Theme:
    c = c or ler()
    return Theme(
        name=nome, primary=c["accent"], secondary=c["blue"], accent=c["accent"],
        foreground=c["foreground"], background=c["background"],
        surface=c["fundo_escuro"], panel=c["painel"],
        success=c["green"], warning=c["yellow"], error=c["red"], dark=c["escuro"],
        variables={"footer-key-foreground": c["accent"], "oma-mudo": c["mudo"], "oma-selecao": c["selecao"],
                   "oma-linha": c["linha"], "oma-painel": c["painel"], "oma-campo": c["campo"], "oma-forte": c["forte"],
                   "oma-hover": c["hover"], "oma-escuro": c["fundo_escuro"],
                   "scrollbar": c["linha"], "scrollbar-hover": c["mudo"], "scrollbar-active": c["accent"],
                   "scrollbar-background": c["background"], "scrollbar-background-hover": c["background"],
                   "scrollbar-background-active": c["background"], "scrollbar-corner-color": c["background"]},
    )
