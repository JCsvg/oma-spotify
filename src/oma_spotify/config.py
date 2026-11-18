"""Configuração do app (Client ID, porta, abertura) em $XDG_CONFIG_HOME/oma-spotify/config.json.

O Client ID não é segredo (PKCE não usa secret), mas fica só aqui, nunca no estado nem em log.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PORTA_PADRAO = 8888


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
        self.carregar()

    @property
    def arquivo(self) -> Path:
        return self.pasta / "config.json"

    def carregar(self) -> None:
        try:
            d = json.loads(self.arquivo.read_text())
        except (OSError, ValueError):
            return
        if isinstance(d, dict):
            self.client_id = str(d.get("client_id", "")).strip()
            try:
                p = int(d.get("porta", PORTA_PADRAO))
                self.porta = p if 1024 <= p <= 65535 else PORTA_PADRAO
            except (TypeError, ValueError):
                pass
            self.abertura = bool(d.get("abertura", True))
            self.tocar_por = d.get("tocar_por") if d.get("tocar_por") in ("auto", "plugin", "pc", "escolher") else "auto"

    def salvar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo.write_text(json.dumps({"client_id": self.client_id, "porta": self.porta, "abertura": self.abertura, "tocar_por": self.tocar_por}, indent=1))

    @property
    def redirect(self) -> str:
        return f"http://127.0.0.1:{self.porta}/callback"
