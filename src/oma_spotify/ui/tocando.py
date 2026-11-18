"""Janelas Tocando (capa, faixa, artista, álbum, curtir) e Fila · letra (a sua fila e o que vem depois, ou a letra)."""

from __future__ import annotations

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from oma_spotify.services.modelos import Item, mmss
from oma_spotify.ui.capa import Capa
from oma_spotify.ui.icones import ic
from oma_spotify.ui.lista import EstadoLinha, Lista, ajustar, colunas
from oma_spotify.ui.widgets import Botao


class Tocando(Vertical):
    NOME = "tocando"
    DEFAULT_CSS = """
    Tocando { align-horizontal: center; }
    Tocando #tc-capa { width: 32; height: 16; margin-top: 1; }
    Tocando #tc-linha { height: 1; margin-top: 1; }
    Tocando #tc-titulo { width: 1fr; text-style: bold; color: $oma-forte; }
    Tocando #tc-curtir { padding: 0; color: $accent; }
    Tocando #tc-artista { color: $foreground; }
    Tocando #tc-album { color: $oma-mudo; margin-bottom: 1; }
    Tocando .link { width: 100%; }
    """
    BINDINGS = [Binding("left,h", "andar(-1)", show=False), Binding("right,l", "andar(1)", show=False),
                Binding("up,k", "andar(-1)", show=False), Binding("down,j", "andar(1)", show=False)]

    def compose(self) -> ComposeResult:
        yield Capa(id="tc-capa")
        with Horizontal(id="tc-linha"):
            yield Static("nada tocando", id="tc-titulo")
            yield Botao(ic("nao_curtida"), id="tc-curtir", tooltip="curtir (c)")
        yield Botao("", id="tc-artista", classes="link", tooltip="ir para o artista (a)")
        yield Botao("", id="tc-album", classes="link", tooltip="ir para o álbum")

    def on_mount(self) -> None:
        self.border_title = "tocando"

    def ajustar(self, corpo: int, baixo: bool = False) -> None:
        capa = self.query_one("#tc-capa", Capa)
        h = max(0, min(16, corpo - 26))
        capa.display = not baixo and h >= 6
        capa.styles.height = h
        capa.styles.width = min(32, h * 2)

    def pintar(self, p, curtido: bool) -> None:
        a = self.app
        q = self.query_one
        cur = q("#tc-curtir", Botao)
        if p is None or p.item is None:
            q("#tc-capa", Capa).definir("", "", "")
            q("#tc-titulo", Static).update("nada tocando")
            q("#tc-artista", Botao).label = "d escolhe onde tocar"
            q("#tc-album", Botao).label = ""
            cur.display = False
            return
        it = p.item
        cur.display = it.tipo == "track"
        q("#tc-capa", Capa).definir(it.uri, it.tipo, it.extra or it.nome)
        q("#tc-titulo", Static).update(Text(it.nome, overflow="ellipsis", no_wrap=True))
        cur.label = ic("curtida") if curtido else ic("nao_curtida")
        q("#tc-artista", Botao).label = it.sub
        q("#tc-album", Botao).label = " · ".join(x for x in (it.extra, it.ano) if x)

    def focar_entrada(self) -> None:
        b = self.query_one("#tc-curtir", Botao)
        (b if b.display else self.query_one("#tc-artista", Botao)).focus()

    def action_andar(self, passo: int) -> None:
        ordem = [w for w in (self.query_one("#tc-curtir"), self.query_one("#tc-artista"), self.query_one("#tc-album"))
                 if w.display and w.label]
        f = self.app.focused
        if not ordem:
            return
        i = ordem.index(f) if f in ordem else -1
        ordem[(i + passo) % len(ordem)].focus()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        a = self.app
        it = a.player.item if a.player else None
        if it is None:
            if ev.botao.id == "tc-artista":
                a.action_tocar_em()
            return
        {"tc-curtir": lambda: a.curtir_itens([it]), "tc-artista": lambda: a.ir_artista(it),
         "tc-album": lambda: a.ir_album(it)}.get(ev.botao.id or "", lambda: None)()

    def on_click(self, ev: events.Click) -> None:
        if ev.widget is self and ev.y == 0 and ev.chain >= 2:
            self.app.action_zoom()

    def rodape(self):
        return [("←→", "curtir, artista, álbum", "app.mover(1,0)"), ("enter", "abrir", "app.enter"), ("z", "palco", "app.zoom")]

    def teclas(self):
        return [("nesta janela", [("← →", "entre curtir, artista e álbum"), ("enter", "curte, ou abre o artista ou o álbum"),
                                  ("z", "palco (letra grande)")])]


# ---------------------------------------------------------------- fila e letra
class Cabeca(str):
    """Linha de seção na fila (não selecionável)."""


def linha_letra(app, lin: tuple[int, str], n: int, e: EstadoLinha, atual: int, sincronizada: bool, tempo: bool = False) -> list[Text]:
    ms, txt = lin
    dist = abs(n - atual) if atual >= 0 else 3
    if n == atual:
        est = f"bold {app.cor('accent')}"
    elif dist <= 2:
        est = app.cor("texto")
    elif dist <= 4:
        est = app.cor("mudo")
    else:
        est = app.cor("linha")
    if e.destacado and n != atual:
        est = f"bold {app.cor('forte')}"
    t = Text(no_wrap=True)
    if tempo:
        t.append(ajustar(Text(mmss(ms) if (n == atual or e.destacado) and ms >= 0 else "", style=app.cor("accent")), 6, "right"))
        t.append(" ▎ " if n == atual else " ▏ " if e.destacado else "   ", style=app.cor("accent"))
    t.append(txt, style=est)
    return [ajustar(t, e.largura)]


class FilaLetra(Vertical):
    NOME = "fila · letra"
    DEFAULT_CSS = """
    FilaLetra #fila-lista, FilaLetra #letra-lista { height: 1fr; }
    FilaLetra #letra-aviso { height: auto; color: $oma-mudo; margin-top: 1; dock: top; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.aba = "fila"
        self._mexeu = 0.0

    def compose(self) -> ComposeResult:
        yield Lista(self._linha_fila, alturas=self._altura, selecionavel=lambda x: not isinstance(x, (Cabeca, str)), marcar=True,
                    id="fila-lista")
        yield Lista(self._linha_letra, fundo_cursor=False, id="letra-lista")
        yield Static("", id="letra-aviso")

    def on_mount(self) -> None:
        self._mostrar_aba()

    def _titulo(self) -> None:
        a = self.app
        fila_est = "bold" if self.aba == "fila" else ""
        letra_est = "bold" if self.aba == "letra" else ""
        self.border_title = Text.assemble((" fila", fila_est), (" · ", ""), ("letra ", letra_est))

    def _mostrar_aba(self) -> None:
        self._titulo()
        fila = self.aba == "fila"
        self.query_one("#fila-lista").display = fila
        self.query_one("#letra-lista").display = not fila
        self.query_one("#letra-aviso").display = not fila
        if fila:
            self.pintar_fila()
        else:
            self.app.carregar_letra()
            self.pintar_letra()

    def trocar_aba(self, aba: str) -> None:
        if aba == self.aba:
            return
        foco = self.app.nome_janela(self.app.focused) == "fila"
        self.aba = aba
        self.app.guardar("aba_fila", aba)
        self._mostrar_aba()
        if foco:
            self.focar_entrada()

    def alt_horizontal(self, passo: int) -> None:
        self.trocar_aba("letra" if self.aba == "fila" else "fila")

    def focar_entrada(self) -> None:
        if self.aba == "fila":
            self.query_one("#fila-lista", Lista).focus()
        else:
            self.query_one("#letra-lista", Lista).focus()

    # ------------------------------------------------------------ fila
    def _altura(self, x) -> int:
        return 1 if isinstance(x, (Cabeca, str)) else 2

    def nome_contexto(self) -> str:
        a = self.app
        p = a.player
        if p is None or not p.contexto:
            return ""
        if p.contexto.endswith(":collection"):
            return "Músicas Curtidas"
        alvo = next((i for i in a.dados_bib if i.uri == p.contexto), None)
        return alvo.nome if alvo else ""

    def linhas_fila(self) -> list:
        a = self.app
        saida: list = []
        minha = list(a.minha_fila)
        if minha:
            saida.append(Cabeca(f"na sua fila|{len(minha)}"))
            saida += minha
        depois = list(a.fila_spotify)
        if a._entregue and depois and depois[0].uri == a._entregue:
            depois = depois[1:]
        if depois:
            if minha:
                saida.append(Cabeca(""))
            ctx = self.nome_contexto()
            saida.append(Cabeca(f"depois, de {ctx}" if ctx else "depois"))
            saida += depois[:30]
        if not saida:
            saida.append(Cabeca("a fila está vazia · f põe a faixa aqui"))
        return saida

    def pintar_fila(self) -> None:
        l = self.query_one("#fila-lista", Lista)
        l.definir(self.linhas_fila())

    def _linha_fila(self, x, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        w = e.largura
        if isinstance(x, (Cabeca, str)):
            txt, _, cont = str(x).partition("|")
            return [colunas([(Text(txt, style=a.cor("mudo")), 0, "left"), (Text(cont, style=a.cor("mudo")), 3, "right")], w)]
        l = self.query_one("#fila-lista", Lista)
        num = sum(1 for y in l.itens[:n + 1] if not isinstance(y, (Cabeca, str)))
        barra = Text("▌", style=a.cor("accent")) if e.destacado else Text("")
        est = f"bold {a.cor('forte')}" if e.destacado else a.cor("texto")
        l1 = barra + colunas([(Text(str(num), style=a.cor("mudo")), 1 if num < 10 else 2, "left"), (Text(x.nome, style=est), 0, "left"),
                              (Text(mmss(x.dur_ms), style=a.cor("mudo")), 5, "right")], w - barra.cell_len)
        l2 = barra + Text("  " if num < 10 else "   ") + ajustar(Text(x.sub, style=a.cor("mudo")), w - 3 - barra.cell_len)
        return [l1, l2]

    def _indices_minha(self, l: Lista) -> list[int]:
        """Índices (na sua fila) dos itens marcados ou do cursor, se forem da sua fila."""
        a = self.app
        alvo = l.itens_marcados()
        minhas = []
        for it in alvo:
            for k, m in enumerate(a.minha_fila):
                if m is it:
                    minhas.append(k)
        return minhas

    def tratar(self, acao: str, itens: list) -> bool:
        a = self.app
        if self.aba == "letra":
            return acao not in ("curtir", "seguir", "playlist", "artista", "link", "opcoes")
        l = self.query_one("#fila-lista", Lista)
        if acao == "remover":
            k = self._indices_minha(l)
            if k:
                a.tirar_da_minha_fila(k)
            else:
                a.notify("O que vem depois é do Spotify: a API não deixa tirar.", timeout=5)
            return True
        if acao == "tocar" and itens:
            self.tocar_agora(itens[0])
            return True
        return False

    def tocar_agora(self, it: Item) -> None:
        """Na sua fila: toca agora e sai da fila. No que vem depois: toca a faixa a partir dela."""
        a = self.app
        if it in a.minha_fila:
            a.minha_fila.remove(it)
            a.guardar_minha_fila()
        a.tocar_item(it, contexto=a.player.contexto if a.player and a.player.contexto and it.tipo == "track"
                     and not a.player.contexto.endswith(":collection") else "")
        self.pintar_fila()

    def mover_item(self, passo: int) -> None:
        a = self.app
        if self.aba != "fila":
            return
        l = self.query_one("#fila-lista", Lista)
        k = self._indices_minha(l)
        if not k:
            a.notify("Só a sua fila se move. O que vem depois é do Spotify.", timeout=4)
            return
        novos = a.mover_na_minha_fila(k, passo)
        self.pintar_fila()
        alvo = [n for n, it in enumerate(l.itens) if any(it is a.minha_fila[j] for j in novos)]
        if alvo:
            l.marcados = set(alvo) if len(alvo) > 1 else set()
            l.mover_cursor(alvo[0] if passo < 0 else alvo[-1])
            l.redesenhar()

    def opcoes_extra(self, itens):
        return [("remover", "tirar da sua fila", "x")] if self.aba == "fila" and itens and itens[0] in self.app.minha_fila else []

    @on(Lista.Escolhido, "#fila-lista")
    def _fila(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.tocar_agora(ev.item)

    @on(Lista.Menu, "#fila-lista")
    def _menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes([ev.item], self)

    # ------------------------------------------------------------ letra
    def _sem_letra(self) -> bool:
        lt = self.app.letra
        return lt is not None and lt.vazia

    def pintar_letra(self) -> None:
        a = self.app
        lt = a.letra
        l = self.query_one("#letra-lista", Lista)
        aviso = self.query_one("#letra-aviso", Static)
        if self.aba != "letra":
            return
        if a.player is None or a.player.item is None or lt is None or lt.vazia:
            l.definir([])
            aviso.display = True
            if a.player is None or a.player.item is None:
                aviso.update("nada tocando")
            elif lt is None:
                aviso.update("buscando a letra em lrclib.net...")
            else:
                aviso.update(Text.assemble((lt.motivo or "sem letra para esta faixa", a.cor("mudo")),
                                           ("\n\nalt+←→ volta para a fila", a.cor("linha"))))
                self._titulo_sem_letra()
            return
        self._titulo()
        aviso.update("" if lt.sincronizada else "letra sem sincronia")
        aviso.display = not lt.sincronizada
        l.definir(lt.linhas)
        self.tick(forcar=True)

    def _titulo_sem_letra(self) -> None:
        self.border_title = Text.assemble((" fila", ""), (" · ", ""), ("sem letra ", "bold"))

    def _linha_letra(self, lin, n: int, e: EstadoLinha) -> list[Text]:
        lt = self.app.letra
        atual = lt.indice(self.app.player.posicao()) if lt and self.app.player else -1
        return linha_letra(self.app, lin, n, e, atual, bool(lt and lt.sincronizada))

    def tick(self, forcar: bool = False) -> None:
        import time as _t
        a = self.app
        if self.aba != "letra" or a.letra is None or a.letra.vazia or not a.letra.sincronizada or a.player is None:
            return
        l = self.query_one("#letra-lista", Lista)
        atual = a.letra.indice(a.player.posicao())
        if atual != getattr(self, "_atual", None) or forcar:
            self._atual = atual
            l.redesenhar()
            if _t.monotonic() - getattr(l, "_mexeu", 0) > 5 and atual >= 0:
                l.cursor = atual
                l.mostrar_item(atual, centralizar=True)

    @on(Lista.Destacado, "#letra-lista")
    def _mexeu_letra(self, ev: Lista.Destacado) -> None:
        import time as _t
        ev.lista._mexeu = _t.monotonic()

    @on(Lista.Escolhido, "#letra-lista")
    def _pular(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        ms = ev.item[0]
        if ms >= 0:
            self.app.pular_para(ms)
            ev.lista._mexeu = 0

    def on_click(self, ev: events.Click) -> None:
        if ev.widget is self and ev.y == 0:
            ev.stop()
            if ev.chain >= 2:
                self.app.action_zoom()
                return
            self.trocar_aba("letra" if ev.x >= 8 else "fila")

    def rodape(self):
        if self.aba == "letra":
            return [("↑↓", "linhas", "app.mover(0,1)"), ("enter", "pular para a linha", "app.enter"),
                    ("alt+←→", "fila", "app.alt_h(1)"), ("z", "palco", "app.zoom")]
        return [("enter", "tocar agora", "app.enter"), ("x", "tirar", "app.item('remover')"), ("alt+↑↓", "mover", "app.alt_v(-1)"),
                ("u", "desfaz", "app.item('desfazer')"), ("alt+←→", "letra", "app.alt_h(1)")]

    def teclas(self):
        return [("nesta janela", [("alt+← →", "fila ou letra"), ("↑ ↓", "faixas da fila, ou linhas da letra"),
                                  ("enter", "na fila, toca agora; na letra, pula para a linha"), ("x", "tira da sua fila"),
                                  ("alt+↑ ↓", "move na sua fila"), ("u", "desfaz"), ("z", "palco")])]
