"""Widgets pequenos: barra de progresso e volume, abas, cartões, trilha e cabeçalho de seção."""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget

from oma_spotify.services.modelos import Item
from oma_spotify.tema import misturar
from oma_spotify.ui.capa import linhas_capa
from oma_spotify.ui.lista import ajustar


class Barra(Widget, can_focus=True):
    """Barra clicável (progresso e volume): ━ cheio na cor de destaque (no volume, na cor do texto) e ━ na cor linha.

    Com o player em foco, ● marca o ponto. ← → (h l) e a roda do mouse dão passos; clique pula; arrastar o ● procura.
    """

    DEFAULT_CSS = "Barra { height: 1; width: 1fr; }"
    BINDINGS = [Binding("left,h", "passo(-1)", show=False), Binding("right,l", "passo(1)", show=False)]

    class Passo(Message):
        def __init__(self, barra: "Barra", direcao: int) -> None:
            super().__init__()
            self.barra, self.direcao = barra, direcao

    class Clique(Message):
        def __init__(self, barra: "Barra", fracao: float) -> None:
            super().__init__()
            self.barra, self.fracao = barra, fracao

    def __init__(self, volume: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.valor = 0.0
        self.volume = volume
        self.marcador = False
        self._arrastando = False

    def definir(self, v: float) -> None:
        v = max(0.0, min(1.0, v))
        if self._arrastando:
            return
        if abs(v - self.valor) > 1e-4:
            self.valor = v
            self.refresh()

    def marcar(self, ligado: bool) -> None:
        if ligado != self.marcador:
            self.marcador = ligado
            self.refresh()

    def render(self) -> Text:
        w = max(self.size.width, 1)
        cheio = int(round(self.valor * w))
        a = self.app
        cor = a.cor("texto") if self.volume else a.cor("accent")
        t = Text(no_wrap=True)
        if (self.marcador or self.has_focus) and w > 1:
            ponto = min(w - 1, cheio)
            t.append("━" * ponto, style=cor)
            t.append("●", style=f"bold {a.cor('accent') if self.has_focus or not self.volume else cor}")
            t.append("━" * (w - ponto - 1), style=a.cor("linha"))
        else:
            t.append("━" * cheio, style=cor)
            t.append("━" * (w - cheio), style=a.cor("linha"))
        return t

    def action_passo(self, d: int) -> None:
        self.post_message(self.Passo(self, d))

    def on_mouse_scroll_up(self, ev: events.MouseScrollUp) -> None:
        ev.stop()
        self.post_message(self.Passo(self, 1))

    def on_mouse_scroll_down(self, ev: events.MouseScrollDown) -> None:
        ev.stop()
        self.post_message(self.Passo(self, -1))

    def _fracao(self, x: int) -> float:
        return max(0.0, min(1.0, x / max(self.size.width - 1, 1)))

    def on_mouse_down(self, ev: events.MouseDown) -> None:
        if ev.button == 1:
            self._arrastando = True
            self.capture_mouse()

    def on_mouse_move(self, ev: events.MouseMove) -> None:
        if self._arrastando:
            self.valor = self._fracao(ev.x)
            self.refresh()

    def on_mouse_up(self, ev: events.MouseUp) -> None:
        if self._arrastando:
            self._arrastando = False
            self.release_mouse()
            self.valor = self._fracao(ev.x)
            self.refresh()
            self.post_message(self.Clique(self, self.valor))


class Abas(Widget):
    """Abas ou chips numa linha. Clique escolhe; com foco, ← → trocam."""

    DEFAULT_CSS = "Abas { height: 1; width: 1fr; }"
    BINDINGS = [Binding("left,h", "trocar(-1)", show=False), Binding("right,l", "trocar(1)", show=False)]

    class Mudou(Message):
        def __init__(self, abas: "Abas", valor: str) -> None:
            super().__init__()
            self.abas, self.valor = abas, valor

        @property
        def control(self) -> "Abas":
            return self.abas

    def __init__(self, opcoes: list[tuple[str, str]], atual: str = "", estilo: str = "chip", focavel: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.opcoes = list(opcoes)
        self.atual = atual or (opcoes[0][0] if opcoes else "")
        self.estilo = estilo
        self.can_focus = focavel
        self._x: list[tuple[int, int, str]] = []

    def definir(self, valor: str, avisar: bool = False) -> None:
        if valor != self.atual and any(v == valor for v, _ in self.opcoes):
            self.atual = valor
            self.refresh()
            if avisar:
                self.post_message(self.Mudou(self, valor))

    def trocar(self, passo: int) -> None:
        ids = [v for v, _ in self.opcoes]
        if self.atual in ids:
            self.definir(ids[(ids.index(self.atual) + passo) % len(ids)], avisar=True)

    def action_trocar(self, passo: int) -> None:
        self.trocar(passo)

    def render(self) -> Text:
        a = self.app
        t = Text(no_wrap=True, overflow="ellipsis")
        self._x = []
        for n, (v, rot) in enumerate(self.opcoes):
            if n:
                t.append(" " if self.estilo == "chip" else "   ")
            x0 = t.cell_len
            ligado = v == self.atual
            if self.estilo == "chip":
                if ligado:
                    est = f"bold {a.cor('fundo')} on {a.cor('accent')}"
                    if self.has_focus:
                        est += " underline"
                else:
                    est = f"{a.cor('texto')} on {a.cor('painel')}"
                t.append(f" {rot} ", style=est)
            else:
                est = f"bold underline {a.cor('accent')}" if ligado and self.has_focus else \
                    f"bold underline {a.cor('forte')}" if ligado else a.cor("mudo")
                t.append(rot, style=est)
            self._x.append((x0, t.cell_len, v))
        return t

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()

    def on_click(self, ev: events.Click) -> None:
        for a, b, v in self._x:
            if a <= ev.x < b:
                ev.stop()
                self.definir(v, avisar=True)
                return


class Cartao(Widget, can_focus=True):
    """Item com capa: atalho (capa à esquerda, numa faixa), grande (capa em cima) ou mini (capa pequena e duas linhas)."""

    DEFAULT_CSS = """
    Cartao { width: 1fr; height: 3; }
    Cartao.grande { width: 16; height: 8; }
    Cartao.mini { width: 1fr; height: 2; }
    """
    BINDINGS = [Binding("enter", "abrir", show=False)]

    class Aberto(Message):
        def __init__(self, cartao: "Cartao", item: Item) -> None:
            super().__init__()
            self.cartao, self.item = cartao, item

        @property
        def control(self) -> "Cartao":
            return self.cartao

    class Menu(Aberto):
        pass

    def __init__(self, item: Item, modo: str = "atalho", sub: str = "", **kw) -> None:
        super().__init__(classes=modo, **kw)
        self.item, self.modo, self.sub = item, modo, sub
        self._hover = False
        self._ultimo = False

    def render(self) -> Text:
        a = self.app
        w, h = self.size
        it = self.item
        tocando = a.tocando_uri(it.uri)
        if self.has_focus:
            fundo = a.cor("selecao")
        elif tocando and self.modo == "atalho":
            fundo = misturar(a.cor("accent"), a.cor("fundo"), 0.16)
        elif self.modo == "atalho":
            fundo = a.cor("hover") if self._hover else a.cor("painel")
        else:
            fundo = a.cor("hover") if self._hover else ""
        nome_est = f"bold {a.cor('accent') if tocando else a.cor('forte')}"
        linhas: list[Text] = []
        if self.modo == "atalho":
            cw = min(6, max(0, w // 4))
            capa = linhas_capa(it.uri, it.tipo, it.nome, cw, h, a.paleta) if cw else []
            eq = a.eq_texto() if tocando else ""
            for y in range(h):
                t = capa[y].copy() if cw else Text("")
                resto = w - cw
                if y == h // 2:
                    t.append_text(ajustar(Text("  ") + Text(it.nome, style=nome_est), max(0, resto - 3)))
                    t.append_text(ajustar(Text(eq, style=a.cor("accent")), min(3, resto)))
                else:
                    t.append(" " * resto)
                linhas.append(t)
        elif self.modo == "mini":
            cw = 4
            capa = linhas_capa(it.uri, it.tipo, it.nome, cw, 2, a.paleta)
            sub = self.sub or it.sub
            for y in range(h):
                t = capa[y].copy() if y < 2 else Text(" " * cw)
                if y == 0:
                    t.append_text(ajustar(Text("  ") + Text(it.nome, style=nome_est), w - cw))
                elif y == 1:
                    t.append_text(ajustar(Text("  ") + Text(sub, style=a.cor("mudo")), w - cw))
                else:
                    t.append(" " * (w - cw))
                linhas.append(t)
        else:  # grande: capa em cima, nome e sub embaixo, centralizados
            ch = max(1, h - 2)
            cw = min(w, ch * 2)
            capa = linhas_capa(it.uri, it.tipo, it.nome, cw, ch, a.paleta)
            esq = (w - cw) // 2
            for y in range(ch):
                linhas.append(Text(" " * esq) + capa[y] + Text(" " * (w - cw - esq)))
            linhas.append(ajustar(Text(it.nome, style=nome_est), w, "center"))
            linhas.append(ajustar(Text(self.sub or it.sub, style=a.cor("mudo")), w, "center"))
        saida = Text("\n").join(linhas[:h])
        if fundo:
            saida = Text("\n").join(_sob(l, fundo) for l in linhas[:h])
        return saida

    def on_enter(self) -> None:
        self._hover = True
        self.refresh()

    def on_leave(self) -> None:
        self._hover = False
        self.refresh()

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self._ultimo = False
        self.refresh()

    def on_click(self, ev: events.Click) -> None:
        ev.stop()
        if ev.button == 3:
            self.focus()
            self.post_message(self.Menu(self, self.item))
            return
        if ev.chain >= 2 or self._ultimo:
            self.post_message(self.Aberto(self, self.item))
        self._ultimo = True

    def action_abrir(self) -> None:
        self.post_message(self.Aberto(self, self.item))


def _sob(t: Text, fundo: str) -> Text:
    """Fundo por baixo do texto, sem cobrir o fundo que a capa já tem."""
    base = Text(t.plain, style=f"on {fundo}", no_wrap=True)
    for sp in t.spans:
        base.stylize(sp.style, sp.start, sp.end)
    if t.style:
        base.stylize(t.style)
    return base


class Secao(Widget):
    """Título de seção com régua: `tocadas recentemente ──────── ver tudo ›` (o “ver tudo” é clicável)."""

    DEFAULT_CSS = "Secao { height: 1; width: 1fr; margin-top: 1; }"

    class Mais(Message):
        def __init__(self, secao: "Secao") -> None:
            super().__init__()
            self.secao = secao

        @property
        def control(self) -> "Secao":
            return self.secao

    def __init__(self, titulo: str, mais: str = "", regua: bool = True, **kw) -> None:
        super().__init__(**kw)
        self.titulo, self.mais, self.regua = titulo, mais, regua

    def render(self) -> Text:
        a = self.app
        w = self.size.width
        t = Text(self.titulo, style=f"bold {a.cor('forte')}", no_wrap=True)
        fim = Text(f" {self.mais}", style=a.cor("mudo")) if self.mais else Text("")
        meio = w - t.cell_len - fim.cell_len - 2
        if self.regua and meio > 0:
            t.append(" " + "─" * meio + " ", style=a.cor("linha"))
        else:
            t.append(" " * max(0, w - t.cell_len - fim.cell_len))
        return t + fim

    def on_click(self, ev: events.Click) -> None:
        if self.mais and ev.x >= self.size.width - len(self.mais) - 1:
            ev.stop()
            self.post_message(self.Mais(self))


class Trilha(Widget):
    """Onde você está: `início / busca / Nome`. Clique num pedaço volta para aquela página."""

    DEFAULT_CSS = "Trilha { height: 1; width: auto; max-width: 60; }"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.partes: list[tuple[str, int]] = []
        self._x: list[tuple[int, int, int]] = []

    def definir(self, partes: list[tuple[str, int]]) -> None:
        self.partes = partes
        self.refresh(layout=True)

    def get_content_width(self, container, viewport) -> int:
        return min(60, max(1, sum(len(p) + 3 for p, _ in self.partes) - 3))

    def render(self) -> Text:
        a = self.app
        t = Text(no_wrap=True, overflow="ellipsis")
        self._x = []
        for n, (rot, idx) in enumerate(self.partes):
            if n:
                t.append(" / ", style=a.cor("linha"))
            x0 = t.cell_len
            ultimo = n == len(self.partes) - 1
            t.append(rot, style=f"bold {a.cor('forte')}" if ultimo else a.cor("mudo"))
            self._x.append((x0, t.cell_len, idx))
        return t

    def on_click(self, ev: events.Click) -> None:
        for a, b, idx in self._x:
            if a <= ev.x < b:
                ev.stop()
                self.app.ir_historico(idx)
                return


class Botao(Widget, can_focus=True):
    """Botão de uma linha: clique ou Enter apertam. `cheio` é o de tocar; `link` não tem margem."""

    DEFAULT_CSS = """
    Botao { width: auto; height: 1; padding: 0 1; color: $foreground; }
    Botao:hover { background: $oma-hover; }
    Botao:focus { background: $oma-selecao; text-style: bold; }
    Botao.cheio { background: $accent; color: $background; text-style: bold; }
    Botao.cheio:hover { background: $accent 85%; }
    Botao.cheio:focus { background: $accent; color: $background; text-style: bold underline; }
    Botao.link { padding: 0; }
    Botao.mudo { color: $oma-mudo; }
    Botao.ligado { color: $accent; }
    Botao.vazado { background: $oma-painel; }
    Botao.vermelho { color: $error; }
    Botao:disabled { color: $oma-linha; }
    """
    BINDINGS = [Binding("enter", "apertar", show=False)]

    class Apertado(Message):
        def __init__(self, botao: "Botao") -> None:
            super().__init__()
            self.botao = botao

        @property
        def control(self) -> "Botao":
            return self.botao

    def __init__(self, rotulo: str = "", id: str | None = None, classes: str = "", tooltip: str | None = None,
                 desativado: bool = False) -> None:
        super().__init__(id=id, classes=classes, disabled=desativado)
        self._rotulo = rotulo
        if tooltip:
            self.tooltip = tooltip

    @property
    def label(self) -> str:
        return self._rotulo

    @label.setter
    def label(self, v: str) -> None:
        if v != self._rotulo:
            self._rotulo = v
            self.refresh(layout=True)

    def get_content_width(self, container, viewport) -> int:
        return Text(self._rotulo).cell_len

    def render(self) -> Text:
        return Text(self._rotulo, no_wrap=True, overflow="ellipsis")

    def press(self) -> None:
        if not self.disabled:
            self.post_message(self.Apertado(self))

    def action_apertar(self) -> None:
        self.press()

    def on_click(self, ev: events.Click) -> None:
        ev.stop()
        if ev.button == 1:
            self.press()


class Regua(Widget):
    """Linha horizontal na cor linha, na largura do widget."""

    DEFAULT_CSS = "Regua { height: 1; width: 1fr; }"

    def render(self) -> Text:
        return Text("─" * self.size.width, style=self.app.cor("linha"))
