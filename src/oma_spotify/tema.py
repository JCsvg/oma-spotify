"""Cores do tema ativo do Omarchy (colors.toml), convertidas num tema do Textual."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from textual.theme import Theme

PADRAO = {"background": "#1a1b26", "foreground": "#a9b1d6", "accent": "#7aa2f7", "muted": "#565f89",
          "red": "#f7768e", "green": "#9ece6a", "yellow": "#e0af68", "blue": "#7aa2f7", "selection": "#2f3b54"}


def arquivo_do_tema() -> Path:
    base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return base / "omarchy" / "current" / "theme" / "colors.toml"


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
    cores["escuro"] = escuro
    return cores


def tema_textual(nome: str = "omarchy") -> Theme:
    c = ler()
    return Theme(
        name=nome, primary=c["accent"], secondary=c["blue"], accent=c["accent"],
        foreground=c["foreground"], background=c["background"],
        surface=c.get("dark_background", c["background"]), panel=c.get("lighter_background", c["selection"]),
        success=c["green"], warning=c["yellow"], error=c["red"], dark=c["escuro"],
        variables={"footer-key-foreground": c["accent"], "oma-mudo": c["muted"], "oma-selecao": c["selection"]},
    )
