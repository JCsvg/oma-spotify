"""Telas (abas) do oma-spotify."""

from __future__ import annotations

import time

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from oma_spotify.services.modelos import ErroSpotify, Item, mmss
from oma_spotify.ui.dialogos import Confirmar, EscolherPlaylist, Pedir
from oma_spotify.ui.navegacao import NavegacaoMixin, RodapeEnxuto
from oma_spotify.ui.widgets import Barra, Tabela

CONTEXTOS = ("album", "playlist", "artist", "show")


class Pagina(NavegacaoMixin, Vertical):
    ID = ""
    NOME = ""
    carregado = False

    def restaurar(self, d: dict) -> None: ...

    def recarregar(self) -> None: ...

    def salvar(self, d: dict) -> None:
        self.app.guardar_aba(self.ID, d)


class ListaItens(Pagina):
    """Lista de itens do Spotify com ações por tecla e por botão."""

    CATEGORIAS: tuple[tuple[str, str], ...] = ()
    BINDINGS = [
        Binding("enter", "tocar_item", "Tocar", key_display="Enter"),
        Binding("o", "abrir_item", "Abrir"),
        Binding("a", "enfileirar", "Fila"),
        Binding("c", "curtir_item", "Curtir"),
        Binding("p", "para_playlist", "Playlist", show=False),
        Binding("r", "remover_item", "Remover", show=False),
        Binding("slash", "filtrar", "Filtrar", key_display="/"),
        Binding("f5", "atualizar", "Atualizar", show=False),
    ]
    RODAPE = ("tocar_item", "abrir_item", "enfileirar", "curtir_item", "filtrar")
    BOTOES = (("tocar", "Tocar"), ("abrir", "Abrir"), ("fila", "Adicionar à fila"), ("curtir", "Curtir"),
              ("playlist", "Adicionar a playlist"), ("atualizar", "Atualizar"))
    VAZIO = "Nada por aqui ainda."
    COLUNAS = ("", "Nome", "De", "Álbum / info", "Tempo")

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.itens: list = []
        self.visiveis: list = []
        self.categoria = self.CATEGORIAS[0][0] if self.CATEGORIAS else ""
        self.curtidos: set[str] = set()
        self._linha_salva = 0
        self.contexto = ""  # uri da playlist/álbum aberto (tocar desde a faixa)
        self.erro = ""

    # ------------------------------------------------------------ montagem
    def compose(self) -> ComposeResult:
        yield from self.topo()
        with Horizontal(id="cats"):
            for cid, rot in self.CATEGORIAS:
                yield Button(rot, id=f"cat-{cid}", classes="cat")
        yield Tabela(id="tabela")
        yield Static("", id="vazio")
        with Horizontal(id="acoes"):
            for bid, rot in self.BOTOES:
                yield Button(rot, id=bid)

    def topo(self) -> ComposeResult:
        yield Input(placeholder="/ filtrar esta lista", id="filtro")

    def on_mount(self) -> None:
        t = self.query_one("#tabela", Tabela)
        t.add_columns(*self.COLUNAS)
        self.query_one("#vazio").display = False
        self.query_one("#cats").display = bool(self.CATEGORIAS)
        self._marcar_cats()

    def _marcar_cats(self) -> None:
        for cid, rot in self.CATEGORIAS:
            self.query_one(f"#cat-{cid}", Button).variant = "primary" if cid == self.categoria else "default"

    # ------------------------------------------------------------ dados
    def carregar(self, c) -> list:
        return []

    def recarregar(self) -> None:
        if not self.app.conectado:
            return
        self.carregado = False
        cat = self.categoria

        def trabalho():
            itens = self.carregar(self.app.cliente)
            vivos = set()
            if itens and all(getattr(i, "tipo", "") == "track" for i in itens):
                uris = [i.uri for i in itens]
                for n in range(0, len(uris), 40):
                    try:
                        for u, ok in zip(uris[n:n + 40], self.app.cliente.curtido(uris[n:n + 40])):
                            if ok:
                                vivos.add(u)
                    except ErroSpotify:
                        break
            return itens, vivos

        def depois(r, erro):
            if cat != self.categoria:
                return
            if erro:
                self.erro = str(erro)
                self.itens, self.curtidos = [], set()
                if erro.sem_login:
                    self.app.pedir_login(str(erro))
            else:
                self.erro = ""
                self.itens, self.curtidos = r
            self.carregado = True
            self.mostrar()

        self.app.em_thread(trabalho, depois)

    def mostrar(self) -> None:
        t = self.query_one("#tabela", Tabela)
        filtro = self.query_one("#filtro", Input).value.strip().lower() if self.query("#filtro") else ""
        self.visiveis = [i for i in self.itens if not filtro or filtro in self.texto(i).lower()]
        t.clear()
        for n, i in enumerate(self.visiveis):
            t.add_row(*self.linha(i), key=str(n))
        vazio = self.query_one("#vazio", Static)
        vazio.display = not self.visiveis
        t.display = bool(self.visiveis)
        if not self.visiveis:
            vazio.update(Text(self.erro or (f"Nenhum resultado para o filtro." if filtro else self.VAZIO)))
        elif self._linha_salva:
            t.move_cursor(row=min(self._linha_salva, len(self.visiveis) - 1), animate=False)
            self._linha_salva = 0

    def texto(self, i) -> str:
        return f"{i.nome} {i.sub} {i.extra}"

    def linha(self, i) -> tuple:
        marca = Text("♥ " if i.uri in self.curtidos else "  ", style=self.app.cor("accent"))
        return (marca, Text(i.nome), Text(i.sub), Text(i.extra), Text(mmss(i.dur_ms) if i.dur_ms else ""))

    def atual(self):
        t = self.query_one("#tabela", Tabela)
        if not self.visiveis or t.row_count == 0:
            return None
        return self.visiveis[min(t.cursor_row, len(self.visiveis) - 1)]

    # ------------------------------------------------------------ estado
    def estado_(self) -> dict:
        t = self.query_one("#tabela", Tabela)
        d = {"linha": t.cursor_row, "categoria": self.categoria}
        if self.query("#filtro"):
            d["filtro"] = self.query_one("#filtro", Input).value
        return d

    def restaurar(self, d: dict) -> None:
        if not isinstance(d, dict):
            return
        cat = d.get("categoria")
        if cat in [c for c, _ in self.CATEGORIAS]:
            self.categoria = cat
            self._marcar_cats()
        if self.query("#filtro") and isinstance(d.get("filtro"), str):
            self.query_one("#filtro", Input).value = d["filtro"]
        self._linha_salva = int(d.get("linha", 0) or 0)

    def _guardar(self) -> None:
        if self.is_mounted:
            self.salvar(self.estado_())

    @on(Tabela.RowHighlighted)
    def _linha_mudou(self) -> None:
        self._guardar()

    @on(Input.Changed, "#filtro")
    def _filtro_mudou(self) -> None:
        self.mostrar()
        self._guardar()

    @on(Input.Submitted, "#filtro")
    def _filtro_ok(self) -> None:
        self.focar_entrada()

    # ------------------------------------------------------------ ações
    @on(Tabela.RowSelected)
    def _selecionada(self) -> None:
        self.action_tocar_item()

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        if bid.startswith("cat-"):
            self.categoria = bid[4:]
            self._marcar_cats()
            self._guardar()
            self.mudou_categoria()
            return
        acao = {"tocar": self.action_tocar_item, "abrir": self.action_abrir_item, "fila": self.action_enfileirar,
                "curtir": self.action_curtir_item, "playlist": self.action_para_playlist,
                "remover": self.action_remover_item, "atualizar": self.action_atualizar}.get(bid)
        if acao:
            ev.stop()
            acao()
        else:
            self.botao_extra(bid)

    def mudou_categoria(self) -> None:
        self.recarregar()

    def botao_extra(self, bid: str) -> None: ...

    def action_atualizar(self) -> None:
        self.recarregar()

    def action_filtrar(self) -> None:
        self.call_after_refresh(self.query_one("#filtro", Input).focus)

    def action_tocar_item(self) -> None:
        i = self.atual()
        if i is not None:
            self.app.tocar_item(i, self.contexto, [v.uri for v in self.visiveis if v.tipo == "track"] if not self.contexto else None)

    def action_abrir_item(self) -> None:
        i = self.atual()
        if i is None:
            return
        if i.tipo in CONTEXTOS:
            self.app.abrir_item(i)
        else:
            self.app.notify("Só álbuns, playlists, artistas e podcasts abrem. Faixas tocam com Enter.")

    def action_enfileirar(self) -> None:
        i = self.atual()
        if i is not None and i.tipo in ("track", "episode"):
            self.app.executar("Adicionar à fila", self.app.cliente.enfileirar, i.uri, ok=f"Na fila: {i.nome}")
        elif i is not None:
            self.app.notify("Só faixas e episódios vão para a fila.")

    def action_curtir_item(self) -> None:
        i = self.atual()
        if i is None:
            return
        if i.tipo not in ("track", "album", "artist", "playlist", "show", "episode"):
            return
        ja = i.uri in self.curtidos

        def trabalho():
            c = self.app.cliente
            if i.tipo == "track":
                c.descurtir(i.uri) if ja else c.curtir(i.uri)
            else:
                (c.descurtir if ja else c.curtir)(i.uri)
        def depois(ok):
            if ok:
                (self.curtidos.discard if ja else self.curtidos.add)(i.uri)
                self.mostrar()
        self.app.executar("Curtir", trabalho, ok=f"Removido: {i.nome}" if ja else f"Salvo: {i.nome}", depois=depois, recarregar=False)

    def action_para_playlist(self) -> None:
        i = self.atual()
        if i is None or i.tipo not in ("track", "episode"):
            self.app.notify("Selecione uma faixa para adicionar a uma playlist.")
            return
        self.app.adicionar_a_playlist(i)

    def action_remover_item(self) -> None: ...

    def acoes_do_rodape(self) -> list[str]:
        base = super().acoes_do_rodape()
        return base


class PaginaPlaylists(ListaItens):
    ID, NOME = "playlists", "Playlists"
    VAZIO = "Nenhuma playlist ainda. Crie a primeira com o botão Nova playlist (tecla n)."
    COLUNAS = ("", "Playlist", "De", "Faixas", "")
    BOTOES = (("tocar", "Tocar playlist"), ("abrir", "Abrir"), ("nova", "Nova playlist"), ("atualizar", "Atualizar"))
    BINDINGS = ListaItens.BINDINGS + [Binding("n", "nova", "Nova playlist")]
    RODAPE = ("tocar_item", "abrir_item", "nova", "filtrar")

    def carregar(self, c):
        return c.playlists()

    def linha(self, i):
        return (Text("  "), Text(i.nome), Text(i.sub), Text(i.extra), Text(""))

    def botao_extra(self, bid: str) -> None:
        if bid == "nova":
            self.action_nova()

    def action_nova(self) -> None:
        def fim(nome):
            if nome:
                self.app.executar("Criar playlist", self.app.cliente.criar_playlist, nome, ok=f"Playlist criada: {nome}",
                                  depois=lambda ok: self.recarregar())
        self.app.push_screen(Pedir("Nova playlist", "", "Dê um nome. Ela nasce privada."), fim)


class PaginaBiblioteca(ListaItens):
    ID, NOME = "biblioteca", "Biblioteca"
    CATEGORIAS = (("curtidas", "Músicas curtidas"), ("albuns", "Álbuns"), ("artistas", "Artistas"), ("podcasts", "Podcasts"))
    VAZIO = "Nada salvo nesta seção."

    def carregar(self, c):
        return {"curtidas": c.curtidas, "albuns": c.albuns_salvos, "artistas": c.artistas_seguidos, "podcasts": c.podcasts}[self.categoria]()

    def mostrar(self) -> None:
        if self.categoria == "curtidas":
            self.curtidos = {i.uri for i in self.itens}
        super().mostrar()


class PaginaBusca(ListaItens):
    ID, NOME = "busca", "Busca"
    CATEGORIAS = (("track", "Faixas"), ("album", "Álbuns"), ("artist", "Artistas"), ("playlist", "Playlists"))
    VAZIO = "Digite o que procura e aperte Enter."
    BOTOES = ListaItens.BOTOES

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.q = ""
        self._foco_ao_chegar = False
        self.resultados: dict = {}

    def topo(self) -> ComposeResult:
        with Horizontal(id="barra"):
            yield Input(placeholder="Buscar músicas, álbuns, artistas, playlists", id="q")
            yield Button("Buscar", id="buscar", variant="primary")

    def action_filtrar(self) -> None:
        self.call_after_refresh(self.query_one("#q", Input).focus)

    def texto(self, i) -> str:
        return ""

    def estado_(self) -> dict:
        return {"linha": self.query_one("#tabela", Tabela).cursor_row, "categoria": self.categoria,
                "q": self.query_one("#q", Input).value}

    def restaurar(self, d: dict) -> None:
        super().restaurar(d)
        if isinstance(d, dict) and isinstance(d.get("q"), str):
            self.query_one("#q", Input).value = d["q"]
            self.q = d["q"]

    @on(Input.Changed, "#q")
    def _q_mudou(self) -> None:
        self._guardar()

    @on(Input.Submitted, "#q")
    def _buscar(self) -> None:
        self.q = self.query_one("#q", Input).value.strip()
        self._foco_ao_chegar = True
        self.recarregar()

    def botao_extra(self, bid: str) -> None:
        if bid == "buscar":
            self._buscar()

    def mudou_categoria(self) -> None:
        self.itens = self.resultados.get(self.categoria, [])
        self.mostrar()

    def recarregar(self) -> None:
        if not self.app.conectado or not self.q:
            if not self.q:
                self.mostrar()
            return

        def depois(r, erro):
            if erro:
                self.erro = str(erro)
                self.resultados = {}
            else:
                self.erro = ""
                self.resultados = r
            self.itens = self.resultados.get(self.categoria, [])
            self.carregado = True
            self.mostrar()
            if self._foco_ao_chegar and self.itens:
                self.query_one("#tabela", Tabela).focus()
            self._foco_ao_chegar = False
        self.app.em_thread(lambda: self.app.cliente.buscar(self.q), depois)

    def mostrar(self) -> None:
        if not self.q:
            self.erro = ""
        super().mostrar()

    def focar_entrada(self) -> None:
        t = self.query_one("#tabela", Tabela)
        (t if t.display and t.row_count else self.query_one("#q", Input)).focus()


class PaginaFila(ListaItens):
    ID, NOME = "fila", "Fila"
    VAZIO = "A fila está vazia. Adicione faixas com a tecla a, em qualquer lista."
    BOTOES = (("tocar", "Tocar agora"), ("curtir", "Curtir"), ("atualizar", "Atualizar"))
    RODAPE = ("tocar_item", "curtir_item", "atualizar", "filtrar")
    BINDINGS = ListaItens.BINDINGS

    def carregar(self, c):
        return c.fila()


class PaginaRecentes(ListaItens):
    ID, NOME = "recentes", "Recentes"
    VAZIO = "Nada tocado recentemente."

    def carregar(self, c):
        return c.recentes()


class PaginaTop(ListaItens):
    ID, NOME = "top", "Mais ouvidos"
    CATEGORIAS = (("tracks", "Faixas"), ("artists", "Artistas"))
    VAZIO = "Ainda não há dados de mais ouvidos para você."
    PERIODOS = (("short_term", "últimas 4 semanas"), ("medium_term", "últimos 6 meses"), ("long_term", "desde sempre"))
    BOTOES = ListaItens.BOTOES + (("periodo", "Período"),)

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.periodo = 1

    def on_mount(self) -> None:
        super().on_mount()
        self._rotulo()

    def _rotulo(self) -> None:
        self.query_one("#periodo", Button).label = f"Período: {self.PERIODOS[self.periodo][1]}"

    def carregar(self, c):
        return c.mais_ouvidos(self.categoria, self.PERIODOS[self.periodo][0])

    def botao_extra(self, bid: str) -> None:
        if bid == "periodo":
            self.periodo = (self.periodo + 1) % 3
            self._rotulo()
            self.recarregar()


class PaginaDispositivos(ListaItens):
    ID, NOME = "dispositivos", "Dispositivos"
    COLUNAS = ("", "Dispositivo", "Tipo", "Volume", "")
    VAZIO = "Nenhum dispositivo encontrado. Abra o Spotify no PC ou no celular."
    BOTOES = (("tocar", "Transferir para este"), ("pc", "Abrir o Spotify do PC"), ("atualizar", "Atualizar"))
    RODAPE = ("tocar_item", "abrir_pc", "atualizar", "filtrar")
    BINDINGS = [Binding("enter", "tocar_item", "Transferir", key_display="Enter"), Binding("s", "abrir_pc", "Abrir Spotify do PC"),
                Binding("f5", "atualizar", "Atualizar", show=False), Binding("slash", "filtrar", "Filtrar", key_display="/")]

    def carregar(self, c):
        return c.dispositivos()

    def texto(self, d) -> str:
        return d.nome

    def linha(self, d):
        return (Text("▶ " if d.ativo else "  ", style=self.app.cor("accent")), Text(d.nome), Text(d.tipo),
                Text(f"{d.volume}%" if d.volume is not None else ""), Text("ativo" if d.ativo else ""))

    def action_tocar_item(self) -> None:
        d = self.atual()
        if d is not None:
            self.app.transferir(d)

    def action_abrir_pc(self) -> None:
        self.app.abrir_spotify_pc()

    def botao_extra(self, bid: str) -> None:
        if bid == "pc":
            self.action_abrir_pc()


# ---------------------------------------------------------------- detalhe de álbum, playlist, artista
class ListaDetalhe(ListaItens):
    NOME = "Detalhe"
    BOTOES = (("tocar", "Tocar daqui"), ("tudo", "Tocar tudo"), ("fila", "Adicionar à fila"), ("curtir", "Curtir"),
              ("playlist", "Adicionar a playlist"), ("remover", "Remover da playlist"))
    VAZIO = "Vazio."

    def __init__(self, item: Item, **kw) -> None:
        super().__init__(**kw)
        self.pai = item
        self.contexto = item.uri if item.tipo in ("album", "playlist") else ""

    def on_mount(self) -> None:
        super().on_mount()
        self.query_one("#remover").display = self.pai.tipo == "playlist" and self.pai.meu
        self.recarregar()

    def carregar(self, c):
        p = self.pai
        if p.tipo == "playlist":
            return c.itens_playlist(p.id)
        if p.tipo == "album":
            return c.faixas_do_album(p.id, p.nome)
        if p.tipo == "artist":
            return c.albuns_do_artista(p.id)
        return []

    def salvar(self, d: dict) -> None: ...

    def botao_extra(self, bid: str) -> None:
        if bid == "tudo":
            self.app.tocar_item(self.pai)

    def action_remover_item(self) -> None:
        i = self.atual()
        if i is None or not (self.pai.tipo == "playlist" and self.pai.meu):
            return

        def fim(ok):
            if ok:
                self.app.executar("Remover da playlist", self.app.cliente.remover_da_playlist, self.pai.id, i.uri,
                                  ok=f"Removida: {i.nome}", depois=lambda s: self.recarregar())
        self.app.push_screen(Confirmar("Remover da playlist?", [f"{i.nome} sai de {self.pai.nome}.",
                                                                 "A faixa continua no Spotify, só deixa de estar aqui."], "Remover"), fim)

    def action_tocar_item(self) -> None:
        i = self.atual()
        if i is None:
            return
        if self.pai.tipo == "artist":
            self.app.tocar_item(i)
        elif self.pai.tipo == "playlist":
            self.app.tocar_item(i, self.pai.uri)
        else:
            self.app.tocar_item(i, self.contexto)


class TelaItens(Screen):
    BINDINGS = [Binding("escape", "voltar", "Voltar", priority=True)]

    def __init__(self, item: Item) -> None:
        super().__init__()
        self.item = item
        self.lista = ListaDetalhe(item, id="detalhe")

    def compose(self) -> ComposeResult:
        yield Label(Text(f"{self.item.nome}  ·  {self.item.sub}".strip(" ·")), id="titulo-detalhe")
        yield self.lista
        yield RodapeEnxuto()

    def on_mount(self) -> None:
        self.lista.focar_entrada()

    def action_voltar(self) -> None:
        if isinstance(self.focused, Input):
            self.lista.focar_entrada()
        else:
            self.dismiss(None)


# ---------------------------------------------------------------- tocando agora
class PaginaTocando(Pagina):
    ID, NOME = "tocando", "Tocando agora"
    BINDINGS = [
        Binding("n", "proxima", "Próxima"),
        Binding("b", "anterior", "Anterior"),
        Binding("s", "aleatorio", "Aleatório"),
        Binding("r", "repetir", "Repetir"),
        Binding("c", "curtir", "Curtir"),
        Binding("plus,equals", "volume(5)", "Volume +", show=False),
        Binding("minus", "volume(-5)", "Volume -", show=False),
    ]
    RODAPE = ("proxima", "anterior", "curtir", "aleatorio")
    REPETIR = {"off": "desligado", "context": "contexto", "track": "faixa"}

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.player = None
        self.curtido = False
        self._uri = ""
        self._buscando = False
        self._fila_em = 0.0

    def compose(self) -> ComposeResult:
        with Horizontal(id="topo"):
            yield Static("", id="capa")
            with Vertical(id="info"):
                yield Static("", id="titulo")
                yield Static("", id="artista")
                yield Static("", id="album")
                yield Static("", id="dispositivo")
        with Horizontal(id="linha-prog"):
            yield Static("0:00", id="t-pos")
            yield Barra(id="progresso")
            yield Static("0:00", id="t-dur")
        with Horizontal(id="linha-vol"):
            yield Static("Volume", id="rot-vol")
            yield Barra(id="volume")
            yield Static("", id="pct-vol")
        with Horizontal(id="acoes"):
            yield Button("Anterior", id="anterior")
            yield Button("Play / Pausa", id="play", variant="primary")
            yield Button("Próxima", id="proxima")
            yield Button("Aleatório: não", id="aleatorio")
            yield Button("Repetir: desligado", id="repetir")
            yield Button("Curtir", id="curtir")
            yield Button("Dispositivos", id="disp")
        yield Static("", id="aviso")
        yield Label("A seguir", id="rot-fila")
        yield Tabela(id="tabela")

    def on_mount(self) -> None:
        self.query_one("#tabela", Tabela).add_columns("Nome", "De")
        self.set_interval(0.25, self._tick)
        self.set_interval(2.0, self._poll)

    def focar_entrada(self) -> None:
        self.query_one("#play", Button).focus()

    def restaurar(self, d: dict) -> None: ...

    def ativa(self) -> bool:
        a = self.app
        return a.conectado and a.aba_atual() == self.ID and len(a.screen_stack) == 1

    # ------------------------------------------------------------ atualização
    def recarregar(self) -> None:
        self._poll(forcar=True)

    def _poll(self, forcar: bool = False) -> None:
        if not (forcar or self.ativa()) or self._buscando or not self.app.conectado:
            return
        self._buscando = True

        def trabalho():
            c = self.app.cliente
            p = c.player()
            fila = None
            curtido = None
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
            self._aplicar(r, erro)
        self.app.em_thread(trabalho, depois)

    def _aplicar(self, r, erro) -> None:
        aviso = self.query_one("#aviso", Static)
        if erro:
            aviso.update(Text(str(erro)))
            if erro.sem_login:
                self.app.pedir_login(str(erro))
            return
        p, fila, curtido = r
        self.player = p
        if curtido is not None:
            self.curtido = curtido
        if p is None or p.item is None:
            self._uri = ""
            aviso.update(Text("Nada tocando agora. Abra o Spotify no PC ou escolha um dispositivo na tela 6."))
        else:
            aviso.update("")
            self._uri = p.item.uri
        if fila is not None:
            self._fila_em = time.monotonic()
            t = self.query_one("#tabela", Tabela)
            t.clear()
            for n, i in enumerate(fila[:30]):
                t.add_row(Text(i.nome), Text(i.sub), key=str(n))
        self._pintar()

    def _pintar(self) -> None:
        p = self.player
        q = self.query_one
        if p is None or p.item is None:
            q("#titulo", Static).update(Text("Nada tocando"))
            for i in ("#artista", "#album", "#dispositivo"):
                q(i, Static).update("")
            q("#capa", Static).update(Text("\n  ♪\n"))
            q("#t-dur", Static).update("0:00")
            q("#progresso", Barra).definir(0)
            return
        it = p.item
        q("#titulo", Static).update(Text(it.nome, style="bold"))
        q("#artista", Static).update(Text(it.sub))
        q("#album", Static).update(Text(it.extra, style=self.app.cor("muted")))
        q("#dispositivo", Static).update(Text(f"em {p.dispositivo}" if p.dispositivo else "", style=self.app.cor("muted")))
        ini = "".join(w[0] for w in it.nome.split()[:2]).upper()
        q("#capa", Static).update(Text(f"\n  {ini}\n", style=f"bold {self.app.cor('accent')}"))
        q("#t-dur", Static).update(mmss(it.dur_ms))
        q("#aleatorio", Button).label = f"Aleatório: {'sim' if p.aleatorio else 'não'}"
        q("#repetir", Button).label = f"Repetir: {self.REPETIR.get(p.repetir, p.repetir)}"
        q("#curtir", Button).label = "Descurtir" if self.curtido else "Curtir"
        q("#play", Button).label = "Pausar" if p.tocando else "Tocar"
        if p.volume is not None:
            q("#volume", Barra).definir(p.volume / 100)
            q("#pct-vol", Static).update(f"{p.volume}%")
        self._tick()

    def _tick(self) -> None:
        p = self.player
        if p is None or p.item is None or not self.is_mounted:
            return
        pos = p.posicao()
        self.query_one("#t-pos", Static).update(mmss(pos))
        if p.item.dur_ms:
            self.query_one("#progresso", Barra).definir(pos / p.item.dur_ms)

    # ------------------------------------------------------------ ações
    def _depois_acao(self, ok: bool = True) -> None:
        self._poll(forcar=True)

    def _agir(self, desc: str, func, *args) -> None:
        self.app.executar(desc, func, *args, depois=self._depois_acao, recarregar=False)

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        {"anterior": self.action_anterior, "play": self.app.action_play_pause, "proxima": self.action_proxima,
         "aleatorio": self.action_aleatorio, "repetir": self.action_repetir, "curtir": self.action_curtir,
         "disp": lambda: self.app.action_aba("dispositivos")}.get(ev.button.id or "", lambda: None)()

    def action_proxima(self) -> None:
        self._agir("Próxima", self.app.cliente.proxima)

    def action_anterior(self) -> None:
        self._agir("Anterior", self.app.cliente.anterior)

    def action_aleatorio(self) -> None:
        if self.player:
            novo = not self.player.aleatorio
            self.player.aleatorio = novo
            self._agir("Aleatório", self.app.cliente.aleatorio, novo)

    def action_repetir(self) -> None:
        if self.player:
            ordem = ["off", "context", "track"]
            novo = ordem[(ordem.index(self.player.repetir) + 1) % 3 if self.player.repetir in ordem else 0]
            self.player.repetir = novo
            self._agir("Repetir", self.app.cliente.repetir, novo)

    def action_curtir(self) -> None:
        p = self.player
        if not p or not p.item:
            return
        ja = self.curtido
        self.curtido = not ja
        c = self.app.cliente
        self._agir("Curtir", c.descurtir if ja else c.curtir, p.item.uri)
        self.app.notify("Removida das curtidas." if ja else "Faixa curtida.")

    def action_volume(self, passo: int) -> None:
        if self.player and self.player.volume is not None:
            self.player.volume = max(0, min(100, self.player.volume + passo))
            self._agir("Volume", self.app.cliente.volume, self.player.volume)
            self._pintar()

    @on(Barra.Passo)
    def _passo(self, ev: Barra.Passo) -> None:
        ev.stop()
        if ev.barra.id == "volume":
            self.action_volume(5 * ev.direcao)
        elif self.player and self.player.item:
            alvo = max(0, min(self.player.item.dur_ms, self.player.posicao() + 5000 * ev.direcao))
            self._buscar(alvo)

    @on(Barra.Clique)
    def _clique(self, ev: Barra.Clique) -> None:
        ev.stop()
        if ev.barra.id == "volume":
            if self.player:
                self.player.volume = round(ev.fracao * 100)
                self._agir("Volume", self.app.cliente.volume, self.player.volume)
                self._pintar()
        elif self.player and self.player.item:
            self._buscar(int(ev.fracao * self.player.item.dur_ms))

    def _buscar(self, ms: int) -> None:
        self.player.progresso_ms, self.player.marca = ms, time.monotonic()
        self._agir("Buscar posição", self.app.cliente.buscar_posicao, ms)
        self._tick()

    @on(Tabela.RowSelected)
    def _fila_enter(self) -> None:
        t = self.query_one("#tabela", Tabela)
        self.app.notify("Para pular até essa faixa, use Próxima. A API do Spotify não toca direto da fila.")
