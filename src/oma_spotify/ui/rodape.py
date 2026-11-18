"""Rodapé (as teclas da janela em foco, clicáveis) e a divisa entre janelas (arrastar muda a largura)."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.widget import Widget


class Rodape(Widget):
    DEFAULT_CSS = "Rodape { height: 1; width: 1fr; }"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self._x: list[tuple[int, int, str]] = []

    def pintar(self) -> None:
        self.refresh()

    def _itens(self) -> list[tuple[str, str, str]]:
        a = self.app
        try:
            j = a._janela_que_trata()
            if a.nome_janela(a.focused) == "principal":
                j = a.query_one("#principal")
        except Exception:
            j = None
        return list(j.rodape()) if j is not None and hasattr(j, "rodape") else []

    def render(self) -> Text:
        a = self.app
        w = self.size.width
        acc, mudo = a.cor("accent"), a.cor("mudo")
        esq = Text(no_wrap=True)
        self._x = []
        for tecla, rot, acao in self._itens():
            if esq.cell_len:
                esq.append("   ")
            x0 = esq.cell_len
            esq.append(tecla, style=acc)
            esq.append(" " + rot, style=mudo)
            self._x.append((x0, esq.cell_len, acao))
        if a.modo_largura() == "estreito":
            dir_ = [("[", "biblioteca", "lado('bib')"), ("]", "tocando", "lado('dir')"), ("/", "buscar", "buscar"),
                    ("ctrl+espaço", "ajuda", "teclas")]
        else:
            dir_ = [("ctrl+hjkl", "janelas", "janela('dir')"), ("ctrl+espaço", "ajuda", "teclas")]
        d = Text(no_wrap=True)
        xs = []
        for tecla, rot, acao in dir_:
            if d.cell_len:
                d.append("   ")
            x0 = d.cell_len
            d.append(tecla, style=acc)
            d.append(" " + rot, style=mudo)
            xs.append((x0, d.cell_len, acao))
        if esq.cell_len + d.cell_len + 2 > w:
            esq.truncate(max(0, w - d.cell_len - 2), overflow="ellipsis")
        meio = max(1, w - esq.cell_len - d.cell_len)
        self._x += [(a0 + esq.cell_len + meio, b0 + esq.cell_len + meio, acao) for a0, b0, acao in xs]
        return esq + Text(" " * meio) + d

    async def on_click(self, ev: events.Click) -> None:
        for x0, x1, acao in self._x:
            if x0 <= ev.x < x1:
                await self.app.run_action(acao.removeprefix("app."))
                return


class Divisa(Widget):
    """Coluna de espaço entre janelas. Arrastar muda a largura da Biblioteca ou do Tocando; a largura fica salva."""

    DEFAULT_CSS = "Divisa { width: 1; height: 1fr; }"

    def __init__(self, lado: str, **kw) -> None:
        super().__init__(**kw)
        self.lado = lado
        self._arrastando = False
        self._sobre = False

    def render(self) -> Text:
        if self._arrastando or self._sobre:
            return Text("\n".join("┃" for _ in range(self.size.height)), style=self.app.cor("accent"))
        return Text("")

    def on_enter(self) -> None:
        self._sobre = True
        self.refresh()

    def on_leave(self) -> None:
        self._sobre = False
        self.refresh()

    def on_mouse_down(self, ev: events.MouseDown) -> None:
        self._arrastando = True
        self.capture_mouse()
        self.refresh()

    def on_mouse_move(self, ev: events.MouseMove) -> None:
        if not self._arrastando:
            return
        a = self.app
        if self.lado == "bib":
            r = a.query_one("#bib").region
            a.mudar_largura("bib", ev.screen_x - r.x)
        else:
            r = a.query_one("#direita").region
            a.mudar_largura("dir", r.right - ev.screen_x - 1)

    def on_mouse_up(self, ev: events.MouseUp) -> None:
        if self._arrastando:
            self._arrastando = False
            self.release_mouse()
            self.refresh()
