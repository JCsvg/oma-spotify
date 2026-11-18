"""Aplicativo Textual do oma-spotify: janelas, navegação, reprodução e a sua fila."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import time
import webbrowser
from collections import OrderedDict
import queue
import threading
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Input

from oma_spotify import __version__, tema
from oma_spotify.config import MAX_FIXADOS, Config
from oma_spotify.estado import Estado
from oma_spotify.services.auth import Armazem
from oma_spotify.services.diagnostico import HOST_SPOTIFY
from oma_spotify.services.modelos import ErroSpotify, Item
from oma_spotify.services.plugin import DICA_CONFIGURAR, PluginOmaSpotify
from oma_spotify.ui import icones
from oma_spotify.ui.biblioteca import CURTIDAS, Biblioteca
from oma_spotify.ui.lista import Lista
from oma_spotify.ui.player import Player
from oma_spotify.ui.principal import Principal, item_de_dict, serializar, titulo_vista, vista_valida
from oma_spotify.ui.rodape import Divisa, Rodape
from oma_spotify.ui.tocando import FilaLetra, Tocando
from oma_spotify.ui.topo import Topo
from oma_spotify.ui.widgets import Cartao

JANELAS = ("topo", "bib", "principal", "tocando", "fila", "player")
DE_CIMA = ("bib", "principal", "tocando", "fila")
LARGO, MEDIO = 150, 110  # colunas
BAIXO = 30  # linhas
CONTEXTOS = ("album", "playlist", "artist", "show")
MAX_MINHA_FILA = 50


def abrir_spotify_do_pc() -> bool:
    """Roda o comando `spotify` (o app de desktop) solto do terminal."""
    exe = shutil.which("spotify")
    if not exe:
        return False
    try:
        subprocess.Popen([exe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except OSError:
        return False


def copiar_para_area(texto: str) -> bool:
    """wl-copy, se existir. False quando não deu para copiar de verdade."""
    exe = shutil.which("wl-copy")
    if not exe:
        return False
    try:
        subprocess.run([exe], input=texto.encode(), timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def link_de(i: Item) -> str:
    if i.tipo == "curtidas":
        return "https://open.spotify.com/collection/tracks"
    partes = i.uri.split(":")
    return f"https://open.spotify.com/{partes[1]}/{partes[-1]}" if len(partes) >= 3 else ""


class OmaSpotifyApp(App[None]):
    TITLE = "oma-spotify"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: $background; color: $foreground; }
    ModalScreen { background: $background 55%; }
    Input.-textual-compact { border: none; padding: 0 1; }
    Input > .input--placeholder { color: $oma-mudo; }
    .janela { border: solid $oma-linha; border-title-color: $oma-mudo; border-title-align: left;
              border-subtitle-color: $oma-mudo; border-subtitle-align: right; padding: 0 1; }
    .janela:focus-within { border: solid $accent; border-title-color: $accent; border-title-style: bold; }
    #topo { height: 1; background: $oma-escuro; }
    #corpo { height: 1fr; layers: base gaveta; }
    #bib { width: 34; }
    #principal { width: 1fr; }
    #direita { width: 41; }
    #tocando { height: auto; }
    #fila { height: 1fr; min-height: 8; }
    #player { height: 4; background: $oma-escuro; padding: 1 1 0 1; }
    #rodape { height: 1; }
    #bib.-gaveta { dock: left; layer: gaveta; width: 36; height: 100%; border: solid $accent; background: $background;
                   border-title-color: $accent; border-title-style: bold; border-subtitle-color: $oma-mudo; }
    #direita.-gaveta { dock: right; layer: gaveta; width: 43; height: 100%; background: $background; }
    Toast { background: $background; border: solid $oma-linha; padding: 0 1; width: auto; max-width: 60; margin-top: 0; }
    Toast.-information { border: solid $oma-linha; }
    Toast.-warning { border: solid $warning; }
    Toast.-error { border: solid $error; }
    Toast .toast--title { color: $accent; }
    ToastRack { margin-bottom: 6; }
    """
    BINDINGS = [
        Binding("ctrl+left,ctrl+h", "janela('esq')", show=False, priority=True),
        Binding("ctrl+right,ctrl+l", "janela('dir')", show=False, priority=True),
        Binding("ctrl+up,ctrl+k", "janela('cima')", show=False, priority=True),
        Binding("ctrl+down,ctrl+j", "janela('baixo')", show=False, priority=True),
        Binding("tab", "ciclo(1)", show=False, priority=True),
        Binding("shift+tab", "ciclo(-1)", show=False, priority=True),
        Binding("alt+left,alt+h", "alt_h(-1)", show=False, priority=True),
        Binding("alt+right,alt+l", "alt_h(1)", show=False, priority=True),
        Binding("alt+up,alt+k", "alt_v(-1)", show=False, priority=True),
        Binding("alt+down,alt+j", "alt_v(1)", show=False, priority=True),
        Binding("ctrl+p", "ir_para", show=False, priority=True),
        Binding("ctrl+@,ctrl+space,ctrl+at,f1", "teclas", show=False, priority=True),
        Binding("ctrl+f", "filtrar", show=False, priority=True),
        Binding("f5", "recarregar", show=False, priority=True),
        Binding("escape", "esc", show=False),
        Binding("shift+left", "seek(-5)", show=False),
        Binding("shift+right", "seek(5)", show=False),
        Binding("left,h", "mover(-1, 0)", show=False),
        Binding("right,l", "mover(1, 0)", show=False),
        Binding("up,k", "mover(0, -1)", show=False),
        Binding("down,j", "mover(0, 1)", show=False),
        Binding("space", "play_pause", show=False),
        Binding("comma", "anterior", show=False),
        Binding("full_stop", "proxima", show=False),
        Binding("minus", "volume(-5)", show=False),
        Binding("plus,equals_sign", "volume(5)", show=False),
        Binding("m", "mudo", show=False),
        Binding("s", "aleatorio", show=False),
        Binding("r", "repetir", show=False),
        Binding("slash", "buscar", show=False),
        Binding("d", "tocar_em", show=False),
        Binding("z", "zoom", show=False),
        Binding("left_square_bracket", "lado('bib')", show=False),
        Binding("right_square_bracket", "lado('dir')", show=False),
        Binding("question_mark", "ajuda", show=False),
        Binding("q", "quit", show=False),
        *[Binding(str(n), f"numero({n})", show=False) for n in range(10)],
        Binding("t", "item('tocar')", show=False),
        Binding("f", "item('seguir')", show=False),
        Binding("p", "item('playlist')", show=False),
        Binding("a", "item('artista')", show=False),
        Binding("y", "item('link')", show=False),
        Binding("o", "item('opcoes')", show=False),
        Binding("P,shift+p", "item('fixar')", show=False),
        Binding("x", "item('remover')", show=False),
        Binding("u", "item('desfazer')", show=False),
        Binding("c", "item('curtir')", show=False),
        Binding("n", "nova_playlist", show=False),
    ]

    def __init__(self, cliente=None, demo: bool = False, estado: Estado | None = None, config: Config | None = None,
                 armazem: Armazem | None = None, abertura: bool = True, abridor=None, lancador=None,
                 espera_dispositivo: float = 1.5, copiador=None, tempo_login: float = 180.0, tempo_ajuda: float = 15.0,
                 url_rede: str | None = None, plugin=None, letras=None) -> None:
        super().__init__()
        self.demo = demo
        self.estado = estado or Estado()
        self.config = config or Config()
        self.armazem = armazem or Armazem()
        if cliente is None and demo:
            from oma_spotify.services.falso import ClienteFalso
            cliente = ClienteFalso()
        self.cliente = cliente
        self.conectado = self.cliente is not None
        if demo and not self.config.fixados:
            from oma_spotify.services.falso import FIXADOS
            self.config.fixados = list(FIXADOS)
        icones.definir_modo(self.config.icones)
        self.com_abertura = abertura
        self.abridor_navegador = abridor or webbrowser.open
        self.lancador = lancador or abrir_spotify_do_pc
        self.espera_dispositivo = espera_dispositivo
        self.copiador = copiador or copiar_para_area
        self.tempo_login, self.tempo_ajuda = tempo_login, tempo_ajuda
        self.url_rede = url_rede or HOST_SPOTIFY
        self.plugin = plugin or PluginOmaSpotify()
        self._letras = letras
        self._exec = Trabalhadores(4)
        self._garantindo = False
        self._ultima_garantia = -100.0
        self.espera_max = 30.0
        self.paleta = tema.ler()
        self.pronto = False
        self.salvo: dict = {}
        self.focado = True  # o terminal está em foco (eventos de foco do terminal)
        # navegação
        self.historico: list[dict] = []
        self.pos = -1
        self.pref_bib = True
        self.pref_dir = True
        self.gaveta = ""  # "", "bib" ou "dir"
        self.zoom = ""  # "", "palco", "principal" ou "bib"
        self._ultimo_foco: dict[str, object] = {}
        self._ultima_cima = "principal"
        self._antes_da_busca = None
        self._busca_timer = None
        # reprodução
        self.player = None
        self.curtido = False
        self.fila_spotify: list[Item] = []
        self.minha_fila: list[Item] = []
        self._entregue = ""
        self._uri = ""
        self._buscando = False
        self._fila_em = 0.0
        self._poll_em = 0.0
        self._volume_antes = 0
        self.eq_quadro = 0
        self.letra = None
        self._letra_uri = ""
        # dados
        self.dados_bib: list[Item] = []
        self.total_curtidas = 0
        self.curtidas_cache: list[Item] = []
        self.dispositivos: list = []
        self.nome_usuario = ""
        self.pl_cache: OrderedDict[str, list[Item]] = OrderedDict()
        self._desfazer = None

    # ------------------------------------------------------------ montagem
    def compose(self) -> ComposeResult:
        yield Topo(id="topo")
        with Horizontal(id="corpo"):
            yield Biblioteca(id="bib")
            yield Divisa("bib", id="div-bib")
            yield Principal(id="principal", classes="janela")
            yield Divisa("dir", id="div-dir")
            with Vertical(id="direita"):
                yield Tocando(id="tocando", classes="janela")
                yield FilaLetra(id="fila", classes="janela")
        yield Player(id="player")
        yield Rodape(id="rodape")

    def get_css_variables(self) -> dict[str, str]:
        v = super().get_css_variables()
        paleta = getattr(self, "paleta", None) or tema.ler()
        v.update(tema.tema_textual("omarchy", paleta).variables)
        return v

    def on_mount(self) -> None:
        self.register_theme(tema.tema_textual("omarchy", self.paleta))
        self.theme = "omarchy"
        self.estado.carregar()
        self.salvo = dict(self.estado.dados)
        self.set_interval(0.5, self._tick)
        self.set_interval(2.0, self._poll)
        self.set_interval(15.0, self.carregar_dispositivos)
        self._eq_timer = self.set_interval(0.18, self._eq_tick, pause=True)
        self.call_after_refresh(self._iniciar)

    def _iniciar(self) -> None:
        s = self.salvo
        self.pref_bib = bool(s.get("pref_bib", True))
        self.pref_dir = bool(s.get("pref_dir", True))
        larg = s.get("larguras") if isinstance(s.get("larguras"), dict) else {}
        larg = {k: v for k, v in larg.items() if k in ("bib", "dir") and isinstance(v, int)}
        for chave, wid in (("bib", "#bib"), ("dir", "#direita")):
            if isinstance(larg.get(chave), int):
                self.query_one(wid).styles.width = max(24, min(60, larg[chave]))
        self._larguras = dict(larg)
        fila = s.get("minha_fila") if isinstance(s.get("minha_fila"), list) else []
        self.minha_fila = [i for i in (item_de_dict(d) for d in fila) if i and i.tipo in ("track", "episode")][:MAX_MINHA_FILA]
        try:
            self.query_one(Biblioteca).restaurar(s.get("bib", {}))
            self.query_one(FilaLetra).aba = "letra" if s.get("aba_fila") == "letra" else "fila"
        except Exception:
            pass
        self.ajustar()
        primeira = self.com_abertura and self.config.abertura and not self.estado.ja_abriu()
        self.pronto = True
        if primeira:
            from oma_spotify.ui.abertura import Abertura
            self.estado.marcar_abertura()
            self.push_screen(Abertura(f"{__version__}"), lambda _: self._apos_abertura())
        else:
            self._apos_abertura()

    def _apos_abertura(self) -> None:
        if not self.conectado:
            if self.config.client_id and self.armazem.logado():
                self.conectar()
            else:
                self.pedir_login("")
                return
        self._entrar_no_app()

    def _entrar_no_app(self) -> None:
        self.carregar_biblioteca()
        self.carregar_dispositivos()
        salvo_hist = self.salvo.get("hist") if isinstance(self.salvo.get("hist"), list) else []
        hist = [v for v in (vista_valida(x) for x in salvo_hist) if v]  # páginas antigas ou quebradas saem
        if hist and not self.historico:
            self.historico = hist[-30:]
            try:
                pos = int(self.salvo.get("pos", len(self.historico) - 1))
            except (TypeError, ValueError):
                pos = len(self.historico) - 1
            atual_valida = 0 <= pos < len(salvo_hist) and vista_valida(salvo_hist[pos]) is not None
            if len(hist) != len(salvo_hist):
                # a página aberta pode ter sumido (Dispositivos e Fila da 0.3.0): abre o início
                inicios = [n for n, v in enumerate(self.historico) if v["t"] == "inicio"]
                pos = len(self.historico) - 1 if atual_valida else (inicios[-1] if inicios else -1)
            if pos < 0:
                self.pos = len(self.historico) - 1
                self.navegar({"t": "inicio"}, foco=False)
            else:
                self.pos = max(0, min(pos, len(self.historico) - 1))
                self._mostrar_vista(self.historico[self.pos], foco=False)
        elif not self.historico:
            self.navegar({"t": "inicio"}, foco=False)
        self._poll(forcar=True)
        self.set_timer(0.3, self._foco_inicial)

    def _foco_inicial(self) -> None:
        if len(self.screen_stack) == 1 and self.nome_janela(self.focused) in ("", "topo") and not isinstance(self.focused, Input):
            self.focar_janela("principal")

    def cor(self, nome: str) -> str:
        p = self.paleta
        nome = {"success": "green", "warning": "yellow", "error": "red", "muted": "mudo"}.get(nome, nome)
        return p.get(nome, p["foreground"])

    def eq_texto(self) -> str:
        p = self.player
        return icones.EQ[self.eq_quadro % 4] if p is not None and p.tocando else icones.EQ_PARADO

    def tocando_uri(self, uri: str) -> bool:
        p = self.player
        if p is None or p.item is None or not uri:
            return False
        if uri == CURTIDAS.uri:
            return p.contexto.endswith(":collection")
        return p.item.uri == uri or p.contexto == uri

    # ------------------------------------------------------------ layout
    def on_resize(self, ev=None) -> None:
        if self.pronto:
            self.ajustar()

    def modo_largura(self) -> str:
        w = self.size.width
        return "largo" if w >= LARGO else "medio" if w >= MEDIO else "estreito"

    def ajustar(self) -> None:
        w, h = self.size
        modo = self.modo_largura()
        bib, direita = self.query_one(Biblioteca), self.query_one("#direita")
        principal = self.query_one(Principal)
        div_bib, div_dir = self.query_one("#div-bib"), self.query_one("#div-dir")
        if self.zoom == "palco":
            for x in (bib, direita, principal, div_bib, div_dir):
                x.display = False
        else:
            ver_bib = self.zoom in ("", "bib") and (self.gaveta == "bib" or (modo != "estreito" and self.pref_bib))
            ver_dir = self.zoom == "" and (self.gaveta == "dir" or (modo == "largo" and self.pref_dir))
            bib.display, direita.display = ver_bib, ver_dir
            principal.display = self.zoom != "bib"
            bib.set_class(self.gaveta == "bib", "-gaveta")
            direita.set_class(self.gaveta == "dir", "-gaveta")
            div_bib.display = ver_bib and self.gaveta != "bib" and principal.display
            div_dir.display = ver_dir and self.gaveta != "dir"
            larg = getattr(self, "_larguras", {})
            if self.gaveta != "bib":
                bib.styles.width = larg.get("bib", 34) if modo == "largo" else 30
            if self.zoom == "bib":
                bib.styles.width = "1fr"
        bib.border_title = "biblioteca" if self.gaveta == "bib" else ""
        bib.border_subtitle = "[" if self.gaveta == "bib" else ""
        corpo = h - 6 if h >= BAIXO else h - 3
        self.query_one(Tocando).ajustar(corpo, baixo=h < BAIXO)
        self.query_one(Player).ajustar(w, h)
        principal.ajustar(w)
        self.query_one(Topo).ajustar(w)
        self.query_one(Rodape).pintar()

    def action_lado(self, lado: str) -> None:
        """[ e ]: esconde ou mostra a Biblioteca e o Tocando; em tela estreita, abrem como gaveta."""
        if len(self.screen_stack) > 1:
            return
        if self.zoom:
            self.sair_zoom()
        modo = self.modo_largura()
        gaveta = (lado == "bib" and modo == "estreito") or (lado == "dir" and modo != "largo")
        if gaveta:
            if self.gaveta == lado:
                self.fechar_gaveta()
            else:
                self.gaveta = lado
                self.ajustar()
                self.call_after_refresh(self.focar_janela, "bib" if lado == "bib" else "tocando")
            return
        if lado == "bib":
            self.pref_bib = not self.pref_bib
            self.guardar("pref_bib", self.pref_bib)
        else:
            self.pref_dir = not self.pref_dir
            self.guardar("pref_dir", self.pref_dir)
        self.ajustar()
        if self.nome_janela(self.focused) in ("bib", "tocando", "fila") and not self.janela_visivel(self.nome_janela(self.focused)):
            self.focar_janela("principal")

    def fechar_gaveta(self) -> None:
        if self.gaveta:
            self.gaveta = ""
            self.ajustar()
            self.focar_janela("principal")

    def mudar_largura(self, lado: str, largura: int) -> None:
        """Arrastar a divisa entre as janelas."""
        largura = max(24, min(60, largura))
        self._larguras = {**getattr(self, "_larguras", {}), lado: largura}
        self.query_one("#bib" if lado == "bib" else "#direita").styles.width = largura
        self.guardar("larguras", self._larguras)

    def action_zoom(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if self.zoom:
            self.sair_zoom()
            return
        nome = self.nome_janela(self.focused)
        if nome in ("tocando", "fila"):
            self.abrir_palco()
        elif nome in ("principal", "bib"):
            self.gaveta = ""
            self.zoom = nome
            self.ajustar()

    def abrir_palco(self) -> None:
        from oma_spotify.ui.palco import Palco
        self.gaveta = ""
        self.zoom = "palco"
        self.ajustar()
        p = Palco(id="palco", classes="janela")
        self.query_one("#corpo").mount(p)  # o palco pega o foco quando termina de montar
        self.carregar_letra()
        self.atualizar_trilha()

    def sair_zoom(self) -> None:
        era = self.zoom
        self.zoom = ""
        for p in self.query("#palco"):
            p._pronto = False  # chamadas que chegarem durante a remoção são ignoradas
            p.remove()
        self.ajustar()
        self.atualizar_trilha()
        self.focar_janela("tocando" if era == "palco" and self.janela_visivel("tocando") else
                          era if era in ("bib", "principal") else "principal")

    # ------------------------------------------------------------ conta
    def nova_sessao(self):
        from oma_spotify.services.auth import Sessao
        return Sessao(self.config.client_id, self.config.porta, self.armazem)

    def conectar(self) -> None:
        from oma_spotify.services.api import ClienteSpotify
        self.cliente = ClienteSpotify(self.nova_sessao())
        self.conectado = True

    def pedir_login(self, motivo: str) -> None:
        from oma_spotify.ui.setup import TelaSetup
        if isinstance(self.screen, TelaSetup):
            return

        def fim(ok):
            if ok:
                self.conectar()
                self.notify("Conectado ao Spotify.")
                self._entrar_no_app()
        self.push_screen(TelaSetup(motivo), fim)

    def sair_da_conta(self) -> None:
        if self.demo:
            self.notify("Demonstração: não há conta para sair.")
            return
        self.armazem.apagar()
        self.cliente, self.conectado = None, False
        self.player = None
        self.pedir_login("Você saiu da conta.")

    def copiar(self, texto: str) -> bool:
        """Copia para a área de transferência. True só se foi com wl-copy (senão a tela mostra o texto)."""
        ok = self.copiador(texto)
        try:
            self.copy_to_clipboard(texto)
        except Exception:
            pass
        return ok

    def abrir_link(self, url: str) -> None:
        try:
            self.abridor_navegador(url)
        except Exception:
            pass
        self.notify("Abrindo no navegador. Se não abriu, o endereço é " + url, timeout=6)

    def abrir_menu_conta(self) -> None:
        from oma_spotify.ui.dialogos import Confirmar, MenuConta

        def fim(r):
            if r in ("recentes", "top", "config"):
                self.navegar({"t": r})
            elif r == "dispositivos":
                self.action_tocar_em()
            elif r == "verificar":
                self.navegar({"t": "config"})
                self.call_after_refresh(lambda: self.set_timer(0.2, self._verificar_config))
            elif r == "sair":
                self.push_screen(Confirmar("sair da conta?", ["Os tokens deste computador serão apagados.",
                                                              "Para voltar, é preciso entrar de novo."], "sair da conta"),
                                 lambda ok: self.sair_da_conta() if ok else None)
        self.push_screen(MenuConta(), fim)

    def _verificar_config(self) -> None:
        a = self.query_one(Principal).pagina
        if a is not None and hasattr(a, "action_verificar"):
            a.action_verificar()

    # ------------------------------------------------------------ estado
    def guardar(self, chave: str, valor) -> None:
        if self.pronto:
            self.estado.definir(chave, valor)

    def guardar_vista(self, pagina) -> None:
        if not self.pronto or not self.historico or self.pos < 0:
            return
        try:
            v = pagina.estado_()
        except Exception:
            return
        if v:
            self.historico[self.pos] = v
            self._salvar_hist()

    def guardar_minha_fila(self) -> None:
        self.guardar("minha_fila", [serializar(i) for i in self.minha_fila[:MAX_MINHA_FILA]])

    # ------------------------------------------------------------ histórico de páginas
    def navegar(self, vista: dict, foco: bool = True) -> None:
        if self.pos >= 0 and self.historico and _mesma(self.historico[self.pos], vista):
            self._mostrar_vista(vista, foco)
            return
        self.historico = (self.historico[: self.pos + 1] + [vista])[-30:]
        self.pos = len(self.historico) - 1
        self._mostrar_vista(vista, foco)
        self._salvar_hist()

    def substituir(self, vista: dict) -> None:
        """Troca a página atual sem criar entrada nova (busca ao vivo)."""
        if self.pos < 0:
            self.navegar(vista, foco=False)
            return
        self.historico[self.pos] = vista
        self._salvar_hist()
        self.atualizar_trilha()

    def _salvar_hist(self) -> None:
        self.guardar("hist", self.historico[-30:])
        self.guardar("pos", self.pos)

    def _mostrar_vista(self, vista: dict, foco: bool = True) -> None:
        if self.zoom == "palco":
            self.sair_zoom()
        self.query_one(Principal).mostrar(vista, foco)
        self.atualizar_trilha()

    def atualizar_trilha(self) -> None:
        if self.zoom == "palco":
            partes = [("tocando", -1), ("palco", -1)]
        else:
            ini = max(0, self.pos - 2)
            partes = [(titulo_vista(v, curto=True), n) for n, v in enumerate(self.historico[ini:self.pos + 1], ini)]
        try:
            self.query_one(Topo).pintar(partes, self.pos > 0, self.pos < len(self.historico) - 1)
        except Exception:
            pass

    def ir_historico(self, n: int) -> None:
        if 0 <= n < len(self.historico) and n != self.pos and len(self.screen_stack) == 1:
            self.pos = n
            self._mostrar_vista(self.historico[n])
            self._salvar_hist()

    def voltar_pagina(self) -> None:
        self.ir_historico(self.pos - 1)

    def avancar_pagina(self) -> None:
        self.ir_historico(self.pos + 1)

    # ------------------------------------------------------------ janelas e foco
    def janela(self, nome: str):
        return self.query_one(f"#{nome}")

    def nome_janela(self, w) -> str:
        while w is not None:
            i = getattr(w, "id", None)
            if i in JANELAS or i == "palco":
                return i
            w = w.parent
        return ""

    def janela_visivel(self, nome: str) -> bool:
        try:
            w = self.janela(nome)
        except Exception:
            return False
        while w is not None and w is not self.screen:
            if not w.display:
                return False
            w = w.parent
        return True

    def on_descendant_focus(self, ev) -> None:
        n = self.nome_janela(ev.widget)
        if not n:
            return
        self._ultimo_foco[n] = ev.widget
        if n in DE_CIMA:
            self._ultima_cima = n
        if self.gaveta and n not in (("bib",) if self.gaveta == "bib" else ("tocando", "fila")):
            self.gaveta = ""  # clicar fora fecha a gaveta
            self.call_after_refresh(self.ajustar)
        self.call_after_refresh(self._depois_do_foco)

    def _depois_do_foco(self) -> None:
        try:
            self.query_one(Player).marcar_foco(self.nome_janela(self.focused) == "player")
            self.query_one(Biblioteca).marcar_foco(self.nome_janela(self.focused) == "bib")
            self.query_one(Rodape).pintar()
        except Exception:
            pass

    def on_descendant_blur(self, ev) -> None:
        self.call_after_refresh(self._depois_do_foco)

    def focar_janela(self, nome: str) -> None:
        if nome == "palco":
            for p in self.query("#palco"):
                p.focar_entrada()
            return
        if not self.janela_visivel(nome):
            if nome == "bib" or (nome in ("tocando", "fila") and self.modo_largura() != "largo"):
                if self.modo_largura() == "estreito" or nome != "bib":
                    self.gaveta = "bib" if nome == "bib" else "dir"
                else:
                    self.pref_bib = True
                self.ajustar()
            elif nome in ("tocando", "fila") and not self.pref_dir:
                self.pref_dir = True
                self.ajustar()
            else:
                return
        w = self.janela(nome)
        ult = self._ultimo_foco.get(nome)
        if ult is not None and getattr(ult, "is_attached", False) and ult.focusable and self._dentro_visivel(ult):
            ult.focus()
        else:
            w.focar_entrada()

    def _dentro_visivel(self, w) -> bool:
        while w is not None and w is not self.screen:
            if not w.display:
                return False
            w = w.parent
        return True

    def visiveis(self) -> list[str]:
        if self.zoom == "palco":
            return ["topo", "palco", "player"]
        return [n for n in JANELAS if self.janela_visivel(n)]

    def _linha_cursor(self, w) -> int:
        f = self.focused
        if isinstance(f, Lista) and f.cursor >= 0:
            return f.region.y + f._y[f.cursor] - int(f.scroll_offset.y)
        if f is not None and f.region.area:
            return f.region.y
        r = w.region
        return r.y + r.height // 2

    def vizinha(self, atual: str, direcao: str) -> str:
        vis = self.visiveis()
        if atual not in vis:
            return "principal" if "principal" in vis else vis[0]
        if atual == "player" and direcao == "cima":
            return self._ultima_cima if self._ultima_cima in vis else ("palco" if "palco" in vis else "principal")
        if atual == "topo" and direcao == "baixo":
            return self._ultima_cima if self._ultima_cima in vis else ("palco" if "palco" in vis else "principal")
        if atual == "topo" and direcao in ("esq", "dir"):
            return ""
        r = self.janela(atual).region
        cy = self._linha_cursor(self.janela(atual))
        melhor, chave = "", None
        for n in vis:
            if n == atual:
                continue
            o = self.janela(n).region
            if not o.area:
                continue
            if direcao in ("esq", "dir"):
                if n in ("topo", "player"):
                    continue
                if (direcao == "dir" and o.x < r.right) or (direcao == "esq" and o.right > r.x):
                    continue
                cruza = o.y <= cy < o.bottom
                k = (0 if cruza else 1, abs((o.x if direcao == "dir" else r.x - o.right) - (r.right if direcao == "dir" else 0)),
                     abs(o.y + o.height / 2 - cy))
            else:
                if (direcao == "baixo" and o.y < r.bottom) or (direcao == "cima" and o.bottom > r.y):
                    continue
                sobrepoe = o.x < r.right and r.x < o.right
                k = (0 if sobrepoe else 1, abs(o.y - r.bottom) if direcao == "baixo" else abs(r.y - o.bottom), 0)
            if chave is None or k < chave:
                melhor, chave = n, k
        return melhor

    def action_janela(self, direcao: str) -> None:
        """Ctrl+setas e Ctrl+hjkl: vai para a janela que está naquele lado da tela."""
        if len(self.screen_stack) > 1:
            s = self.screen
            if hasattr(s, "mover_janela"):
                s.mover_janela(direcao)
            else:
                (s.focus_next if direcao in ("dir", "baixo") else s.focus_previous)()
            return
        f = self.focused
        if isinstance(f, Input) and direcao in ("esq", "dir") and self.nome_janela(f) == "topo":
            (f.action_cursor_left_word if direcao == "esq" else f.action_cursor_right_word)()
            return
        atual = self.nome_janela(f) or "principal"
        alvo = self.vizinha(atual, direcao)
        if alvo:
            self.focar_janela(alvo)

    def action_ciclo(self, passo: int) -> None:
        if len(self.screen_stack) > 1:
            (self.screen.focus_next if passo > 0 else self.screen.focus_previous)()
            return
        vis = self.visiveis()
        atual = self.nome_janela(self.focused)
        i = vis.index(atual) if atual in vis else -1
        self.focar_janela(vis[(i + passo) % len(vis)])

    def action_mover(self, dx: int, dy: int) -> None:
        """Setas e hjkl: andam pelos controles vizinhos da mesma janela, pela posição na tela."""
        f = self.focused
        if len(self.screen_stack) > 1:
            raiz = self.screen
        else:
            nome = self.nome_janela(f)
            if f is None or not nome:
                self.focar_janela("principal")
                return
            if nome == "topo" and dy > 0:
                self.focar_janela("principal")
                return
            raiz = self.janela(nome)
        if f is None:
            return
        cands = [w for w in raiz.query("*") if w is not f and w.focusable and w.can_focus and self._dentro_visivel(w)
                 and w.region.area > 0]
        fr = f.region
        cy = self._linha_cursor(f) if isinstance(f, Lista) else fr.y + fr.height / 2
        fcx = fr.x + fr.width / 2
        melhor, chave = None, None
        for w in cands:
            r = w.region
            cx, wcy = r.x + r.width / 2, r.y + r.height / 2
            if dx:
                sobrepoe = r.y <= cy < r.bottom or fr.y <= wcy < fr.bottom
                if not sobrepoe or (cx - fcx) * dx <= 0:
                    continue
                k = (abs(cx - fcx), abs(wcy - cy))
            else:
                if dy > 0 and r.y < fr.bottom or dy < 0 and r.bottom > fr.y:
                    continue
                k = (abs(r.y - fr.bottom) if dy > 0 else abs(fr.y - r.bottom), abs(cx - fcx))
            if chave is None or k < chave:
                melhor, chave = w, k
        if melhor is not None:
            melhor.focus()
            if isinstance(melhor, Lista) and dy:
                melhor.mover_cursor(melhor._proximo(-1, 1) if dy > 0 else melhor._proximo(len(melhor.itens), -1), avisar=False)

    def action_alt_h(self, passo: int) -> None:
        """Alt+←/→: troca o que a janela mostra (aba ou página)."""
        if len(self.screen_stack) > 1:
            return
        nome = self.nome_janela(self.focused) or "principal"
        if nome in ("principal", "topo"):
            self.voltar_pagina() if passo < 0 else self.avancar_pagina()
            return
        w = self.janela(nome) if nome != "palco" else self.query_one("#palco")
        if hasattr(w, "alt_horizontal"):
            w.alt_horizontal(passo)

    def action_alt_v(self, passo: int) -> None:
        """Alt+↑/↓: move o item selecionado (playlist sua, sua fila)."""
        if len(self.screen_stack) > 1:
            return
        nome = self.nome_janela(self.focused)
        w = self.query_one(Principal).pagina if nome == "principal" else self.janela(nome) if nome in JANELAS else None
        if w is not None and hasattr(w, "mover_item"):
            w.mover_item(passo)

    def _janela_que_trata(self):
        nome = self.nome_janela(self.focused)
        if nome == "principal":
            return self.query_one(Principal).pagina
        if nome == "palco":
            return self.query_one("#palco")
        return self.janela(nome) if nome in JANELAS else None

    # ------------------------------------------------------------ threads e chamadas à API
    def em_thread(self, func, depois) -> None:
        """Roda func no pool de threads; depois(resultado, erro) volta para a thread da interface."""
        def trabalho() -> None:
            r, erro = None, None
            try:
                r = func()
            except ErroSpotify as e:
                erro = e
            except Exception:
                erro = ErroSpotify("Algo deu errado ao falar com o Spotify. Tente de novo.")
            if not self.is_running:
                return  # o app fechou enquanto a chamada rodava
            try:
                self.call_from_thread(self._depois_seguro, depois, r, erro)
            except Exception:
                pass
        self._exec.submit(trabalho)

    def _no_palco(self, metodo: str) -> None:
        from textual.css.query import NoMatches
        for p in self.query("#palco"):
            try:
                getattr(p, metodo)()
            except NoMatches:
                pass  # o palco está saindo

    def _depois_seguro(self, depois, r, erro) -> None:
        """Um dado inesperado da API não derruba o app: vira aviso."""
        try:
            depois(r, erro)
        except Exception:
            self.notify("Algo veio diferente do esperado do Spotify; parte da tela pode ficar vazia.", severity="warning",
                        timeout=6)

    def executar(self, descricao: str, func, *args, ok: str = "", depois=None, recarregar: bool = True) -> None:
        def fim(_, erro) -> None:
            if erro is not None:
                if erro.sem_dispositivo:
                    self._sem_dispositivo(lambda: self.executar(descricao, func, *args, ok=ok, depois=depois, recarregar=recarregar))
                    return
                self.notify(f"{descricao}: {erro}", severity="error", timeout=8)
                if erro.sem_login:
                    self.pedir_login(str(erro))
            elif ok:
                self.notify(ok, timeout=4)
            if depois:
                depois(erro is None)
            if erro is None and recarregar:
                self._poll(forcar=True)
        self.em_thread(lambda: func(*args), fim)

    def _sem_dispositivo(self, repetir) -> None:
        """404 sem dispositivo ativo: tenta sozinho o alvo configurado, sem diálogo."""
        if time.monotonic() - self._ultima_garantia < 10:  # acabou de tentar: não entra em laço
            self.msg_player("Ainda sem dispositivo ativo. d mostra os aparelhos.", 10)
            return
        self.garantir(self.modo_tocar(), repetir)

    # ------------------------------------------------------------ onde tocar (plugin, PC ou escolha)
    def modo_tocar(self) -> str:
        m = self.config.tocar_por
        if m == "auto":
            return "plugin" if self.plugin.instalado() else "pc" if shutil.which("spotify") else "escolher"
        return m

    def msg_player(self, txt: str, segundos: float = 0) -> None:
        try:
            self.query_one(Player).mensagem(txt)
        except Exception:
            return
        self._msg_id = getattr(self, "_msg_id", 0) + 1
        n = self._msg_id
        if segundos:
            self.set_timer(segundos, lambda: self.msg_player("") if getattr(self, "_msg_id", 0) == n else None)

    def iniciar_plugin(self) -> None:
        self.garantir("plugin", None)

    def abrir_spotify_pc(self, depois=None) -> None:
        self.garantir("pc", depois)

    def garantir(self, modo: str, depois=None) -> None:
        """Acha ou inicia o dispositivo do alvo, transfere a reprodução para ele e repete a ação pedida."""
        if self._garantindo or not self.conectado:
            return
        if modo == "escolher":
            self.action_tocar_em()
            self.msg_player("Escolha onde tocar.", 10)
            return
        self._garantindo = True
        self._ultima_garantia = time.monotonic()
        c = self.cliente
        plugin = modo == "plugin"

        def alvo(ds):
            return next((d for d in ds if (self.plugin.eh_dispositivo(d) if plugin else d.tipo.lower() == "computer")), None)

        def status(txt):
            self.call_from_thread(self.msg_player, txt)

        def preparar():
            d = alvo(c.dispositivos())
            if d is None:
                if plugin:
                    if not self.plugin.instalado():
                        raise ErroSpotify("Plugin OmaSpotify não encontrado. Instale-o ou mude em Configurações (tocar por).")
                    status("Iniciando o player do OmaSpotify...")
                    if not self.plugin.ativo() and not self.plugin.iniciar():
                        raise ErroSpotify("Não consegui iniciar o OmaSpotify. " + DICA_CONFIGURAR)
                else:
                    if not self.lancador():
                        raise ErroSpotify("Comando spotify não encontrado. Instale o Spotify do PC ou mude em Configurações (tocar por).")
                    status("Abrindo o Spotify do PC...")
                for _ in range(max(1, int(self.espera_max / max(self.espera_dispositivo, 0.01)))):
                    time.sleep(self.espera_dispositivo)
                    d = alvo(c.dispositivos())
                    if d:
                        break
                else:
                    raise ErroSpotify(("O player do OmaSpotify não apareceu. " + DICA_CONFIGURAR) if plugin
                                      else "O Spotify do PC não apareceu. Entre nele com a mesma conta.")
            c.transferir(d.id, False)
            return d

        def fim(d, erro):
            self._garantindo = False
            if erro:
                self.msg_player(str(erro), 15)
                self.notify(str(erro), severity="warning", timeout=10)
                return
            self.msg_player(f"Tocando por {d.nome}", 4)
            self.carregar_dispositivos()
            if depois:
                depois()
            else:
                self._poll(forcar=True)
        self.msg_player("Procurando o player..." if not plugin else "Procurando o player do OmaSpotify...")
        self.em_thread(preparar, fim)

    # ------------------------------------------------------------ biblioteca e dispositivos
    def carregar_biblioteca(self) -> None:
        if not self.conectado:
            return
        c = self.cliente

        def trabalho():
            saida = []
            for f in (c.playlists, c.albuns_salvos, c.artistas_seguidos, c.podcasts):
                try:
                    saida += f()
                except ErroSpotify as e:
                    if e.sem_login:
                        raise
            try:
                curt = c.curtidas()
            except ErroSpotify:
                curt = []
            try:
                nome = c.nome_usuario() if hasattr(c, "nome_usuario") else ""
            except ErroSpotify:
                nome = ""
            return saida, curt, nome

        def depois(r, erro):
            if erro:
                if erro.sem_login:
                    self.pedir_login(str(erro))
                return
            self.dados_bib, self.curtidas_cache, self.nome_usuario = r
            self.total_curtidas = len(self.curtidas_cache)
            self.query_one(Biblioteca).definir(self.dados_bib, self.total_curtidas)
            self.query_one(Topo).pintar_conta(self.nome_usuario)
            self.query_one(Principal).dados_mudaram()
        self.em_thread(trabalho, depois)

    def carregar_dispositivos(self, depois=None) -> None:
        if not self.conectado or (len(self.screen_stack) > 1 and depois is None):
            return

        def fim(r, erro):
            if erro is None:
                self.dispositivos = r or []
                try:
                    self.query_one(Biblioteca).pintar_dispositivos(self.dispositivos)
                except Exception:
                    pass
            if depois:
                depois(self.dispositivos)
        self.em_thread(self.cliente.dispositivos, fim)

    def fixados(self) -> list[Item]:
        por_uri = {i.uri: i for i in self.dados_bib}
        return [por_uri[u] for u in self.config.fixados if u in por_uri]

    def salvar_config(self) -> None:
        if not self.demo:
            self.config.salvar()

    def itens_da_playlist(self, pid: str):
        """Faixas de uma playlist sua, com cache pequeno (LRU de 24) para "já tem" e para a página do artista."""
        if pid in self.pl_cache:
            self.pl_cache.move_to_end(pid)
            return self.pl_cache[pid]
        itens = self.cliente.itens_playlist(pid)
        self.pl_cache[pid] = itens
        while len(self.pl_cache) > 24:
            self.pl_cache.popitem(last=False)
        return itens

    def esquecer_playlist(self, pid: str) -> None:
        self.pl_cache.pop(pid, None)

    # ------------------------------------------------------------ player
    def on_app_focus(self, ev: events.AppFocus) -> None:
        self.focado = True
        self._eq_ligar()
        self._poll(forcar=True)

    def on_app_blur(self, ev: events.AppBlur) -> None:
        self.focado = False
        self._eq_ligar()

    def _poll(self, forcar: bool = False) -> None:
        if not self.conectado or self._buscando:
            return
        agora = time.monotonic()
        if not forcar:
            # em segundo plano (terminal sem foco ou diálogo aberto) consulta a cada 10 s
            if (not self.focado or len(self.screen_stack) > 1) and agora - self._poll_em < 10:
                return
        self._poll_em = agora
        self._buscando = True
        c = self.cliente

        def trabalho():
            p = c.player()
            fila = curtido = None
            nova = bool(p and p.item and p.item.uri != self._uri)
            if nova or time.monotonic() - self._fila_em > 15:
                try:
                    fila = c.fila()
                except ErroSpotify:
                    fila = None
            if nova and p.item.tipo == "track":
                try:
                    curtido = c.curtido([p.item.uri])[0]
                except (ErroSpotify, IndexError):
                    curtido = None
            return p, fila, curtido

        def depois(r, erro):
            self._buscando = False
            if erro:
                if erro.sem_login:
                    self.pedir_login(str(erro))
                return
            p, fila, curtido = r
            mudou = (p.item.uri if p and p.item else "") != self._uri
            tocava = self.player.tocando if self.player else None
            self.player = p
            if curtido is not None:
                self.curtido = curtido
            self._uri = p.item.uri if p and p.item else ""
            if fila is not None:
                self._fila_em = time.monotonic()
                self.fila_spotify = fila
            if mudou:
                self._faixa_mudou()
            self._pintar(fila is not None or mudou)
            if mudou or tocava != (p.tocando if p else None):
                self._eq_ligar()
        self.em_thread(trabalho, depois)

    def _faixa_mudou(self) -> None:
        if self.minha_fila and self._entregue and self._uri == self._entregue:
            self.minha_fila.pop(0)
            self._entregue = ""
            self.guardar_minha_fila()
        self.letra, self._letra_uri = None, ""
        if self.precisa_letra():
            self.carregar_letra()
        self.query_one(Principal).tocando_mudou()
        self.query_one(Biblioteca).tocando_mudou()

    def _pintar(self, com_fila: bool = False) -> None:
        self.query_one(Player).pintar(self.player, self.curtido)
        self.query_one(Tocando).pintar(self.player, self.curtido)
        if com_fila:
            self.query_one(FilaLetra).pintar_fila()
            self._no_palco("pintar")

    def _tick(self) -> None:
        if self.player is None or not self.pronto:
            return
        try:
            self.query_one(Player).tick(self.player)
            self.query_one(FilaLetra).tick()
            self._no_palco("tick")
        except Exception:
            pass
        self._entregar_se_preciso()

    def _eq_visivel(self) -> bool:
        return self.player is not None and self.player.tocando and self.focado

    def _eq_ligar(self) -> None:
        t = getattr(self, "_eq_timer", None)
        if t is None:
            return
        if self._eq_visivel():
            t.resume()
        else:
            t.pause()
            self._eq_tick(parado=True)

    def _eq_tick(self, parado: bool = False) -> None:
        if not parado:
            self.eq_quadro += 1
        try:
            self.query_one(Player).pintar_eq()
            if self.janela_visivel("bib"):
                self.query_one(Biblioteca).pintar_eq()
            if self.janela_visivel("principal"):
                self.query_one(Principal).pintar_eq()
        except Exception:
            pass

    def _precisa_player(self) -> bool:
        return self.conectado and not isinstance(self.focused, Input) and len(self.screen_stack) == 1

    def action_play_pause(self) -> None:
        if not self._precisa_player():
            return
        c = self.cliente
        if self.player is not None:
            self.player.tocando = not self.player.tocando
            self.player.progresso_ms, self.player.marca = self.player.posicao(), time.monotonic()
            self._pintar()
            self._eq_ligar()

        def alternar():
            p = c.player()
            (c.pausar if p and p.tocando else c.retomar)()
        self.executar("Tocar ou pausar", alternar)

    def action_proxima(self) -> None:
        if not self._precisa_player():
            return
        c = self.cliente
        head = self.minha_fila[0] if self.minha_fila and not self._entregue else None

        def pular():
            if head is not None:
                c.enfileirar(head.uri)
            c.proxima()
        if head is not None:
            self._entregue = head.uri
        self.executar("Próxima", pular)

    def action_anterior(self) -> None:
        if self._precisa_player():
            self.executar("Anterior", self.cliente.anterior)

    def action_aleatorio(self) -> None:
        if self._precisa_player() and self.player:
            novo = not self.player.aleatorio
            self.player.aleatorio = novo
            self._pintar()
            self.executar("Aleatório", self.cliente.aleatorio, novo, ok="aleatório ligado" if novo else "aleatório desligado")

    def action_repetir(self) -> None:
        if self._precisa_player() and self.player:
            ordem = ["off", "context", "track"]
            novo = ordem[(ordem.index(self.player.repetir) + 1) % 3 if self.player.repetir in ordem else 0]
            self.player.repetir = novo
            self._pintar()
            self.executar("Repetir", self.cliente.repetir, novo,
                          ok={"off": "repetir desligado", "context": "repetir: a lista toda", "track": "repetir: só esta faixa"}[novo])

    def action_volume(self, passo: int) -> None:
        if self._precisa_player() and self.player and self.player.volume is not None:
            self.player.volume = max(0, min(100, self.player.volume + passo))
            self.executar("Volume", self.cliente.volume, self.player.volume, recarregar=False)
            self._pintar()

    def action_mudo(self) -> None:
        if not self._precisa_player() or not self.player or self.player.volume is None:
            return
        if self.player.volume > 0:
            self._volume_antes = self.player.volume
            self.player.volume = 0
        else:
            self.player.volume = self._volume_antes or 50
        self.executar("Mudo", self.cliente.volume, self.player.volume, recarregar=False)
        self._pintar()

    def action_seek(self, segundos: int) -> None:
        if self._precisa_player():
            self.passo_barra("progresso", 1 if segundos > 0 else -1)

    def passo_barra(self, barra: str, direcao: int) -> None:
        if barra == "volume":
            self.action_volume(5 * direcao)
        elif self.player and self.player.item:
            self._buscar(max(0, min(self.player.item.dur_ms, self.player.posicao() + 5000 * direcao)))

    def clique_barra(self, barra: str, fracao: float) -> None:
        if barra == "volume":
            if self.player:
                self.player.volume = round(fracao * 100)
                self.executar("Volume", self.cliente.volume, self.player.volume, recarregar=False)
                self._pintar()
        elif self.player and self.player.item:
            self._buscar(int(fracao * self.player.item.dur_ms))

    def _buscar(self, ms: int) -> None:
        self.player.progresso_ms, self.player.marca = ms, time.monotonic()
        self.executar("Buscar posição", self.cliente.buscar_posicao, ms)
        self._tick()

    def pular_para(self, ms: int) -> None:
        if self.player and self.player.item and ms >= 0:
            self._buscar(ms)

    # ------------------------------------------------------------ tocar
    def tocar_item(self, item: Item, contexto: str = "", uris: list[str] | None = None) -> None:
        c = self.cliente
        if item.tipo == "curtidas":
            uris_c = [i.uri for i in self.curtidas_cache]
            if uris_c:
                self.tocar_uris(uris_c)
            return
        if item.tipo in CONTEXTOS:
            func = lambda: c.tocar(contexto=item.uri)  # noqa: E731
        elif contexto:
            func = lambda: c.tocar(contexto=contexto, desde=item.uri)  # noqa: E731
        elif uris and item.uri in uris:
            fila = uris[uris.index(item.uri):][:100]
            func = lambda: c.tocar(uris=fila, desde=item.uri)  # noqa: E731
        else:
            func = lambda: c.tocar(uris=[item.uri])  # noqa: E731
        self.executar(f"Tocar {item.nome}", func, ok=f"{icones.ic('tocar')} {item.nome}")

    def tocar_uris(self, uris: list[str], desde: str | None = None, aleatorio: bool = False) -> None:
        c = self.cliente
        if not uris:
            return

        def tocar():
            if aleatorio:
                c.aleatorio(True)
            c.tocar(uris=uris[:100], desde=desde)
        self.executar("Tocar", tocar, ok="tocando")

    def tocar_contexto_aleatorio(self, item: Item) -> None:
        c = self.cliente

        def tocar():
            c.aleatorio(True)
            c.tocar(contexto=item.uri)
        self.executar("Tocar em aleatório", tocar, ok=f"{icones.ic('aleatorio')} {item.nome}")

    def transferir(self, d, depois=None) -> None:
        self.executar(f"Tocar em {d.nome}", self.cliente.transferir, d.id, ok=f"tocando em {d.nome}",
                      depois=lambda ok: (self.carregar_dispositivos(), depois(ok) if depois else None))

    # ------------------------------------------------------------ a sua fila (do app)
    def a_seguir(self, itens: list[Item]) -> None:
        faixas = [i for i in itens if i.tipo in ("track", "episode")]
        if not faixas:
            self.notify("Só faixas e episódios vão para a fila.", timeout=4)
            return
        self.minha_fila.extend(faixas)
        del self.minha_fila[MAX_MINHA_FILA:]
        self.guardar_minha_fila()
        self.query_one(FilaLetra).pintar_fila()
        nome = faixas[0].nome if len(faixas) == 1 else f"{len(faixas)} faixas"
        self.notify(f"{icones.ic('a_seguir')} {nome} entrou na sua fila" if len(faixas) == 1 else f"{icones.ic('a_seguir')} {nome} entraram na sua fila",
                    timeout=4)

    def _entregar_se_preciso(self) -> None:
        """Entrega a primeira da sua fila ao Spotify quando a faixa atual está acabando."""
        p = self.player
        if not self.minha_fila or self._entregue or p is None or p.item is None or not p.tocando:
            return
        if p.item.dur_ms and p.item.dur_ms - p.posicao() < 12_000:
            head = self.minha_fila[0]
            self._entregue = head.uri
            self.executar("Fila", self.cliente.enfileirar, head.uri, recarregar=False)

    def tirar_da_minha_fila(self, indices: list[int]) -> None:
        tirados = [(i, self.minha_fila[i]) for i in sorted(indices) if 0 <= i < len(self.minha_fila)]
        if not tirados:
            return
        for i, _ in reversed(tirados):
            if i == 0 and self._entregue:
                continue  # já foi entregue ao Spotify: não dá para tirar de lá
            del self.minha_fila[i]
        self.guardar_minha_fila()
        self.query_one(FilaLetra).pintar_fila()

        def desfazer():
            for i, it in tirados:
                if it not in self.minha_fila:
                    self.minha_fila.insert(min(i, len(self.minha_fila)), it)
            self.guardar_minha_fila()
            self.query_one(FilaLetra).pintar_fila()
        self.avisar(f"{icones.ic('remover')} {tirados[0][1].nome if len(tirados) == 1 else f'{len(tirados)} faixas'} saiu da sua fila",
                    desfazer)

    def mover_na_minha_fila(self, indices: list[int], passo: int) -> list[int]:
        idx = sorted(i for i in indices if 0 <= i < len(self.minha_fila))
        if not idx:
            return indices
        travada = 1 if self._entregue else 0
        if (passo < 0 and idx[0] - 1 < travada) or (passo > 0 and idx[-1] + 1 >= len(self.minha_fila)):
            return idx
        bloco = [self.minha_fila[i] for i in idx]
        for i in reversed(idx):
            del self.minha_fila[i]
        novo0 = idx[0] + passo
        self.minha_fila[novo0:novo0] = bloco
        self.guardar_minha_fila()
        novos = list(range(novo0, novo0 + len(bloco)))
        self._desfazer = lambda: (self.mover_na_minha_fila(novos, -passo), self.query_one(FilaLetra).pintar_fila())
        return novos

    # ------------------------------------------------------------ ações sobre itens (t f p a y o P x u c)
    def itens_foco(self) -> list[Item]:
        f = self.focused
        if isinstance(f, Lista):
            return [i for i in f.itens_marcados() if isinstance(i, Item)]
        if isinstance(f, Cartao):
            return [f.item]
        if self.nome_janela(f) in ("tocando", "player", "palco") and self.player and self.player.item:
            return [self.player.item]
        return []

    def action_item(self, acao: str) -> None:
        if len(self.screen_stack) > 1 or isinstance(self.focused, Input):
            return
        if acao == "desfazer":
            self.desfazer()
            return
        itens = self.itens_foco()
        janela = self._janela_que_trata()
        if janela is not None and hasattr(janela, "tratar") and janela.tratar(acao, itens):
            return
        if not itens:
            if acao == "curtir" and self.player and self.player.item:
                itens = [self.player.item]
            else:
                return
        self.fazer(acao, itens)

    def fazer(self, acao: str, itens: list[Item], origem=None) -> None:
        """Ação padrão sobre itens, usada pelas teclas e pelo menu de opções."""
        if not itens:
            return
        i = itens[0]
        if acao == "tocar":
            if i.tipo in CONTEXTOS or i.tipo == "curtidas":
                self.tocar_item(i)
            else:
                self.tocar_uris([x.uri for x in itens if x.tipo in ("track", "episode")])
        elif acao == "abrir":
            if i.tipo in CONTEXTOS or i.tipo == "curtidas":
                self.abrir_item(i)
            else:
                self.tocar_item(i)
        elif acao == "seguir":
            self.a_seguir(itens)
        elif acao == "playlist":
            self.adicionar_a_playlist(itens)
        elif acao == "artista":
            self.ir_artista(i)
        elif acao == "album":
            self.ir_album(i)
        elif acao == "link":
            self.copiar_link(i)
        elif acao == "opcoes":
            self.opcoes(itens, origem)
        elif acao == "fixar":
            self.fixar(i)
        elif acao == "remover":
            if i.tipo in CONTEXTOS:
                self.remover_da_biblioteca(i)
        elif acao == "curtir":
            self.curtir_itens(itens)

    def avisar(self, msg: str, desfazer=None, severidade: str = "information") -> None:
        if desfazer is not None:
            self._desfazer = desfazer
            self.notify(f"{msg} · u desfaz", timeout=8, severity=severidade)
        else:
            self.notify(msg, timeout=4, severity=severidade)

    def desfazer(self) -> None:
        f, self._desfazer = self._desfazer, None
        if f is None:
            self.notify("Nada para desfazer.", timeout=3)
            return
        f()

    def curtir_itens(self, itens: list[Item]) -> None:
        if not itens:
            return
        c = self.cliente
        tocando = self.player.item.uri if self.player and self.player.item else ""
        if len(itens) == 1 and itens[0].uri == tocando:
            ja = self.curtido
        else:
            try:
                ja = all(c.curtido([i.uri for i in itens[:40]]))
            except ErroSpotify:
                ja = False
        uris = [i.uri for i in itens if i.tipo != "curtidas"]
        if tocando in uris:
            self.curtido = not ja
            self._pintar()

        def fazer():
            for u in uris:
                (c.descurtir if ja else c.curtir)(u)

        def depois(ok):
            if ok:
                self.query_one(Principal).curtidas_mudaram(uris, not ja)
                if any(i.tipo in CONTEXTOS for i in itens):
                    self.carregar_biblioteca()
        rot = itens[0].nome if len(itens) == 1 else f"{len(itens)} itens"
        self.executar("Curtir", fazer, ok=f"{icones.ic('nao_curtida')} {rot} descurtida" if ja else f"{icones.ic('curtida')} {rot} curtida",
                      depois=depois, recarregar=False)

    def abrir_item(self, item: Item) -> None:
        if item.tipo == "curtidas":
            self.navegar({"t": "curtidas"})
        else:
            self.navegar({"t": "item", "item": serializar(item)})

    def _achar(self, q: str, tipo: str, nome: str, depois) -> None:
        def busca():
            r = self.cliente.buscar(q, [tipo], 0, 5).get(tipo, [])
            exato = [x for x in r if x.nome.lower() == nome.lower()]
            return (exato or r or [None])[0]

        def fim(r, erro):
            if r is None:
                self.notify(f"Não achei {nome} no Spotify.", timeout=4)
            else:
                depois(r)
        self.em_thread(busca, fim)

    def ir_artista(self, i: Item) -> None:
        if i.tipo == "artist":
            self.abrir_item(i)
            return
        nome = (i.sub if i.tipo in ("track", "album") else "").split(",")[0].strip()
        if not nome:
            return
        alvo = next((x for x in self.dados_bib if x.tipo == "artist" and x.nome == nome), None)
        if alvo is not None:
            self.abrir_item(alvo)
        else:
            self._achar(nome, "artist", nome, self.abrir_item)

    def ir_album(self, i: Item) -> None:
        if i.tipo == "album":
            self.abrir_item(i)
            return
        if i.tipo != "track" or not i.extra:
            return
        alvo = next((x for x in self.dados_bib if x.tipo == "album" and x.nome == i.extra), None)
        if alvo is not None:
            self.abrir_item(alvo)
        else:
            self._achar(f'album:"{i.extra}" artist:"{i.sub.split(",")[0]}"', "album", i.extra, self.abrir_item)

    def copiar_link(self, i: Item) -> None:
        url = link_de(i)
        if not url:
            return
        if self.copiar(url):
            self.notify(f"{icones.ic('link')} link copiado: {url}", timeout=4)
        else:
            self.notify(f"Link: {url}", timeout=8)

    def fixar(self, i: Item) -> None:
        if i.tipo not in CONTEXTOS:
            self.notify("Só playlists, álbuns, artistas e podcasts da biblioteca são fixados.", timeout=4)
            return
        fx = self.config.fixados
        if i.uri in fx:
            fx.remove(i.uri)
            msg = f"{i.nome} desafixado"
        elif len(fx) >= MAX_FIXADOS:
            self.notify("Já há 9 fixados. Desafixe um antes (P nele).", timeout=5)
            return
        else:
            if i.uri not in {x.uri for x in self.dados_bib}:
                self.notify("Salve na biblioteca antes de fixar (c).", timeout=4)
                return
            fx.append(i.uri)
            msg = f"{i.nome} fixado no {len(fx)}"
        self.salvar_config()
        self.query_one(Biblioteca).reconstruir()
        self.notify(msg, timeout=4)

    def remover_da_biblioteca(self, i: Item) -> None:
        from oma_spotify.ui.dialogos import Confirmar
        if i.uri not in {x.uri for x in self.dados_bib}:
            return
        c = self.cliente

        def fim(ok):
            if ok:
                self.executar("Remover da biblioteca", c.descurtir, i.uri, ok=f"{i.nome} saiu da biblioteca",
                              depois=lambda s: self.carregar_biblioteca(), recarregar=False)
        self.push_screen(Confirmar(f"remover {i.nome}?", ["Sai da sua biblioteca. No Spotify, continua existindo."],
                                   "remover"), fim)

    # ------------------------------------------------------------ diálogos
    def opcoes(self, itens: list[Item], origem=None) -> None:
        from oma_spotify.ui.dialogos import Opcoes
        if not itens:
            return
        if origem is None:
            origem = self._janela_que_trata()
        extra = origem.opcoes_extra(itens) if origem is not None and hasattr(origem, "opcoes_extra") else []

        def fim(acao):
            if not acao:
                return
            if origem is not None and hasattr(origem, "tratar") and origem.tratar(acao, itens):
                return
            self.fazer(acao, itens, origem)
        self.push_screen(Opcoes(itens, self.config.fixados, extra), fim)

    def action_ir_para(self) -> None:
        from oma_spotify.ui.dialogos import IrPara
        if len(self.screen_stack) > 1:
            if isinstance(self.screen, IrPara):
                self.screen.dismiss(None)
            return
        self.push_screen(IrPara(), self._ir_para_fim)

    def _ir_para_fim(self, r) -> None:
        if not r:
            return
        tipo, valor, tocar = r
        if tipo == "item":
            (self.tocar_item if tocar else self.abrir_item)(valor)
            if not tocar:
                self.focar_janela("principal")
        elif tipo == "pagina":
            self.navegar(valor)
        elif tipo == "comando":
            self.call_later(self.run_action, valor)
        elif tipo == "buscar":
            self.query_one(Topo).definir_busca(valor)
            self.navegar({"t": "busca", "q": valor, "cat": "tudo"})

    def action_tocar_em(self) -> None:
        from oma_spotify.ui.dialogos import TocarEm
        if len(self.screen_stack) > 1 or not self.conectado:
            return
        self.push_screen(TocarEm())

    def action_teclas(self) -> None:
        from oma_spotify.ui.dialogos import Teclas
        if len(self.screen_stack) > 1:
            if isinstance(self.screen, Teclas):
                self.screen.dismiss(None)
            return
        nome = self.nome_janela(self.focused) or "principal"
        self.push_screen(Teclas(nome, self._janela_que_trata()))

    def action_ajuda(self) -> None:
        from oma_spotify.ui.dialogos import AjudaCompleta
        if len(self.screen_stack) == 1:
            self.push_screen(AjudaCompleta())

    def adicionar_a_playlist(self, itens: list[Item]) -> None:
        from oma_spotify.ui.dialogos import AdicionarPlaylist
        faixas = [i for i in itens if i.tipo in ("track", "episode")]
        if not faixas:
            self.notify("Selecione faixas para adicionar a uma playlist.", timeout=4)
            return
        minhas = [p for p in self.dados_bib if p.tipo == "playlist" and (p.meu or p.colab)]

        def fim(r):
            if not r:
                return
            if r == "nova":
                self.nova_playlist(faixas)
                return
            pl = next((p for p in minhas if p.id == r), None)
            if pl is None:
                return
            c = self.cliente

            def add():
                for f in faixas:
                    c.adicionar_a_playlist(pl.id, f.uri)
            self.esquecer_playlist(pl.id)
            self.executar("Adicionar à playlist", add, ok=f"{icones.ic('adicionar')} {len(faixas) if len(faixas) > 1 else faixas[0].nome} em {pl.nome}",
                          depois=lambda ok: self.query_one(Principal).playlist_mudou(pl.id), recarregar=False)
        self.push_screen(AdicionarPlaylist(faixas, minhas), fim)

    def action_nova_playlist_global(self) -> None:
        self.nova_playlist()

    def action_enter(self) -> None:
        """Enter clicável no rodapé: aperta o que está em foco."""
        f = self.focused
        if isinstance(f, Lista):
            f.action_escolher()
        elif hasattr(f, "action_abrir"):
            f.action_abrir()
        elif hasattr(f, "press"):
            f.press()

    def action_nova_playlist(self) -> None:
        if len(self.screen_stack) == 1 and self.nome_janela(self.focused) == "bib":
            self.nova_playlist()

    def nova_playlist(self, faixas: list[Item] | None = None) -> None:
        from oma_spotify.ui.dialogos import Pedir

        def fim(nome):
            if not nome:
                return
            c = self.cliente

            def criar():
                p = c.criar_playlist(nome)
                for f in faixas or []:
                    c.adicionar_a_playlist(p.id, f.uri)
                return p
            self.executar("Criar playlist", criar, ok=f"playlist criada: {nome}", depois=lambda ok: self.carregar_biblioteca(),
                          recarregar=False)
        self.push_screen(Pedir("nova playlist", "", "Dê um nome. Ela nasce privada."), fim)

    # ------------------------------------------------------------ teclas globais
    def action_buscar(self) -> None:
        if len(self.screen_stack) == 1 and not isinstance(self.focused, Input):
            self._antes_da_busca = self.focused
            if self.zoom:
                self.sair_zoom()
            self.call_after_refresh(self.query_one(Topo).focar_entrada)

    def buscar_ao_vivo(self, q: str) -> None:
        """Busca enquanto digita, depois de 300 ms sem tecla."""
        if self._busca_timer is not None:
            self._busca_timer.stop()
        self._busca_timer = self.set_timer(0.3, lambda: self._buscar_agora(q.strip()))

    def _buscar_agora(self, q: str) -> None:
        self._busca_timer = None
        self.guardar("busca", q)
        if not q:
            return
        principal = self.query_one(Principal)
        vista = {"t": "busca", "q": q, "cat": principal.vista.get("cat", "tudo") if principal.vista.get("t") == "busca" else "tudo"}
        if principal.vista.get("t") == "busca":
            principal.pagina.nova_busca(q)
            self.substituir(vista)
        else:
            self.navegar(vista, foco=False)

    def voltar_da_busca(self) -> None:
        alvo = self._antes_da_busca
        self._antes_da_busca = None
        if alvo is not None and getattr(alvo, "is_attached", False) and self._dentro_visivel(alvo) and self.nome_janela(alvo) != "topo":
            alvo.focus()
        else:
            self.focar_janela("principal")

    def action_esc(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if self.gaveta:
            self.fechar_gaveta()
            return
        if self.zoom:
            self.sair_zoom()
            return
        f = self.focused
        if isinstance(f, Lista) and f.limpar_marcas():
            return
        j = self._janela_que_trata()
        if j is not None and hasattr(j, "esc") and j.esc():
            return

    def action_filtrar(self) -> None:
        if len(self.screen_stack) > 1:
            return
        j = self._janela_que_trata()
        if j is not None and hasattr(j, "filtrar"):
            j.filtrar()
        elif self.nome_janela(self.focused) == "topo":
            pass
        else:
            pg = self.query_one(Principal).pagina
            if pg is not None and hasattr(pg, "filtrar"):
                pg.filtrar()

    def action_recarregar(self) -> None:
        if len(self.screen_stack) > 1:
            return
        self.pl_cache.clear()
        self.carregar_biblioteca()
        self.carregar_dispositivos()
        self.query_one(Principal).recarregar()
        self._poll(forcar=True)
        self.notify("recarregando", timeout=2)

    def action_numero(self, n: int) -> None:
        if len(self.screen_stack) > 1 or isinstance(self.focused, Input):
            return
        if n == 0:
            self.abrir_item(CURTIDAS)
        else:
            fx = self.fixados()
            if n > len(fx):
                self.notify(f"Nada fixado no {n}. P fixa o item selecionado na biblioteca.", timeout=4)
                return
            self.abrir_item(fx[n - 1])
        self.focar_janela("principal")

    def check_action(self, action: str, parameters):
        if len(self.screen_stack) > 1 and action in ("play_pause", "proxima", "anterior", "aleatorio", "repetir", "volume",
                                                       "mudo", "seek", "buscar", "zoom", "lado", "numero", "item",
                                                       "nova_playlist", "tocar_em", "filtrar", "recarregar", "ajuda",
                                                       "alt_h", "alt_v"):
            return False
        return True

    # ------------------------------------------------------------ letra
    def precisa_letra(self) -> bool:
        return bool(self.query("#palco")) or (self.query_one(FilaLetra).aba == "letra" and self.janela_visivel("fila"))

    def carregar_letra(self) -> None:
        p = self.player
        if p is None or p.item is None:
            return
        it = p.item
        if self._letra_uri == it.uri and self.letra is not None:
            return
        from oma_spotify.services.letras import Letra
        if not self.config.letra:
            self.letra, self._letra_uri = Letra(motivo="letra desligada nas configurações"), it.uri
            self._pintar_letra()
            return
        if it.tipo != "track":
            self.letra, self._letra_uri = Letra(motivo="episódio não tem letra"), it.uri
            self._pintar_letra()
            return
        if self._letras is None:
            if self.demo:
                from oma_spotify.services.falso import LETRAS
                from oma_spotify.services.letras import LetrasFalsas
                self._letras = LetrasFalsas(LETRAS)
            else:
                from oma_spotify.services.letras import Letras
                self._letras = Letras()
        self._letra_uri = it.uri
        self.letra = None
        prov = self._letras

        def fim(r, erro):
            if self._letra_uri != it.uri:
                return
            self.letra = r if erro is None else Letra(motivo="não consegui buscar a letra")
            self._pintar_letra()
        self.em_thread(lambda: prov.buscar(it.uri, it.nome, it.sub, it.extra, it.dur_ms), fim)
        self._pintar_letra()

    def _pintar_letra(self) -> None:
        self.query_one(FilaLetra).pintar_letra()
        self._no_palco("pintar_letra")

    # ------------------------------------------------------------ saída
    async def action_quit(self) -> None:
        self.estado.salvar()
        self._exec.parar()
        self.exit()


class Trabalhadores:
    """Pool pequeno de threads daemon para as chamadas à API (não seguram o fim do processo)."""

    def __init__(self, n: int = 4) -> None:
        self.n = n
        self.fila: queue.SimpleQueue = queue.SimpleQueue()
        self.threads: list[threading.Thread] = []

    def submit(self, f) -> None:
        if len(self.threads) < self.n:
            t = threading.Thread(target=self._laco, name=f"oma-{len(self.threads)}", daemon=True)
            self.threads.append(t)
            t.start()
        self.fila.put(f)

    def _laco(self) -> None:
        while True:
            f = self.fila.get()
            if f is None:
                return
            try:
                f()
            except Exception:
                pass

    def parar(self) -> None:
        for _ in self.threads:
            self.fila.put(None)


def _mesma(a: dict, b: dict) -> bool:
    ka = {k: v for k, v in a.items() if k not in ("linha", "per", "cat")}
    kb = {k: v for k, v in b.items() if k not in ("linha", "per", "cat")}
    return ka == kb


def main() -> None:
    p = argparse.ArgumentParser(prog="oma-spotify", description="Cliente de Spotify em TUI (precisa de Premium)")
    p.add_argument("--demo", action="store_true", help="usa dados fictícios, sem login e sem rede")
    p.add_argument("--version", action="version", version=f"oma-spotify {__version__}")
    a = p.parse_args()
    if a.demo:
        # demo não mexe na configuração nem no contexto reais
        from oma_spotify.estado import pasta_padrao
        pasta = pasta_padrao()
        OmaSpotifyApp(demo=True, estado=Estado(pasta.with_name(pasta.name + "-demo")),
                      config=Config(Path(tempfile.mkdtemp(prefix="oma-spotify-demo-")))).run()
    else:
        OmaSpotifyApp().run()


if __name__ == "__main__":
    main()
