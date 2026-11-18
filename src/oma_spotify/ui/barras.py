"""Barra superior, barra do player e menu da conta."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from oma_spotify.services.modelos import mmss
from oma_spotify.ui.capa import Capa
from oma_spotify.ui.dialogos import _Base, _css
from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import Barra


class BarraTopo(NavegacaoMixin, Horizontal):
    NOME = "Barra superior"
    RODAPE = ("app.buscar", "botao_acionar")
    DEFAULT_CSS = """
    BarraTopo { height: 3; padding: 0 1; }
    BarraTopo Button { min-width: 5; margin-right: 1; }
    BarraTopo #busca { width: 1fr; }
    BarraTopo #conta { margin-left: 1; margin-right: 0; }
    """
    BINDINGS = [Binding("slash", "app.buscar", "Buscar", key_display="/")]

    def compose(self) -> ComposeResult:
        yield Button("⌂", id="inicio", tooltip="Início")
        yield Button("◀", id="voltar", tooltip="Voltar (Esc)")
        yield Button("▶", id="avancar", tooltip="Avançar (Alt+])")
        yield Input(placeholder="O que você quer ouvir?  ( / )", id="busca")
        yield Button("Conta ▾", id="conta", tooltip="Dispositivos, configurações, sair")

    def focar_entrada(self) -> None:
        self.query_one("#busca", Input).focus()

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        a = self.app
        {"inicio": lambda: a.navegar({"t": "inicio"}), "voltar": a.action_voltar_historico,
         "avancar": a.action_avancar_historico, "conta": a.abrir_menu_conta}.get(ev.button.id or "", lambda: None)()

    @on(Input.Submitted, "#busca")
    def _buscar(self, ev: Input.Submitted) -> None:
        ev.stop()
        q = ev.value.strip()
        if q:
            self.app.navegar({"t": "busca", "q": q, "cat": "tudo"})
            self.app.focar_area("centro")

    @on(Input.Changed, "#busca")
    def _mudou(self, ev: Input.Changed) -> None:
        self.app.guardar("busca", ev.value)


class BarraPlayer(NavegacaoMixin, Horizontal):
    NOME = "Player"
    RODAPE = ("play_pause", "proxima", "anterior", "curtir_tocando")
    DEFAULT_CSS = """
    BarraPlayer { height: 4; padding: 0 1; }
    BarraPlayer #esq { width: 1fr; }
    BarraPlayer #meio { width: 2fr; }
    BarraPlayer #dir { width: 1fr; }
    BarraPlayer #mini { width: 8; height: 4; margin-right: 1; }
    BarraPlayer #info { width: 1fr; height: 4; }
    BarraPlayer #titulo, BarraPlayer #artista { height: 1; text-wrap: nowrap; text-overflow: ellipsis; }
    BarraPlayer .controles { height: 1; align-horizontal: center; margin-top: 1; }
    BarraPlayer .controles Button { margin: 0 1; }
    BarraPlayer #play { text-style: bold; background: $accent; color: $background; }
    BarraPlayer .ligado { color: $accent; text-style: bold; }
    BarraPlayer #linha-prog { height: 1; }
    BarraPlayer #t-pos, BarraPlayer #t-dur { width: 6; }
    BarraPlayer #t-pos { text-align: right; margin-right: 1; }
    BarraPlayer #t-dur { margin-left: 1; }
    BarraPlayer #botoes-dir { height: 1; align-horizontal: right; margin-top: 1; }
    BarraPlayer #botoes-dir Button { margin-left: 1; }
    BarraPlayer #linha-vol { height: 1; align-horizontal: right; }
    BarraPlayer #volume { width: 14; }
    BarraPlayer #rot-vol { width: 5; text-align: right; margin-right: 1; }
    """
    BINDINGS = [Binding("n", "app.proxima", "Próxima"), Binding("p", "app.anterior", "Anterior")]
    REPETIR = {"off": ("↻", "desligado"), "context": ("↻ lista", "contexto"), "track": ("↻ faixa", "faixa")}

    def compose(self) -> ComposeResult:
        with Horizontal(id="esq"):
            yield Capa(8, 4, id="mini")
            with Vertical(id="info"):
                yield Static("", id="titulo")
                yield Static("", id="artista")
                yield Button("♡ Curtir", id="curtir", compact=True)
        with Vertical(id="meio"):
            with Horizontal(classes="controles"):
                yield Button("⇄", id="aleatorio", compact=True, tooltip="Aleatório (s)")
                yield Button("|◀", id="anterior", compact=True, tooltip="Anterior (p)")
                yield Button(" ▶ ", id="play", compact=True, tooltip="Play/pausa (Espaço)")
                yield Button("▶|", id="proxima", compact=True, tooltip="Próxima (n)")
                yield Button("↻", id="repetir", compact=True, tooltip="Repetir (r)")
            with Horizontal(id="linha-prog"):
                yield Static("0:00", id="t-pos")
                yield Barra(id="progresso")
                yield Static("0:00", id="t-dur")
        with Vertical(id="dir"):
            with Horizontal(id="botoes-dir"):
                yield Button("Fila", id="fila", compact=True, tooltip="Fila (f)")
                yield Button("Painel", id="btn-painel", compact=True, tooltip="Painel Tocando agora (Ctrl+P)")
                yield Button("Dispositivos", id="disp", compact=True, tooltip="Dispositivos (d)")
            with Horizontal(id="linha-vol"):
                yield Static("Vol", id="rot-vol")
                yield Barra(id="volume")

    def focar_entrada(self) -> None:
        self.query_one("#play", Button).focus()

    def ajustar(self, largura: int) -> None:
        self.query_one("#mini").display = largura >= 100
        self.query_one("#btn-painel").display = largura >= 120

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        a = self.app
        {"curtir": a.action_curtir_tocando, "aleatorio": a.action_aleatorio, "anterior": a.action_anterior,
         "play": a.action_play_pause, "proxima": a.action_proxima, "repetir": a.action_repetir,
         "fila": lambda: a.navegar({"t": "fila"}), "btn-painel": a.action_painel,
         "disp": lambda: a.navegar({"t": "dispositivos"})}.get(ev.button.id or "", lambda: None)()

    @on(Barra.Passo)
    def _passo(self, ev: Barra.Passo) -> None:
        ev.stop()
        self.app.passo_barra(ev.barra.id, ev.direcao)

    @on(Barra.Clique)
    def _clique(self, ev: Barra.Clique) -> None:
        ev.stop()
        self.app.clique_barra(ev.barra.id, ev.fracao)

    def pintar(self, p, curtido: bool) -> None:
        q = self.query_one
        if p is None or p.item is None:
            q("#titulo", Static).update(Text("Nada tocando", style="bold"))
            q("#artista", Static).update(Text("Abra um dispositivo", style=self.app.cor("muted")))
            q("#t-dur", Static).update("0:00")
            q("#progresso", Barra).definir(0)
            q("#play", Button).label = " ▶ "
            return
        it = p.item
        q("#titulo", Static).update(Text(it.nome, style="bold", no_wrap=True, overflow="ellipsis"))
        q("#artista", Static).update(Text(it.sub, style=self.app.cor("muted"), no_wrap=True, overflow="ellipsis"))
        q("#mini", Capa).definir(it)
        q("#t-dur", Static).update(mmss(it.dur_ms))
        q("#curtir", Button).label = "♥ Curtida" if curtido else "♡ Curtir"
        q("#play", Button).label = " ▮▮ " if p.tocando else " ▶ "
        q("#aleatorio", Button).set_class(p.aleatorio, "ligado")
        txt, nome = self.REPETIR.get(p.repetir, ("↻", p.repetir))
        q("#repetir", Button).label = txt
        q("#repetir", Button).set_class(p.repetir != "off", "ligado")
        q("#repetir", Button).tooltip = f"Repetir: {nome} (r)"
        q("#disp", Button).label = (p.dispositivo[:16] if p.dispositivo else "Dispositivos")
        if p.volume is not None:
            q("#volume", Barra).definir(p.volume / 100)
            q("#rot-vol", Static).update(f"{p.volume}%")
        self.tick(p)

    def tick(self, p) -> None:
        if p is None or p.item is None:
            return
        pos = p.posicao()
        self.query_one("#t-pos", Static).update(mmss(pos))
        if p.item.dur_ms:
            self.query_one("#progresso", Barra).definir(pos / p.item.dur_ms)


class MenuConta(_Base):
    """Menu do botão de conta. Enter ou clique escolhe, Esc fecha."""

    DEFAULT_CSS = _css("MenuConta") + "MenuConta #caixa { width: 40; } MenuConta Button { width: 100%; margin-bottom: 0; }"
    ITENS = (("dispositivos", "Dispositivos"), ("fila", "Fila"), ("recentes", "Tocados recentemente"),
             ("top", "Mais ouvidos"), ("config", "Configurações"), ("verificar", "Verificar configuração"),
             ("sair", "Sair da conta"))

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa"):
            yield Label("Conta e menu", classes="titulo")
            for cid, rot in self.ITENS:
                yield Button(rot, id=f"m-{cid}")
            yield Button("Fechar", id="m-fechar")

    def on_mount(self) -> None:
        self.query_one("#m-dispositivos", Button).focus()

    def mover_secao(self, passo: int) -> None:
        self.focus_next() if passo > 0 else self.focus_previous()

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        self.dismiss((ev.button.id or "")[2:])

    def on_key(self, ev) -> None:
        if ev.key in ("down", "j"):
            self.focus_next()
            ev.stop()
        elif ev.key in ("up", "k"):
            self.focus_previous()
            ev.stop()
