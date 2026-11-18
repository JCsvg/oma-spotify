"""Área central: Início, páginas de playlist, álbum e artista, listas, busca, dispositivos e configurações."""

from __future__ import annotations

from dataclasses import asdict

from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Button, Label, Static

from oma_spotify.services.modelos import ErroSpotify, Item, mmss
from oma_spotify.ui.capa import Capa
from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import Tabela

CONTEXTOS = ("album", "playlist", "artist", "show")
TIPO = {"track": "Faixa", "album": "Álbum", "artist": "Artista", "playlist": "Playlist", "show": "Podcast", "episode": "Episódio",
        "curtidas": "Playlist"}
CATS_BUSCA = (("tudo", "Tudo"), ("track", "Músicas"), ("album", "Álbuns"), ("artist", "Artistas"), ("playlist", "Playlists"),
              ("show", "Podcasts"))
CATS_TOP = (("tracks", "Faixas"), ("artists", "Artistas"))
PERIODOS = (("short_term", "últimas 4 semanas"), ("medium_term", "últimos 6 meses"), ("long_term", "desde sempre"))


def serializar(i: Item) -> dict:
    return asdict(i)


def item_de_dict(d: dict) -> Item | None:
    try:
        return Item(**{k: v for k, v in d.items() if k in Item.__dataclass_fields__})
    except TypeError:
        return None


# ---------------------------------------------------------------- cartas
class CartaCapa(Widget, can_focus=True):
    """Capa com nome e subtítulo. Clique ou Enter abre, `t` toca."""

    DEFAULT_CSS = """
    CartaCapa { width: 20; height: 11; padding: 0 1; }
    CartaCapa.rapida { width: 1fr; height: 3; padding: 0; background: $surface; }
    CartaCapa:hover { background: $accent 12%; }
    CartaCapa:focus { background: $accent 30%; text-style: bold; }
    """
    BINDINGS = [Binding("enter", "abrir", "Abrir"), Binding("t", "tocar", "Tocar")]

    def __init__(self, item: Item, rapida: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.item = item
        self.rapida = rapida
        self.set_class(rapida, "rapida")

    def render(self):
        a = self.app
        if self.rapida:
            thumb = a.capas.texto(self.item, 6, 3, self.refresh, a.cor("accent")) if self.item.tipo != "curtidas" else a.miniatura_curtidas()
            g = Table.grid(padding=(0, 1), expand=True)
            g.add_column(width=6)
            g.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
            g.add_row(thumb, Text("\n" + self.item.nome, style="bold"))
            return g
        t = a.capas.texto(self.item, 18, 8, self.refresh, a.cor("accent"))
        t.append("\n")
        t.append(Text(self.item.nome, style="bold", no_wrap=True, overflow="ellipsis"))
        t.append("\n")
        sub = self.item.sub or TIPO.get(self.item.tipo, "")
        t.append(Text(sub, style=a.cor("muted"), no_wrap=True, overflow="ellipsis"))
        return t

    def on_click(self) -> None:
        self.focus()
        self.action_abrir()

    def action_abrir(self) -> None:
        if self.item.tipo in CONTEXTOS or self.item.tipo == "curtidas":
            self.app.abrir_item(self.item)
        else:
            self.app.tocar_item(self.item)

    def action_tocar(self) -> None:
        self.app.tocar_item(self.item)


# ---------------------------------------------------------------- início
class VistaInicio(NavegacaoMixin, VerticalScroll):
    NOME = "Início"
    RODAPE = ("abrir", "tocar")
    DEFAULT_CSS = """
    VistaInicio { padding: 0 1; }
    VistaInicio .secao { text-style: bold; margin: 1 0 0 0; }
    VistaInicio #rapido { layout: grid; grid-size: 2; grid-gutter: 0 1; height: auto; }
    VistaInicio .carrossel { height: 11; overflow-x: auto; overflow-y: hidden; }
    VistaInicio .vazio { color: $text-muted; margin: 1 0; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.dados: dict = {}

    def compose(self) -> ComposeResult:
        yield Label("Início", classes="secao")
        yield Static("", id="aviso-inicio", classes="vazio")

    def focar_entrada(self) -> None:
        for w in self.query(CartaCapa):
            w.focus()
            return
        self.focus()  # ainda carregando: o foco fica na própria área

    async def mostrar(self, dados: dict) -> None:
        """dados: rapido (lista), secoes [(titulo, itens)]."""
        self.dados = dados
        await self.query(".dinamico").remove()
        rapido = dados.get("rapido", [])
        aviso = self.query_one("#aviso-inicio", Static)
        if not rapido and not any(i for _, i in dados.get("secoes", [])):
            aviso.update(Text("Ainda não há nada por aqui. Toque algo, curta músicas ou crie playlists e o Início se enche.\n"
                              "A API do Spotify não tem feed Home nem novos lançamentos: o Início usa só a sua biblioteca."))
            return
        aviso.update("")
        if rapido:
            grade = Vertical(*[CartaCapa(i, rapida=True) for i in rapido[:8]], id="rapido", classes="dinamico")
            grade.styles.layout = "grid"
            grade.styles.grid_size_columns = 4 if self.app.size.width >= 150 else 2
            self.mount(grade)
        for titulo, itens in dados.get("secoes", []):
            if not itens:
                continue
            self.mount(Label(titulo, classes="secao dinamico"))
            self.mount(Horizontal(*[CartaCapa(i) for i in itens[:20]], classes="carrossel dinamico"))


# ---------------------------------------------------------------- listas
class VistaLista(NavegacaoMixin, Vertical):
    """Página com cabeçalho (capa, título, tocar) e tabela. Serve a playlist, álbum, artista, curtidas, fila, busca..."""

    NOME = "Lista"
    RODAPE = ("select_cursor", "tocar_sel", "fila_sel", "curtir_sel")
    DEFAULT_CSS = """
    VistaLista { padding: 0 1; }
    VistaLista #cab { height: auto; margin-bottom: 1; }
    VistaLista #cab-txt { width: 1fr; height: auto; padding-left: 2; }
    VistaLista #tipo { color: $text-muted; }
    VistaLista #titulo-v { text-style: bold; color: $accent; }
    VistaLista #botoes-cab { height: 3; margin-top: 1; }
    VistaLista #botoes-cab Button { margin-right: 1; }
    VistaLista #chips-v { height: 1; margin-bottom: 1; }
    VistaLista #chips-v Button { margin-right: 1; }
    VistaLista #chips-v Button.ligado { background: $accent; color: $background; text-style: bold; }
    VistaLista #toolbar { height: 1; margin-bottom: 1; }
    VistaLista #toolbar Button { margin-right: 1; }
    VistaLista #vazio { height: 1fr; content-align: center middle; text-align: center; color: $text-muted; }
    """
    BINDINGS = [
        Binding("t", "tocar_sel", "Tocar"),
        Binding("a", "fila_sel", "Fila"),
        Binding("c", "curtir_sel", "Curtir"),
        Binding("m", "para_playlist", "+Playlist", show=False),
        Binding("d", "remover_sel", "Remover", show=False),
        Binding("o", "abrir_sel", "Abrir", show=False),
        Binding("ctrl+t", "tocar_tudo", "Tocar tudo", show=False),
        Binding("f5", "atualizar", "Atualizar", show=False),
    ]
    COLUNAS = ("#", "Título", "De", "Álbum / tipo", "Duração")

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(**kw)
        self.vista = vista
        self.item = item_de_dict(vista["item"]) if vista.get("item") else None
        self.itens: list = []
        self.visiveis: list = []
        self.curtidos: set[str] = set()
        self.item_curtido = False
        self.resultados: dict = {}
        self.erro = ""
        self.carregado = False
        self.linha_salva = int(vista.get("linha", 0) or 0)
        t = vista["t"]
        self.cat = vista.get("cat") or ("tudo" if t == "busca" else "tracks")
        self.per = int(vista.get("per", 1) or 1)

    # ------------------------------------------------------------ meta
    def titulo(self) -> tuple[str, str, str]:
        t, i = self.vista["t"], self.item
        if t == "item" and i:
            return TIPO.get(i.tipo, ""), i.nome, i.sub
        return {"curtidas": ("Playlist", "Músicas Curtidas", "Suas faixas salvas"),
                "fila": ("", "Fila", "A seguir"), "recentes": ("", "Tocados recentemente", "Suas últimas 50 faixas"),
                "top": ("", "Mais ouvidos", PERIODOS[self.per][1]),
                "busca": ("Busca", f"Resultados para “{self.vista.get('q', '')}”", ""),
                "dispositivos": ("", "Dispositivos", "Onde o Spotify pode tocar")}.get(t, ("", "", ""))

    def chips(self):
        t = self.vista["t"]
        return CATS_BUSCA if t == "busca" else CATS_TOP if t == "top" else ()

    def compose(self) -> ComposeResult:
        tipo, titulo, sub = self.titulo()
        grande = self.app.size.height >= 34
        with Horizontal(id="cab"):
            yield Capa(16 if grande else 10, 8 if grande else 5, id="capa-v")
            with Vertical(id="cab-txt"):
                yield Static(Text(tipo.upper(), style="dim"), id="tipo")
                yield Static(Text(titulo), id="titulo-v")
                yield Static(Text(sub, style=self.app.cor("muted")), id="sub-v")
                with Horizontal(id="botoes-cab"):
                    yield Button("▶ Tocar", id="tocar", variant="primary")
                    if self.item is not None:
                        yield Button("♡ Salvar", id="salvar")
                    if self.vista["t"] == "top":
                        yield Button("Período", id="periodo")
        if self.chips():
            with Horizontal(id="chips-v"):
                for cid, rot in self.chips():
                    yield Button(rot, id=f"c-{cid}", compact=True)
        with Horizontal(id="toolbar"):
            yield Button("Fila", id="fila", compact=True)
            yield Button("♥ Curtir", id="curtir", compact=True)
            yield Button("+ Playlist", id="playlist", compact=True)
            yield Button("Remover", id="remover", compact=True)
            yield Button("Atualizar", id="atualizar", compact=True)
        yield Tabela(id="tabela")
        yield Static("", id="vazio")

    def on_mount(self) -> None:
        try:
            self._montado()
        except NoMatches:
            pass  # a vista foi trocada antes de terminar de montar

    def _montado(self) -> None:
        t = self.query_one("#tabela", Tabela)
        t.add_columns(*self.colunas())
        self.query_one("#vazio").display = False
        capa = self.query_one("#capa-v", Capa)
        if self.item is not None:
            capa.definir(self.item)
        elif self.vista["t"] == "curtidas":
            capa.definir(Item("oma:curtidas", "curtidas", "Músicas Curtidas"))
        else:
            capa.definir(Item("oma:" + self.vista["t"], "playlist", self.titulo()[1]))
        self.query_one("#remover").display = bool(self.item and self.item.tipo == "playlist" and self.item.meu)
        if self.item is None:
            self.query_one("#curtir").display = self.vista["t"] not in ("dispositivos",)
        if self.vista["t"] in ("dispositivos",):
            for b in ("fila", "curtir", "playlist", "remover"):
                self.query_one(f"#{b}").display = False
            self.query_one("#tocar", Button).label = "Transferir"
            self.query_one("#atualizar", Button).display = True
        self._marcar_chips()
        self.recarregar()

    def colunas(self) -> tuple:
        return ("", "Dispositivo", "Tipo", "Volume", "") if self.vista["t"] == "dispositivos" else self.COLUNAS

    def _marcar_chips(self) -> None:
        for cid, _ in self.chips():
            self.query_one(f"#c-{cid}", Button).set_class(self.cat == cid, "ligado")

    def focar_entrada(self) -> None:
        t = self.query_one("#tabela", Tabela)
        (t if t.display and t.row_count else self.query_one("#tocar", Button)).focus()

    # ------------------------------------------------------------ dados
    def carregar(self, c) -> list:
        t, i = self.vista["t"], self.item
        if t == "item":
            if i.tipo == "playlist":
                return c.itens_playlist(i.id)
            if i.tipo == "album":
                return c.faixas_do_album(i.id, i.nome)
            if i.tipo == "artist":
                return c.albuns_do_artista(i.id)
            if i.tipo == "show":
                return c.episodios_do_show(i.id)
            return []
        if t == "curtidas":
            return c.curtidas()
        if t == "fila":
            return c.fila()
        if t == "recentes":
            return c.recentes()
        if t == "top":
            return c.mais_ouvidos(self.cat, PERIODOS[self.per][0])
        if t == "dispositivos":
            return c.dispositivos()
        if t == "busca":
            self.resultados = c.buscar(self.vista.get("q", ""))
            return self.da_categoria()
        return []

    def da_categoria(self) -> list:
        if self.cat == "tudo":
            return [x for k in ("track", "album", "artist", "playlist", "show") for x in self.resultados.get(k, [])]
        return self.resultados.get(self.cat, [])

    def recarregar(self) -> None:
        if not self.app.conectado:
            return
        c = self.app.cliente

        def trabalho():
            itens = self.carregar(c)
            vivos, salvo = set(), False
            tracks = [i.uri for i in itens if getattr(i, "tipo", "") == "track"]
            for n in range(0, len(tracks), 40):
                try:
                    vivos |= {u for u, ok in zip(tracks[n:n + 40], c.curtido(tracks[n:n + 40])) if ok}
                except ErroSpotify:
                    break
            if self.item is not None and self.item.tipo in ("playlist", "album", "artist", "show"):
                try:
                    salvo = bool(c.curtido([self.item.uri])[0])
                except (ErroSpotify, IndexError):
                    salvo = False
            return itens, vivos, salvo

        def depois(r, erro):
            if not self.is_mounted:
                return
            try:
                self._aplicar(r, erro)
            except NoMatches:
                pass  # a vista foi trocada enquanto os dados chegavam
        self.app.em_thread(trabalho, depois)

    def _aplicar(self, r, erro) -> None:
        if True:
            if erro:
                self.erro, self.itens, self.curtidos = str(erro), [], set()
                if erro.sem_login:
                    self.app.pedir_login(str(erro))
            else:
                self.erro = ""
                self.itens, self.curtidos, self.item_curtido = r
            self.carregado = True
            self.mostrar()

    def mostrar(self) -> None:
        t = self.query_one("#tabela", Tabela)
        self.visiveis = self.itens
        antes = t.cursor_row if t.row_count else 0
        t.clear()
        eh_dev = self.vista["t"] == "dispositivos"
        for n, i in enumerate(self.visiveis, 1):
            t.add_row(*(self.linha_dev(i) if eh_dev else self.linha(i, n)), key=str(n - 1))
        vazio = self.query_one("#vazio", Static)
        vazio.display = not self.visiveis
        t.display = bool(self.visiveis)
        if not self.visiveis:
            vazio.update(Text(self.erro or self.msg_vazio()))
        elif self.linha_salva or antes:
            t.move_cursor(row=min(self.linha_salva or antes, len(self.visiveis) - 1), animate=False)
            self.linha_salva = 0
        n_tracks = sum(1 for i in self.visiveis if getattr(i, "tipo", "") in ("track", "episode"))
        if n_tracks and self.vista["t"] in ("item", "curtidas", "recentes", "top"):
            dur = sum(i.dur_ms for i in self.visiveis)
            base = self.titulo()[2]
            self.query_one("#sub-v", Static).update(Text(" • ".join(x for x in (base, f"{n_tracks} faixas", mmss(dur) if dur else "") if x),
                                                         style=self.app.cor("muted")))
        if self.item is not None and self.query("#salvar"):
            self.query_one("#salvar", Button).label = "♥ Salvo" if self.item_curtido else "♡ Salvar"

    def msg_vazio(self) -> str:
        return {"fila": "A fila está vazia. Adicione faixas com a tecla a, em qualquer lista.",
                "busca": "Nada encontrado. Tente outra palavra.", "dispositivos": "Nenhum dispositivo encontrado. Abra o Spotify no PC ou no celular.",
                "recentes": "Nada tocado recentemente.", "top": "Ainda não há dados de mais ouvidos para você.",
                "curtidas": "Você ainda não curtiu nada. Aperte c em uma faixa."}.get(self.vista["t"], "Nada por aqui ainda.")

    def linha(self, i, n: int) -> tuple:
        marca = Text("♥" if i.uri in self.curtidos else str(n), style=self.app.cor("accent") if i.uri in self.curtidos else "")
        extra = i.extra if i.tipo == "track" else " ".join(x for x in (TIPO.get(i.tipo, ""), i.extra) if x)
        return (marca, Text(i.nome), Text(i.sub), Text(extra), Text(mmss(i.dur_ms) if i.dur_ms else ""))

    def linha_dev(self, d) -> tuple:
        return (Text("▶" if d.ativo else " ", style=self.app.cor("accent")), Text(d.nome), Text(d.tipo),
                Text(f"{d.volume}%" if d.volume is not None else ""), Text("ativo" if d.ativo else ""))

    def atual(self):
        t = self.query_one("#tabela", Tabela)
        if not self.visiveis or t.row_count == 0:
            return None
        return self.visiveis[min(t.cursor_row, len(self.visiveis) - 1)]

    # ------------------------------------------------------------ estado
    def estado_(self) -> dict:
        t = self.query_one("#tabela", Tabela)
        return {**self.vista, "linha": t.cursor_row, "cat": self.cat, "per": self.per}

    @on(Tabela.RowHighlighted)
    def _linha_mudou(self) -> None:
        self.app.guardar_vista(self)

    # ------------------------------------------------------------ ações
    @on(Tabela.RowSelected)
    def _enter(self, ev: Tabela.RowSelected) -> None:
        ev.stop()
        i = self.atual()
        if i is None:
            return
        if self.vista["t"] == "dispositivos":
            self.app.transferir(i)
        elif i.tipo in CONTEXTOS:
            self.app.abrir_item(i)
        else:
            self.tocar_linha(i)

    def tocar_linha(self, i) -> None:
        ctx = self.item.uri if self.item is not None and self.item.tipo in ("album", "playlist") else ""
        uris = [v.uri for v in self.visiveis if v.tipo in ("track", "episode")]
        self.app.tocar_item(i, ctx, uris if not ctx else None)

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        b = ev.button.id or ""
        if b.startswith("c-"):
            self.cat = b[2:]
            self._marcar_chips()
            if self.vista["t"] == "busca":
                self.itens = self.da_categoria()
                self.mostrar()
            else:
                self.recarregar()
            self.app.guardar_vista(self)
            return
        {"tocar": self.action_tocar_tudo, "salvar": self.action_salvar_pagina, "periodo": self.action_periodo,
         "fila": self.action_fila_sel, "curtir": self.action_curtir_sel, "playlist": self.action_para_playlist,
         "remover": self.action_remover_sel, "atualizar": self.action_atualizar}.get(b, lambda: None)()

    def action_atualizar(self) -> None:
        self.recarregar()

    def action_periodo(self) -> None:
        self.per = (self.per + 1) % 3
        self.query_one("#sub-v", Static).update(Text(PERIODOS[self.per][1], style=self.app.cor("muted")))
        self.recarregar()

    def action_tocar_tudo(self) -> None:
        t = self.vista["t"]
        if t == "dispositivos":
            d = self.atual()
            if d is not None:
                self.app.transferir(d)
        elif self.item is not None and self.item.tipo in CONTEXTOS:
            self.app.tocar_item(self.item)
        else:
            uris = [v.uri for v in self.visiveis if v.tipo in ("track", "episode")]
            if uris:
                self.app.tocar_uris(uris)
            else:
                self.app.notify("Não há faixas para tocar aqui.")

    def action_tocar_sel(self) -> None:
        i = self.atual()
        if i is None:
            return
        if self.vista["t"] == "dispositivos":
            self.app.transferir(i)
        elif i.tipo in CONTEXTOS:
            self.app.tocar_item(i)
        else:
            self.tocar_linha(i)

    def action_abrir_sel(self) -> None:
        i = self.atual()
        if i is not None and i.tipo in CONTEXTOS:
            self.app.abrir_item(i)

    def action_fila_sel(self) -> None:
        i = self.atual()
        if i is not None and i.tipo in ("track", "episode"):
            self.app.executar("Adicionar à fila", self.app.cliente.enfileirar, i.uri, ok=f"Na fila: {i.nome}")
        elif i is not None:
            self.app.notify("Só faixas e episódios vão para a fila.")

    def action_curtir_sel(self) -> None:
        i = self.atual()
        if i is None or self.vista["t"] == "dispositivos":
            return
        ja = i.uri in self.curtidos
        c = self.app.cliente

        def depois(ok):
            if ok:
                (self.curtidos.discard if ja else self.curtidos.add)(i.uri)
                self.mostrar()
                self.app.atualizar_curtidas()
        self.app.executar("Curtir", c.descurtir if ja else c.curtir, i.uri, ok=f"Removido: {i.nome}" if ja else f"Salvo: {i.nome}",
                          depois=depois, recarregar=False)

    def action_salvar_pagina(self) -> None:
        if self.item is None:
            return
        ja, c = self.item_curtido, self.app.cliente

        def depois(ok):
            if ok:
                self.item_curtido = not ja
                self.query_one("#salvar", Button).label = "♥ Salvo" if self.item_curtido else "♡ Salvar"
                self.app.carregar_biblioteca()
        self.app.executar("Salvar", c.descurtir if ja else c.curtir, self.item.uri,
                          ok="Removido da biblioteca" if ja else "Salvo na biblioteca", depois=depois, recarregar=False)

    def action_para_playlist(self) -> None:
        i = self.atual()
        if i is None or i.tipo not in ("track", "episode"):
            self.app.notify("Selecione uma faixa para adicionar a uma playlist.")
            return
        self.app.adicionar_a_playlist(i)

    def action_remover_sel(self) -> None:
        from oma_spotify.ui.dialogos import Confirmar
        i = self.atual()
        if i is None or not (self.item and self.item.tipo == "playlist" and self.item.meu):
            return

        def fim(ok):
            if ok:
                self.app.executar("Remover da playlist", self.app.cliente.remover_da_playlist, self.item.id, i.uri,
                                  ok=f"Removida: {i.nome}", depois=lambda s: self.recarregar(), recarregar=False)
        self.app.push_screen(Confirmar("Remover da playlist?", [f"{i.nome} sai de {self.item.nome}.",
                                                                 "A faixa continua no Spotify, só deixa de estar aqui."], "Remover"), fim)

    def acoes_do_rodape(self) -> list[str]:
        base = super().acoes_do_rodape()
        return base


# ---------------------------------------------------------------- área central
class AreaCentral(NavegacaoMixin, Vertical):
    NOME = "Centro"
    RODAPE = ("select", "tocar_sel")
    DEFAULT_CSS = "AreaCentral { width: 1fr; background: $surface; }"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.vista: dict = {"t": "inicio"}
        self.atual = None

    def zonas(self):
        return self.atual.zonas() if self.atual is not None and hasattr(self.atual, "zonas") else []

    def focar_entrada(self) -> None:
        self._focar_atual()

    def fileira(self):
        return self.atual.fileira() if self.atual is not None and hasattr(self.atual, "fileira") else []

    def acoes_do_rodape(self) -> list[str]:
        return self.atual.acoes_do_rodape() if self.atual is not None else []

    def texto_ajuda(self) -> str:
        return self.atual.texto_ajuda() if self.atual is not None and hasattr(self.atual, "texto_ajuda") else super().texto_ajuda()

    def mostrar(self, vista: dict, foco: bool = True) -> None:
        from oma_spotify.ui.setup import PaginaConfig
        if self.atual is not None:
            self.atual.remove()
        self.vista = vista
        t = vista["t"]
        if t == "inicio":
            w = VistaInicio()
        elif t == "config":
            w = PaginaConfig()
        else:
            w = VistaLista(vista)
        self.atual = w
        self.mount(w)
        if t == "inicio":
            self.app.carregar_inicio()
        if foco:
            self.call_after_refresh(self._focar_atual)

    def _focar_atual(self) -> None:
        try:
            if self.atual is not None:
                self.atual.focar_entrada()
        except NoMatches:
            pass
