"""Painel direito "Tocando agora"."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Label, OptionList
from textual.widgets import Static
from textual.widgets.option_list import Option

from oma_spotify.ui.capa import Capa
from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import ListaOpcoes


class PainelAgora(NavegacaoMixin, Vertical):
    NOME = "Tocando agora"
    RODAPE = ("select", "curtir_tocando")
    DEFAULT_CSS = """
    PainelAgora { width: 34; background: $surface; padding: 0 1; }
    PainelAgora #cab-painel { text-style: bold; margin-bottom: 1; }
    PainelAgora #capa-grande { margin-bottom: 1; }
    PainelAgora #titulo-p { text-style: bold; }
    PainelAgora #rot-fila { color: $accent; text-style: bold; margin-top: 1; }
    PainelAgora #fila-lista { height: 1fr; background: $surface; }
    """

    def compose(self) -> ComposeResult:
        yield Label("Tocando agora", id="cab-painel")
        yield Capa(24, 11, id="capa-grande")
        yield Static("", id="titulo-p")
        yield Static("", id="artista-p")
        yield Button("♡ Curtir", id="curtir-p", compact=True)
        yield Label("A seguir", id="rot-fila")
        yield ListaOpcoes(id="fila-lista")

    def focar_entrada(self) -> None:
        self.query_one("#curtir-p", Button).focus()

    def pintar(self, p, curtido: bool, fila: list | None) -> None:
        q = self.query_one
        if p is None or p.item is None:
            q("#titulo-p", Static).update(Text("Nada tocando", style="bold"))
            q("#artista-p", Static).update(Text("Abra o Spotify em um dispositivo", style=self.app.cor("muted")))
            return
        q("#capa-grande", Capa).definir(p.item)
        q("#titulo-p", Static).update(Text(p.item.nome, style="bold"))
        q("#artista-p", Static).update(Text(p.item.sub, style=self.app.cor("muted")))
        q("#curtir-p", Button).label = "♥ Curtida" if curtido else "♡ Curtir"
        if fila is not None:
            lista = q("#fila-lista", ListaOpcoes)
            lista.clear_options()
            for n, i in enumerate(fila[:30]):
                lista.add_option(Option(Text.assemble((i.nome + "\n", "bold"), (i.sub, self.app.cor("muted"))), id=str(n)))
            self.fila = fila[:30]

    fila: list = []

    def ajustar(self, altura: int) -> None:
        capa = self.query_one("#capa-grande", Capa)
        capa.tamanho(24, 11) if altura >= 38 else capa.tamanho(16, 7) if altura >= 28 else capa.tamanho(8, 4)

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        self.app.action_curtir_tocando()

    @on(OptionList.OptionSelected, "#fila-lista")
    def _fila(self, ev: OptionList.OptionSelected) -> None:
        ev.stop()
        self.app.notify("A API só avança a fila: use Próxima. Abra a Fila para ver tudo.")
