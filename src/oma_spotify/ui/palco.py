"""Palco (z no Tocando ou na Fila): capa, título grande, letra sincronizada e a próxima faixa."""

from __future__ import annotations

import time

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from oma_spotify.services.modelos import mmss
from oma_spotify.ui.capa import Capa, linhas_capa
from oma_spotify.ui.fonte import grande, largura_grande
from oma_spotify.ui.icones import ic
from oma_spotify.ui.lista import EstadoLinha, Lista, ajustar, colunas
from oma_spotify.ui.tocando import linha_letra
from oma_spotify.ui.widgets import Abas, Botao, Regua


class Palco(Horizontal):
    DEFAULT_CSS = """
    Palco { width: 1fr; height: 1fr; padding: 1 4; }
    Palco #pc-esq { width: 2fr; height: 1fr; }
    Palco #pc-capa { width: 36; height: 18; margin-top: 1; }
    Palco #pc-titulo { height: auto; margin-top: 1; color: $oma-forte; }
    Palco #pc-meta { height: 1; margin-top: 1; }
    Palco #pc-curtir { margin-top: 1; color: $oma-mudo; padding: 0; }
    Palco #pc-dir { width: 3fr; height: 1fr; margin-left: 4; }
    Palco #pc-cab { height: 1; margin-top: 1; }
    Palco #pc-abas { width: 1fr; }
    Palco #pc-fonte { width: auto; color: $oma-linha; }
    Palco #pc-letra, Palco #pc-fila { height: 1fr; margin-top: 2; }
    Palco #pc-aviso { height: 1fr; margin-top: 2; color: $oma-mudo; }
    Palco #pc-regua { height: 1; color: $oma-linha; }
    Palco #pc-seguinte-rot { height: 1; color: $oma-mudo; margin-top: 1; }
    Palco #pc-seguinte { height: 2; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.aba = "letra"
        self._mexeu = 0.0
        self._atual = None
        self._pronto = False

    def compose(self) -> ComposeResult:
        with Vertical(id="pc-esq"):
            yield Capa(id="pc-capa")
            yield Static("", id="pc-titulo")
            yield Static("", id="pc-meta")
            yield Botao("", id="pc-curtir", tooltip="curtir (c)")
        with Vertical(id="pc-dir"):
            with Horizontal(id="pc-cab"):
                yield Abas([("letra", "letra"), ("fila", "fila")], "letra", estilo="aba", id="pc-abas")
                yield Static("", id="pc-fonte")
            yield Lista(self._linha_letra, altura=2, fundo_cursor=False, id="pc-letra")
            yield Lista(self._linha_fila, altura=2, id="pc-fila")
            yield Static("", id="pc-aviso")
            yield Regua(id="pc-regua")
            yield Static("a seguir", id="pc-seguinte-rot")
            yield Static("", id="pc-seguinte")

    def on_mount(self) -> None:
        self._pronto = True
        self.border_title = "tocando"
        self.border_subtitle = "z sai do zoom"
        self.pintar()
        self.pintar_letra()

    def on_resize(self) -> None:
        if not self._pronto:
            return
        h = self.size.height
        capa = self.query_one("#pc-capa", Capa)
        ch = max(0, min(18, h - 14))
        capa.display = ch >= 6
        capa.styles.height = ch
        capa.styles.width = ch * 2
        self.pintar()

    def focar_entrada(self) -> None:
        l = self.query_one("#pc-letra" if self.aba == "letra" else "#pc-fila", Lista)
        if l.display:
            l.focus()
        else:
            self.query_one("#pc-curtir", Botao).focus()

    # ------------------------------------------------------------ dados
    def pintar(self) -> None:
        if not self._pronto:
            return
        a = self.app
        p = a.player
        q = self.query_one
        if p is None or p.item is None:
            q("#pc-titulo", Static).update("nada tocando")
            q("#pc-meta", Static).update("")
            return
        it = p.item
        q("#pc-capa", Capa).definir(it.uri, it.tipo, it.extra or it.nome)
        w = q("#pc-esq").size.width
        if w and largura_grande(it.nome) <= w:
            q("#pc-titulo", Static).update(Text("\n".join(grande(it.nome)), style=a.cor("forte")))
        else:
            q("#pc-titulo", Static).update(Text(it.nome, style=f"bold {a.cor('forte')}"))
        q("#pc-meta", Static).update(Text.assemble((it.sub, f"bold {a.cor('texto')}"),
                                                   (" · ".join([""] + [x for x in (it.extra, it.ano) if x]), a.cor("mudo"))))
        cur = q("#pc-curtir", Botao)
        cur.label = f"{ic('curtida')} na sua biblioteca" if a.curtido else f"{ic('nao_curtida')} curtir"
        cur.set_class(a.curtido, "ligado")
        self._seguinte()
        self.query_one("#pc-fila", Lista).definir([x for x in a.minha_fila + a.fila_spotify][:30])

    def _seguinte(self) -> None:
        a = self.app
        prox = (a.minha_fila or a.fila_spotify or [None])[0]
        w = max(20, self.query_one("#pc-dir").size.width)
        if prox is None:
            self.query_one("#pc-seguinte", Static).update(Text("nada na fila", style=a.cor("mudo")))
            return
        capa = linhas_capa(prox.uri, prox.tipo, prox.extra or prox.nome, 4, 2, a.paleta)
        l1 = capa[0] + Text("  ") + colunas([(Text(prox.nome, style=f"bold {a.cor('forte')}"), 0, "left"),
                                              (Text(mmss(prox.dur_ms), style=a.cor("mudo")), 5, "right")], w - 6)
        l2 = capa[1] + Text("  ") + ajustar(Text(prox.sub, style=a.cor("mudo")), w - 6)
        self.query_one("#pc-seguinte", Static).update(Text("\n").join([l1, l2]))

    def pintar_letra(self) -> None:
        if not self._pronto:
            return
        a = self.app
        lt = a.letra
        abas = self.query_one("#pc-abas", Abas)
        fonte = self.query_one("#pc-fonte", Static)
        aviso = self.query_one("#pc-aviso", Static)
        sem = lt is not None and lt.vazia
        abas.opcoes = [("letra", "sem letra" if sem else "letra"), ("fila", "fila")]
        if sem and self.aba == "letra":
            self.aba = "fila"  # sem letra, a fila ocupa o lugar
        abas.definir(self.aba)
        abas.refresh()
        if lt is None:
            fonte.update("buscando em lrclib.net")
        elif sem:
            fonte.update(lt.motivo)
        else:
            fonte.update(("sincronizada" if lt.sincronizada else "sem sincronia") + " · lrclib.net")
        if lt is not None and not lt.vazia:
            self.query_one("#pc-letra", Lista).definir(lt.linhas)
        aviso.update(Text("buscando a letra..." if lt is None else "", style=a.cor("mudo")))
        self._mostrar()
        self.tick(forcar=True)

    def _mostrar(self) -> None:
        lt = self.app.letra
        tem = lt is not None and not lt.vazia
        self.query_one("#pc-letra").display = self.aba == "letra" and tem
        self.query_one("#pc-fila").display = self.aba == "fila"
        self.query_one("#pc-aviso").display = self.aba == "letra" and not tem

    def alt_horizontal(self, passo: int) -> None:
        lt = self.app.letra
        if lt is not None and lt.vazia:
            return
        self.aba = "fila" if self.aba == "letra" else "letra"
        self.query_one("#pc-abas", Abas).definir(self.aba)
        self._mostrar()
        self.focar_entrada()

    @on(Abas.Mudou, "#pc-abas")
    def _aba(self, ev: Abas.Mudou) -> None:
        ev.stop()
        if ev.valor != self.aba:
            self.alt_horizontal(1)

    # ------------------------------------------------------------ desenho e sincronia
    def _linha_letra(self, lin, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        lt = a.letra
        atual = lt.indice(a.player.posicao()) if lt and a.player else -1
        return linha_letra(a, lin, n, e, atual, bool(lt and lt.sincronizada), tempo=True) + [Text("")]

    def _linha_fila(self, it, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        est = f"bold {a.cor('forte')}" if e.destacado else a.cor("texto")
        return [colunas([(Text(str(n + 1), style=a.cor("mudo")), 3, "right"), (Text(it.nome, style=est), 0, "left"),
                         (Text(mmss(it.dur_ms), style=a.cor("mudo")), 5, "right")], e.largura),
                Text("    ") + ajustar(Text(it.sub, style=a.cor("mudo")), e.largura - 4)]

    def tick(self, forcar: bool = False) -> None:
        if not self._pronto:
            return
        a = self.app
        lt = a.letra
        if lt is None or lt.vazia or not lt.sincronizada or a.player is None:
            return
        atual = lt.indice(a.player.posicao())
        if atual != self._atual or forcar:
            self._atual = atual
            l = self.query_one("#pc-letra", Lista)
            l.redesenhar()
            if time.monotonic() - self._mexeu > 5 and atual >= 0:
                l.cursor = atual
                l.mostrar_item(atual, centralizar=True)

    @on(Lista.Destacado, "#pc-letra")
    def _mexeu_letra(self, ev: Lista.Destacado) -> None:
        self._mexeu = time.monotonic()

    @on(Lista.Escolhido, "#pc-letra")
    def _pular(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        if ev.item[0] >= 0:
            self.app.pular_para(ev.item[0])
            self._mexeu = 0

    @on(Lista.Escolhido, "#pc-fila")
    def _fila(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.query_one("#fila").tocar_agora(ev.item)

    @on(Botao.Apertado, "#pc-curtir")
    def _curtir(self, ev: Botao.Apertado) -> None:
        ev.stop()
        if self.app.player and self.app.player.item:
            self.app.curtir_itens([self.app.player.item])

    def tratar(self, acao: str, itens: list) -> bool:
        return False

    def rodape(self):
        return [("z", "sair do zoom", "zoom"), ("alt+←→", "letra/fila", "alt_h(1)"), ("↑↓", "linhas", "mover(0,1)"),
                ("enter", "pular para a linha", "enter")]

    def teclas(self):
        return [("palco", [("↑ ↓", "escolhe uma linha"), ("enter", "pula a música para ela"), ("alt+← →", "letra ou fila"),
                           ("z  esc", "sai do palco")])]
