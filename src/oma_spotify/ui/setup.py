"""Configuração guiada (primeira execução) e Configurações."""

from __future__ import annotations

import threading
import webbrowser

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from oma_spotify.services.modelos import ErroSpotify
from oma_spotify.ui.dialogos import Confirmar, Pedir
from oma_spotify.ui.navegacao import NavegacaoMixin, RodapeEnxuto
from oma_spotify.ui.telas import Pagina

PAINEL = "https://developer.spotify.com/dashboard"
CRIAR = "https://developer.spotify.com/dashboard/create"


class TelaSetup(NavegacaoMixin, Screen):
    """Passo a passo para criar o app no painel do Spotify e entrar."""

    NOME = "configuração"
    BINDINGS = [Binding("escape", "sair_setup", "Sair", priority=True),
                Binding("ctrl+right,ctrl+l", "app.botao(1)", show=False, priority=True),
                Binding("ctrl+left,ctrl+h", "app.botao(-1)", show=False, priority=True),
                Binding("ctrl+enter", "app.botao_acionar", show=False, priority=True),
                Binding("ctrl+down,ctrl+j", "app.secao(1)", show=False, priority=True),
                Binding("ctrl+up,ctrl+k", "app.secao(-1)", show=False, priority=True)]
    RODAPE = ("botao_acionar", "botao")

    def __init__(self, motivo: str = "") -> None:
        super().__init__()
        self.motivo = motivo
        self.entrando = False

    def compose(self) -> ComposeResult:
        c = self.app.config
        with VerticalScroll(id="setup"):
            yield Label("Vamos conectar o Spotify", id="titulo-setup")
            yield Static(Text("Você precisa ter o Spotify Premium. O app é seu: crie um no painel de desenvolvedor (5 minutos, uma vez só)."))
            if self.motivo:
                yield Static(Text(self.motivo), id="motivo")
            yield Static(Text("1. Abra o painel de desenvolvedor e entre com sua conta."), classes="passo")
            with Horizontal(classes="linha"):
                yield Button("Abrir developer.spotify.com/dashboard", id="abrir-painel")
            yield Static(Text("2. Clique em Create app. Nome e descrição livres. Em Redirect URIs, adicione exatamente o endereço abaixo "
                              "e marque Web API."), classes="passo")
            yield Static(Text(c.redirect), id="redirect")
            with Horizontal(classes="linha"):
                yield Button("Abrir a página Create app", id="abrir-criar")
                yield Button("Copiar o Redirect URI", id="copiar")
            yield Static(Text("3. Abra Settings do app, copie o Client ID e cole aqui."), classes="passo")
            yield Input(c.client_id, placeholder="Client ID (32 caracteres)", id="client-id")
            yield Static(Text("4. Entre. O navegador abre, você autoriza e volta para cá. Em modo de desenvolvimento, "
                              "seu e-mail precisa estar em User Management do app."), classes="passo")
            with Horizontal(classes="linha"):
                yield Button("Entrar com o Spotify", id="entrar", variant="primary")
                yield Button("Sair do app", id="sair")
            yield Static("", id="status")
        yield RodapeEnxuto()

    def on_mount(self) -> None:
        self.query_one("#client-id", Input).focus()

    def focar_entrada(self) -> None:
        self.query_one("#entrar", Button).focus()

    def zonas(self):
        return [[w] if not isinstance(w, Button) else [w] for w in self.query("Input, Button") if w.focusable]

    def fileira(self):
        return [w for w in self.query(Button) if w.focusable]

    def acoes_do_rodape(self) -> list[str]:
        return ["botao_acionar", "botao"]

    def action_sair_setup(self) -> None:
        if isinstance(self.focused, Input):
            self.focar_entrada()
        else:
            self.app.exit()

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        b = ev.button.id
        if b == "abrir-painel":
            self.app.abrir_link(PAINEL)
        elif b == "abrir-criar":
            self.app.abrir_link(CRIAR)
        elif b == "copiar":
            self.app.copy_to_clipboard(self.app.config.redirect)
            self.app.notify("Redirect URI copiado. Cole no campo Redirect URIs do painel.")
        elif b == "sair":
            self.app.exit()
        elif b == "entrar":
            self._entrar()

    @on(Input.Submitted, "#client-id")
    def _enter_campo(self) -> None:
        self._entrar()

    def _status(self, msg: str) -> None:
        self.query_one("#status", Static).update(Text(msg))

    def _entrar(self) -> None:
        cid = self.query_one("#client-id", Input).value.strip()
        if len(cid) < 10 or " " in cid:
            self._status("Cole o Client ID do seu app (veja o passo 3).")
            return
        if self.entrando:
            return
        self.entrando = True
        self.app.config.client_id = cid
        self.app.config.salvar()
        self._status("Abrindo o navegador. Autorize o acesso e volte aqui...")

        def trabalho():
            try:
                sessao = self.app.nova_sessao()
                sessao.entrar(abrir=self.app.abridor_navegador)
                erro = ""
            except ErroSpotify as e:
                erro = str(e)
            except Exception:
                erro = "Não consegui concluir o login. Tente de novo."
            try:
                self.app.call_from_thread(self._fim, erro)
            except Exception:
                pass
        threading.Thread(target=trabalho, daemon=True).start()

    def _fim(self, erro: str) -> None:
        self.entrando = False
        if erro:
            self._status(erro)
            return
        self.dismiss(True)


class PaginaConfig(Pagina):
    ID, NOME = "config", "Configurações"
    RODAPE = ("botao_acionar", "botao")
    BINDINGS = [Binding("e", "editar_id", "Client ID", show=False)]

    def compose(self) -> ComposeResult:
        yield Static("", id="resumo")
        with Vertical(id="acoes-config"):
            yield Button("Client ID", id="cid")
            yield Button("Porta do callback", id="porta")
            yield Button("Mostrar a abertura", id="abertura")
            yield Button("Entrar de novo (guia de configuração)", id="guia")
            yield Button("Sair da conta", id="sair-conta", variant="error")

    def on_mount(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        c = self.app.config
        conectado = self.app.armazem.logado() if not self.app.demo else True
        linhas = [f"Client ID: {c.client_id or 'não definido'}", f"Redirect URI (adicione no painel do app): {c.redirect}",
                  f"Porta do callback: {c.porta}", f"Mostrar a abertura: {'sim' if c.abertura else 'não'}",
                  f"Conta: {'conectada' + (' (demonstração)' if self.app.demo else '') if conectado else 'não conectada'}"]
        self.query_one("#resumo", Static).update(Text("\n".join(linhas)))
        self.query_one("#abertura", Button).label = f"Mostrar a abertura: {'sim' if c.abertura else 'não'}"

    def focar_entrada(self) -> None:
        self.query_one("#cid", Button).focus()

    def zonas(self):
        return [[b for b in self.query(Button) if b.focusable]]

    def fileira(self):
        return [b for b in self.query(Button) if b.focusable]

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        b = ev.button.id
        c = self.app.config
        if b == "cid":
            self.action_editar_id()
        elif b == "porta":
            def fim(v):
                if v and v.isdigit() and 1024 <= int(v) <= 65535:
                    c.porta = int(v)
                    c.salvar()
                    self.recarregar()
                    self.app.notify(f"Porta {v}. Atualize o Redirect URI no painel do Spotify.", timeout=8)
                elif v:
                    self.app.notify("Use um número entre 1024 e 65535.", severity="error")
            self.app.push_screen(Pedir("Porta do callback", str(c.porta), "O Redirect URI muda junto, e precisa estar igual no painel."), fim)
        elif b == "abertura":
            c.abertura = not c.abertura
            c.salvar()
            self.recarregar()
        elif b == "guia":
            self.app.pedir_login("")
        elif b == "sair-conta":
            def fim2(ok):
                if ok:
                    self.app.sair_da_conta()
                    self.recarregar()
            self.app.push_screen(Confirmar("Sair da conta?", ["Os tokens deste computador serão apagados.",
                                                              "Para voltar, é preciso entrar de novo."], "Sair da conta"), fim2)

    def action_editar_id(self) -> None:
        def fim(v):
            if v is not None:
                self.app.config.client_id = v
                self.app.config.salvar()
                self.recarregar()
        self.app.push_screen(Pedir("Client ID", self.app.config.client_id, "Está em Settings do seu app no painel do Spotify."), fim)
