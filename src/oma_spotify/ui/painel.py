"""Janela [4] Fila: o que toca agora e o que vem a seguir."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Label, OptionList, Static
from textual.widgets.option_list import Option

from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import ListaOpcoes


class PainelAgora(NavegacaoMixin, Vertical):
    NOME = "Fila"
    RODAPE = ("select", "curtir_tocando")
    DEFAULT_CSS = """
    PainelAgora { padding: 0 1; }
    PainelAgora #titulo-p { text-style: bold; }
    PainelAgora #rot-fila { color: $accent; text-style: bold; margin-top: 1; }
    PainelAgora #fila-lista { height: 1fr; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Tocando agora", id="rot-agora")
        yield Static("", id="titulo-p")
        yield Static("", id="artista-p")
        yield Button("♡ Curtir", id="curtir-p", compact=True)
        yield Label("A seguir", id="rot-fila")
        yield ListaOpcoes(id="fila-lista")

    def focar_entrada(self) -> None:
        self.query_one("#fila-lista", ListaOpcoes).focus()

    fila: list = []

    def pintar(self, p, curtido: bool, fila: list | None) -> None:
        q = self.query_one
        if p is None or p.item is None:
            q("#titulo-p", Static).update(Text("Nada tocando", style="bold"))
            q("#artista-p", Static).update(Text("Toque algo e ele aparece aqui", style=self.app.cor("muted")))
        else:
            q("#titulo-p", Static).update(Text(p.item.nome, style="bold"))
            q("#artista-p", Static).update(Text(p.item.sub, style=self.app.cor("muted")))
        q("#curtir-p", Button).label = "♥ Curtida" if curtido else "♡ Curtir"
        if fila is not None:
            lista = q("#fila-lista", ListaOpcoes)
            lista.clear_options()
            for n, i in enumerate(fila[:30]):
                t = Text.assemble((i.nome, "bold"), (f" · {i.sub}" if i.sub else "", self.app.cor("muted")))
                t.no_wrap = True
                t.truncate(max(self.size.width - 4, 10), overflow="ellipsis")
                lista.add_option(Option(t, id=str(n)))
            self.fila = fila[:30]

    def on_resize(self, ev=None) -> None:
        if self.fila and self.is_mounted and self.size.width != getattr(self, "_larg", 0):
            self._larg = self.size.width
            self.pintar(self.app.player, self.app.curtido, self.fila)

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        self.app.action_curtir_tocando()

    @on(OptionList.OptionSelected, "#fila-lista")
    def _fila(self, ev: OptionList.OptionSelected) -> None:
        ev.stop()
        self.app.notify("A API só avança a fila: use Próxima. Abra a Fila (f) para ver tudo.")
