"""Tela de abertura OMA SPOTIFY, mostrada na primeira abertura de cada boot."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

LETRAS = {
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "],
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "I": ["███", " █ ", " █ ", " █ ", "███"],
    "F": ["█████", "█    ", "████ ", "█    ", "█    "],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    " ": ["   ", "   ", "   ", "   ", "   "],
}
TITULO = "OMA SPOTIFY"


def banner(largura: int, altura: int) -> list[str]:
    """Letras grandes se couberem; senão, uma linha só."""
    linhas = [" ".join(LETRAS[c][i] for c in TITULO) for i in range(5)]
    if largura >= len(linhas[0]) + 2 and altura >= 11:
        return linhas
    return [TITULO]


class Abertura(ModalScreen[None]):
    DEFAULT_CSS = """
    Abertura { align: center middle; background: $background; }
    Abertura #conteudo { width: auto; height: auto; }
    Abertura #logo { color: $accent; text-style: bold; width: auto; }
    Abertura #conteudo { align-horizontal: center; }
    Abertura #sub { color: $text-muted; margin-top: 1; width: 100%; text-align: center; }
    """

    def __init__(self, versao: str = "") -> None:
        super().__init__()
        self.versao = versao

    def compose(self) -> ComposeResult:
        w, h = self.app.size
        with Vertical(id="conteudo"):
            yield Static(Text("\n".join(banner(w, h))), id="logo")
            yield Static(Text(f"Spotify no terminal {self.versao}\nQualquer tecla ou clique entra"), id="sub")

    def on_mount(self) -> None:
        self.set_timer(1.5, self._sair)

    def _sair(self) -> None:
        if self.is_current:
            self.dismiss(None)

    def on_key(self, ev: events.Key) -> None:
        ev.stop()
        self._sair()

    def on_click(self, ev: events.Click) -> None:
        self._sair()
