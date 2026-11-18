"""Configuração guiada (primeira execução) e Configurações."""

from __future__ import annotations

import threading
import time

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from oma_spotify.services.auth import validar_client_id
from oma_spotify.services.modelos import ErroSpotify
from oma_spotify.ui.dialogos import Confirmar, Pedir
from oma_spotify.ui.navegacao import NavegacaoMixin, RodapeEnxuto
from oma_spotify.ui.base import Pagina

TOCAR_POR = {"auto": "automático (plugin OmaSpotify se instalado, senão Spotify do PC)", "plugin": "plugin OmaSpotify",
             "pc": "Spotify do PC", "escolher": "escolher o dispositivo"}
PAINEL = "https://developer.spotify.com/dashboard"
CRIAR = "https://developer.spotify.com/dashboard/create"


def texto_ajuda_erros(redirect: str) -> str:
    return (
        "Deu erro na página do Spotify? Veja qual foi:\n\n"
        "1. \"redirect_uri: Not matching configuration\" ou INVALID_CLIENT: o Redirect URI do painel não é igual ao que "
        "o app envia. O app envia exatamente:\n"
        f"   {redirect}\n"
        "   No painel do app: Edit settings, remova o URI antigo, cole o valor copiado pelo botão \"Copiar o Redirect URI\", "
        "Add, e clique em SAVE no fim da página. Espere um minuto e tente de novo.\n\n"
        "2. \"User not registered in the Developer Dashboard\" ou 403: em User Management do app, adicione o e-mail "
        "da sua conta Spotify.\n\n"
        "3. Página em branco ou \"não foi possível conectar\" em 127.0.0.1: a porta está ocupada ou o app foi fechado "
        "durante a espera. Use \"Verificar configuração\" e tente de novo.\n\n"
        "4. Client ID: precisa ter 32 caracteres (números e letras de a a f), sem espaços."
    )


def segundos(n: float) -> str:
    n = int(n + 0.999)
    return f"{n // 60}:{n % 60:02d}"


class TelaSetup(NavegacaoMixin, Screen):
    """Passo a passo para criar o app no painel do Spotify, entrar e esperar a autorização."""

    NOME = "configuração"
    BINDINGS = [Binding("escape", "sair_setup", "Sair", priority=True),
                Binding("ctrl+right,ctrl+l", "app.botao(1)", show=False, priority=True),
                Binding("ctrl+left,ctrl+h", "app.botao(-1)", show=False, priority=True),
                Binding("ctrl+enter", "app.botao_acionar", show=False, priority=True),
                Binding("ctrl+down,ctrl+j", "app.secao(1)", show=False, priority=True),
                Binding("ctrl+up,ctrl+k", "app.secao(-1)", show=False, priority=True),
                Binding("c", "copiar_link", "Copiar link", show=False),
                Binding("a", "reabrir", "Abrir de novo", show=False),
                Binding("u", "copiar_redirect", "Copiar Redirect URI", show=False),
                Binding("x", "cancelar_espera", "Cancelar", show=False),
                Binding("e", "ajuda_erros", "Erros comuns", show=False),
                Binding("v", "verificar", "Verificar", show=False)]
    RODAPE = ("botao_acionar", "botao")

    def __init__(self, motivo: str = "") -> None:
        super().__init__()
        self.motivo = motivo
        self.login = None
        self.entrando = False
        self.ajuda_mostrada = False

    def compose(self) -> ComposeResult:
        c = self.app.config
        with VerticalScroll(id="setup"):
            yield Label("Vamos conectar o Spotify", id="titulo-setup")
            yield Static(Text("Você precisa ter o Spotify Premium. O app é seu: crie um no painel de desenvolvedor (5 minutos, uma vez só)."))
            if self.motivo:
                yield Static(Text(self.motivo), id="motivo")
            with Vertical(id="passos"):
                yield Static(Text("1. Abra o painel de desenvolvedor e entre com sua conta."), classes="passo")
                with Horizontal(classes="linha"):
                    yield Button("Abrir developer.spotify.com/dashboard", id="abrir-painel")
                yield Static(Text("2. Clique em Create app. Nome e descrição livres. Em Redirect URIs, adicione exatamente o endereço abaixo "
                                  "e marque Web API."), classes="passo")
                yield Static(Text(c.redirect), id="redirect")
                with Horizontal(classes="linha"):
                    yield Button("Abrir a página Create app", id="abrir-criar")
                    yield Button("Copiar o Redirect URI", id="copiar")
                yield Static(Text("3. Abra Settings do app, copie o Client ID (32 caracteres) e cole aqui."), classes="passo")
                yield Input(c.client_id, placeholder="Client ID (32 caracteres)", id="client-id")
                yield Static(Text("4. Entre. O navegador abre, você autoriza e volta para cá. Em modo de desenvolvimento, "
                                  "seu e-mail precisa estar em User Management do app."), classes="passo")
                with Horizontal(classes="linha"):
                    yield Button("Entrar com o Spotify", id="entrar", variant="primary")
                    yield Button("Verificar configuração", id="verificar")
                    yield Button("Sair do app", id="sair")
            with Vertical(id="espera"):
                yield Static("", id="contagem")
                with Horizontal(classes="linha"):
                    yield Button("Copiar link de login", id="copiar-link", variant="primary")
                    yield Button("Abrir o navegador de novo", id="reabrir")
                    yield Button("Copiar o Redirect URI", id="copiar-redirect")
                with Horizontal(classes="linha"):
                    yield Button("Cancelar a espera", id="cancelar", variant="error")
                    yield Button("Deu erro na página do Spotify?", id="ajuda-erros")
                    yield Button("Verificar configuração", id="verificar2")
                yield Static("", id="link")
                yield Static("", id="ajuda-texto")
            yield Static("", id="status")
            yield Static("", id="diag")
        yield RodapeEnxuto()

    def on_mount(self) -> None:
        self.query_one("#espera").display = False
        self.query_one("#ajuda-texto").display = False
        self.query_one("#client-id", Input).focus()
        self.set_interval(0.5, self._tick)

    def focar_entrada(self) -> None:
        alvo = "#cancelar" if self.login else "#entrar"
        self.query_one(alvo, Button).focus()

    def zonas(self):
        return [[w] for w in self.query("Input, Button") if w.focusable]

    def fileira(self):
        return [w for w in self.query(Button) if w.focusable]

    def acoes_do_rodape(self) -> list[str]:
        return ["botao_acionar", "botao(1)", "ajuda_aba"]

    def action_sair_setup(self) -> None:
        if self.login:
            self.action_cancelar_espera()
        elif isinstance(self.focused, Input):
            self.focar_entrada()
        else:
            self.app.exit()

    # ------------------------------------------------------------ ações
    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        {"abrir-painel": lambda: self.app.abrir_link(PAINEL), "abrir-criar": lambda: self.app.abrir_link(CRIAR),
         "copiar": self.action_copiar_redirect, "copiar-redirect": self.action_copiar_redirect,
         "sair": self.app.exit, "entrar": self._entrar, "copiar-link": self.action_copiar_link,
         "reabrir": self.action_reabrir, "cancelar": self.action_cancelar_espera,
         "ajuda-erros": self.action_ajuda_erros, "verificar": self.action_verificar,
         "verificar2": self.action_verificar}.get(ev.button.id or "", lambda: None)()

    @on(Input.Submitted, "#client-id")
    def _enter_campo(self) -> None:
        self._entrar()

    def _status(self, msg: str) -> None:
        self.query_one("#status", Static).update(Text(msg))

    def action_copiar_redirect(self) -> None:
        self.app.copiar(self.app.config.redirect)
        self.app.notify("Redirect URI copiado. Cole no campo Redirect URIs do painel.")

    def action_copiar_link(self) -> None:
        if not self.login:
            return
        ok = self.app.copiar(self.login.url)
        link = self.query_one("#link", Static)
        if ok:
            self.app.notify("Link de login copiado. Cole no navegador.")
            link.update("")
        else:
            link.update(Text("Não consegui copiar sozinho. Link de login (selecione e copie):\n" + self.login.url))

    def action_reabrir(self) -> None:
        if self.login:
            self.login.abrir(self.app.abridor_navegador)
            self.app.notify("Abrindo o navegador de novo.")

    def action_ajuda_erros(self) -> None:
        w = self.query_one("#ajuda-texto", Static)
        w.update(Text(texto_ajuda_erros(self.app.config.redirect)))
        w.display = not w.display if self.ajuda_mostrada else True
        self.ajuda_mostrada = True

    def action_verificar(self) -> None:
        from oma_spotify.services.diagnostico import verificar
        cfg = self.app.config
        cid = self.query_one("#client-id", Input).value or cfg.client_id
        self._diag("Verificando...")
        self.app.em_thread(lambda: verificar(cid, cfg.porta, cfg.redirect, self.app.url_rede),
                           lambda r, e: self._diag("\n".join(r) if r else str(e)))

    def _diag(self, txt: str) -> None:
        self.query_one("#diag", Static).update(Text(txt))

    def action_cancelar_espera(self) -> None:
        if self.login:
            self.login.cancelar()

    def _tick(self) -> None:
        if not self.login:
            return
        resta = self.login.restante()
        self.query_one("#contagem", Static).update(Text(f"Esperando você autorizar no navegador ({segundos(resta)})"))
        if not self.ajuda_mostrada and time.monotonic() - self.login.inicio >= self.app.tempo_ajuda:
            self.action_ajuda_erros()

    # ------------------------------------------------------------ login
    def _entrar(self) -> None:
        if self.entrando:
            return
        cid, erro = validar_client_id(self.query_one("#client-id", Input).value)
        if erro:
            self._status(erro)
            return
        self.app.config.client_id = cid
        self.app.config.salvar()
        try:
            login = self.app.nova_sessao().iniciar_login(self.app.abridor_navegador, self.app.tempo_login)
        except ErroSpotify as e:
            self._status(str(e))
            return
        self.entrando, self.login, self.ajuda_mostrada = True, login, False
        self.query_one("#passos").display = False
        self.query_one("#espera").display = True
        self.query_one("#ajuda-texto").display = False
        self.query_one("#link", Static).update("")
        self._status("O navegador foi aberto. Autorize o acesso e volte aqui.")
        self._tick()
        self.focar_entrada()

        def trabalho():
            try:
                login.concluir()
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
        self.entrando, self.login = False, None
        if erro:
            self.query_one("#espera").display = False
            self.query_one("#passos").display = True
            self._status(erro)
            self.focar_entrada()
            return
        self.dismiss(True)


class PaginaConfig(Pagina):
    ID, NOME = "config", "Configurações"
    RODAPE = ("botao_acionar", "botao")
    BINDINGS = [Binding("e", "editar_id", "Client ID", show=False), Binding("v", "verificar", "Verificar", show=False)]

    def compose(self) -> ComposeResult:
        yield Static("", id="resumo")
        yield Static("", id="diag-config")
        with Vertical(id="acoes-config"):
            yield Button("Client ID", id="cid", compact=True)
            yield Button("Porta do callback", id="porta", compact=True)
            yield Button("Tocar por", id="tocar-por", compact=True)
            yield Button("Mostrar a abertura", id="abertura", compact=True)
            yield Button("Verificar configuração", id="verificar", compact=True)
            yield Button("Entrar de novo (guia de configuração)", id="guia", compact=True)
            yield Button("Sair da conta", id="sair-conta", variant="error", compact=True)

    def on_mount(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        c = self.app.config
        conectado = self.app.armazem.logado() if not self.app.demo else True
        linhas = [f"Client ID: {c.client_id or 'não definido'}", f"Redirect URI (adicione no painel do app): {c.redirect}",
                  f"Porta do callback: {c.porta}", f"Mostrar a abertura: {'sim' if c.abertura else 'não'}",
                  f"Tocar por: {TOCAR_POR[c.tocar_por]}",
                  f"Conta: {'conectada' + (' (demonstração)' if self.app.demo else '') if conectado else 'não conectada'}"]
        self.query_one("#resumo", Static).update(Text("\n".join(linhas)))
        self.query_one("#tocar-por", Button).label = f"Tocar por: {TOCAR_POR[c.tocar_por]}"
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
        elif b == "tocar-por":
            ordem = list(TOCAR_POR)
            c.tocar_por = ordem[(ordem.index(c.tocar_por) + 1) % len(ordem)]
            c.salvar()
            self.recarregar()
        elif b == "abertura":
            c.abertura = not c.abertura
            c.salvar()
            self.recarregar()
        elif b == "verificar":
            self.action_verificar()
        elif b == "guia":
            self.app.pedir_login("")
        elif b == "sair-conta":
            def fim2(ok):
                if ok:
                    self.app.sair_da_conta()
                    self.recarregar()
            self.app.push_screen(Confirmar("Sair da conta?", ["Os tokens deste computador serão apagados.",
                                                              "Para voltar, é preciso entrar de novo."], "Sair da conta"), fim2)

    def action_verificar(self) -> None:
        from oma_spotify.services.diagnostico import verificar
        c = self.app.config
        self.query_one("#diag-config", Static).update(Text("Verificando..."))
        self.app.em_thread(lambda: verificar(c.client_id, c.porta, c.redirect, self.app.url_rede),
                           lambda r, e: self.query_one("#diag-config", Static).update(Text("\n".join(r) if r else str(e))))

    def action_editar_id(self) -> None:
        def fim(v):
            if v is not None:
                v, aviso = validar_client_id(v) if v else ("", "")
                if aviso:
                    self.app.notify(aviso, severity="warning", timeout=8)
                self.app.config.client_id = v
                self.app.config.salvar()
                self.recarregar()
        self.app.push_screen(Pedir("Client ID", self.app.config.client_id, "Está em Settings do seu app no painel do Spotify."), fim)
