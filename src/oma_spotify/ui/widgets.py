"""Widgets próprios: barra clicável e tabela com j/k e saída pelas bordas."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, OptionList


class Barra(Widget, can_focus=True):
    """Barra horizontal clicável (progresso e volume). ←/→/h/l mexem só com ela em foco."""

    DEFAULT_CSS = "Barra { height: 1; width: 1fr; }"
    BINDINGS = [Binding("left,h", "passo(-1)", "Voltar", show=False), Binding("right,l", "passo(1)", "Avançar", show=False)]

    class Passo(Message):
        def __init__(self, barra: "Barra", direcao: int) -> None:
            super().__init__()
            self.barra, self.direcao = barra, direcao

    class Clique(Message):
        def __init__(self, barra: "Barra", fracao: float) -> None:
            super().__init__()
            self.barra, self.fracao = barra, fracao

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.valor = 0.0

    def definir(self, v: float) -> None:
        v = max(0.0, min(1.0, v))
        if v != self.valor:
            self.valor = v
            self.refresh()

    def render(self) -> Text:
        w = max(self.size.width, 1)
        cheio = int(round(self.valor * w))
        cor = self.app.cor("accent") if self.has_focus else self.app.cor("muted")
        t = Text()
        t.append("━" * cheio, style=f"bold {cor}")
        t.append("─" * (w - cheio), style=self.app.cor("muted"))
        return t

    def action_passo(self, d: int) -> None:
        self.post_message(self.Passo(self, d))

    def on_click(self, ev: events.Click) -> None:
        self.focus()
        self.post_message(self.Clique(self, ev.x / max(self.size.width - 1, 1)))


class Tabela(DataTable):
    BINDINGS = [Binding("enter", "select_cursor", "Tocar", key_display="Enter"), Binding("j", "cursor_down", show=False), Binding("k", "cursor_up", show=False),
                Binding("left,h", "app.mover(-1, 0)", show=False), Binding("right,l", "app.mover(1, 0)", show=False)]

    def __init__(self, **kw) -> None:
        super().__init__(cursor_type="row", zebra_stripes=False, **kw)

    def action_cursor_up(self) -> None:
        if self.cursor_row <= 0:
            self.app.action_mover(0, -1)
        else:
            super().action_cursor_up()

    def action_cursor_down(self) -> None:
        if self.row_count and self.cursor_row >= self.row_count - 1:
            self.app.action_mover(0, 1)  # fim da lista: desce para o que vem depois
        else:
            super().action_cursor_down()


class ListaOpcoes(OptionList):
    """Lista vertical com j/k, ←/→ saem para os vizinhos, igual à Tabela."""

    BINDINGS = [Binding("enter", "select", "Abrir", key_display="Enter"),
                Binding("j", "cursor_down", show=False), Binding("k", "cursor_up", show=False),
                Binding("left,h", "app.mover(-1, 0)", show=False), Binding("right,l", "app.mover(1, 0)", show=False)]
