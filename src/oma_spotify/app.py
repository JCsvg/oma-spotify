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
from textual.widgets import Button, Header, Input, Tabs, TabbedContent, TabPane

from oma_spotify import __version__, tema
from oma_spotify.config import Config
from oma_spotify.estado import Estado
from oma_spotify.services.api import ClienteSpotify
from oma_spotify.services.auth import Armazem, Sessao
from oma_spotify.services.falso import ClienteFalso
from oma_spotify.services.modelos import ErroSpotify, Item
from oma_spotify.ui.abertura import Abertura
from oma_spotify.ui.dialogos import EscolherPlaylist, SemDispositivo
from oma_spotify.ui.navegacao import AjudaAba, RodapeEnxuto
from oma_spotify.ui.setup import PaginaConfig, TelaSetup
from oma_spotify.ui.telas import (CONTEXTOS, ListaItens, PaginaBiblioteca, PaginaBusca, PaginaDispositivos, PaginaFila,
                                  PaginaPlaylists, PaginaRecentes, PaginaTocando, PaginaTop, TelaItens)
from oma_spotify.ui.widgets import Tabela

ABAS = [("tocando", "Tocando", PaginaTocando), ("playlists", "Playlists", PaginaPlaylists),
        ("biblioteca", "Biblioteca", PaginaBiblioteca), ("busca", "Busca", PaginaBusca), ("fila", "Fila", PaginaFila),
        ("dispositivos", "Dispositivos", PaginaDispositivos), ("recentes", "Recentes", PaginaRecentes),
        ("top", "Top", PaginaTop), ("config", "Config", PaginaConfig)]


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


class OmaSpotifyApp(App[None]):
    TITLE = "OMA SPOTIFY"
    ENABLE_COMMAND_PALETTE = False
    CSS = """
    Screen { background: $background; color: $foreground; }
    TabbedContent { height: 1fr; }
    TabPane { padding: 0 1; }
    DataTable { height: 1fr; }
    DataTable > .datatable--cursor { background: $accent 28%; color: $foreground; text-style: bold; }
    DataTable:focus > .datatable--cursor { background: $accent 40%; color: $foreground; text-style: bold; }
    #barra, #acoes, #cats { height: 3; }
    #barra Input { width: 1fr; }
    #barra Button, #acoes Button, #cats Button { margin-right: 1; }
    #vazio { height: 1fr; content-align: center middle; text-align: center; color: $text-muted; }
    #topo { height: 6; margin-bottom: 1; }
    #capa { width: 14; height: 6; background: $accent 18%; content-align: center middle; margin-right: 2; }
    #info { width: 1fr; }
    #titulo { text-style: bold; }
    #linha-prog, #linha-vol { height: 1; margin-bottom: 1; }
    #t-pos, #t-dur { width: 6; }
    #t-dur { text-align: right; }
    #rot-vol { width: 9; }
    #pct-vol { width: 6; text-align: right; }
    #aviso { color: $warning; height: auto; }
    #rot-fila { color: $accent; text-style: bold; margin-top: 1; }
    #resumo { margin: 1 0; height: auto; }
    #acoes-config Button { margin-bottom: 1; }
    #titulo-setup, #titulo-detalhe { text-style: bold; color: $accent; margin: 0 1 1 1; }
    #setup { padding: 1 2; }
    #setup .passo { margin-top: 1; }
    #setup .linha { height: 3; }
    #setup .linha Button { margin-right: 1; }
    #redirect { background: $surface; padding: 0 1; color: $accent; text-style: bold; }
    #status, #motivo { color: $warning; margin-top: 1; }
    """
    BINDINGS = [
        Binding("q", "quit", "Sair"),
        *[Binding(str(n + 1), f"aba('{a[0]}')", a[1], show=False) for n, a in enumerate(ABAS)],
        Binding("alt+l,alt+right", "aba_relativa(1)", "Próxima tela", key_display="Alt+L", priority=True),
        Binding("alt+h,alt+left", "aba_relativa(-1)", "Tela anterior", key_display="Alt+H", priority=True),
        Binding("left,h", "lateral(-1)", show=False),
        Binding("right,l", "lateral(1)", show=False),
        Binding("up,k", "linha(-1)", show=False),
        Binding("down,j", "linha(1)", show=False),
        Binding("space", "play_pause", "Play/Pausa", key_display="Espaço"),
        Binding("ctrl+right,ctrl+l", "botao(1)", "Próximo botão", key_display="Ctrl+→", priority=True),
        Binding("ctrl+left,ctrl+h", "botao(-1)", "Botão anterior", key_display="Ctrl+←", priority=True),
        Binding("ctrl+down,ctrl+j", "secao(1)", "Próxima seção", key_display="Ctrl+↓", priority=True),
        Binding("ctrl+up,ctrl+k", "secao(-1)", "Seção anterior", key_display="Ctrl+↑", priority=True),
        Binding("ctrl+@,ctrl+space,ctrl+at,f1", "ajuda_aba", "Ajuda", key_display="Ctrl+Espaço", priority=True),
        Binding("ctrl+enter", "botao_acionar", "Apertar botão", key_display="Ctrl+Enter", priority=True),
        Binding("escape", "voltar_foco", "Voltar à lista", show=False),
    ]

    def __init__(self, cliente=None, demo: bool = False, estado: Estado | None = None, config: Config | None = None,
                 armazem: Armazem | None = None, abertura: bool = True, abridor=None, lancador=None,
                 espera_dispositivo: float = 1.5) -> None:
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
        self.paleta = tema.ler()
        self._aba_alvo, self._aba_alvo_em = "", 0.0
        self.pronto = False
        self.salvo: dict = {}

    # ------------------------------------------------------------ montagem
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with TabbedContent(initial="tocando", id="abas"):
            for n, (id_, rotulo, cls) in enumerate(ABAS):
                with TabPane(f"{n + 1} {rotulo}", id=id_):
                    yield cls()
        yield RodapeEnxuto()

    def on_mount(self) -> None:
        self.register_theme(tema.tema_textual("omarchy"))
        self.theme = "omarchy"
        self.sub_title = "Spotify" + (" (demonstração)" if self.demo else "")
        for t in self.query(Tabs):
            t.can_focus = False  # as setas não trocam de aba, só Alt e os números
        self.estado.carregar()
        self.salvo = dict(self.estado.dados)
        self.call_after_refresh(self._iniciar)

    def _iniciar(self) -> None:
        for id_, _, cls in ABAS:
            try:
                self.query_one(cls).restaurar(self.salvo.get(f"aba_{id_}", {}))
            except Exception:
                pass
        primeira = self.com_abertura and self.config.abertura and not self.estado.ja_abriu()
        aba = self.salvo.get("aba", "tocando")
        if aba in {a[0] for a in ABAS} and not primeira:
            self.query_one("#abas", TabbedContent).active = aba
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
        self.recarregar_tudo()
        self.call_after_refresh(self.focar_tabela)

    def cor(self, nome: str) -> str:
        p = self.paleta
        return {"success": p["green"], "warning": p["yellow"], "error": p["red"], "accent": p["accent"],
                "muted": p.get("dark_foreground", p["muted"])}.get(nome, p["foreground"])

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
                self.recarregar_tudo()
                self.call_after_refresh(self.focar_tabela)
        self.push_screen(TelaSetup(motivo), fim)

    def sair_da_conta(self) -> None:
        if self.demo:
            self.notify("Demonstração: não há conta para sair.")
            return
        self.armazem.apagar()
        self.cliente, self.conectado = None, False
        self.pedir_login("Você saiu da conta.")

    def abrir_link(self, url: str) -> None:
        try:
            self.abridor_navegador(url)
        except Exception:
            pass
        self.notify("Abrindo no navegador. Se não abriu, o endereço é " + url, timeout=6)

    # ------------------------------------------------------------ estado
    def guardar_aba(self, nome: str, d: dict) -> None:
        if self.pronto:
            self.estado.definir(f"aba_{nome}", d)

    # ------------------------------------------------------------ navegação
    def aba_atual(self) -> str:
        return self.query_one("#abas", TabbedContent).active

    def aba_widget(self):
        a = self.aba_atual()
        for id_, _, cls in ABAS:
            if id_ == a:
                return self.query_one(cls)
        return None

    def nav_da_aba(self):
        if len(self.screen_stack) > 1:
            s = self.screen
            if isinstance(s, TelaItens):
                return s.lista
            return s if hasattr(s, "mover_secao") else None
        return self.aba_widget()

    def check_action(self, action: str, parameters):
        if action in ("aba_relativa", "play_pause") and len(self.screen_stack) > 1 and not isinstance(self.screen, TelaItens):
            return False
        if action == "ajuda_aba":
            return self.nav_da_aba() is not None or isinstance(self.screen, AjudaAba)
        return True

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

    def action_voltar_foco(self) -> None:
        nav = self.nav_da_aba()
        if nav is not None:
            nav.focar_entrada()

    def action_aba(self, aba: str) -> None:
        if len(self.screen_stack) > 1 or aba not in {a[0] for a in ABAS}:
            return
        self._ir_para(aba)

    def _ir_para(self, aba: str) -> None:
        self._aba_alvo, self._aba_alvo_em = aba, time.monotonic()
        self.query_one("#abas", TabbedContent).active = aba
        self.call_after_refresh(self.focar_tabela)

    def action_aba_relativa(self, passo: int) -> None:
        if len(self.screen_stack) > 1:
            return
        ordem = [a[0] for a in ABAS]
        base = self._aba_alvo or self.aba_atual()
        self._ir_para(ordem[(ordem.index(base) + passo) % len(ordem)])

    def _botoes(self) -> list[Button]:
        raiz = self.screen if len(self.screen_stack) > 1 else self.aba_widget()
        if raiz is None:
            return []
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

    def action_lateral(self, passo: int) -> None:
        """←/→ e h/l: andam entre botões e painéis da tela (nunca trocam de aba)."""
        if isinstance(self.focused, Input):
            return
        if isinstance(self.focused, Button):
            self.action_botao(passo)
            return
        botoes = self._botoes()
        if botoes:
            botoes[0 if passo > 0 else -1].focus()

    def action_linha(self, passo: int) -> None:
        f = self.focused
        if isinstance(f, Button) and passo < 0:
            nav = self.nav_da_aba()
            if nav is not None:
                for z in nav.zonas():
                    if f in z and isinstance(z[0], Tabela):
                        z[0].focus()
                        return
        self.action_secao(passo)

    def action_botao_acionar(self) -> None:
        if isinstance(self.focused, Button) and not self.focused.disabled:
            self.focused.press()

    def focar_tabela(self) -> None:
        nav = self.nav_da_aba()
        if nav is not None:
            nav.focar_entrada()

    def recarregar_tudo(self) -> None:
        a = self.aba_widget()
        if a is not None:
            a.recarregar()

    @on(TabbedContent.TabActivated)
    def _aba_mudou(self) -> None:
        ativa = self.aba_atual()
        if self._aba_alvo and ativa != self._aba_alvo and time.monotonic() - self._aba_alvo_em < 0.6:
            self.query_one("#abas", TabbedContent).active = self._aba_alvo
            return
        self._aba_alvo = ativa
        if self.pronto:
            self.estado.definir("aba", ativa)
            if self.conectado:
                self.recarregar_tudo()
        self.call_after_refresh(self.focar_tabela)

    def pop_screen(self):
        r = super().pop_screen()
        if len(self.screen_stack) == 1:
            self.call_after_refresh(self.focar_tabela)
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
                for cls in (PaginaTocando,):
                    try:
                        self.query_one(cls)._poll(forcar=True)
                    except Exception:
                        pass
                if recarregar and self.aba_atual() in ("fila",):
                    self.recarregar_tudo()
        self.em_thread(lambda: func(*args), fim)

    def _sem_dispositivo(self, repetir) -> None:
        if isinstance(self.screen, SemDispositivo):
            return

        def fim(r):
            if r == "abrir":
                self.abrir_spotify_pc(repetir)
            elif r == "escolher":
                self.action_aba("dispositivos")
        self.push_screen(SemDispositivo(), fim)

    def action_play_pause(self) -> None:
        if not self.conectado or len(self.screen_stack) > 1 and not isinstance(self.screen, TelaItens):
            return
        c = self.cliente

        def alternar():
            p = c.player()
            (c.pausar if p and p.tocando else c.retomar)()
        self.executar("Play/pausa", alternar, recarregar=False)

    def tocar_item(self, item: Item, contexto: str = "", uris: list[str] | None = None) -> None:
        c = self.cliente
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

    def abrir_item(self, item: Item) -> None:
        self.push_screen(TelaItens(item))

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

    def transferir(self, d) -> None:
        self.executar(f"Transferir para {d.nome}", self.cliente.transferir, d.id, ok=f"Tocando em {d.nome}",
                      depois=lambda ok: self.recarregar_tudo())

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
            self.recarregar_tudo()
            if depois:
                depois()
        self.em_thread(esperar, fim)

    # ------------------------------------------------------------ saída
    async def action_quit(self) -> None:
        self.estado.salvar()
        self.exit()


def main() -> None:
    p = argparse.ArgumentParser(prog="oma-spotify", description="Cliente de Spotify em TUI (precisa de Premium)")
    p.add_argument("--demo", action="store_true", help="usa dados fictícios, sem login e sem rede")
    p.add_argument("--version", action="version", version=f"oma-spotify {__version__}")
    a = p.parse_args()
    OmaSpotifyApp(demo=a.demo).run()


if __name__ == "__main__":
    main()
