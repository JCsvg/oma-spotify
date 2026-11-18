"""Player em faixa, sem borda: a faixa à esquerda, os controles no meio, curtir, aparelho e volume à direita,
e a barra de progresso na largura toda embaixo. O botão de tocar é o único cheio."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from oma_spotify.services.modelos import mmss
from oma_spotify.ui.capa import Capa
from oma_spotify.ui.icones import de_aparelho, ic
from oma_spotify.ui.widgets import Barra, Botao


class Player(Horizontal):
    NOME = "player"
    DEFAULT_CSS = """
    Player #pl-capa { width: 4; height: 2; margin-right: 1; display: none; }
    Player #pl-corpo { width: 1fr; }
    Player #pl-l1, Player #pl-l2 { height: 1; }
    Player #pl-esq { width: 1fr; }
    Player #pl-eq { width: 3; color: $accent; }
    Player #pl-titulo { width: 1fr; }
    Player #pl-msg { width: auto; color: $warning; text-style: bold; max-width: 70; }
    Player #pl-ctrl { width: auto; }
    Player #pl-ctrl Botao { margin: 0 1; }
    Player #play { width: 5; content-align: center middle; }
    Player #pl-dir { width: 1fr; align-horizontal: right; }
    Player #curtir { color: $accent; margin-right: 2; }
    Player #aparelho { color: $oma-mudo; margin-right: 2; }
    Player #mudo { color: $oma-mudo; }
    Player #volume { width: 14; margin: 0 1; }
    Player #rot-vol { width: 3; color: $oma-mudo; text-align: right; }
    Player #pl-tempo { width: auto; color: $oma-mudo; margin-right: 2; display: none; }
    Player #t-pos, Player #t-dur { width: 5; color: $oma-mudo; }
    Player #t-pos { text-align: right; }
    Player #progresso { margin: 0 1; }
    Player.-estreito #pl-capa { display: block; }
    Player.-estreito #aleatorio, Player.-estreito #repetir, Player.-estreito #aparelho, Player.-estreito #mudo,
    Player.-estreito #volume, Player.-estreito #rot-vol { display: none; }
    Player.-estreito #pl-dir { width: auto; }
    Player.-baixo { height: 1; padding: 0 1; }
    Player.-baixo #pl-l2, Player.-baixo #pl-capa { display: none; }
    Player.-baixo #pl-tempo { display: block; }
    """

    def compose(self) -> ComposeResult:
        yield Capa(id="pl-capa")
        with Vertical(id="pl-corpo"):
            with Horizontal(id="pl-l1"):
                with Horizontal(id="pl-esq"):
                    yield Static("", id="pl-eq")
                    yield Static("", id="pl-titulo")
                    yield Static("", id="pl-msg")
                with Horizontal(id="pl-ctrl"):
                    yield Botao(ic("aleatorio"), id="aleatorio", classes="mudo link", tooltip="aleatório (s)")
                    yield Botao(ic("anterior"), id="anterior", classes="link", tooltip="anterior (,)")
                    yield Botao(ic("tocar"), id="play", classes="cheio", tooltip="tocar ou pausar (espaço)")
                    yield Botao(ic("proxima"), id="proxima", classes="link", tooltip="próxima (.)")
                    yield Botao(ic("repetir"), id="repetir", classes="mudo link", tooltip="repetir (r)")
                with Horizontal(id="pl-dir"):
                    yield Static("", id="pl-tempo")
                    yield Botao(ic("nao_curtida"), id="curtir", classes="link", tooltip="curtir (c)")
                    yield Botao("", id="aparelho", classes="link", tooltip="tocar em (d)")
                    yield Botao(ic("volume"), id="mudo", classes="link", tooltip="mudo (m)")
                    yield Barra(volume=True, id="volume")
                    yield Static("", id="rot-vol")
            with Horizontal(id="pl-l2"):
                yield Static("0:00", id="t-pos")
                yield Barra(id="progresso")
                yield Static("0:00", id="t-dur")

    def ajustar(self, largura: int, altura: int) -> None:
        self.set_class(largura < 110, "-estreito")
        self.set_class(altura < 30, "-baixo")
        self.styles.height = 1 if altura < 30 else 4

    def focar_entrada(self) -> None:
        self.query_one("#play", Botao).focus()

    def marcar_foco(self, ligado: bool) -> None:
        self.query_one("#progresso", Barra).marcar(ligado)

    def mensagem(self, txt: str) -> None:
        self.query_one("#pl-msg", Static).update(Text(txt, no_wrap=True, overflow="ellipsis") if txt else "")

    def pintar_eq(self) -> None:
        p = self.app.player
        self.query_one("#pl-eq", Static).update(self.app.eq_texto() if p and p.item else "")

    def pintar(self, p, curtido: bool) -> None:
        a = self.app
        q = self.query_one
        q("#curtir", Botao).label = ic("curtida") if curtido else ic("nao_curtida")
        if p is None or p.item is None:
            q("#pl-titulo", Static).update(Text.assemble(("nada tocando", "bold"), (" · d escolhe onde", a.cor("mudo"))))
            q("#pl-capa", Capa).definir("", "", "")
            q("#t-dur", Static).update("0:00")
            q("#progresso", Barra).definir(0)
            q("#play", Botao).label = ic("tocar")
            q("#aparelho", Botao).label = f"{de_aparelho('computer')} nenhum"
            self.pintar_eq()
            return
        it = p.item
        estreito = self.has_class("-estreito")
        t = Text(no_wrap=True, overflow="ellipsis")
        t.append(it.nome, style=f"bold {a.cor('forte')}")
        if it.sub:
            t.append(" · " if estreito else "  ", style=a.cor("mudo"))
            t.append(it.sub, style=a.cor("mudo"))
        q("#pl-titulo", Static).update(t)
        q("#pl-capa", Capa).definir(it.uri, it.tipo, it.extra or it.nome)
        q("#t-dur", Static).update(mmss(it.dur_ms))
        q("#play", Botao).label = ic("pausar") if p.tocando else ic("tocar")
        al = q("#aleatorio", Botao)
        al.set_class(p.aleatorio, "ligado")
        al.set_class(not p.aleatorio, "mudo")
        rep = q("#repetir", Botao)
        rep.label = ic("repetir1") if p.repetir == "track" else ic("repetir")
        rep.set_class(p.repetir != "off", "ligado")
        rep.set_class(p.repetir == "off", "mudo")
        tipo = next((d.tipo for d in a.dispositivos if d.nome == p.dispositivo), "computer")
        q("#aparelho", Botao).label = f"{de_aparelho(tipo)} {p.dispositivo[:18] or 'aparelho'}"
        if p.volume is not None:
            q("#volume", Barra).definir(p.volume / 100)
            q("#rot-vol", Static).update(str(p.volume))
            q("#mudo", Botao).label = ic("mudo") if p.volume == 0 else ic("volume")
        self.pintar_eq()
        self.tick(p)

    def tick(self, p) -> None:
        if p is None or p.item is None:
            return
        pos = p.posicao()
        self.query_one("#t-pos", Static).update(mmss(pos))
        if self.has_class("-baixo"):
            self.query_one("#pl-tempo", Static).update(f"{mmss(pos)} / {mmss(p.item.dur_ms)}")
        if p.item.dur_ms:
            self.query_one("#progresso", Barra).definir(pos / p.item.dur_ms)

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        a = self.app
        {"aleatorio": a.action_aleatorio, "anterior": a.action_anterior, "play": a.action_play_pause,
         "proxima": a.action_proxima, "repetir": a.action_repetir, "curtir": lambda: a.action_item("curtir"),
         "aparelho": a.action_tocar_em, "mudo": a.action_mudo}.get(ev.botao.id or "", lambda: None)()

    @on(Barra.Passo)
    def _passo(self, ev: Barra.Passo) -> None:
        ev.stop()
        self.app.passo_barra(ev.barra.id, ev.direcao)

    @on(Barra.Clique)
    def _clique(self, ev: Barra.Clique) -> None:
        ev.stop()
        self.app.clique_barra(ev.barra.id, ev.fracao)

    def tratar(self, acao: str, itens: list) -> bool:
        if acao == "curtir":
            self.app.curtir_itens(itens)
            return True
        return False

    def rodape(self):
        return [("←→", "controles", "app.mover(1,0)"), ("enter", "apertar", "app.enter"), ("↑↓", "barra / volume", "app.mover(0,1)"),
                ("c", "curtir", "app.item('curtir')"), ("d", "dispositivos", "app.tocar_em")]

    def teclas(self):
        return [("player", [("← →", "entre os controles; na barra e no volume, -5 e +5"), ("↑ ↓", "controles ou barra de progresso"),
                            ("enter", "aperta o controle"), ("d", "tocar em")])]
