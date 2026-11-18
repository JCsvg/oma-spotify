"""Modelos simples, iguais para o cliente real e o falso."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class ErroSpotify(Exception):
    """Erro já em português, pronto para mostrar. Nunca carrega token."""

    def __init__(self, msg: str, status: int = 0, sem_dispositivo: bool = False, sem_login: bool = False) -> None:
        super().__init__(msg)
        self.msg = msg
        self.status = status
        self.sem_dispositivo = sem_dispositivo
        self.sem_login = sem_login

    def __str__(self) -> str:
        return self.msg


@dataclass
class Item:
    uri: str
    tipo: str  # track, album, artist, playlist, show, episode
    nome: str
    sub: str = ""  # artista, dono, editora
    extra: str = ""  # álbum, número de faixas
    dur_ms: int = 0
    id: str = ""
    meu: bool = False  # playlist do próprio usuário (editável)
    capa: str = ""  # URL da imagem (só no cliente real)


@dataclass
class Dispositivo:
    id: str
    nome: str
    tipo: str = "Computer"
    ativo: bool = False
    volume: int | None = None


@dataclass
class Player:
    item: Item | None = None
    progresso_ms: int = 0
    tocando: bool = False
    aleatorio: bool = False
    repetir: str = "off"  # off, context, track
    volume: int | None = None
    dispositivo: str = ""
    marca: float = field(default_factory=time.monotonic)

    def posicao(self) -> int:
        """Posição estimada agora, interpolada entre as consultas."""
        pos = self.progresso_ms
        if self.tocando:
            pos += int((time.monotonic() - self.marca) * 1000)
        dur = self.item.dur_ms if self.item else 0
        return max(0, min(pos, dur) if dur else pos)


def mmss(ms: int) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"
