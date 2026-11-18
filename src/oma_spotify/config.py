"""Configuração do app em $XDG_CONFIG_HOME/oma-spotify/config.json.

Client ID, porta, abertura, onde tocar, itens fixados na biblioteca, ícones e letra.
O Client ID não é segredo (PKCE não usa secret), mas fica só aqui, nunca no estado nem em log.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PORTA_PADRAO = 8888
MAX_FIXADOS = 9


def pasta_config() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "oma-spotify"


class Config:
    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = pasta or pasta_config()
        self.client_id = ""
        self.porta = PORTA_PADRAO
        self.abertura = True
        self.tocar_por = "auto"  # auto, plugin, pc ou escolher
        self.fixados: list[str] = []  # URIs, na ordem dos números 1 a 9
        self.icones = "nerd"  # nerd ou simples
        self.letra = True  # buscar a letra na LRCLIB
        self.capas = True  # mostrar capas e fotos de verdade
        self.carregar()

    @property
    def arquivo(self) -> Path:
        return self.pasta / "config.json"

    def carregar(self) -> None:
        try:
            d = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return
        if not isinstance(d, dict):
            return
        self.client_id = str(d.get("client_id", "")).strip()
        try:
            p = int(d.get("porta", PORTA_PADRAO))
            self.porta = p if 1024 <= p <= 65535 else PORTA_PADRAO
        except (TypeError, ValueError):
            pass
        self.abertura = bool(d.get("abertura", True))
        self.tocar_por = d.get("tocar_por") if d.get("tocar_por") in ("auto", "plugin", "pc", "escolher") else "auto"
        fx = d.get("fixados")
        if isinstance(fx, list):
            self.fixados = [u for u in fx if isinstance(u, str) and u.startswith("spotify:")][:MAX_FIXADOS]
        self.icones = "simples" if d.get("icones") == "simples" else "nerd"
        self.letra = bool(d.get("letra", True))
        self.capas = bool(d.get("capas", True))

    def salvar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps({"client_id": self.client_id, "porta": self.porta, "abertura": self.abertura,
                                            "tocar_por": self.tocar_por, "fixados": self.fixados, "icones": self.icones,
                                            "letra": self.letra, "capas": self.capas}, indent=1))

    @property
    def redirect(self) -> str:
        return f"http://127.0.0.1:{self.porta}/callback"
