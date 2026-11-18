"""Diálogos: confirmar, pedir texto, conta, opções do item, ir para, tocar em, adicionar à playlist, teclas e ajuda."""

from __future__ import annotations

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from oma_spotify.services.modelos import Item
from oma_spotify.ui.icones import de_aparelho, ic
from oma_spotify.ui.lista import EstadoLinha, Lista, ajustar, colunas
from oma_spotify.ui.widgets import Botao

_CSS = """
{n} { align: center middle; background: $background 60%; }
{n} #caixa { width: 64; max-width: 100%; height: auto; max-height: 90%; background: $background; border: solid $accent;
             border-title-color: $accent; border-title-style: bold; border-subtitle-color: $oma-mudo; padding: 0 1; }
{n} .linha-texto { height: auto; }
{n} #botoes { height: 1; margin-top: 1; }
{n} #botoes Botao { margin-right: 2; }
{n} .pe { height: 1; margin-top: 1; }
{n} .nota { color: $oma-mudo; height: auto; }
"""


def css(nome: str, extra: str = "") -> str:
    return _CSS.replace("{n}", nome) + extra


def pe(app, itens: list[tuple[str, str]]) -> Text:
    t = Text(no_wrap=True)
    for n, (k, rot) in enumerate(itens):
        if n:
            t.append("   ")
        t.append(k, style=app.cor("accent"))
        t.append(" " + rot, style=app.cor("mudo"))
    return t


class Dialogo(ModalScreen):
    BINDINGS = [Binding("escape", "cancelar", "fechar", priority=True)]

    def action_cancelar(self) -> None:
        self.dismiss(None)

    def mover_janela(self, direcao: str) -> None:
        (self.focus_next if direcao in ("dir", "baixo") else self.focus_previous)()

    def on_click(self, ev: events.Click) -> None:
        # clicar fora da caixa fecha
        if ev.widget is self:
            self.action_cancelar()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        self.apertou(ev.botao.id or "")

    def apertou(self, bid: str) -> None:
        pass


class Confirmar(Dialogo):
    DEFAULT_CSS = css("Confirmar")

    def __init__(self, titulo: str, linhas: list[str], rotulo: str = "confirmar") -> None:
        super().__init__()
        self.titulo, self.linhas, self.rotulo = titulo, linhas, rotulo

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = self.titulo
            for l in self.linhas:
                yield Static(Text(l), classes="linha-texto")
            with Horizontal(id="botoes"):
                yield Botao(self.rotulo, id="sim", classes="vermelho vazado")
                yield Botao("cancelar", id="nao", classes="vazado")

    def on_mount(self) -> None:
        self.query_one("#nao", Botao).focus()  # padrão seguro

    def apertou(self, bid: str) -> None:
        self.dismiss(bid == "sim")

    def action_cancelar(self) -> None:
        self.dismiss(False)

    def on_key(self, ev: events.Key) -> None:
        if ev.key in ("left", "right", "h", "l"):
            ev.stop()
            self.focus_next()


class Pedir(Dialogo):
    DEFAULT_CSS = css("Pedir", "Pedir #campo { margin-top: 1; }")

    def __init__(self, titulo: str, valor: str = "", dica: str = "") -> None:
        super().__init__()
        self.titulo, self.valor, self.dica = titulo, valor, dica

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = self.titulo
            if self.dica:
                yield Static(Text(self.dica), classes="nota")
            yield Input(self.valor, id="campo", compact=True)
            with Horizontal(id="botoes"):
                yield Botao("salvar", id="ok", classes="cheio")
                yield Botao("cancelar", id="nao", classes="vazado")

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.dismiss(ev.value.strip())

    def apertou(self, bid: str) -> None:
        self.dismiss(self.query_one("#campo", Input).value.strip() if bid == "ok" else None)


# ---------------------------------------------------------------- menus em lista
class MenuLista(Dialogo):
    """Diálogo com uma lista de opções: (id, rótulo, tecla, ícone, vermelho). Enter, clique ou a tecla escolhem."""

    DEFAULT_CSS = css("MenuLista", "MenuLista #opcoes { height: auto; max-height: 24; margin-top: 1; }")

    def __init__(self, titulo: str, opcoes: list, nota: str = "", largura: int = 46) -> None:
        super().__init__()
        self.titulo, self.opcoes, self.nota, self.largura = titulo, opcoes, nota, largura

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = self.titulo
            c.styles.width = self.largura
            yield Lista(self._linha, selecionavel=lambda o: bool(o and o[0]), cursor_sem_foco=True, id="opcoes", classes="-auto")
            if self.nota:
                yield Static(self.nota, classes="nota")

    def on_mount(self) -> None:
        l = self.query_one("#opcoes", Lista)
        l.definir(self.opcoes)
        l.focus()

    def _linha(self, o, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        if not o or not o[0]:
            return [Text("")]
        oid, rot, tecla, icone, vermelho = (list(o) + ["", "", False])[:5]
        cor = a.cor("red") if vermelho else a.cor("forte") if e.destacado else a.cor("texto")
        barra = Text("▌", style=a.cor("accent")) if e.destacado else Text(" ")
        return [barra + colunas([(Text(icone, style=a.cor("red") if vermelho else a.cor("mudo")), 2, "left"),
                                 (Text(rot, style=cor), 0, "left"), (Text(tecla, style=a.cor("mudo")), 5, "right")], e.largura - 1)]

    @on(Lista.Escolhido, "#opcoes")
    def _escolheu(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.dismiss(ev.item[0])

    def on_key(self, ev: events.Key) -> None:
        for o in self.opcoes:
            if o and len(o) > 2 and o[2] and o[2] not in ("enter",) and ev.character == o[2]:
                ev.stop()
                self.dismiss(o[0])
                return


class MenuConta(MenuLista):
    def __init__(self) -> None:
        super().__init__("conta", [("config", "configurações", "", "◆"), ("dispositivos", "tocar em", "d", ic("computer")),
                                   ("recentes", "tocadas recentemente", "", ic("duracao")), ("top", "mais ouvidos", "", ic("nota")),
                                   None, ("verificar", "verificar configuração", "", ic("ok")),
                                   ("sair", "sair da conta", "", ic("remover"), True)], largura=40)


class Opcoes(MenuLista):
    """o ou botão direito: as opções do item."""

    def __init__(self, itens: list[Item], fixados: list[str], extra: list | None = None) -> None:
        i = itens[0]
        faixa = i.tipo in ("track", "episode")
        ops: list = []
        if faixa:
            ops += [("tocar", "tocar agora", "enter", ic("tocar")), ("seguir", "tocar a seguir", "f", ic("a_seguir")),
                    ("curtir", "curtir", "c", ic("nao_curtida")), ("playlist", "adicionar à playlist  ›", "p", ic("adicionar")), None]
            if i.tipo == "track":
                ops += [("artista", "ir para o artista", "a", ic("artist")), ("album", "ir para o álbum", "", ic("album"))]
            ops += [("link", "copiar link", "y", ic("link"))]
        else:
            ops += [("abrir", "abrir", "enter", ic(i.tipo if i.tipo in ("playlist", "album", "artist", "show") else "playlist")),
                    ("tocar", "tocar", "t", ic("tocar")), ("curtir", "seguir ou salvar na biblioteca", "c", ic("nao_curtida")), None]
            if i.tipo == "album":
                ops.append(("artista", "ir para o artista", "a", ic("artist")))
            ops.append(("link", "copiar link", "y", ic("link")))
            if i.tipo != "curtidas":
                ops.append(("fixar", "desafixar da biblioteca" if i.uri in fixados else "fixar na biblioteca", "P", "⊼"))
                ops += [None, ("remover", "remover da biblioteca", "x", ic("remover"), True)]
        for e in extra or []:
            ops += [None, (e[0], e[1], e[2], ic("remover"), True)]
        titulo = i.nome if len(itens) == 1 else f"{len(itens)} itens"
        super().__init__(titulo, ops, largura=48)


# ---------------------------------------------------------------- ir para (ctrl+p)
def casar(alvo: str, q: str) -> list[int] | None:
    """Letras de q em ordem dentro de alvo (sem diferenciar maiúsculas). Devolve as posições ou None."""
    if not q:
        return []
    a, pos, j = alvo.lower(), [], 0
    qq = q.lower()
    k = a.find(qq)
    if k >= 0:
        return list(range(k, k + len(qq)))
    for c in qq:
        j = a.find(c, j)
        if j < 0:
            return None
        pos.append(j)
        j += 1
    return pos


class IrPara(Dialogo):
    DEFAULT_CSS = css("IrPara", """
    IrPara #caixa { width: 70; height: 26; }
    IrPara #linha-q { height: 1; }
    IrPara #seta { width: 2; color: $accent; }
    IrPara #q { width: 1fr; background: $background; padding: 0; }
    IrPara #conta-q { width: auto; color: $oma-mudo; }
    IrPara #res { height: 1fr; margin-top: 1; }
    """)
    BINDINGS = [Binding("escape", "cancelar", "fechar", priority=True), Binding("down", "descer", show=False),
                Binding("up", "subir", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "ir para"
            c.border_subtitle = "ctrl+p"
            with Horizontal(id="linha-q"):
                yield Static("›", id="seta")
                yield Input(placeholder="biblioteca, páginas e comandos", id="q", compact=True)
                yield Static("", id="conta-q")
            yield Lista(self._linha, selecionavel=lambda x: not isinstance(x, str), cursor_sem_foco=True, id="res")
            yield Static("", classes="pe", id="pe")

    def on_mount(self) -> None:
        self.query_one("#pe", Static).update(pe(self.app, [("↑↓", "escolher"), ("enter", "abrir"), ("t", "tocar (na lista)"),
                                                           ("esc", "fechar")]))
        self.query_one("#q", Input).focus()
        self.filtrar("")

    def fontes(self) -> list[tuple[str, list]]:
        a = self.app
        from oma_spotify.ui.biblioteca import CURTIDAS
        bib = [CURTIDAS] + list(a.dados_bib)
        grupos = [("playlists", [("item", i) for i in bib if i.tipo in ("playlist", "curtidas")]),
                  ("artistas", [("item", i) for i in bib if i.tipo == "artist"]),
                  ("álbuns", [("item", i) for i in bib if i.tipo == "album"]),
                  ("podcasts", [("item", i) for i in bib if i.tipo == "show"]),
                  ("páginas", [("pagina", {"t": "inicio"}, "início"), ("pagina", {"t": "recentes"}, "tocadas recentemente"),
                               ("pagina", {"t": "top"}, "mais ouvidos"), ("pagina", {"t": "config"}, "configurações")])]
        p = a.player
        prox_rep = {"off": "a lista toda", "context": "só esta faixa", "track": "desligado"}.get(p.repetir if p else "off", "a lista toda")
        cmds = [("comando", "repetir", f"repetir: {prox_rep}", "r"),
                ("comando", "aleatorio", f"aleatório: {'desligar' if p and p.aleatorio else 'ligar'}", "s"),
                ("comando", "nova_playlist_cmd", "nova playlist", "n"), ("comando", "tocar_em", "tocar em: escolher o aparelho", "d"),
                ("comando", "recarregar", "recarregar", "F5"), ("comando", "ajuda", "ajuda completa", "?")]
        grupos.append(("comandos", cmds))
        return grupos

    def filtrar(self, q: str) -> None:
        saida: list = []
        total = achados = 0
        for titulo, itens in self.fontes():
            bloco = []
            for x in itens:
                total += 1
                nome = x[1].nome if x[0] == "item" else x[2]
                pos = casar(nome, q)
                if pos is not None:
                    bloco.append((x, nome, pos))
            if bloco:
                if saida:
                    saida.append("")
                saida.append(titulo)
                saida += bloco[:8]
                achados += len(bloco)
        if q.strip():
            saida += ["", "no Spotify", (("buscar", q.strip()), f"buscar “{q.strip()}” no catálogo do Spotify", [])]
        self.query_one("#res", Lista).definir(saida, 0)
        self.query_one("#conta-q", Static).update(f"{achados} de {total}" if q else "")

    def _linha(self, x, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        if isinstance(x, str):
            return [Text(x, style=a.cor("mudo"))]
        fonte, nome, pos = x
        t = Text(nome, style=a.cor("forte") if e.destacado else a.cor("texto"), no_wrap=True)
        for p in pos:
            t.stylize(f"underline {a.cor('accent')}", p, p + 1)
        if fonte[0] == "item":
            i = fonte[1]
            icone = ic("curtida") if i.tipo == "curtidas" else ic(i.tipo)
            dir_ = Text("tocando" if a.tocando_uri(i.uri) else {"playlist": "playlist", "artist": "artista", "album": "álbum",
                                                                 "show": "podcast", "curtidas": "playlist"}.get(i.tipo, ""),
                        style=a.cor("accent") if a.tocando_uri(i.uri) else a.cor("mudo"))
        elif fonte[0] == "comando":
            icone, dir_ = "›", Text(fonte[3], style=a.cor("mudo"))
        elif fonte[0] == "pagina":
            icone, dir_ = "→", Text("página", style=a.cor("mudo"))
        else:
            icone, dir_ = ic("buscar"), Text("")
        barra = Text("▌", style=a.cor("accent")) if e.destacado else Text(" ")
        return [barra + colunas([(Text(icone, style=a.cor("mudo")), 2, "left"), (t, 0, "left"), (dir_, 12, "right")], e.largura - 1)]

    @on(Input.Changed, "#q")
    def _mudou(self, ev: Input.Changed) -> None:
        ev.stop()
        self.filtrar(ev.value)

    @on(Input.Submitted, "#q")
    def _enter(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.escolher(False)

    @on(Lista.Escolhido, "#res")
    def _escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.escolher(False)

    def escolher(self, tocar: bool) -> None:
        x = self.query_one("#res", Lista).item_atual()
        if x is None or isinstance(x, str):
            return
        fonte = x[0]
        if fonte[0] == "item":
            self.dismiss(("item", fonte[1], tocar))
        elif fonte[0] == "pagina":
            self.dismiss(("pagina", fonte[1], False))
        elif fonte[0] == "comando":
            acao = "nova_playlist_global" if fonte[1] == "nova_playlist_cmd" else fonte[1]
            self.dismiss(("comando", acao, False))
        else:
            self.dismiss(("buscar", fonte[1], False))

    def action_descer(self) -> None:
        l = self.query_one("#res", Lista)
        j = l._proximo(l.cursor, 1)
        if j >= 0:
            l.mover_cursor(j)

    def action_subir(self) -> None:
        l = self.query_one("#res", Lista)
        j = l._proximo(l.cursor, -1)
        if j >= 0:
            l.mover_cursor(j)

    def on_key(self, ev: events.Key) -> None:
        if self.focused is self.query_one("#res") and ev.character:
            if ev.character == "t":
                ev.stop()
                self.escolher(True)
            elif ev.is_printable and ev.character not in "jkgG":
                ev.stop()
                q = self.query_one("#q", Input)
                q.focus()
                q.insert_text_at_cursor(ev.character)


# ---------------------------------------------------------------- tocar em (d)
class TocarEm(Dialogo):
    DEFAULT_CSS = css("TocarEm", """
    TocarEm #caixa { width: 72; }
    TocarEm #aparelhos { height: auto; max-height: 12; margin-top: 1; }
    """)
    BINDINGS = [Binding("escape", "cancelar", "fechar", priority=True), Binding("left,h", "vol(-5)", show=False),
                Binding("right,l", "vol(5)", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "tocar em"
            c.border_subtitle = "d"
            yield Lista(self._linha, cursor_sem_foco=True, id="aparelhos", classes="-auto")
            yield Static("", classes="nota", id="nota-ap")
            yield Static("", classes="pe", id="pe")

    def on_mount(self) -> None:
        a = self.app
        self.query_one("#pe", Static).update(pe(a, [("enter", "tocar aqui"), ("←→", "volume"), ("esc", "fechar")]))
        self.query_one("#nota-ap", Static).update(Text(f"\n{ic('info')} só aparecem aparelhos com o Spotify aberto", style=a.cor("mudo")))
        self.pintar(a.dispositivos)
        a.carregar_dispositivos(lambda ds: self.is_mounted and self.pintar(ds))
        self.query_one("#aparelhos", Lista).focus()

    def pintar(self, ds: list) -> None:
        a = self.app
        linhas = list(ds)
        if not any(a.plugin.eh_dispositivo(d) for d in ds):
            linhas.append(("plugin", "OmaSpotify", "iniciar o player do plugin"))
        if not any(getattr(d, "tipo", "").lower() == "computer" for d in ds if not a.plugin.eh_dispositivo(d)):
            linhas.append(("pc", "Spotify do PC", "abrir o app de desktop"))
        l = self.query_one("#aparelhos", Lista)
        cur = l.cursor
        l.definir(linhas, cur if cur >= 0 else next((n for n, d in enumerate(ds) if d.ativo), 0))

    def _linha(self, d, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        barra = Text("▌", style=a.cor("accent")) if e.destacado else Text(" ")
        if isinstance(d, tuple):
            return [barra + colunas([(Text(ic("computer"), style=a.cor("mudo")), 2, "left"), (Text(d[1], style=a.cor("texto")), 18, "left"),
                                     (Text(d[2], style=a.cor("mudo")), 0, "left")], e.largura - 1)]
        p = a.player
        estado = "tocando" if d.ativo and p and p.tocando else "pausado" if d.ativo else "pronto"
        if d.volume is None:
            vol = Text("sem controle de volume", style=a.cor("mudo"))
        else:
            cheio = round(d.volume / 100 * 12)
            vol = Text.assemble((ic("volume") + " ", a.cor("mudo")), ("━" * cheio, a.cor("texto")), ("━" * (12 - cheio), a.cor("linha")),
                                (f" {d.volume:>3}", a.cor("mudo")))
        return [barra + colunas([(Text(de_aparelho(d.tipo), style=a.cor("accent") if d.ativo else a.cor("mudo")), 2, "left"),
                                 (Text(d.nome, style=f"bold {a.cor('forte')}" if d.ativo else a.cor("texto")), 18, "left"),
                                 (Text(estado, style=a.cor("accent") if estado == "tocando" else a.cor("mudo")), 9, "left"),
                                 (vol, 0, "left")], e.largura - 1)]

    @on(Lista.Escolhido, "#aparelhos")
    def _escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        a, d = self.app, ev.item
        self.dismiss(None)
        if isinstance(d, tuple):
            a.iniciar_plugin() if d[0] == "plugin" else a.abrir_spotify_pc()
        else:
            a.transferir(d)

    def action_vol(self, passo: int) -> None:
        d = self.query_one("#aparelhos", Lista).item_atual()
        if d is None or isinstance(d, tuple) or d.volume is None:
            return
        d.volume = max(0, min(100, d.volume + passo))
        self.query_one("#aparelhos", Lista).redesenhar()
        a = self.app
        if d.ativo and a.player is not None:
            a.player.volume = d.volume
            a._pintar()
        a.executar("Volume", a.cliente.volume, d.volume, d.id, recarregar=False)


# ---------------------------------------------------------------- adicionar à playlist (p)
class AdicionarPlaylist(Dialogo):
    DEFAULT_CSS = css("AdicionarPlaylist", """
    AdicionarPlaylist #caixa { width: 56; height: 22; }
    AdicionarPlaylist #linha-f { height: 1; margin-top: 1; }
    AdicionarPlaylist #lupa { width: 2; color: $oma-mudo; }
    AdicionarPlaylist #f { width: 1fr; background: $background; padding: 0; }
    AdicionarPlaylist #pls { height: 1fr; margin-top: 1; }
    """)
    BINDINGS = [Binding("escape", "cancelar", "fechar", priority=True), Binding("ctrl+f", "filtrar", show=False, priority=True),
                Binding("down", "descer", show=False), Binding("up", "subir", show=False)]

    def __init__(self, faixas: list[Item], playlists: list[Item]) -> None:
        super().__init__()
        self.faixas, self.playlists = faixas, playlists
        self.tem: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        n = len(self.faixas)
        with Vertical(id="caixa") as c:
            c.border_title = f"adicionar {n} faixas a…" if n > 1 else f"adicionar {self.faixas[0].nome} a…"
            c.border_subtitle = "p"
            with Horizontal(id="linha-f"):
                yield Static(ic("filtro"), id="lupa")
                yield Input(placeholder="filtrar", id="f", compact=True)
            yield Lista(self._linha, selecionavel=lambda x: not isinstance(x, str), cursor_sem_foco=True, id="pls")
            yield Static("", classes="pe", id="pe")

    def on_mount(self) -> None:
        a = self.app
        self.query_one("#pe", Static).update(pe(a, [("enter", "adicionar"), ("ctrl+f", "filtrar"), ("esc", "fechar")]))
        self.pintar()
        self.query_one("#pls", Lista).focus()
        uris = {f.uri for f in self.faixas}
        pls = list(self.playlists)[:24]

        def contar():
            r = {}
            for p in pls:
                try:
                    r[p.id] = sum(1 for x in {i.uri for i in a.itens_da_playlist(p.id)} if x in uris)
                except Exception:
                    continue
            return r

        def depois(r, erro):
            if r and self.is_mounted:
                self.tem = r
                self.query_one("#pls", Lista).redesenhar()
        a.em_thread(contar, depois)

    def pintar(self) -> None:
        q = self.query_one("#f", Input).value.strip().lower()
        pls = [p for p in self.playlists if not q or q in p.nome.lower()]
        self.query_one("#pls", Lista).definir([("nova", None)] + pls + ["", "só playlists suas ou colaborativas"], 1 if pls else 0)

    def _linha(self, x, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        if isinstance(x, str):
            return [Text(x, style=a.cor("mudo"))]
        barra = Text("▌", style=a.cor("accent")) if e.destacado else Text(" ")
        if isinstance(x, tuple):
            return [barra + Text.assemble((ic("adicionar") + " ", a.cor("accent")), ("nova playlist", a.cor("forte") if e.destacado else a.cor("texto")))]
        k = self.tem.get(x.id, 0)
        total = len(self.faixas)
        tem = "" if not k else "já tem" if total == 1 else f"já tem as {k}" if k == total else f"já tem {k}"
        ja = bool(k) and k == total
        est = a.cor("mudo") if ja and not e.destacado else f"bold {a.cor('forte')}" if e.destacado else a.cor("texto")
        return [barra + colunas([(Text(x.nome, style=est), 0, "left"), (Text(tem, style=a.cor("mudo")), 12, "right")], e.largura - 1)]

    @on(Input.Changed, "#f")
    def _f(self, ev: Input.Changed) -> None:
        ev.stop()
        self.pintar()

    @on(Input.Submitted, "#f")
    def _f_ok(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.query_one("#pls", Lista).focus()

    def action_filtrar(self) -> None:
        self.query_one("#f", Input).focus()

    def action_descer(self) -> None:
        if isinstance(self.focused, Input):
            self.query_one("#pls", Lista).focus()
        else:
            self.query_one("#pls", Lista).action_cursor(1)

    def action_subir(self) -> None:
        if not isinstance(self.focused, Input):
            l = self.query_one("#pls", Lista)
            if l.cursor <= 0:
                self.query_one("#f", Input).focus()
            else:
                l.action_cursor(-1)

    @on(Lista.Escolhido, "#pls")
    def _escolhido(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        x = ev.item
        self.dismiss("nova" if isinstance(x, tuple) else x.id)


# ---------------------------------------------------------------- teclas (ctrl+espaço, F1) e ajuda (?)
JANELAS_TECLAS = [("ctrl+←↑↓→ / hjkl", "janela ao lado"), ("tab  shift+tab", "próxima / anterior"),
                  ("[  ]", "esconde biblioteca / tocando"), ("z", "zoom na janela")]
FAIXA_TECLAS = [("enter  t", "tocar"), ("f  c  p", "fila · curtir · playlist"), ("a  y  o", "artista · link · opções"),
                ("x  u", "remover · desfazer"), ("P", "fixar na biblioteca")]
PLAYER_TECLAS = [("espaço", "tocar / pausar"), (",  .", "anterior / próxima"), ("shift+←→", "-5 s / +5 s"), ("-  +", "volume"),
                 ("s  r", "aleatório · repetir"), ("m", "mudo"), ("d", "tocar em")]


class Teclas(Dialogo):
    DEFAULT_CSS = css("Teclas", """
    Teclas #caixa { width: 104; }
    Teclas #cols { height: auto; margin-top: 1; }
    Teclas .col { width: 1fr; height: auto; text-wrap: nowrap; text-overflow: ellipsis; }
    """)
    BINDINGS = [Binding("escape,q", "cancelar", "fechar", priority=True), Binding("question_mark", "ajuda", show=False)]

    def __init__(self, nome: str, janela) -> None:
        super().__init__()
        self.nome, self.janela = nome, janela

    def _bloco(self, titulo: str, linhas: list[tuple[str, str]]) -> Text:
        a = self.app
        t = Text(titulo + "\n", style=f"bold {a.cor('forte')}", no_wrap=True, overflow="ellipsis")
        for k, v in linhas:
            t.append(ajustar(Text(k, style=a.cor("accent")), 18))
            t.append(v + "\n", style=a.cor("texto"))
        return t

    def compose(self) -> ComposeResult:
        a = self.app
        nome = self.nome
        pg = a.query_one("#principal").vista.get("t") if nome == "principal" else ""
        sub = {"inicio": "início", "item": "playlist", "curtidas": "playlist", "busca": "busca"}.get(pg, pg)
        proprias = self.janela.teclas() if self.janela is not None and hasattr(self.janela, "teclas") else []
        esq = self._bloco("janelas", JANELAS_TECLAS)
        for tit, linhas in proprias:
            esq.append("\n")
            esq.append_text(self._bloco(tit, linhas))
        dir_ = self._bloco("faixa", FAIXA_TECLAS)
        dir_.append("\n")
        dir_.append_text(self._bloco("player", PLAYER_TECLAS))
        with Vertical(id="caixa") as c:
            c.border_title = f"teclas · {nome}" + (f" ({sub})" if sub else "")
            with Horizontal(id="cols"):
                yield Static(esq, classes="col")
                yield Static(dir_, classes="col")
            yield Static(pe(a, [("esc, q ou ctrl+espaço", "fecham"), ("?", "ajuda completa"), ("dentro do herdr", "use F1")]), classes="pe")

    def action_ajuda(self) -> None:
        self.dismiss(None)
        self.app.call_after_refresh(self.app.action_ajuda)


AJUDA = """[b]O modelo: três camadas[/b]
  Ctrl+setas ou Ctrl+h j k l   troca de janela, pela posição na tela
  setas ou h j k l             anda dentro da janela (linhas, colunas, botões e cartões)
  Alt+← →  (Alt+h l)           troca o que a janela mostra: a aba ou a página (voltar, avançar)
  Alt+↑ ↓  (Alt+k j)           move o item selecionado (playlist sua, sua fila)
  Shift+↑ ↓ marcam várias linhas; Shift+← → voltam ou avançam 5 s.

[b]Em qualquer janela (fora de campo de texto)[/b]
  Espaço          tocar ou pausar               ,  .     anterior, próxima
  -  +            volume -5, +5                 m        mudo
  s               aleatório                     r        repetir: desligado, lista, faixa
  c               curtir o item em foco         /        buscar no Spotify
  Ctrl+p          ir para…                      0        Músicas Curtidas
  1 a 9           o item fixado com o número    d        tocar em (aparelhos)
  z               zoom na janela (palco no Tocando)
  [  ]            esconde ou mostra a Biblioteca, o Tocando (gavetas em tela estreita)
  Tab Shift+Tab   próxima, anterior janela      Ctrl+Espaço ou F1   teclas da janela
  ?               esta ajuda                    F5       recarregar
  Esc             fecha diálogo, gaveta ou zoom; limpa a seleção e a busca
  q               sair (a música continua tocando)

[b]Num item (faixa, álbum, playlist, artista, episódio)[/b]
  Enter  abre ou toca     t  toca sem abrir      f  tocar a seguir (sua fila)
  p      adicionar à playlist                     a  ir para o artista
  y      copiar o link    o  opções (botão direito)
  P      fixar ou desafixar na biblioteca (ganha um número de 1 a 9)
  x      remover da playlist ou da fila; da biblioteca, pede confirmação
  u      desfaz a última remoção ou movimento
  Ctrl+f filtra a lista   g G (Home End) topo, fim

[b]Mouse[/b]
  Clique foca e seleciona; clique de novo ou duplo clique abre ou toca. Botão direito abre as opções.
  A roda rola; em cima da barra de progresso volta e avança 5 s; em cima do volume muda de 5 em 5.
  Na barra, o clique pula para o ponto e arrastar o ● procura. Arrastar a divisa muda a largura.
  Clique nas abas do título (fila · letra) troca a aba. Clique na trilha do topo volta para a página.

[b]Cuidados[/b]
  Em alguns terminais Ctrl+j chega como Enter e Ctrl+h como Backspace: use Ctrl com as setas.
  Dentro do herdr, Ctrl+Espaço é o prefixo dele: use F1."""


class AjudaCompleta(Dialogo):
    DEFAULT_CSS = css("AjudaCompleta", """
    AjudaCompleta #caixa { width: 100; height: 90%; }
    AjudaCompleta #rolar { height: 1fr; margin-top: 1; }
    """)
    BINDINGS = [Binding("escape,q,question_mark", "cancelar", "fechar", priority=True)]

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa") as c:
            c.border_title = "ajuda completa"
            c.border_subtitle = "esc fecha"
            with VerticalScroll(id="rolar"):
                yield Static(AJUDA)

    def on_mount(self) -> None:
        self.query_one("#rolar").focus()
