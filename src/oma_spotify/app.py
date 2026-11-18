"""Aplicativo Textual do oma-spotify."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import threading
import time
import webbrowser

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Input

from oma_spotify import __version__, tema
from oma_spotify.config import Config
from oma_spotify.estado import Estado
from oma_spotify.services.api import ClienteSpotify
from oma_spotify.services.auth import Armazem, Sessao
from oma_spotify.services.diagnostico import HOST_SPOTIFY
from oma_spotify.services.falso import ClienteFalso
from oma_spotify.services.modelos import ErroSpotify, Item
from oma_spotify.ui.abertura import Abertura
from oma_spotify.ui.barras import BarraPlayer, BarraTopo, MenuConta
from oma_spotify.ui.biblioteca import CURTIDAS, Biblioteca
from oma_spotify.ui.capa import Capas
from oma_spotify.ui.central import CONTEXTOS, AreaCentral, VistaInicio, VistaLista, item_de_dict, serializar
from oma_spotify.ui.dialogos import EscolherPlaylist, Pedir, SemDispositivo
from oma_spotify.ui.navegacao import AjudaAba, RodapeEnxuto, eh_controle
from oma_spotify.ui.painel import PainelAgora
from oma_spotify.ui.setup import TelaSetup
from oma_spotify.ui.widgets import Barra, Tabela

AREAS = ("topo", "bib", "centro", "painel", "player")
LARGURA_PAINEL, LARGURA_BIB = 120, 100


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


class OmaSpotifyApp(App[None]):
    TITLE = "OMA SPOTIFY"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: $background; color: $foreground; }
    Button { min-width: 0; }
    #corpo { height: 1fr; }
    #bib, #painel { height: 1fr; }
    #centro { height: 1fr; }
    DataTable { height: 1fr; background: $surface; }
    DataTable > .datatable--cursor { background: $accent 28%; color: $foreground; text-style: bold; }
    DataTable:focus > .datatable--cursor { background: $accent 40%; color: $foreground; text-style: bold; }
    OptionList { border: none; padding: 0; }
    OptionList > .option-list--option-highlighted { background: $accent 28%; }
    OptionList:focus > .option-list--option-highlighted { background: $accent 40%; text-style: bold; }
    #resumo, #diag-config { height: auto; margin: 1 0; }
    #acoes-config Button { margin-bottom: 1; }
    #titulo-setup { text-style: bold; color: $accent; margin: 0 1 1 1; }
    #setup { padding: 1 2; }
    #passos, #espera { height: auto; }
    #setup .passo { margin-top: 1; }
    #setup .linha { height: 3; }
    #setup .linha Button { margin-right: 1; }
    #redirect { background: $surface; padding: 0 1; color: $accent; text-style: bold; }
    #status, #motivo, #link, #diag, #contagem { height: auto; }
    #contagem { text-style: bold; color: $accent; margin: 1 0; }
    #ajuda-texto { background: $surface; padding: 0 1; margin-top: 1; height: auto; }
    #status, #motivo { color: $warning; margin-top: 1; }
    """
    BINDINGS = [
        Binding("q", "quit", "Sair"),
        Binding("alt+left,alt+h", "area(-1, 0)", "Área à esquerda", key_display="Alt+←", priority=True),
        Binding("alt+right,alt+l", "area(1, 0)", "Área à direita", key_display="Alt+→", priority=True),
        Binding("alt+up,alt+k", "area(0, -1)", "Área acima", key_display="Alt+↑", priority=True),
        Binding("alt+down,alt+j", "area(0, 1)", "Área abaixo", key_display="Alt+↓", priority=True),
        Binding("alt+left_square_bracket", "voltar_historico", "Voltar", key_display="Alt+[", priority=True),
        Binding("alt+right_square_bracket", "avancar_historico", "Avançar", key_display="Alt+]", priority=True),
        Binding("left,h", "mover(-1, 0)", show=False),
        Binding("right,l", "mover(1, 0)", show=False),
        Binding("up,k", "mover(0, -1)", show=False),
        Binding("down,j", "mover(0, 1)", show=False),
        Binding("escape,backspace", "voltar", "Voltar", show=False),
        Binding("space", "play_pause", "Play/Pausa", key_display="Espaço"),
        Binding("n", "proxima", "Próxima"),
        Binding("p", "anterior", "Anterior"),
        Binding("s", "aleatorio", "Aleatório"),
        Binding("r", "repetir", "Repetir"),
        Binding("plus,equals_sign", "volume(5)", "Volume +", show=False),
        Binding("minus", "volume(-5)", "Volume -", show=False),
        Binding("c", "curtir_tocando", "Curtir"),
        Binding("f", "ir('fila')", "Fila", show=False),
        Binding("d", "ir('dispositivos')", "Dispositivos", show=False),
        Binding("i", "ir('inicio')", "Início", show=False),
        Binding("slash", "buscar", "Buscar", key_display="/"),
        Binding("ctrl+p", "painel", "Painel", priority=True),
        Binding("ctrl+b", "coluna", "Biblioteca", priority=True),
        Binding("ctrl+right,ctrl+l", "botao(1)", "Próximo botão", key_display="Ctrl+→", priority=True),
        Binding("ctrl+left,ctrl+h", "botao(-1)", "Botão anterior", key_display="Ctrl+←", priority=True),
        Binding("ctrl+down,ctrl+j", "secao(1)", "Próxima seção", key_display="Ctrl+↓", priority=True),
        Binding("ctrl+up,ctrl+k", "secao(-1)", "Seção anterior", key_display="Ctrl+↑", priority=True),
        Binding("ctrl+@,ctrl+space,ctrl+at,f1", "ajuda_aba", "Ajuda", key_display="Ctrl+Espaço", priority=True),
        Binding("ctrl+enter", "botao_acionar", "Apertar botão", key_display="Ctrl+Enter", priority=True),
    ]

    def __init__(self, cliente=None, demo: bool = False, estado: Estado | None = None, config: Config | None = None,
                 armazem: Armazem | None = None, abertura: bool = True, abridor=None, lancador=None,
                 espera_dispositivo: float = 1.5, copiador=None, tempo_login: float = 180.0, tempo_ajuda: float = 15.0,
                 url_rede: str | None = None, capas: Capas | None = None) -> None:
        super().__init__()
        self.demo = demo
        self.estado = estado or Estado()
        self.config = config or Config()
        self.armazem = armazem or Armazem()
        self.cliente = cliente or (ClienteFalso() if demo else None)
        self.conectado = self.cliente is not None
        self.com_abertura = abertura
        self.abridor_navegador = abridor or webbrowser.open
        self.lancador = lancador or abrir_spotify_do_pc
        self.espera_dispositivo = espera_dispositivo
        self.copiador = copiador or copiar_para_area
        self.tempo_login, self.tempo_ajuda = tempo_login, tempo_ajuda
        self.url_rede = url_rede or HOST_SPOTIFY
        self.capas = capas or Capas(demo, chamar=lambda f, *a: self.call_from_thread(f, *a))
        self.paleta = tema.ler()
        self.pronto = False
        self.salvo: dict = {}
        # navegação
        self.historico: list[dict] = []
        self.pos = -1
        self.painel_pref = True
        self.coluna_pref = False
        self.ultimo: dict = {}
        # reprodução
        self.player = None
        self.curtido = False
        self.fila_atual: list = []
        self._uri = ""
        self._buscando = False
        self._fila_em = 0.0
        # dados
        self.dados_bib: list[Item] = []

    # ------------------------------------------------------------ montagem
    def compose(self) -> ComposeResult:
        yield BarraTopo(id="topo")
        with Horizontal(id="corpo"):
            yield Biblioteca(id="bib")
            yield AreaCentral(id="centro")
            yield PainelAgora(id="painel")
        yield BarraPlayer(id="player")
        yield RodapeEnxuto()

    def on_mount(self) -> None:
        self.register_theme(tema.tema_textual("omarchy"))
        self.theme = "omarchy"
        self.estado.carregar()
        self.salvo = dict(self.estado.dados)
        self.set_interval(0.25, self._tick)
        self.set_interval(2.0, self._poll)
        self.call_after_refresh(self._iniciar)

    def _iniciar(self) -> None:
        s = self.salvo
        self.painel_pref = bool(s.get("painel", True))
        self.coluna_pref = bool(s.get("coluna", False))
        try:
            self.query_one(Biblioteca).restaurar(s.get("bib", {}))
            if isinstance(s.get("busca"), str):
                self.query_one("#busca", Input).value = s["busca"]
        except Exception:
            pass
        self.ajustar()
        primeira = self.com_abertura and self.config.abertura and not self.estado.ja_abriu()
        self.pronto = True
        if primeira:
            self.estado.marcar_abertura()
            self.push_screen(Abertura(f"v{__version__}"), lambda _: self._apos_abertura())
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
        hist = [v for v in self.salvo.get("hist", []) if isinstance(v, dict) and "t" in v]
        if hist and not self.historico:
            self.historico = hist[-30:]
            self.pos = min(int(self.salvo.get("pos", len(self.historico) - 1)), len(self.historico) - 1)
            self._mostrar_vista(self.historico[self.pos], foco=False)
        elif not self.historico:
            self.navegar({"t": "inicio"}, foco=False)
        self._poll(forcar=True)
        self.set_timer(0.3, self._foco_inicial)

    def _foco_inicial(self) -> None:
        """O foco automático do Textual cai na barra superior; leva para o centro se ninguém mexeu."""
        if len(self.screen_stack) == 1 and self.nome_area(self.focused) in ("", "topo") and not isinstance(self.focused, Input):
            self.focar_area("centro")

    def cor(self, nome: str) -> str:
        p = self.paleta
        return {"success": p["green"], "warning": p["yellow"], "error": p["red"], "accent": p["accent"],
                "muted": p.get("dark_foreground", p["muted"])}.get(nome, p["foreground"])

    def miniatura_curtidas(self):
        return self.query_one(Biblioteca).miniatura_curtidas()

    # ------------------------------------------------------------ layout
    def on_resize(self, ev=None) -> None:
        if self.pronto:
            self.ajustar()

    def ajustar(self) -> None:
        w, h = self.size
        painel = self.query_one(PainelAgora)
        bib = self.query_one(Biblioteca)
        painel.display = self.painel_pref and w >= LARGURA_PAINEL
        bib.alternar_recolhida(self.coluna_pref or w < LARGURA_BIB) if bib.recolhida != (self.coluna_pref or w < LARGURA_BIB) else None
        bib.styles.width = 10 if bib.recolhida else (34 if w >= 150 else 30)
        painel.styles.width = 38 if w >= 150 else 34
        painel.ajustar(h)
        self.query_one(BarraPlayer).ajustar(w)

    def action_painel(self) -> None:
        if self.size.width < LARGURA_PAINEL:
            self.notify(f"O terminal precisa de ao menos {LARGURA_PAINEL} colunas para o painel Tocando agora.")
            return
        self.painel_pref = not self.painel_pref
        self.guardar("painel", self.painel_pref)
        self.ajustar()
        if not self.painel_pref and self.nome_area(self.focused) == "painel":
            self.focar_area("centro")

    def action_coluna(self) -> None:
        self.coluna_pref = not self.coluna_pref
        self.guardar("coluna", self.coluna_pref)
        self.ajustar()

    # ------------------------------------------------------------ conta
    def nova_sessao(self) -> Sessao:
        return Sessao(self.config.client_id, self.config.porta, self.armazem)

    def conectar(self) -> None:
        self.cliente = ClienteSpotify(self.nova_sessao())
        self.conectado = True

    def pedir_login(self, motivo: str) -> None:
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
        def fim(r):
            if r in ("dispositivos", "fila", "recentes", "top", "config"):
                self.navegar({"t": r})
            elif r == "verificar":
                self.navegar({"t": "config"})
                self.call_after_refresh(lambda: self.set_timer(0.2, self._verificar_config))
            elif r == "sair":
                from oma_spotify.ui.dialogos import Confirmar
                self.push_screen(Confirmar("Sair da conta?", ["Os tokens deste computador serão apagados.",
                                                              "Para voltar, é preciso entrar de novo."], "Sair da conta"),
                                 lambda ok: self.sair_da_conta() if ok else None)
        self.push_screen(MenuConta(), fim)

    def _verificar_config(self) -> None:
        a = self.query_one(AreaCentral).atual
        if a is not None and hasattr(a, "action_verificar"):
            a.action_verificar()

    # ------------------------------------------------------------ estado
    def guardar(self, chave: str, valor) -> None:
        if self.pronto:
            self.estado.definir(chave, valor)

    def guardar_vista(self, view) -> None:
        if not self.pronto or not self.historico or self.pos < 0:
            return
        try:
            v = view.estado_()
        except Exception:
            return
        self.historico[self.pos] = v
        self.estado.definir("hist", self.historico[-30:])
        self.estado.definir("pos", min(self.pos, 29) if len(self.historico) <= 30 else self.pos - (len(self.historico) - 30))

    # ------------------------------------------------------------ navegação por histórico
    def navegar(self, vista: dict, foco: bool = True) -> None:
        if self.pos >= 0 and self.historico and _mesma(self.historico[self.pos], vista):
            self._mostrar_vista(vista, foco)
            return
        self.historico = self.historico[: self.pos + 1] + [vista]
        self.pos = len(self.historico) - 1
        self._mostrar_vista(vista, foco)
        self._salvar_hist()

    def _salvar_hist(self) -> None:
        self.guardar("hist", self.historico[-30:])
        self.guardar("pos", self.pos - max(0, len(self.historico) - 30))

    def _mostrar_vista(self, vista: dict, foco: bool = True) -> None:
        self.query_one(AreaCentral).mostrar(vista, foco)
        self._botoes_historico()

    def _botoes_historico(self) -> None:
        try:
            self.query_one("#voltar", Button).disabled = self.pos <= 0
            self.query_one("#avancar", Button).disabled = self.pos >= len(self.historico) - 1
        except Exception:
            pass

    def action_voltar_historico(self) -> None:
        if len(self.screen_stack) == 1 and self.pos > 0:
            self.pos -= 1
            self._mostrar_vista(self.historico[self.pos])
            self._salvar_hist()

    def action_avancar_historico(self) -> None:
        if len(self.screen_stack) == 1 and self.pos < len(self.historico) - 1:
            self.pos += 1
            self._mostrar_vista(self.historico[self.pos])
            self._salvar_hist()

    def action_voltar(self) -> None:
        if len(self.screen_stack) > 1:
            return
        if isinstance(self.focused, Input):
            self.focar_area("centro")
        else:
            self.action_voltar_historico()

    def action_ir(self, destino: str) -> None:
        if len(self.screen_stack) == 1:
            self.navegar({"t": destino})

    def abrir_item(self, item: Item) -> None:
        if item.tipo == "curtidas":
            self.navegar({"t": "curtidas"})
        else:
            self.navegar({"t": "item", "item": serializar(item)})

    def action_buscar(self) -> None:
        if len(self.screen_stack) == 1:
            self.call_after_refresh(self.query_one("#busca", Input).focus)

    # ------------------------------------------------------------ áreas, foco e setas
    def nome_area(self, w) -> str:
        while w is not None:
            if getattr(w, "id", None) in AREAS and w.parent is not None and w.parent.id in ("corpo", None, "_default"):
                return w.id
            w = w.parent
        return ""

    def _area_widget(self, nome: str):
        return self.query_one(f"#{nome}")

    def on_descendant_focus(self, ev) -> None:
        n = self.nome_area(ev.widget)
        if n:
            self.ultimo[n] = ev.widget

    def focar_area(self, nome: str) -> None:
        w = self._area_widget(nome)
        if not w.display:
            return
        ult = self.ultimo.get(nome)
        if ult is not None and ult.is_attached and ult.focusable and ult.display:
            ult.focus()
        else:
            w.focar_entrada()

    def action_area(self, dx: int, dy: int) -> None:
        if len(self.screen_stack) > 1:
            return
        atual = self.nome_area(self.focused) or "centro"
        meio = [n for n in ("bib", "centro", "painel") if self._area_widget(n).display]
        if dy < 0:
            dest = "topo" if atual in meio or atual == "player" and False else ("centro" if atual == "player" else "topo")
        elif dy > 0:
            dest = "centro" if atual == "topo" else "player"
        else:
            if atual not in meio:
                return
            i = max(0, min(len(meio) - 1, meio.index(atual) + dx))
            dest = meio[i]
        self.focar_area(dest)

    def nav_da_aba(self):
        if len(self.screen_stack) > 1:
            s = self.screen
            return s if hasattr(s, "mover_secao") else None
        n = self.nome_area(self.focused) or "centro"
        return self._area_widget(n)

    def check_action(self, action: str, parameters):
        if action == "ajuda_aba":
            return self.nav_da_aba() is not None or isinstance(self.screen, AjudaAba)
        if len(self.screen_stack) > 1 and not isinstance(self.screen, AjudaAba) and action in (
                "area", "voltar_historico", "avancar_historico", "painel", "coluna", "ir", "buscar", "play_pause", "proxima",
                "anterior", "aleatorio", "repetir", "volume", "curtir_tocando"):
            return False
        return True

    def action_mover(self, dx: int, dy: int) -> None:
        """Setas e hjkl: andam pelos controles vizinhos da mesma área, por posição na tela."""
        f = self.focused
        raiz = self.screen if len(self.screen_stack) > 1 else None
        if f is None:
            if raiz is None:
                self.focar_area("centro")
            return
        if raiz is None:
            raiz = self._area_widget(self.nome_area(f) or "centro")
        cands = [w for w in raiz.query("*") if w is not f and eh_controle(w) and w.display and w.region.area > 0]
        fr = f.region
        fcx, fcy = fr.x + fr.width / 2, fr.y + fr.height / 2
        melhor, chave = None, None
        for w in cands:
            r = w.region
            cx, cy = r.x + r.width / 2, r.y + r.height / 2
            sobrepoe = fr.y < r.bottom and r.y < fr.bottom
            if dx:
                if not sobrepoe or (cx - fcx) * dx <= 0:
                    continue
                k = (abs(cx - fcx), 0)
            else:
                if sobrepoe or (cy - fcy) * dy <= 0:
                    continue
                k = (abs(cy - fcy), abs(cx - fcx))
            if chave is None or k < chave:
                melhor, chave = w, k
        if melhor is not None:
            melhor.focus()

    def action_secao(self, passo: int) -> None:
        nav = self.nav_da_aba()
        if nav is not None:
            nav.mover_secao(passo)

    def action_ajuda_aba(self) -> None:
        if len(self.screen_stack) > 1 and isinstance(self.screen, AjudaAba):
            self.screen.dismiss(None)
            return
        nav = self.nav_da_aba()
        if nav is not None:
            self.push_screen(AjudaAba(nav.NOME.capitalize(), nav.texto_ajuda()))

    def _botoes(self) -> list[Button]:
        raiz = self.screen if len(self.screen_stack) > 1 else self._area_widget(self.nome_area(self.focused) or "centro")
        nav = self.nav_da_aba()
        fileira = nav.fileira() if nav is not None else []
        if fileira:
            return [w for w in fileira if w.focusable and isinstance(w, Button)]
        return [b for b in raiz.query(Button) if b.display and not b.disabled and b.region.area > 0]

    def action_botao(self, passo: int) -> None:
        botoes = self._botoes()
        if not botoes:
            return
        atual = self.focused
        if atual in botoes:
            botoes[(botoes.index(atual) + passo) % len(botoes)].focus()
        else:
            botoes[0 if passo > 0 else -1].focus()

    def action_botao_acionar(self) -> None:
        if isinstance(self.focused, Button) and not self.focused.disabled:
            self.focused.press()

    def pop_screen(self):
        r = super().pop_screen()
        if len(self.screen_stack) == 1 and self.pronto:
            self.call_after_refresh(self.focar_area, "centro")
        return r

    # ------------------------------------------------------------ chamadas à API
    def em_thread(self, func, depois) -> None:
        """Roda func numa thread; depois(resultado, erro) volta para a thread da interface."""
        def trabalho() -> None:
            r, erro = None, None
            try:
                r = func()
            except ErroSpotify as e:
                erro = e
            except Exception:
                erro = ErroSpotify("Algo deu errado ao falar com o Spotify. Tente de novo.")
            try:
                self.call_from_thread(depois, r, erro)
            except Exception:
                pass
        threading.Thread(target=trabalho, daemon=True).start()

    def executar(self, descricao: str, func, *args, ok: str = "", depois=None, recarregar: bool = True) -> None:
        def fim(_, erro) -> None:
            if erro is not None:
                if erro.sem_dispositivo:
                    self._sem_dispositivo(lambda: self.executar(descricao, func, *args, ok=ok, depois=depois, recarregar=recarregar))
                else:
                    self.notify(f"{descricao}: {erro}", severity="error", timeout=8)
                    if erro.sem_login:
                        self.pedir_login(str(erro))
            elif ok:
                self.notify(ok)
            if depois:
                depois(erro is None)
            if erro is None:
                self._poll(forcar=True)
        self.em_thread(lambda: func(*args), fim)

    def _sem_dispositivo(self, repetir) -> None:
        if isinstance(self.screen, SemDispositivo):
            return

        def fim(r):
            if r == "abrir":
                self.abrir_spotify_pc(repetir)
            elif r == "escolher":
                self.navegar({"t": "dispositivos"})
        self.push_screen(SemDispositivo(), fim)

    # ------------------------------------------------------------ biblioteca e início
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
                n = len(c.curtidas())
            except ErroSpotify:
                n = 0
            return saida, n

        def depois(r, erro):
            if erro:
                if erro.sem_login:
                    self.pedir_login(str(erro))
                return
            self.dados_bib, n = r
            self.query_one(Biblioteca).definir(self.dados_bib, n if n < 100 else 0)
            self.carregar_inicio()
        self.em_thread(trabalho, depois)

    def atualizar_curtidas(self) -> None:
        pass

    def carregar_inicio(self) -> None:
        a = self.query_one(AreaCentral).atual
        if not isinstance(a, VistaInicio) or not self.conectado:
            return
        c, bib = self.cliente, list(self.dados_bib)

        def trabalho():
            def seguro(f, *args):
                try:
                    return f(*args)
                except ErroSpotify:
                    return []
            recentes, vistos = [], set()
            for t in seguro(c.recentes):
                if t.uri not in vistos:
                    vistos.add(t.uri)
                    recentes.append(t)
            tipos = lambda k: [i for i in bib if i.tipo == k]  # noqa: E731
            rapido = [CURTIDAS] + [i for i in bib if i.tipo in ("playlist", "album")][:7]
            secoes = [("Tocados recentemente", recentes), ("Seus programas", tipos("show")), ("Seus artistas", tipos("artist")),
                      ("Suas playlists", tipos("playlist")), ("Seus álbuns", tipos("album")),
                      ("Mais ouvidos", seguro(c.mais_ouvidos, "artists", "medium_term")[:20])]
            return {"rapido": rapido, "secoes": secoes}

        async def depois(r, erro):
            atual = self.query_one(AreaCentral).atual
            if isinstance(atual, VistaInicio) and r:
                await atual.mostrar(r)
        self.em_thread(trabalho, depois)

    # ------------------------------------------------------------ reprodução
    def _poll(self, forcar: bool = False) -> None:
        if not self.conectado or self._buscando or (len(self.screen_stack) > 1 and not forcar):
            return
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
            self.player = p
            if curtido is not None:
                self.curtido = curtido
            self._uri = p.item.uri if p and p.item else ""
            if fila is not None:
                self._fila_em = time.monotonic()
                self.fila_atual = fila
            self._pintar(fila is not None)
        self.em_thread(trabalho, depois)

    def _pintar(self, com_fila: bool = False) -> None:
        self.query_one(BarraPlayer).pintar(self.player, self.curtido)
        self.query_one(PainelAgora).pintar(self.player, self.curtido, self.fila_atual if com_fila else None)

    def _tick(self) -> None:
        if self.player is not None and self.pronto:
            try:
                self.query_one(BarraPlayer).tick(self.player)
            except Exception:
                pass

    def action_play_pause(self) -> None:
        if not self.conectado or isinstance(self.focused, Input):
            return
        c = self.cliente

        def alternar():
            p = c.player()
            (c.pausar if p and p.tocando else c.retomar)()
        self.executar("Play/pausa", alternar, recarregar=False)

    def _precisa_player(self) -> bool:
        return self.conectado and not isinstance(self.focused, Input)

    def action_proxima(self) -> None:
        if self._precisa_player():
            self.executar("Próxima", self.cliente.proxima)

    def action_anterior(self) -> None:
        if self._precisa_player():
            self.executar("Anterior", self.cliente.anterior)

    def action_aleatorio(self) -> None:
        if self._precisa_player() and self.player:
            novo = not self.player.aleatorio
            self.player.aleatorio = novo
            self.executar("Aleatório", self.cliente.aleatorio, novo)

    def action_repetir(self) -> None:
        if self._precisa_player() and self.player:
            ordem = ["off", "context", "track"]
            novo = ordem[(ordem.index(self.player.repetir) + 1) % 3 if self.player.repetir in ordem else 0]
            self.player.repetir = novo
            self.executar("Repetir", self.cliente.repetir, novo)

    def action_volume(self, passo: int) -> None:
        if self._precisa_player() and self.player and self.player.volume is not None:
            self.player.volume = max(0, min(100, self.player.volume + passo))
            self.executar("Volume", self.cliente.volume, self.player.volume)
            self._pintar()

    def action_curtir_tocando(self) -> None:
        if not self._precisa_player() or not self.player or not self.player.item:
            return
        ja, c = self.curtido, self.cliente
        self.curtido = not ja
        self.executar("Curtir", c.descurtir if ja else c.curtir, self.player.item.uri,
                      ok="Removida das curtidas." if ja else "Faixa curtida.")
        self._pintar()

    def passo_barra(self, barra: str, direcao: int) -> None:
        if barra == "volume":
            self.action_volume(5 * direcao)
        elif self.player and self.player.item:
            self._buscar(max(0, min(self.player.item.dur_ms, self.player.posicao() + 5000 * direcao)))

    def clique_barra(self, barra: str, fracao: float) -> None:
        if barra == "volume":
            if self.player:
                self.player.volume = round(fracao * 100)
                self.executar("Volume", self.cliente.volume, self.player.volume)
                self._pintar()
        elif self.player and self.player.item:
            self._buscar(int(fracao * self.player.item.dur_ms))

    def _buscar(self, ms: int) -> None:
        self.player.progresso_ms, self.player.marca = ms, time.monotonic()
        self.executar("Buscar posição", self.cliente.buscar_posicao, ms)
        self._tick()

    def tocar_item(self, item: Item, contexto: str = "", uris: list[str] | None = None) -> None:
        c = self.cliente
        if item.tipo == "curtidas":
            return self.tocar_uris([i.uri for i in c.curtidas()], None)
        if item.tipo in CONTEXTOS:
            func = lambda: c.tocar(contexto=item.uri)  # noqa: E731
        elif contexto:
            func = lambda: c.tocar(contexto=contexto, desde=item.uri)  # noqa: E731
        elif uris and item.uri in uris:
            fila = uris[uris.index(item.uri):][:100]
            func = lambda: c.tocar(uris=fila, desde=item.uri)  # noqa: E731
        else:
            func = lambda: c.tocar(uris=[item.uri])  # noqa: E731
        self.executar(f"Tocar {item.nome}", func, ok=f"Tocando: {item.nome}")

    def tocar_uris(self, uris: list[str], desde: str | None = None) -> None:
        c = self.cliente
        if uris:
            self.executar("Tocar", lambda: c.tocar(uris=uris[:100], desde=desde), ok="Tocando")

    def adicionar_a_playlist(self, item: Item) -> None:
        def listar():
            return [p for p in self.cliente.playlists() if p.meu]

        def mostrar(r, erro):
            if erro:
                self.notify(str(erro), severity="error")
                return

            def fim(pid):
                if pid:
                    self.executar("Adicionar à playlist", self.cliente.adicionar_a_playlist, pid, item.uri,
                                  ok=f"Adicionada: {item.nome}")
            self.push_screen(EscolherPlaylist(r), fim)
        self.em_thread(listar, mostrar)

    def nova_playlist(self) -> None:
        def fim(nome):
            if nome:
                self.executar("Criar playlist", self.cliente.criar_playlist, nome, ok=f"Playlist criada: {nome}",
                              depois=lambda ok: self.carregar_biblioteca())
        self.push_screen(Pedir("Nova playlist", "", "Dê um nome. Ela nasce privada."), fim)

    def transferir(self, d) -> None:
        def depois(ok):
            a = self.query_one(AreaCentral).atual
            if isinstance(a, VistaLista):
                a.recarregar()
        self.executar(f"Transferir para {d.nome}", self.cliente.transferir, d.id, ok=f"Tocando em {d.nome}", depois=depois)

    def abrir_spotify_pc(self, depois=None) -> None:
        """Roda `spotify`, espera ele aparecer como dispositivo e transfere a reprodução."""
        if not self.lancador():
            self.notify("Não achei o comando spotify neste computador. Instale o Spotify do PC.", severity="error", timeout=8)
            return
        self.notify("Abrindo o Spotify do PC. Espere ele aparecer na lista...", timeout=6)

        def esperar():
            for _ in range(30):
                time.sleep(self.espera_dispositivo)
                ds = self.cliente.dispositivos()
                if ds:
                    d = next((x for x in ds if x.tipo.lower() == "computer"), ds[0])
                    self.cliente.transferir(d.id, False)
                    return d
            raise ErroSpotify("O Spotify do PC não apareceu em 45 segundos. Entre nele com a mesma conta e tente de novo.")

        def fim(d, erro):
            if erro:
                self.notify(str(erro), severity="error", timeout=8)
                return
            self.notify(f"Spotify do PC pronto: {d.nome}")
            a = self.query_one(AreaCentral).atual
            if isinstance(a, VistaLista):
                a.recarregar()
            if depois:
                depois()
        self.em_thread(esperar, fim)

    # ------------------------------------------------------------ saída
    async def action_quit(self) -> None:
        self.estado.salvar()
        self.exit()


def _mesma(a: dict, b: dict) -> bool:
    ka = {k: v for k, v in a.items() if k not in ("linha", "per")}
    kb = {k: v for k, v in b.items() if k not in ("linha", "per")}
    return ka == kb


def main() -> None:
    p = argparse.ArgumentParser(prog="oma-spotify", description="Cliente de Spotify em TUI (precisa de Premium)")
    p.add_argument("--demo", action="store_true", help="usa dados fictícios, sem login e sem rede")
    p.add_argument("--version", action="version", version=f"oma-spotify {__version__}")
    a = p.parse_args()
    OmaSpotifyApp(demo=a.demo).run()


if __name__ == "__main__":
    main()
