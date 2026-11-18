"""Primeiro acesso (criar o app, colar o Client ID e entrar) e a página de Configurações."""

from __future__ import annotations

import threading
import time

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, Static

from oma_spotify.services.auth import pasta_estado, validar_client_id
from oma_spotify.services.modelos import ErroSpotify
from oma_spotify.ui.icones import ic
from oma_spotify.ui.paginas import Pagina
from oma_spotify.ui.widgets import Botao

TOCAR_POR = {"auto": "automático (plugin OmaSpotify se instalado, senão Spotify do PC)", "plugin": "plugin OmaSpotify",
             "pc": "Spotify do PC", "escolher": "escolher o aparelho"}
PAINEL = "https://developer.spotify.com/dashboard"
CRIAR = "https://developer.spotify.com/dashboard/create"


def texto_ajuda_erros(redirect: str) -> str:
    return (
        "Deu erro na página do Spotify? Veja qual foi:\n\n"
        "1. \"redirect_uri: Not matching configuration\" ou INVALID_CLIENT: o Redirect URI do painel não é igual ao que "
        "o app envia. O app envia exatamente:\n"
        f"   {redirect}\n"
        "   No painel do app: Edit settings, remova o URI antigo, cole o valor copiado pelo botão \"copiar\", "
        "Add, e clique em SAVE no fim da página. Espere um minuto e tente de novo.\n\n"
        "2. \"User not registered in the Developer Dashboard\" ou 403: em User Management do app, adicione o e-mail "
        "da sua conta Spotify.\n\n"
        "3. Página em branco ou \"não foi possível conectar\" em 127.0.0.1: a porta está ocupada ou o app foi fechado "
        "durante a espera. Use \"verificar configuração\" e tente de novo.\n\n"
        "4. Client ID: precisa ter 32 caracteres (números e letras de a a f), sem espaços."
    )


def segundos(n: float) -> str:
    n = int(n + 0.999)
    return f"{n // 60}:{n % 60:02d}"


class TelaSetup(Screen):
    """Passo a passo para criar o app no painel do Spotify, entrar e esperar a autorização."""

    NOME = "primeiro acesso"
    DEFAULT_CSS = """
    TelaSetup { background: $background; }
    TelaSetup #barra { height: 1; background: $oma-escuro; padding: 0 1; }
    TelaSetup #rolar { height: 1fr; }
    TelaSetup #caixa { width: 86; height: auto; border: solid $oma-linha; border-title-color: $accent; border-title-style: bold;
                       border-subtitle-color: $oma-mudo; padding: 1 2; margin: 2 0; }
    TelaSetup .mudo { color: $oma-mudo; }
    TelaSetup .passo { height: 1; margin-top: 1; }
    TelaSetup .num { width: 2; color: $background; background: $accent; text-style: bold; margin-right: 2; content-align: center middle; }
    TelaSetup .passo-tit { width: auto; text-style: bold; color: $oma-forte; }
    TelaSetup .recuo { margin-left: 4; height: auto; }
    TelaSetup .campo-linha { height: 1; margin: 1 0 0 4; }
    TelaSetup #redirect { width: 44; background: $oma-campo; padding: 0 2; }
    TelaSetup #client-id { width: 44; background: $oma-campo; }
    TelaSetup #client-id:focus { background: $oma-campo; }
    TelaSetup .campo-linha Botao { margin-left: 2; }
    TelaSetup .dica { color: $oma-mudo; margin-left: 2; width: auto; }
    TelaSetup #abrir-painel { color: $secondary; text-style: underline; padding: 0; }
    TelaSetup .linha-botoes { height: 1; margin: 1 0 0 4; }
    TelaSetup .linha-botoes Botao { margin-right: 2; }
    TelaSetup #regua { height: 1; color: $oma-linha; margin-top: 1; }
    TelaSetup #premium { height: auto; margin-top: 1; }
    TelaSetup #pe { height: 1; margin-top: 1; }
    TelaSetup #espera, TelaSetup #passos { height: auto; }
    TelaSetup #status, TelaSetup #motivo { color: $warning; height: auto; margin-top: 1; }
    TelaSetup #contagem { text-style: bold; color: $accent; margin-top: 1; height: auto; }
    TelaSetup #link, TelaSetup #diag { height: auto; }
    TelaSetup #ajuda-texto { background: $oma-painel; padding: 0 1; margin-top: 1; height: auto; }
    """
    BINDINGS = [Binding("escape", "sair_setup", "sair", priority=True),
                Binding("ctrl+right,ctrl+l,ctrl+down,ctrl+j", "app.ciclo(1)", show=False, priority=True),
                Binding("ctrl+left,ctrl+h,ctrl+up,ctrl+k", "app.ciclo(-1)", show=False, priority=True),
                Binding("c", "copiar_link", show=False), Binding("a", "reabrir", show=False),
                Binding("u", "copiar_redirect", show=False), Binding("x", "cancelar_espera", show=False),
                Binding("e", "ajuda_erros", show=False), Binding("v", "verificar", show=False)]

    def __init__(self, motivo: str = "") -> None:
        super().__init__()
        self.motivo = motivo
        self.login = None
        self.entrando = False
        self.ajuda_mostrada = False

    def compose(self) -> ComposeResult:
        a = self.app
        c = a.config
        yield Static(Text.assemble((ic("nota"), f"bold {a.cor('accent')}"), "  ", ("oma-spotify", "bold")), id="barra")
        with VerticalScroll(id="rolar"):
            with Center():
                with Vertical(id="caixa") as cx:
                    cx.border_title = "entrar no Spotify"
                    cx.border_subtitle = "só na primeira vez"
                    yield Static("o oma-spotify conversa com o Spotify por um app seu (um Client ID).")
                    yield Static("leva uns 2 minutos e só se faz uma vez.", classes="mudo")
                    if self.motivo:
                        yield Static(Text(self.motivo), id="motivo")
                    with Vertical(id="passos"):
                        with Horizontal(classes="passo"):
                            yield Static("1", classes="num")
                            yield Static("crie um app em ", classes="passo-tit")
                            yield Botao("developer.spotify.com/dashboard ↗", id="abrir-painel", tooltip="abre no navegador")
                        yield Static("marque “Web API” e cadastre este redirect URI:", classes="recuo mudo")
                        with Horizontal(classes="campo-linha"):
                            yield Static(Text(c.redirect), id="redirect")
                            yield Botao("⧉ copiar", id="copiar", classes="vazado")
                            yield Botao("abrir create app", id="abrir-criar", classes="vazado")
                        yield Static(f"a porta {c.porta} muda nas configurações. localhost não é aceito.", classes="recuo mudo")
                        with Horizontal(classes="passo"):
                            yield Static("2", classes="num")
                            yield Static("cole o Client ID", classes="passo-tit")
                        with Horizontal(classes="campo-linha"):
                            yield Input(c.client_id, placeholder="32 caracteres", id="client-id", compact=True)
                            yield Static("ctrl+v cola", classes="dica")
                        with Horizontal(classes="passo"):
                            yield Static("3", classes="num")
                            yield Static("autorize no navegador", classes="passo-tit")
                        with Horizontal(classes="linha-botoes"):
                            yield Botao("→ entrar pelo navegador", id="entrar", classes="cheio")
                            yield Static("abre o navegador e volta sozinho", classes="dica")
                        with Horizontal(classes="linha-botoes"):
                            yield Botao("verificar configuração", id="verificar", classes="vazado")
                            yield Botao("sair do app", id="sair", classes="vazado")
                    with Vertical(id="espera"):
                        yield Static("", id="contagem")
                        with Horizontal(classes="linha-botoes"):
                            yield Botao("copiar link de login", id="copiar-link", classes="cheio")
                            yield Botao("abrir o navegador de novo", id="reabrir", classes="vazado")
                            yield Botao("copiar o redirect URI", id="copiar-redirect", classes="vazado")
                        with Horizontal(classes="linha-botoes"):
                            yield Botao("cancelar a espera", id="cancelar", classes="vazado vermelho")
                            yield Botao("deu erro na página do Spotify?", id="ajuda-erros", classes="vazado")
                            yield Botao("verificar configuração", id="verificar2", classes="vazado")
                        yield Static("", id="link")
                        yield Static("", id="ajuda-texto")
                    yield Static("", id="status")
                    yield Static("", id="diag")
                    yield Static("", id="regua")
                    yield Static(Text.assemble((f"{ic('aviso')} ", f"bold {a.cor('yellow')}"),
                                               ("precisa de Spotify Premium: sem ele a API não controla o player.\n", a.cor("texto")),
                                               (f"  o token fica em {pasta_estado()}/ (só para você, permissão 600).", a.cor("mudo"))),
                                 id="premium")
                    yield Static("", id="pe")

    def on_mount(self) -> None:
        a = self.app
        from oma_spotify.ui.dialogos import pe
        self.query_one("#pe", Static).update(pe(a, [("tab", "próximo campo"), ("enter", "confirma"), ("esc", "sai")]))
        self.query_one("#regua", Static).update(Text("─" * 80, style=a.cor("linha")))
        self.query_one("#espera").display = False
        self.query_one("#ajuda-texto").display = False
        self.query_one("#client-id", Input).focus()
        self.set_interval(0.5, self._tick)

    def focar_entrada(self) -> None:
        self.query_one("#cancelar" if self.login else "#entrar", Botao).focus()

    def action_sair_setup(self) -> None:
        if self.login:
            self.action_cancelar_espera()
        elif isinstance(self.focused, Input):
            self.focar_entrada()
        else:
            self.app.exit()

    # ------------------------------------------------------------ ações
    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        {"abrir-painel": lambda: self.app.abrir_link(PAINEL), "abrir-criar": lambda: self.app.abrir_link(CRIAR),
         "copiar": self.action_copiar_redirect, "copiar-redirect": self.action_copiar_redirect,
         "sair": self.app.exit, "entrar": self._entrar, "copiar-link": self.action_copiar_link,
         "reabrir": self.action_reabrir, "cancelar": self.action_cancelar_espera,
         "ajuda-erros": self.action_ajuda_erros, "verificar": self.action_verificar,
         "verificar2": self.action_verificar}.get(ev.botao.id or "", lambda: None)()

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
    DEFAULT_CSS = """
    PaginaConfig #rolar-cfg { height: 1fr; }
    PaginaConfig #resumo, PaginaConfig #diag-config { height: auto; margin-top: 1; }
    PaginaConfig #acoes-config { height: auto; margin-top: 1; }
    PaginaConfig #acoes-config Botao { margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="rolar-cfg"):
            yield Static("", id="resumo")
            with Vertical(id="acoes-config"):
                yield Botao("Client ID", id="cid", classes="vazado")
                yield Botao("porta do callback", id="porta", classes="vazado")
                yield Botao("tocar por", id="tocar-por", classes="vazado")
                yield Botao("letra", id="letra", classes="vazado")
                yield Botao("ícones", id="icones", classes="vazado")
                yield Botao("mostrar a abertura", id="abertura", classes="vazado")
                yield Botao("verificar configuração", id="verificar", classes="vazado")
                yield Botao("entrar de novo (primeiro acesso)", id="guia", classes="vazado")
                yield Botao("sair da conta", id="sair-conta", classes="vazado vermelho")
            yield Static("", id="diag-config")

    def on_mount(self) -> None:
        self.recarregar()

    def recarregar(self) -> None:
        a = self.app
        c = a.config
        conectado = a.armazem.logado() if not a.demo else True
        linhas = [f"Client ID: {c.client_id or 'não definido'}", f"Redirect URI (cadastre no painel do app): {c.redirect}",
                  f"Porta do callback: {c.porta}", f"Mostrar a abertura: {'sim' if c.abertura else 'não'}",
                  f"Tocar por: {TOCAR_POR[c.tocar_por]}", f"Letra (lrclib.net): {'buscar' if c.letra else 'desligada'}",
                  f"Ícones: {'Nerd Font' if c.icones == 'nerd' else 'simples'}",
                  f"Conta: {'conectada' + (' (demonstração)' if a.demo else '') if conectado else 'não conectada'}"]
        self.query_one("#resumo", Static).update(Text("\n".join(linhas)))
        q = self.query_one
        q("#tocar-por", Botao).label = f"tocar por: {TOCAR_POR[c.tocar_por]}"
        q("#abertura", Botao).label = f"mostrar a abertura: {'sim' if c.abertura else 'não'}"
        q("#letra", Botao).label = f"letra pela lrclib.net: {'sim' if c.letra else 'não'}"
        q("#icones", Botao).label = f"ícones: {'Nerd Font' if c.icones == 'nerd' else 'simples'}"

    def focar_entrada(self) -> None:
        self.query_one("#cid", Botao).focus()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        from oma_spotify.ui.dialogos import Confirmar, Pedir
        ev.stop()
        b = ev.botao.id
        a = self.app
        c = a.config
        if b == "cid":
            self.action_editar_id()
        elif b == "porta":
            def fim(v):
                if v and v.isdigit() and 1024 <= int(v) <= 65535:
                    c.porta = int(v)
                    c.salvar()
                    self.recarregar()
                    a.notify(f"Porta {v}. Atualize o Redirect URI no painel do Spotify.", timeout=8)
                elif v:
                    a.notify("Use um número entre 1024 e 65535.", severity="error")
            a.push_screen(Pedir("porta do callback", str(c.porta), "O Redirect URI muda junto, e precisa estar igual no painel."), fim)
        elif b == "tocar-por":
            ordem = list(TOCAR_POR)
            c.tocar_por = ordem[(ordem.index(c.tocar_por) + 1) % len(ordem)]
            c.salvar()
            self.recarregar()
        elif b == "abertura":
            c.abertura = not c.abertura
            c.salvar()
            self.recarregar()
        elif b == "letra":
            c.letra = not c.letra
            c.salvar()
            a.letra, a._letra_uri = None, ""
            self.recarregar()
        elif b == "icones":
            c.icones = "simples" if c.icones == "nerd" else "nerd"
            c.salvar()
            self.recarregar()
            a.notify("Os ícones mudam na próxima abertura do app.", timeout=5)
        elif b == "verificar":
            self.action_verificar()
        elif b == "guia":
            a.pedir_login("")
        elif b == "sair-conta":
            def fim2(ok):
                if ok:
                    a.sair_da_conta()
                    self.recarregar()
            a.push_screen(Confirmar("sair da conta?", ["Os tokens deste computador serão apagados.",
                                                       "Para voltar, é preciso entrar de novo."], "sair da conta"), fim2)

    def action_verificar(self) -> None:
        from oma_spotify.services.diagnostico import verificar
        c = self.app.config
        self.query_one("#diag-config", Static).update(Text("Verificando..."))
        self.em_thread(lambda: verificar(c.client_id, c.porta, c.redirect, self.app.url_rede),
                       lambda r, e: self.query_one("#diag-config", Static).update(Text("\n".join(r) if r else str(e))))

    def action_editar_id(self) -> None:
        from oma_spotify.ui.dialogos import Pedir

        def fim(v):
            if v is not None:
                v, aviso = validar_client_id(v) if v else ("", "")
                if aviso:
                    self.app.notify(aviso, severity="warning", timeout=8)
                self.app.config.client_id = v
                self.app.config.salvar()
                self.recarregar()
        self.app.push_screen(Pedir("Client ID", self.app.config.client_id, "Está em Settings do seu app no painel do Spotify."), fim)

    def rodape(self):
        return [("enter", "apertar", "enter"), ("↑↓", "opções", "mover(0,1)")]
