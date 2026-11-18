"""Contexto da interface, guardado em $XDG_RUNTIME_DIR/oma-spotify (tmpfs).

O /run/user/<uid> é um tmpfs que o systemd-logind monta no primeiro login e apaga
quando a última sessão do usuário termina (logout total) ou no desligamento.
Fechar o app não apaga nada daqui.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

VERSAO = 1
PROIBIDAS = re.compile(r"(token|secret|client|conta|account|email|senha|pass)", re.I)


def pasta_padrao() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR")
    if base and os.path.isdir(base):
        return Path(base) / "oma-spotify"
    return Path(tempfile.gettempdir()) / f"oma-spotify-{os.getuid()}"


class Estado:
    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = pasta or pasta_padrao()
        self.dados: dict = {}

    @property
    def arquivo(self) -> Path:
        return self.pasta / "estado.json"

    @property
    def marcador(self) -> Path:
        return self.pasta / "abertura-mostrada"

    def preparar(self) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.pasta, 0o700)
        except OSError:
            pass

    def ja_abriu(self) -> bool:
        return self.marcador.exists()

    def marcar_abertura(self) -> None:
        try:
            self.preparar()
            self.marcador.write_text("1")
        except OSError:
            pass

    def carregar(self) -> dict:
        """Arquivo ausente, corrompido ou de outra versão: começa do zero, sem erro."""
        try:
            bruto = json.loads(self.arquivo.read_text())
            if isinstance(bruto, dict) and bruto.get("versao") == VERSAO and isinstance(bruto.get("dados"), dict):
                self.dados = bruto["dados"]
                return self.dados
        except (OSError, ValueError):
            pass
        self.dados = {}
        return self.dados

    def salvar(self) -> None:
        try:
            self.preparar()
            tmp = self.arquivo.with_suffix(".tmp")
            tmp.write_text(json.dumps({"versao": VERSAO, "dados": self.dados}, ensure_ascii=False))
            os.replace(tmp, self.arquivo)
        except OSError:
            pass

    def definir(self, chave: str, valor) -> None:
        if PROIBIDAS.search(chave):
            return
        if self.dados.get(chave) != valor:
            self.dados[chave] = valor
            self.salvar()

    def obter(self, chave: str, padrao=None):
        return self.dados.get(chave, padrao)
