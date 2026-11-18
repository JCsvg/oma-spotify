"""Janelas [1] Busca e [5] Player, e o menu da conta."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

from oma_spotify.services.modelos import mmss
from oma_spotify.ui.dialogos import _Base, _css
from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import Barra


class BarraTopo(NavegacaoMixin, Horizontal):
    NOME = "Busca"
    RODAPE = ("app.buscar", "botao_acionar")
    DEFAULT_CSS = """
    BarraTopo { height: 3; padding: 0 1; }
    BarraTopo Button { margin-right: 1; }
    BarraTopo #busca { width: 1fr; }
    BarraTopo #conta { margin-left: 1; margin-right: 0; }
    """
    BINDINGS = [Binding("slash", "app.buscar", "Buscar", key_display="/")]

    def compose(self) -> ComposeResult:
        yield Button("⌂ Início", id="inicio", compact=True, tooltip="Início (i)")
        yield Button("◀", id="voltar", compact=True, tooltip="Voltar (Esc)")
        yield Button("▶", id="avancar", compact=True, tooltip="Avançar (Alt+])")
        yield Input(placeholder="O que você quer ouvir?  ( / )", id="busca", compact=True)
        yield Button("Conta ▾", id="conta", compact=True, tooltip="Dispositivos, configurações, sair")

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


class BarraPlayer(NavegacaoMixin, Vertical):
    NOME = "Player"
    RODAPE = ("play_pause", "proxima", "anterior", "curtir_tocando")
    DEFAULT_CSS = """
    BarraPlayer { height: 5; padding: 0 1; }
    BarraPlayer #linha-info, BarraPlayer #linha-ctrl, BarraPlayer #linha-prog { height: 1; }
    BarraPlayer #titulo { width: 1fr; text-wrap: nowrap; text-overflow: ellipsis; }
    BarraPlayer #msg { width: auto; color: $warning; text-style: bold; }
    BarraPlayer #linha-ctrl Button { margin-right: 1; }
    BarraPlayer #play { text-style: bold; background: $accent; color: $background; }
    BarraPlayer .ligado { color: $accent; text-style: bold; }
    BarraPlayer #espaco { width: 1fr; }
    BarraPlayer #volume { width: 12; }
    BarraPlayer #rot-vol { width: 5; text-align: right; margin-left: 1; }
    BarraPlayer #t-pos, BarraPlayer #t-dur { width: 6; }
    BarraPlayer #t-pos { text-align: right; margin-right: 1; }
    BarraPlayer #t-dur { margin-left: 1; }
    """
    BINDINGS = [Binding("n", "app.proxima", "Próxima"), Binding("p", "app.anterior", "Anterior")]
    REPETIR = {"off": ("↻", "desligado"), "context": ("↻ lista", "contexto"), "track": ("↻ faixa", "faixa")}

    def compose(self) -> ComposeResult:
        with Horizontal(id="linha-info"):
            yield Static("", id="titulo")
            yield Static("", id="msg")
        with Horizontal(id="linha-ctrl"):
            yield Button("⇄", id="aleatorio", compact=True, tooltip="Aleatório (s)")
            yield Button("|◀", id="anterior", compact=True, tooltip="Anterior (p)")
            yield Button(" ▶ ", id="play", compact=True, tooltip="Play/pausa (Espaço)")
            yield Button("▶|", id="proxima", compact=True, tooltip="Próxima (n)")
            yield Button("↻", id="repetir", compact=True, tooltip="Repetir (r)")
            yield Button("♡", id="curtir", compact=True, tooltip="Curtir (c)")
            yield Static("", id="espaco")
            yield Button("Fila", id="fila", compact=True, tooltip="Fila (f)")
            yield Button("Dispositivos", id="disp", compact=True, tooltip="Dispositivos (d)")
            yield Button("−", id="vol-menos", compact=True, tooltip="Volume - (-)")
            vol = Barra(id="volume")
            vol.can_focus = False
            yield vol
            yield Button("+", id="vol-mais", compact=True, tooltip="Volume + (+)")
            yield Static("", id="rot-vol")
        with Horizontal(id="linha-prog"):
            yield Static("0:00", id="t-pos")
            yield Barra(id="progresso")
            yield Static("0:00", id="t-dur")

    def focar_entrada(self) -> None:
        self.query_one("#play", Button).focus()

    def ajustar(self, largura: int) -> None:
        self.query_one("#volume").display = largura >= 100
        self.query_one("#rot-vol").display = largura >= 100

    def mensagem(self, txt: str) -> None:
        self.query_one("#msg", Static).update(Text(txt) if txt else "")

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        a = self.app
        {"curtir": a.action_curtir_tocando, "aleatorio": a.action_aleatorio, "anterior": a.action_anterior,
         "play": a.action_play_pause, "proxima": a.action_proxima, "repetir": a.action_repetir,
         "fila": lambda: a.navegar({"t": "fila"}), "disp": lambda: a.navegar({"t": "dispositivos"}),
         "vol-menos": lambda: a.action_volume(-5), "vol-mais": lambda: a.action_volume(5)}.get(ev.button.id or "", lambda: None)()

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
        q("#curtir", Button).label = "♥" if curtido else "♡"
        q("#curtir", Button).set_class(curtido, "ligado")
        if p is None or p.item is None:
            q("#titulo", Static).update(Text("Nada tocando", style="bold"))
            q("#t-dur", Static).update("0:00")
            q("#progresso", Barra).definir(0)
            q("#play", Button).label = " ▶ "
            return
        it = p.item
        q("#titulo", Static).update(Text.assemble((it.nome, "bold"), (f"  {it.sub}" if it.sub else "", self.app.cor("muted"))))
        q("#t-dur", Static).update(mmss(it.dur_ms))
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
