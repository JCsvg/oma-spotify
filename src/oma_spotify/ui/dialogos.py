"""Diálogos: confirmar, pedir texto, escolher uma playlist, aviso de dispositivo."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

_BASE = """
{n} { align: center middle; }
{n} #caixa { width: 64; height: auto; max-height: 90%; background: $surface; border: round $accent; padding: 1 2; }
{n} .titulo { text-style: bold; color: $accent; margin-bottom: 1; }
{n} #botoes { height: 3; margin-top: 1; }
{n} #botoes Button { margin-right: 1; }
"""


def _css(nome: str) -> str:
    return _BASE.replace("{n}", nome)


class _Base(ModalScreen):
    BINDINGS = [Binding("escape", "cancelar", "Cancelar", priority=True),
                Binding("ctrl+right,ctrl+l", "botao(1)", show=False, priority=True),
                Binding("ctrl+left,ctrl+h", "botao(-1)", show=False, priority=True),
                Binding("ctrl+enter", "acionar", show=False, priority=True)]

    def mover_secao(self, passo: int) -> None:
        self.focus_next() if passo > 0 else self.focus_previous()

    def fileira(self):
        return [b for b in self.query(Button) if b.display]

    def action_botao(self, passo: int) -> None:
        bs = self.fileira()
        if bs:
            f = self.focused
            i = bs.index(f) if f in bs else (-1 if passo > 0 else 0)
            bs[(i + passo) % len(bs)].focus()

    def action_acionar(self) -> None:
        if isinstance(self.focused, Button):
            self.focused.press()

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def acoes_do_rodape(self) -> list[str]:
        return []


class Confirmar(_Base):
    DEFAULT_CSS = _css("Confirmar")

    def __init__(self, titulo: str, linhas: list[str], rotulo: str = "Confirmar") -> None:
        super().__init__()
        self.titulo, self.linhas, self.rotulo = titulo, linhas, rotulo

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa"):
            yield Label(self.titulo, classes="titulo")
            for l in self.linhas:
                yield Static(Text(l))
            with Horizontal(id="botoes"):
                yield Button(self.rotulo, id="sim", variant="error")
                yield Button("Cancelar", id="nao")

    def on_mount(self) -> None:
        self.query_one("#nao", Button).focus()  # padrão seguro

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(ev.button.id == "sim")

    def action_cancelar(self) -> None:
        self.dismiss(False)


class Pedir(_Base):
    DEFAULT_CSS = _css("Pedir")

    def __init__(self, titulo: str, valor: str = "", dica: str = "") -> None:
        super().__init__()
        self.titulo, self.valor, self.dica = titulo, valor, dica

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa"):
            yield Label(self.titulo, classes="titulo")
            if self.dica:
                yield Static(Text(self.dica))
            yield Input(self.valor, id="campo")
            with Horizontal(id="botoes"):
                yield Button("Salvar", id="ok", variant="primary")
                yield Button("Cancelar", id="nao")

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        self.dismiss(ev.value.strip())

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(self.query_one("#campo", Input).value.strip() if ev.button.id == "ok" else None)


class EscolherPlaylist(_Base):
    DEFAULT_CSS = _css("EscolherPlaylist") + "EscolherPlaylist OptionList { height: auto; max-height: 14; }"

    def __init__(self, playlists) -> None:
        super().__init__()
        self.playlists = playlists

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa"):
            yield Label("Adicionar a qual playlist?", classes="titulo")
            if self.playlists:
                yield OptionList(*[Option(Text(p.nome), id=p.id) for p in self.playlists], id="lista")
            else:
                yield Static("Você ainda não tem playlists suas. Crie uma na tela Playlists.")
            with Horizontal(id="botoes"):
                yield Button("Cancelar", id="nao")

    def on_mount(self) -> None:
        for l in self.query(OptionList):
            l.focus()
            l.highlighted = 0

    def on_option_list_option_selected(self, ev: OptionList.OptionSelected) -> None:
        self.dismiss(ev.option.id)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(None)


class SemDispositivo(_Base):
    """404 do player: nada tocando em lugar nenhum."""

    DEFAULT_CSS = _css("SemDispositivo")

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa"):
            yield Label("Nenhum dispositivo do Spotify ativo", classes="titulo")
            yield Static("Para tocar, o Spotify precisa estar aberto em algum aparelho "
                         "(o app do PC, o celular...). Abra o do PC ou escolha um dispositivo.")
            with Horizontal(id="botoes"):
                yield Button("Abrir o Spotify do PC", id="abrir", variant="primary")
                yield Button("Escolher dispositivo", id="escolher")
                yield Button("Fechar", id="nao")

    def on_mount(self) -> None:
        self.query_one("#abrir", Button).focus()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(ev.button.id)
