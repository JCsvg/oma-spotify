"""Lista virtualizada: só desenha as linhas visíveis (Line API do Textual).

Serve a biblioteca, as tabelas de faixas, a fila, a letra e os diálogos. Cada item
pode ter mais de uma linha e cabeçalhos não selecionáveis. Teclado (↑ ↓ j k, g G,
Home End, PageUp PageDown, Shift+↑ ↓ marca), mouse (clique seleciona, clique de novo
ou duplo clique escolhe, botão direito abre opções, Shift e Ctrl marcam) e hover.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Any, Callable

from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.geometry import Region, Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.scrollbar import ScrollBar, ScrollBarRender
from textual.strip import Strip
from rich.segment import Segments


class BarraFina(ScrollBarRender):
    """Rolagem: ▐ na cor linha, sem trilho."""

    @classmethod
    def render_bar(cls, size=25, virtual_size=50, window_size=20, position=0, thickness=1, vertical=True,
                   back_color=None, bar_color=None):
        if not vertical:
            return super().render_bar(size, virtual_size, window_size, position, thickness, vertical, back_color, bar_color)
        size = int(size)
        segs = []
        if window_size and size and virtual_size and size != virtual_size and virtual_size > window_size:
            thumb = max(1, round(window_size * size / virtual_size))
            pos = round((size - thumb) * position / max(1, virtual_size - window_size))
            for i in range(size):
                if pos <= i < pos + thumb:
                    segs.append(Segment("▐" * thickness, Style(color=bar_color, bgcolor=back_color, meta={"@mouse.down": "grab"})))
                else:
                    segs.append(Segment(" " * thickness, Style(bgcolor=back_color,
                                                               meta={"@mouse.down": "scroll_up" if i < pos else "scroll_down"})))
        else:
            segs = [Segment(" " * thickness, Style(bgcolor=back_color))] * size
        return Segments(segs, new_lines=True)


ScrollBar.renderer = BarraFina


@dataclass(slots=True, frozen=True)
class EstadoLinha:
    cursor: bool = False
    foco: bool = False
    marcado: bool = False
    hover: bool = False
    largura: int = 40

    @property
    def destacado(self) -> bool:
        """Linha com fundo de seleção."""
        return self.marcado or (self.cursor and self.foco)


def ajustar(t: Text | str, largura: int, alinhar: str = "left", estilo: str = "") -> Text:
    """Corta com reticências ou completa com espaços até a largura."""
    t = t.copy() if isinstance(t, Text) else Text(str(t), style=estilo)
    t.no_wrap = True
    if largura <= 0:
        return Text("")
    if t.cell_len > largura:
        t.truncate(largura, overflow="ellipsis")
    falta = largura - t.cell_len
    if falta > 0:
        if alinhar == "right":
            t = Text(" " * falta) + t
        elif alinhar == "center":
            t = Text(" " * (falta // 2)) + t + Text(" " * (falta - falta // 2))
        else:
            t.append(" " * falta)
    return t


def colunas(partes: list[tuple[Text | str, int, str]], largura: int, sep: int = 1) -> Text:
    """partes: (texto, largura, alinhamento). Largura 0 = o que sobrar (divide entre as flexíveis)."""
    fixas = sum(w for _, w, _ in partes if w > 0) + sep * (len(partes) - 1)
    flex = [i for i, (_, w, _) in enumerate(partes) if w <= 0]
    sobra = max(0, largura - fixas)
    pesos = [-partes[i][1] or 1 for i in flex]
    tot = sum(pesos) or 1
    larg = {i: int(sobra * p / tot) for i, p in zip(flex, pesos)}
    if flex:
        larg[flex[-1]] += sobra - sum(larg.values())
    saida = Text()
    for n, (t, w, al) in enumerate(partes):
        if n:
            saida.append(" " * sep)
        saida.append_text(ajustar(t, w if w > 0 else larg[n], al))
    return saida


class Lista(ScrollView, can_focus=True):
    DEFAULT_CSS = """
    Lista { height: 1fr; background: transparent; overflow-x: hidden; overflow-y: auto; scrollbar-size-vertical: 1; }
    Lista.-auto { height: auto; overflow-y: hidden; }
    """
    BINDINGS = [
        Binding("up,k", "cursor(-1)", show=False), Binding("down,j", "cursor(1)", show=False),
        Binding("pageup", "pagina(-1)", show=False), Binding("pagedown", "pagina(1)", show=False),
        Binding("home,g", "ponta(0)", show=False), Binding("end,G", "ponta(1)", show=False),
        Binding("shift+up", "marcar(-1)", show=False), Binding("shift+down", "marcar(1)", show=False),
        Binding("enter", "escolher", show=False),
    ]

    class _Msg(Message):
        def __init__(self, lista: "Lista", indice: int, item: Any) -> None:
            super().__init__()
            self.lista, self.indice, self.item = lista, indice, item

        @property
        def control(self) -> "Lista":
            return self.lista

    class Escolhido(_Msg):
        """Enter, clique de novo na mesma linha ou duplo clique."""

    class Destacado(_Msg):
        """O cursor mudou."""

    class Menu(_Msg):
        """Botão direito."""

    class Marcas(_Msg):
        """As marcas mudaram."""

    def __init__(self, render_item: Callable[[Any, int, EstadoLinha], list[Text]] | None = None, altura: int = 1,
                 selecionavel: Callable[[Any], bool] | None = None, alturas: Callable[[Any], int] | None = None,
                 cursor_sem_foco: bool = False, marcar: bool = False, ao_clicar=None, fundo_cursor: bool = True, **kw) -> None:
        super().__init__(**kw)
        self.ao_clicar = ao_clicar  # (indice, x) -> True se tratou o clique (ex.: ▶ ou coração)
        self.render_item = render_item or (lambda it, i, e: [Text(str(it))])
        self.altura_padrao = altura
        self.f_altura = alturas
        self.f_sel = selecionavel
        self.cursor_sem_foco = cursor_sem_foco  # mostra o fundo do cursor mesmo sem foco (diálogos)
        self.fundo_cursor = fundo_cursor  # a letra marca a linha sem fundo
        self.pode_marcar = marcar
        self.itens: list = []
        self._y: list[int] = [0]
        self.cursor = -1
        self.hover = -1
        self.marcados: set[int] = set()
        self._ancora = -1
        self._ultimo_clique = -1
        self._cache: dict = {}

    # ------------------------------------------------------------ dados
    def _alt(self, it) -> int:
        return self.f_altura(it) if self.f_altura else self.altura_padrao

    def selecionavel(self, i: int) -> bool:
        return 0 <= i < len(self.itens) and (self.f_sel is None or self.f_sel(self.itens[i]))

    def definir(self, itens: list, cursor: int | None = None) -> None:
        antigo = self.cursor
        self.itens = list(itens)
        y = [0]
        for it in self.itens:
            y.append(y[-1] + self._alt(it))
        self._y = y
        self.marcados = {i for i in self.marcados if i < len(self.itens)}
        self._cache.clear()
        self.hover = -1
        alvo = antigo if cursor is None else cursor
        if not self.itens:
            self.cursor = -1
        else:
            alvo = max(0, min(alvo if alvo >= 0 else 0, len(self.itens) - 1))
            self.cursor = alvo if self.selecionavel(alvo) else self._proximo(alvo, 1, incluir=True)
            if self.cursor < 0:
                self.cursor = self._proximo(alvo, -1, incluir=True)
        self.virtual_size = Size(self.size.width, y[-1])
        if self.is_mounted:
            self.refresh(layout=True)

    def item_atual(self):
        return self.itens[self.cursor] if 0 <= self.cursor < len(self.itens) else None

    def itens_marcados(self) -> list:
        if self.marcados:
            return [self.itens[i] for i in sorted(self.marcados) if i < len(self.itens)]
        it = self.item_atual()
        return [it] if it is not None else []

    def limpar_marcas(self) -> bool:
        if not self.marcados:
            return False
        self.marcados.clear()
        self._ancora = -1
        self._cache.clear()
        self.refresh()
        self.post_message(self.Marcas(self, self.cursor, None))
        return True

    def atualizar_itens(self, indices) -> None:
        """Redesenha só as linhas desses itens (equalizador, curtida)."""
        for i in indices:
            if 0 <= i < len(self.itens):
                self._cache = {k: v for k, v in self._cache.items() if k[0] != i}
                self.refresh_lines(self._y[i], self._y[i + 1] - self._y[i])

    def redesenhar(self) -> None:
        self._cache.clear()
        self.refresh()

    # ------------------------------------------------------------ desenho
    def on_resize(self) -> None:
        self.virtual_size = Size(self.size.width, self._y[-1])
        self._cache.clear()

    def get_content_height(self, container, viewport, width: int) -> int:
        return self._y[-1]

    def render_line(self, y: int) -> Strip:
        largura = self.scrollable_content_region.width
        linha = y + self.scroll_offset.y
        i = bisect_right(self._y, linha) - 1
        base = self.rich_style
        if i < 0 or i >= len(self.itens):
            return Strip.blank(largura, base)
        sub = linha - self._y[i]
        est = EstadoLinha(i == self.cursor, self.has_focus or self.cursor_sem_foco, i in self.marcados,
                          i == self.hover and self.selecionavel(i), largura)
        chave = (i, est)
        textos = self._cache.get(chave)
        if textos is None:
            try:
                textos = self.render_item(self.itens[i], i, est)
            except Exception:  # um item estranho vira uma linha em branco, não derruba a lista
                textos = [Text("")]
            if len(self._cache) > 300:
                self._cache.clear()
            self._cache[chave] = textos
        t = textos[sub] if sub < len(textos) else Text("")
        p = self.app.paleta
        fundo = p["selecao"] if est.destacado and (self.fundo_cursor or est.marcado) else p["hover"] if est.hover else None
        if fundo and sub > 0 and not t.plain:
            fundo = None  # a linha em branco que separa os itens fica sem fundo
        estilo = base + Style(bgcolor=fundo) if fundo else base
        segs = list(t.render(self.app.console))
        return Strip(segs).crop_extend(0, largura, None).apply_style(estilo)

    # ------------------------------------------------------------ cursor
    def _proximo(self, i: int, d: int, incluir: bool = False) -> int:
        j = i if incluir else i + d
        while 0 <= j < len(self.itens):
            if self.selecionavel(j):
                return j
            j += d
        return -1

    def mover_cursor(self, i: int, centralizar: bool = False, avisar: bool = True) -> None:
        if not (0 <= i < len(self.itens)):
            return
        antigo = self.cursor
        self.cursor = i
        self.atualizar_itens([antigo, i])
        self.mostrar_item(i, centralizar)
        if avisar and antigo != i:
            self.post_message(self.Destacado(self, i, self.itens[i]))

    def mostrar_item(self, i: int, centralizar: bool = False) -> None:
        if not (0 <= i < len(self.itens)) or not self.is_mounted:
            return
        y0, h = self._y[i], self._y[i + 1] - self._y[i]
        if centralizar:
            self.scroll_to(y=max(0, y0 - (self.size.height - h) // 2), animate=False, immediate=True)
        else:
            # traz junto o cabeçalho logo acima (seções)
            topo = self._y[i - 1] if i > 0 and not self.selecionavel(i - 1) else y0
            self.scroll_to_region(Region(0, topo, 1, y0 + h - topo), animate=False, immediate=True)

    def action_cursor(self, d: int) -> None:
        if self.cursor < 0:
            j = self._proximo(-1 if d > 0 else len(self.itens), d)
        else:
            j = self._proximo(self.cursor, d)
        if j < 0:
            self.app.action_mover(0, d)  # na ponta: passa para o controle vizinho da janela
            return
        if self.marcados and not self.pode_marcar:
            self.limpar_marcas()
        self.mover_cursor(j)

    def action_pagina(self, d: int) -> None:
        if not self.itens:
            return
        alvo_y = (self._y[max(self.cursor, 0)] if self.cursor >= 0 else 0) + d * max(1, self.size.height - 1)
        i = max(0, min(len(self.itens) - 1, bisect_right(self._y, max(0, alvo_y)) - 1))
        j = self._proximo(i, d, incluir=True)
        if j < 0:
            j = self._proximo(i, -d, incluir=True)
        if j >= 0:
            self.mover_cursor(j)

    def action_ponta(self, fim: int) -> None:
        j = self._proximo(len(self.itens), -1) if fim else self._proximo(-1, 1)
        if j >= 0:
            self.mover_cursor(j)

    def action_marcar(self, d: int) -> None:
        if not self.pode_marcar or self.cursor < 0:
            self.action_cursor(d)
            return
        if self._ancora < 0 or not self.marcados:
            self._ancora = self.cursor
        j = self._proximo(self.cursor, d)
        if j >= 0:
            self.cursor = j
        a, b = sorted((self._ancora, self.cursor))
        self.marcados = {k for k in range(a, b + 1) if self.selecionavel(k)}
        self._cache.clear()
        self.refresh()
        self.mostrar_item(self.cursor)
        self.post_message(self.Marcas(self, self.cursor, self.item_atual()))

    def action_escolher(self) -> None:
        it = self.item_atual()
        if it is not None:
            self.post_message(self.Escolhido(self, self.cursor, it))

    # ------------------------------------------------------------ mouse
    def _indice_em(self, y: int) -> int:
        linha = y + self.scroll_offset.y
        i = bisect_right(self._y, linha) - 1
        return i if 0 <= i < len(self.itens) else -1

    def on_mouse_move(self, ev: events.MouseMove) -> None:
        i = self._indice_em(ev.y)
        if i != self.hover:
            antigo, self.hover = self.hover, i
            self.atualizar_itens([antigo, i])

    def on_leave(self, ev: events.Leave) -> None:
        if self.hover >= 0:
            antigo, self.hover = self.hover, -1
            self.atualizar_itens([antigo])

    def on_blur(self) -> None:
        self._ultimo_clique = -1
        self.atualizar_itens([self.cursor])

    def on_focus(self) -> None:
        self.atualizar_itens([self.cursor])
        if self.cursor >= 0:
            self.mostrar_item(self.cursor)

    def on_click(self, ev: events.Click) -> None:
        i = self._indice_em(ev.y)
        if i < 0 or not self.selecionavel(i):
            return
        ev.stop()
        if ev.button == 3:
            self.mover_cursor(i)
            self.post_message(self.Menu(self, i, self.itens[i]))
            return
        if self.pode_marcar and (ev.shift or ev.ctrl):
            if ev.ctrl:
                self.marcados ^= {i}
            else:
                a, b = sorted((self.cursor if self.cursor >= 0 else i, i))
                self.marcados = {k for k in range(a, b + 1) if self.selecionavel(k)}
            self.cursor = i
            self._cache.clear()
            self.refresh()
            self.post_message(self.Marcas(self, i, self.itens[i]))
            return
        if self.ao_clicar is not None and self.ao_clicar(i, ev.x):
            self.mover_cursor(i)
            return
        repetido = ev.chain >= 2 or self._ultimo_clique == i
        if self.marcados:
            self.limpar_marcas()
        self.mover_cursor(i)
        self._ultimo_clique = i
        if repetido:
            self.post_message(self.Escolhido(self, i, self.itens[i]))
