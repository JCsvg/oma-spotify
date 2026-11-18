"""Páginas da janela Principal: Início, Playlist/Álbum/Curtidas/Podcast, Busca, Artista e listas simples."""

from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Input, Static

from oma_spotify.services.modelos import ErroSpotify, Item, duracao_longa, mmss
from oma_spotify.ui.biblioteca import CURTIDAS
from oma_spotify.ui.capa import Capa
from oma_spotify.ui.fonte import grande, largura_grande
from oma_spotify.ui.icones import ic
from oma_spotify.ui.lista import EstadoLinha, Lista, ajustar, colunas
from oma_spotify.ui.principal import item_de_dict, serializar
from oma_spotify.ui.widgets import Abas, Botao, Cartao, Regua, Secao

DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro",
         "dezembro")
GRUPOS = {"album": "álbum", "single": "single", "compilation": "coletânea", "appears_on": "aparece em"}
TIPO_ROTULO = {"track": "música", "album": "álbum", "artist": "artista", "playlist": "playlist", "show": "podcast",
               "episode": "episódio", "curtidas": "playlist"}


def saudacao(agora: datetime | None = None) -> str:
    h = (agora or datetime.now()).hour
    return "bom dia" if 5 <= h < 12 else "boa tarde" if 12 <= h < 18 else "boa noite"


def data_hoje(agora: datetime | None = None) -> str:
    d = agora or datetime.now()
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]}"


def quando_rel(iso: str, agora: datetime | None = None) -> str:
    if not iso:
        return ""
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return ""
    agora = agora or datetime.now(timezone.utc)
    m = int((agora - t).total_seconds() // 60)
    if m < 1:
        return "agora"
    if m < 60:
        return f"há {m} min"
    if m < 24 * 60 and t.astimezone().date() == agora.astimezone().date():
        return f"há {m // 60} h"
    dias = (agora.astimezone().date() - t.astimezone().date()).days
    return "ontem" if dias == 1 else f"há {dias} dias"


def realcar(texto: str, q: str, estilo: str, destaque: str) -> Text:
    """O trecho que casou com a busca fica sublinhado na cor de destaque."""
    t = Text(texto, style=estilo, no_wrap=True)
    q = (q or "").strip().lower()
    if q and not q.startswith(("artist:", "album:")):
        i = texto.lower().find(q)
        if i >= 0:
            t.stylize(f"underline {destaque}", i, i + len(q))
    return t


# ---------------------------------------------------------------- linha de faixa (tabelas)
class ColunasFaixa:
    """Desenha a linha de uma faixa e acha a coluna do clique (▶ e coração)."""

    def __init__(self, app, curtidos: set[str], album: bool = True, numero: bool = True, artista: bool = True,
                 consulta: str = "", numeros: list[int] | None = None) -> None:
        self.app, self.curtidos, self.album, self.numero, self.artista = app, curtidos, album, numero, artista
        self.consulta = consulta
        self.numeros = numeros

    def partes(self, num: Text, titulo: Text, art: Text, alb: Text, coracao: Text, dur: Text, barra: Text) -> list:
        p = [(barra, 1, "left"), (num, 3, "right"), (titulo, -36, "left")]
        if self.artista:
            p.append((art, -25, "left"))
        if self.album:
            p.append((alb, -25, "left"))
        p += [(coracao, 2, "left"), (dur, 5, "right")]
        return p

    def cabecalho(self, largura: int) -> Text:
        a = self.app
        m = a.cor("mudo")
        return colunas(self.partes(Text("#", style=m), Text("título", style=m), Text("artista", style=m), Text("álbum", style=m),
                                   Text(""), Text(ic("duracao"), style=m), Text(" ")), largura)

    def linha(self, it: Item, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        if not isinstance(it, Item):
            return [Text(str(it))]
        tocando = a.player is not None and a.player.item is not None and a.player.item.uri == it.uri
        barra = Text("▌", style=a.cor("accent")) if e.marcado else Text(" ")
        if tocando:
            num = Text(a.eq_texto(), style=a.cor("accent"))
        elif e.hover:
            num = Text(ic("tocar"), style=f"bold {a.cor('forte')}")
        else:
            rot = str(self.numeros[n]) if self.numeros else str(n + 1)
            num = Text(rot if self.numero else "", style=a.cor("mudo"))
        est = f"bold {a.cor('accent')}" if tocando else f"bold {a.cor('forte')}" if e.destacado else a.cor("texto")
        titulo = realcar(it.nome, self.consulta, est, a.cor("accent"))
        art = realcar(it.sub, self.consulta, a.cor("texto") if e.destacado else a.cor("mudo"), a.cor("accent"))
        alb = Text(it.extra, style=a.cor("mudo"))
        if it.uri in self.curtidos:
            coracao = Text(ic("curtida"), style=a.cor("accent"))
        elif e.hover:
            coracao = Text(ic("nao_curtida"), style=a.cor("mudo"))
        else:
            coracao = Text("")
        dur = Text(mmss(it.dur_ms) if it.dur_ms else "", style=a.cor("mudo"))
        return [colunas(self.partes(num, titulo, art, alb, coracao, dur, barra), e.largura)]

    def coluna(self, x: int, largura: int) -> str:
        if 1 <= x <= 5:
            return "tocar"
        if largura - 9 <= x <= largura - 6:
            return "curtir"
        return ""


# ---------------------------------------------------------------- base
class Pagina(Vertical):
    """Base das páginas. A app chama os ganchos abaixo; cada página sobrescreve o que usa."""

    DEFAULT_CSS = "Pagina { height: 1fr; }"

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(**kw)
        self.vista = vista
        self.item = item_de_dict(vista["item"]) if vista.get("item") else None

    def focar_entrada(self) -> None:
        for w in self.query("*"):
            if w.focusable and w.display:
                w.focus()
                return

    def estado_(self) -> dict:
        return dict(self.vista)

    def rodape(self) -> list[tuple[str, str, str]]:
        return [("enter", "abrir", "app.enter"), ("t", "tocar", "app.item('tocar')"), ("f", "fila", "app.item('seguir')"),
                ("c", "curtir", "app.item('curtir')"), ("o", "opções", "app.item('opcoes')")]

    def teclas(self) -> list[tuple[str, list[tuple[str, str]]]]:
        return [("nesta janela", [("↑ ↓", "linhas; na ponta, a próxima seção"), ("← →", "atalhos, cartões, filtros e botões"),
                                  ("alt+← →", "página anterior, próxima"), ("ctrl+f", "filtra a página")])]

    def tratar(self, acao: str, itens: list) -> bool:
        return False

    def em_thread(self, func, depois) -> None:
        def seguro(r, erro):
            if self.is_mounted:
                try:
                    depois(r, erro)
                except NoMatches:
                    pass
        self.app.em_thread(func, seguro)

    def _cartoes(self):
        return self.query(Cartao)

    def pintar_eq(self) -> None:
        for c in self._cartoes():
            if self.app.tocando_uri(c.item.uri):
                c.refresh()
        for l in self.query(Lista):
            l.atualizar_itens([n for n, i in enumerate(l.itens) if isinstance(i, Item) and self.app.tocando_uri(i.uri)])

    def tocando_mudou(self) -> None:
        for c in self._cartoes():
            c.refresh()
        for l in self.query(Lista):
            l.redesenhar()

    @on(Cartao.Aberto)
    def _cartao(self, ev: Cartao.Aberto) -> None:
        ev.stop()
        self.app.fazer("abrir", [ev.item])

    @on(Cartao.Menu)
    def _cartao_menu(self, ev: Cartao.Menu) -> None:
        ev.stop()
        self.app.opcoes([ev.item], self)


# ---------------------------------------------------------------- início
class PaginaInicio(Pagina):
    DEFAULT_CSS = """
    PaginaInicio #rolagem { height: 1fr; }
    PaginaInicio #saudacao { height: 1; margin-top: 1; }
    PaginaInicio #ola { width: 1fr; text-style: bold; color: $oma-forte; }
    PaginaInicio #data { width: auto; color: $oma-mudo; }
    PaginaInicio #atalhos { grid-size: 3; grid-gutter: 1 2; grid-rows: 3; height: auto; margin-top: 1; }
    PaginaInicio #recentes { margin-top: 1; }
    PaginaInicio .fileira { height: auto; margin-top: 1; }
    PaginaInicio .fileira Cartao.grande { width: 20%; }
    PaginaInicio .fileira Cartao.mini { width: 1fr; max-width: 40; margin-right: 2; }
    PaginaInicio #vazio-inicio { color: $oma-mudo; margin-top: 1; height: auto; }
    """

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(vista, **kw)
        self.dados: dict = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="rolagem"):
            with Horizontal(id="saudacao"):
                yield Static("", id="ola")
                yield Static(data_hoje(), id="data")
            yield Grid(id="atalhos")
            yield Secao("tocadas recentemente", "ver tudo ›", id="sec-recentes")
            yield Lista(self._linha_recente, id="recentes", classes="-auto")
            yield Secao("no seu repeat · últimas 4 semanas", id="sec-repeat")
            yield Horizontal(id="repeat", classes="fileira")
            yield Secao("seus podcasts", "ver tudo ›", id="sec-podcasts")
            yield Horizontal(id="podcasts", classes="fileira")
            yield Static("", id="vazio-inicio")

    def on_mount(self) -> None:
        self._ola()
        if self.app.dados_bib:  # senão, carrega quando a biblioteca chegar (dados_mudaram)
            self.carregar()

    def _ola(self) -> None:
        nome = self.app.nome_usuario
        self.query_one("#ola", Static).update(f"{saudacao()}, {nome}" if nome else saudacao())

    def dados_mudaram(self) -> None:
        self._ola()
        self.carregar()

    def recarregar(self) -> None:
        self.carregar()

    def carregar(self) -> None:
        a = self.app
        if not a.conectado:
            return
        c, bib = a.cliente, list(a.dados_bib)

        def trabalho():
            def seguro(f, *args):
                try:
                    return f(*args)
                except ErroSpotify:
                    return []
            vistos, recentes = set(), []
            for t in seguro(c.recentes):
                if t.uri not in vistos:
                    vistos.add(t.uri)
                    recentes.append(t)
            return {"recentes": recentes, "repeat": seguro(c.mais_ouvidos, "artists", "short_term")[:5],
                    "podcasts": [i for i in bib if i.tipo == "show"][:3], "bib": bib}

        def depois(r, erro):
            if r:
                self.mostrar(r)
        self.em_thread(trabalho, depois)

    def atalhos(self, bib: list[Item]) -> list[Item]:
        fx = self.app.fixados()
        resto = [i for i in bib if i.tipo in ("playlist", "album", "artist") and i not in fx]
        return ([CURTIDAS] + fx + resto)[:6]

    def mostrar(self, d: dict) -> None:
        self.dados = d
        # quem tinha o foco num cartão volta para o mesmo lugar depois de remontar
        foco = self.app.focused
        volta = None
        if isinstance(foco, Cartao) and foco.parent is not None and foco.parent.id in ("atalhos", "repeat", "podcasts"):
            volta = (foco.parent.id, list(foco.parent.children).index(foco))
        novos = {"atalhos": [Cartao(i, "atalho") for i in self.atalhos(d["bib"])],
                 "repeat": [Cartao(i, "grande", sub="artista") for i in d["repeat"]],
                 "podcasts": [Cartao(i, "mini", sub=f"podcast · {i.sub}") for i in d["podcasts"]]}
        for cid, cartoes in novos.items():
            caixa = self.query_one(f"#{cid}")
            caixa.remove_children()
            caixa.mount_all(cartoes)
        if volta is not None and novos[volta[0]]:
            alvo = novos[volta[0]][min(volta[1], len(novos[volta[0]]) - 1)]
            self.call_after_refresh(alvo.focus)
        rec = self._recentes()
        for sid, vazio in (("#sec-repeat", not d["repeat"]), ("#repeat", not d["repeat"]), ("#sec-podcasts", not d["podcasts"]),
                           ("#podcasts", not d["podcasts"]), ("#sec-recentes", not rec), ("#recentes", not rec)):
            self.query_one(sid).display = not vazio
        self.query_one("#vazio-inicio", Static).update(
            "" if rec or d["repeat"] else "Toque algo, curta músicas e crie playlists que o início se enche. "
                                           "A API do Spotify não tem feed nem novidades: o início usa a sua conta.")

    def _linha_recente(self, it: Item, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        tocando = a.player is not None and a.player.item is not None and a.player.item.uri == it.uri
        eq = Text(a.eq_texto() if tocando else "", style=a.cor("accent"))
        est = f"bold {a.cor('accent')}" if tocando else f"bold {a.cor('forte')}" if e.destacado else a.cor("texto")
        quando = "agora" if tocando else quando_rel(it.quando)
        partes = [(eq, 2, "left"), (Text(it.nome, style=est), -40, "left"), (Text(it.sub, style=a.cor("mudo")), -25, "left"),
                  (Text(it.extra, style=a.cor("mudo")), -25, "left"),
                  (Text(quando, style=a.cor("accent") if tocando else a.cor("mudo")), 9, "right")]
        return [colunas(partes, e.largura, sep=2)]

    def focar_entrada(self) -> None:
        cs = list(self.query("#atalhos Cartao"))
        if cs:
            cs[0].focus()
        else:
            self.query_one("#recentes", Lista).focus()

    def _recentes(self) -> list:
        p = self.app.player
        rec = list(self.dados.get("recentes", []))
        if p is not None and p.item is not None:
            rec = [p.item] + [i for i in rec if i.uri != p.item.uri]
        self.query_one("#recentes", Lista).definir(rec[:7])
        return rec

    def tocando_mudou(self) -> None:
        if self.dados:
            self._recentes()
        for c in self._cartoes():
            c.refresh()

    @on(Lista.Escolhido, "#recentes")
    def _recente(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.tocar_item(ev.item)

    @on(Lista.Menu, "#recentes")
    def _recente_menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes([ev.item], self)

    @on(Secao.Mais)
    def _mais(self, ev: Secao.Mais) -> None:
        ev.stop()
        if ev.secao.id == "sec-recentes":
            self.app.navegar({"t": "recentes"})
        elif ev.secao.id == "sec-podcasts":
            bib = self.app.query_one("#bib")
            bib.cat = "show"
            bib.reconstruir()
            self.app.focar_janela("bib")


# ---------------------------------------------------------------- cabeçalho com capa e título grande
class Cabecalho(Horizontal):
    DEFAULT_CSS = """
    Cabecalho { height: auto; margin-top: 1; }
    Cabecalho Capa { width: 14; height: 7; }
    Cabecalho.-estreito Capa { width: 10; height: 5; }
    Cabecalho #cab-txt { width: 1fr; height: auto; margin-left: 3; }
    Cabecalho #cab-tipo { color: $oma-mudo; }
    Cabecalho #cab-titulo { color: $oma-forte; text-style: bold; height: auto; }
    Cabecalho #cab-desc { color: $oma-mudo; height: auto; }
    Cabecalho #cab-meta { color: $oma-mudo; height: auto; }
    Cabecalho .acoes { height: 1; margin-top: 1; }
    Cabecalho .acoes Botao { margin-right: 1; }
    """

    def __init__(self, item: Item, redonda: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.item, self.redonda = item, redonda
        self.desc_txt = item.desc
        self.meta = Text("")

    def compose(self) -> ComposeResult:
        yield Capa(self.item.uri, self.item.tipo, self.item.nome, self.redonda, id="cab-capa")
        with Vertical(id="cab-txt"):
            yield Static(TIPO_ROTULO.get(self.item.tipo, ""), id="cab-tipo")
            yield Static("", id="cab-titulo")
            yield Static(self.desc_txt, id="cab-desc")
            yield Static("", id="cab-meta")

    def on_resize(self) -> None:
        self._titulo()

    def _titulo(self) -> None:
        txt = self.query_one("#cab-txt")
        w = txt.size.width
        estreito = self.app.size.width < 110
        self.set_class(estreito, "-estreito")
        t = self.query_one("#cab-titulo", Static)
        if not estreito and w and largura_grande(self.item.nome) <= w:
            t.update(Text("\n".join(grande(self.item.nome)), style=f"{self.app.cor('forte')}"))
        else:
            t.update(Text(self.item.nome, style="bold", overflow="ellipsis", no_wrap=True))
        self.query_one("#cab-desc").display = bool(self.desc_txt) and not estreito

    def definir_meta(self, meta: Text, desc: str | None = None) -> None:
        self.meta = meta
        self.query_one("#cab-meta", Static).update(meta)
        if desc is not None:
            self.desc_txt = desc
            self.query_one("#cab-desc", Static).update(desc)
            self.query_one("#cab-desc").display = bool(desc)


# ---------------------------------------------------------------- playlist, álbum, curtidas, podcast
ORDENS = (("pers", "ordem personalizada"), ("titulo", "título"), ("artista", "artista"), ("album", "álbum"), ("dur", "duração"))


class PaginaColecao(Pagina):
    DEFAULT_CSS = """
    PaginaColecao #acoes { height: 1; margin-top: 1; }
    PaginaColecao #acoes Botao { margin-right: 1; }
    PaginaColecao #acoes .espaco { width: 1fr; }
    PaginaColecao #filtrar, PaginaColecao #ordem { color: $oma-mudo; }
    PaginaColecao #filtro { margin-top: 1; display: none; }
    PaginaColecao #filtro.-ligado { display: block; }
    PaginaColecao #cab-tabela { height: 1; margin-top: 1; }
    PaginaColecao #regua { height: 1; color: $oma-linha; }
    PaginaColecao #faixas { height: 1fr; }
    PaginaColecao #aviso { height: auto; margin-top: 2; color: $oma-mudo; }
    """

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(vista, **kw)
        if vista["t"] == "curtidas":
            self.item = Item(CURTIDAS.uri, "curtidas", "Músicas Curtidas", "playlist")
        self.todos: list[Item] = []
        self.curtidos: set[str] = set()
        self.salvo = False
        self.ordem = vista.get("ordem", "pers")
        self.carregado = False
        self.cursor_salvo = int(vista.get("linha", 0) or 0)
        self.cols = None

    # quem é
    @property
    def minha(self) -> bool:
        i = self.item
        return i is not None and i.tipo == "playlist" and (i.meu or i.colab)

    @property
    def alheia(self) -> bool:
        i = self.item
        return i is not None and i.tipo == "playlist" and not (i.meu or i.colab)

    def compose(self) -> ComposeResult:
        i = self.item
        yield Cabecalho(i, id="cab")
        with Horizontal(id="acoes"):
            yield Botao(f"{ic('tocar')} tocar", id="tocar", classes="cheio")
            if self.alheia:
                yield Botao(f"{ic('ok')} seguindo" if False else f"{ic('adicionar')} seguir", id="seguir", classes="vazado")
            else:
                yield Botao(ic("aleatorio"), id="aleatorio", tooltip="tocar em ordem aleatória")
                if self.minha:
                    yield Botao(ic("a_seguir"), id="add", tooltip="adicionar faixas (busca)")
                elif i.tipo in ("album", "show"):
                    yield Botao(ic("nao_curtida"), id="salvar", tooltip="salvar na biblioteca (c)")
            yield Botao(ic("opcoes"), id="mais", tooltip="mais opções (o)")
            yield Static("", classes="espaco")
            if not self.alheia:
                yield Botao(f"{ic('filtro')} filtrar ctrl+f", id="filtrar")
                yield Botao(f"{dict(ORDENS)[self.ordem]} {ic('menu')}", id="ordem")
        if self.alheia:
            yield Static("", id="aviso")
            return
        yield Input(placeholder="filtrar esta lista", id="filtro", compact=True)
        yield Static("", id="cab-tabela")
        yield Regua(id="regua")
        yield Lista(self._linha, marcar=True, ao_clicar=self._clique, id="faixas")

    def on_mount(self) -> None:
        a = self.app
        self.cols = ColunasFaixa(a, self.curtidos, album=self._com_album(), numero=True)
        if self.alheia:
            self.query_one("#aviso", Static).update(Text.assemble(
                (f"{ic('info')} ", a.cor("blue")), ("o Spotify não lista as faixas de playlist alheia para app pessoal.\n", a.cor("texto")),
                ("  dá para tocar e seguir. Para ver as faixas, abra no app do Spotify.", a.cor("mudo"))))
            self._meta_alheia()
        self.recarregar()

    def _com_album(self) -> bool:
        return self.item.tipo not in ("album", "show") and self.app.size.width >= 110

    def ajustar(self, largura: int) -> None:
        if self.cols is not None:
            self.cols.album = self._com_album()
            self._cabecalho_tabela()
            for l in self.query(Lista):
                l.redesenhar()

    def on_resize(self) -> None:
        self._cabecalho_tabela()

    def _cabecalho_tabela(self) -> None:
        if self.alheia or self.cols is None:
            return
        try:
            l = self.query_one("#faixas", Lista)
        except NoMatches:
            return
        w = l.scrollable_content_region.width or (self.size.width - 1)
        self.query_one("#cab-tabela", Static).update(self.cols.cabecalho(w))

    def _meta_alheia(self) -> None:
        i = self.item
        self.query_one(Cabecalho).definir_meta(Text.assemble((i.sub, f"bold {self.app.cor('texto')}"),
                                                               (f" · {i.extra}" if i.extra else "", self.app.cor("mudo"))))

    # dados
    def recarregar(self) -> None:
        a = self.app
        if not a.conectado or self.alheia:
            if self.alheia and a.conectado:
                self.carregado = True
                self._conferir_salvo()
            return
        c, i = a.cliente, self.item

        def trabalho():
            if i.tipo == "curtidas":
                itens = list(a.curtidas_cache) or c.curtidas()
            elif i.tipo == "playlist":
                itens = list(a.itens_da_playlist(i.id))
            elif i.tipo == "album":
                itens = c.faixas_do_album(i.id, i.nome)
            elif i.tipo == "show":
                itens = c.episodios_do_show(i.id)
            else:
                itens = []
            if i.tipo == "curtidas":
                vivos = {x.uri for x in itens}
            else:
                vivos = set()
                uris = [x.uri for x in itens if x.tipo == "track"]
                for n in range(0, len(uris), 40):
                    try:
                        vivos |= {u for u, ok in zip(uris[n:n + 40], c.curtido(uris[n:n + 40])) if ok}
                    except ErroSpotify:
                        break
            salvo = False
            if i.tipo in ("album", "show", "playlist"):
                try:
                    salvo = bool(c.curtido([i.uri])[0])
                except (ErroSpotify, IndexError):
                    salvo = False
            return itens, vivos, salvo

        def depois(r, erro):
            if erro:
                self.todos = []
                self.query_one("#cab-tabela", Static).update(Text(str(erro), style=self.app.cor("warning")))
                if erro.sem_login:
                    self.app.pedir_login(str(erro))
            else:
                self.todos, vivos, self.salvo = r
                self.curtidos.clear()
                self.curtidos |= vivos
            self.carregado = True
            self.mostrar()
        self.em_thread(trabalho, depois)

    def _conferir_salvo(self) -> None:
        c, i = self.app.cliente, self.item

        def depois(r, erro):
            self.salvo = bool(r and r[0])
            self.query_one("#seguir", Botao).label = f"{ic('ok')} seguindo" if self.salvo else f"{ic('adicionar')} seguir"
        self.em_thread(lambda: c.curtido([i.uri]), depois)

    def visiveis(self) -> list[Item]:
        q = self.query_one("#filtro", Input).value.strip().lower()
        base = [x for x in self.todos if not q or q in f"{x.nome} {x.sub} {x.extra}".lower()]
        chave = {"titulo": lambda x: x.nome.lower(), "artista": lambda x: x.sub.lower(), "album": lambda x: x.extra.lower(),
                 "dur": lambda x: x.dur_ms}.get(self.ordem)
        return sorted(base, key=chave) if chave else base

    def mostrar(self) -> None:
        lista = self.query_one("#faixas", Lista)
        itens = self.visiveis()
        cursor = self.cursor_salvo if self.cursor_salvo else None
        self.cursor_salvo = 0
        lista.definir(itens, cursor)
        self._cabecalho_tabela()
        a, i = self.app, self.item
        dur = sum(x.dur_ms for x in self.todos)
        n = len(self.todos)
        unidade = "episódios" if i.tipo == "show" else "faixas"
        if i.tipo == "album":
            meta = Text.assemble((i.sub, f"bold {a.cor('texto')}"), (" · ".join([""] + [x for x in (i.ano, f"{n} {unidade}", duracao_longa(dur)) if x]),
                                                                       a.cor("mudo")))
        elif i.tipo == "curtidas":
            meta = Text(f"{n} {unidade} · {duracao_longa(dur)}", style=a.cor("mudo"))
        else:
            meta = Text.assemble((i.sub, f"bold {a.cor('texto')}"), (f" · {n} {unidade} · {duracao_longa(dur)}", a.cor("mudo")))
        self.query_one(Cabecalho).definir_meta(meta)
        if self.query("#salvar"):
            self.query_one("#salvar", Botao).label = ic("curtida") if self.salvo else ic("nao_curtida")
            self.query_one("#salvar", Botao).set_class(self.salvo, "ligado")
        if not itens:
            msg = "Nada por aqui ainda." if not self.query_one("#filtro", Input).value else "Nada casou com o filtro."
            self.query_one("#cab-tabela", Static).update(Text(msg, style=a.cor("mudo")))

    def _linha(self, it, n, e):
        return self.cols.linha(it, n, e)

    def _clique(self, i: int, x: int) -> bool:
        lista = self.query_one("#faixas", Lista)
        col = self.cols.coluna(x, lista.scrollable_content_region.width)
        it = lista.itens[i]
        if col == "tocar" and lista.hover == i:
            self.tocar_linha(it)
            return True
        if col == "curtir":
            self.app.curtir_itens([it])
            return True
        return False

    def curtidas_mudaram(self, uris: list[str], curtido: bool) -> None:
        if self.item and self.item.uri in uris:
            self.salvo = curtido
            for b in self.query("#salvar"):
                b.label = ic("curtida") if curtido else ic("nao_curtida")
            for b in self.query("#seguir"):
                b.label = f"{ic('ok')} seguindo" if curtido else f"{ic('adicionar')} seguir"
        for u in uris:
            (self.curtidos.add if curtido else self.curtidos.discard)(u)
        for l in self.query(Lista):
            l.redesenhar()

    def playlist_mudou(self, pid: str) -> None:
        if self.item and self.item.id == pid:
            self.recarregar()

    # ações
    def tocar_linha(self, it: Item) -> None:
        a, i = self.app, self.item
        if i.tipo in ("album", "playlist", "show"):
            a.tocar_item(it, contexto=i.uri)
        else:
            a.tocar_item(it, uris=[x.uri for x in self.query_one("#faixas", Lista).itens])

    @on(Lista.Escolhido, "#faixas")
    def _enter(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.tocar_linha(ev.item)

    @on(Lista.Menu, "#faixas")
    def _menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes(self.query_one("#faixas", Lista).itens_marcados(), self)

    @on(Lista.Marcas, "#faixas")
    def _marcas(self, ev: Lista.Marcas) -> None:
        ev.stop()
        self.app.query_one("#rodape").pintar()

    @on(Lista.Destacado, "#faixas")
    def _destacado(self, ev: Lista.Destacado) -> None:
        self.app.guardar_vista(self)

    @on(Input.Changed, "#filtro")
    def _filtro(self, ev: Input.Changed) -> None:
        ev.stop()
        self.mostrar()

    @on(Input.Submitted, "#filtro")
    def _filtro_ok(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.query_one("#faixas", Lista).focus()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        a, i = self.app, self.item
        b = ev.botao.id
        if b == "tocar":
            a.tocar_item(i)
        elif b == "aleatorio":
            if i.tipo == "curtidas":
                a.tocar_uris([x.uri for x in self.todos], aleatorio=True)
            else:
                a.tocar_contexto_aleatorio(i)
        elif b in ("salvar", "seguir"):
            a.curtir_itens([i])
        elif b == "add":
            a.notify(f"Busque a faixa (/) e use p para pôr em {i.nome}.", timeout=5)
            a.action_buscar()
        elif b == "mais":
            a.opcoes([i], self)
        elif b == "filtrar":
            self.filtrar()
        elif b == "ordem":
            ids = [k for k, _ in ORDENS]
            self.ordem = ids[(ids.index(self.ordem) + 1) % len(ids)]
            ev.botao.label = f"{dict(ORDENS)[self.ordem]} {ic('menu')}"
            self.vista = {**self.vista, "ordem": self.ordem}
            self.app.guardar_vista(self)
            self.mostrar()

    def filtrar(self) -> None:
        if self.alheia:
            return
        f = self.query_one("#filtro", Input)
        f.add_class("-ligado")
        f.focus()

    def esc(self) -> bool:
        if self.alheia:
            return False
        f = self.query_one("#filtro", Input)
        if f.has_class("-ligado"):
            f.value = ""
            f.remove_class("-ligado")
            self.query_one("#faixas", Lista).focus()
            return True
        return False

    def focar_entrada(self) -> None:
        if self.alheia:
            self.query_one("#tocar", Botao).focus()
            return
        l = self.query_one("#faixas", Lista)
        (l if l.itens or not self.carregado else self.query_one("#tocar", Botao)).focus()

    def estado_(self) -> dict:
        v = dict(self.vista)
        if not self.alheia:
            v["linha"] = max(0, self.query_one("#faixas", Lista).cursor)
        return v

    def tratar(self, acao: str, itens: list) -> bool:
        a = self.app
        foco_lista = not self.alheia and a.focused is self.query_one("#faixas", Lista)
        if acao == "tocar" and foco_lista and itens:
            if len(itens) == 1:
                self.tocar_linha(itens[0])
            else:
                a.tocar_uris([x.uri for x in itens])
            return True
        if acao == "remover" and foco_lista:
            if self.minha:
                self.remover(itens)
            else:
                a.notify("Só dá para tirar faixas de playlist sua.", timeout=4)
            return True
        if not foco_lista and acao in ("tocar", "curtir", "opcoes", "fixar", "link", "remover") and self.item is not None:
            if acao == "remover":
                a.remover_da_biblioteca(self.item)
            else:
                a.fazer(acao, [self.item], self)
            return True
        return False

    def opcoes_extra(self, itens: list) -> list[tuple[str, str, str]]:
        if self.minha and itens and itens[0].tipo == "track" and self.app.focused is not None and isinstance(self.app.focused, Lista):
            return [("remover", "remover desta playlist", "x")]
        return []

    def remover(self, itens: list[Item]) -> None:
        a, pl = self.app, self.item
        lista = self.query_one("#faixas", Lista)
        pos = sorted({self.todos.index(x) for x in itens if x in self.todos})
        if not pos:
            return
        tirados = [(p, self.todos[p]) for p in pos]
        for p, _ in reversed(tirados):
            del self.todos[p]
        lista.limpar_marcas()
        self.mostrar()
        c = a.cliente
        a.esquecer_playlist(pl.id)

        def tirar():
            for u in dict.fromkeys(x.uri for _, x in tirados):
                c.remover_da_playlist(pl.id, u)

        def desfazer():
            def voltar():
                for p, x in tirados:
                    c.inserir_na_playlist(pl.id, [x.uri], p)
            for p, x in tirados:
                self.todos.insert(min(p, len(self.todos)), x)
            if self.is_mounted:
                self.mostrar()
            a.esquecer_playlist(pl.id)
            a.executar("Desfazer", voltar, ok="desfeito", recarregar=False)
        a.executar("Remover da playlist", tirar, recarregar=False,
                   depois=lambda ok: a.avisar(f"{ic('remover')} {tirados[0][1].nome if len(tirados) == 1 else f'{len(tirados)} faixas'} "
                                              f"removida de {pl.nome}" if len(tirados) == 1 else
                                              f"{ic('remover')} {len(tirados)} faixas removidas de {pl.nome}", desfazer) if ok else None)

    def mover_item(self, passo: int) -> None:
        a, pl = self.app, self.item
        if not self.minha:
            a.notify("Só dá para mover faixas de playlist sua.", timeout=4)
            return
        if self.ordem != "pers" or self.query_one("#filtro", Input).value:
            a.notify("Para mover, volte para a ordem personalizada e sem filtro.", timeout=4)
            return
        lista = self.query_one("#faixas", Lista)
        idx = sorted(lista.marcados) or ([lista.cursor] if lista.cursor >= 0 else [])
        if not idx:
            return
        if idx != list(range(idx[0], idx[-1] + 1)):
            a.notify("Marque faixas seguidas (Shift+↑ ↓) para mover.", timeout=4)
            return
        ini, n = idx[0], len(idx)
        if (passo < 0 and ini == 0) or (passo > 0 and ini + n >= len(self.todos)):
            return
        self._mover(ini, n, passo, desfazendo=False)

    def _mover(self, ini: int, n: int, passo: int, desfazendo: bool) -> None:
        a, pl = self.app, self.item
        bloco = self.todos[ini:ini + n]
        del self.todos[ini:ini + n]
        novo = ini + passo
        self.todos[novo:novo] = bloco
        lista = self.query_one("#faixas", Lista)
        lista.definir(self.visiveis(), novo + (n - 1 if passo > 0 else 0))
        if n > 1 or lista.marcados:
            lista.marcados = set(range(novo, novo + n))
            lista._ancora = novo if passo < 0 else novo + n - 1
            lista.redesenhar()
        lista.mostrar_item(lista.cursor)
        antes = ini - 1 if passo < 0 else ini + n + 1
        a.esquecer_playlist(pl.id)
        a.executar("Mover", a.cliente.mover_na_playlist, pl.id, ini, antes, n, recarregar=False,
                   depois=lambda ok: None if ok else self.recarregar())
        if not desfazendo:
            rot = f"{n} faixas" if n > 1 else bloco[0].nome
            verbo = ("subiram" if n > 1 else "subiu") if passo < 0 else ("desceram" if n > 1 else "desceu")
            faixa = f"{novo + 1}-{novo + n}" if n > 1 else f"{novo + 1}"
            a.avisar(f"{ic('mover')} {rot} {verbo} para {faixa}", lambda: self.is_mounted and self._mover(novo, n, -passo, True))

    def rodape(self) -> list[tuple[str, str, str]]:
        if self.alheia:
            return [("enter", "tocar", "app.enter"), ("c", "seguir", "app.item('curtir')"), ("o", "opções", "app.item('opcoes')")]
        try:
            n = len(self.query_one("#faixas", Lista).marcados)
        except NoMatches:
            n = 0
        r = [("enter", "tocar", "app.enter"), ("f", f"fila ({n})" if n else "fila", "app.item('seguir')"),
             ("c", "curtir", "app.item('curtir')"), ("p", "playlist", "app.item('playlist')")]
        if self.minha:
            r.append(("alt+↑↓", "mover", "app.alt_v(-1)"))
        else:
            r.append(("o", "opções", "app.item('opcoes')"))
        return r

    def teclas(self):
        base = [("↑ ↓", "faixas"), ("shift+↑ ↓", "marca várias"), ("ctrl+f", "filtra"), ("g G", "topo, fim"),
                ("alt+← →", "página anterior, próxima")]
        if self.minha:
            base += [("alt+↑ ↓", "move as marcadas"), ("x", "tira da playlist"), ("u", "desfaz")]
        return [("nesta janela", base)]


# ---------------------------------------------------------------- busca
FILTROS = (("tudo", "tudo"), ("track", "músicas"), ("artist", "artistas"), ("album", "álbuns"), ("playlist", "playlists"),
           ("show", "podcasts"))
TITULOS_BUSCA = {"track": "músicas", "artist": "artistas", "album": "álbuns e singles", "playlist": "playlists", "show": "podcasts"}


class PaginaBusca(Pagina):
    DEFAULT_CSS = """
    PaginaBusca #rolagem { height: 1fr; }
    PaginaBusca #filtros { margin-top: 1; }
    PaginaBusca #res { height: auto; }
    PaginaBusca #topo-busca { height: auto; }
    PaginaBusca #col-melhor { width: 36; height: auto; }
    PaginaBusca #melhor { height: 11; background: $oma-painel; padding: 1 2; margin-top: 1; }
    PaginaBusca #melhor Capa { width: 12; height: 6; }
    PaginaBusca #melhor-nome { height: 1; margin-top: 1; }
    PaginaBusca #melhor-pe { height: 1; }
    PaginaBusca #melhor-tipo { width: 1fr; color: $oma-mudo; }
    PaginaBusca #col-musicas { width: 1fr; height: auto; margin-left: 3; }
    PaginaBusca #musicas { margin-top: 1; }
    PaginaBusca .fileira { height: auto; margin-top: 1; }
    PaginaBusca .fileira Cartao.grande { width: 20%; }
    PaginaBusca #nada { color: $oma-mudo; margin-top: 2; height: auto; }
    PaginaBusca #mais-lista { margin-top: 1; color: $oma-mudo; }
    """

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(vista, **kw)
        self.q = vista.get("q", "")
        self.cat = vista.get("cat", "tudo")
        self.res: dict[str, list[Item]] = {}
        self.n_mostrar: dict[str, int] = {}
        self.curtidos: set[str] = set()
        self.carregado = False
        self._pedido = 0

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="rolagem"):
            yield Abas(list(FILTROS), self.cat, estilo="chip", focavel=True, id="filtros")
            yield Vertical(id="res")

    def on_mount(self) -> None:
        self.buscar()

    def nova_busca(self, q: str) -> None:
        self.q = q
        self.vista = {**self.vista, "q": q}
        self.app.query_one("#principal").border_title = f"busca · “{q}”"
        self.buscar()

    def buscar(self) -> None:
        a = self.app
        if not a.conectado or not self.q:
            return
        self._pedido += 1
        pedido, q, c = self._pedido, self.q, a.cliente

        def trabalho():
            r = c.buscar(q)
            uris = [x.uri for x in r.get("track", [])][:40]
            try:
                vivos = {u for u, ok in zip(uris, c.curtido(uris)) if ok} if uris else set()
            except ErroSpotify:
                vivos = set()
            return r, vivos

        def depois(r, erro):
            if pedido != self._pedido:
                return  # chegou uma busca mais nova
            if erro:
                self.res = {}
                self._nada(str(erro))
                return
            self.res, self.curtidos = r
            self.n_mostrar = {}
            self.carregado = True
            self.mostrar()
        self.em_thread(trabalho, depois)

    def _nada(self, msg: str) -> None:
        self._trocar(lambda: [Static(msg, id="nada")])

    def mostrar(self) -> None:
        if not any(self.res.values()):
            self._nada(f"Nada encontrado para “{self.q}”. Tente outra palavra.")
            return
        self._trocar(self._tudo if self.cat == "tudo" else lambda: self._so(self.cat))

    def _trocar(self, fabrica) -> None:
        """Troca os resultados esperando a remoção terminar (os ids se repetem entre uma busca e outra)."""
        self._geracao = getattr(self, "_geracao", 0) + 1
        g = self._geracao

        async def trocar() -> None:
            res = self.query_one("#res", Vertical)
            await res.remove_children()
            if g != self._geracao or not self.is_mounted:
                return
            await res.mount_all(fabrica())
        self.call_later(trocar)

    def _cols(self) -> ColunasFaixa:
        return ColunasFaixa(self.app, self.curtidos, album=False, numero=False, consulta=self.q)

    def _tudo(self) -> list:
        a = self.app
        partes = []
        faixas = self.res.get("track", [])
        melhor = self._melhor()
        colunas_topo = []
        if melhor is not None:
            self.melhor = melhor
            caixa = Vertical(Capa(melhor.uri, melhor.tipo, melhor.nome),
                             Static(realcar(melhor.nome, self.q, f"bold {a.cor('forte')}", a.cor("accent")), id="melhor-nome"),
                             Horizontal(Static(TIPO_ROTULO.get(melhor.tipo, ""), id="melhor-tipo"),
                                        Botao(f"{ic('tocar')} tocar", id="melhor-tocar", classes="cheio"), id="melhor-pe"),
                             id="melhor")
            colunas_topo.append(Vertical(Secao("melhor resultado", regua=False), caixa, id="col-melhor"))
        if faixas:
            n = self.n_mostrar.get("track", 5)
            cols = self._cols()
            l = Lista(lambda it, i, e: self._linha_musica(it, i, e, cols), alturas=lambda it: 2, id="musicas", classes="-auto")
            l.ao_clicar = lambda i, x: self._clique_musica(l, i, x)
            l.definir(faixas[:n])
            mais = "mais 5 ›" if len(faixas) > n or len(faixas) >= 10 else ""
            colunas_topo.append(Vertical(Secao("músicas", mais, id="mais-track"), l, id="col-musicas"))
        if colunas_topo:
            partes.append(Horizontal(*colunas_topo, id="topo-busca"))
        for tipo in ("artist", "album", "playlist", "show"):
            itens = self.res.get(tipo, [])
            if not itens:
                continue
            partes.append(Secao(TITULOS_BUSCA[tipo], "mais ›", id=f"mais-{tipo}"))
            partes.append(Horizontal(*[Cartao(i, "grande", sub=self._sub(i)) for i in itens[:5]], classes="fileira"))
        return partes

    def _so(self, tipo: str) -> list:
        itens = self.res.get(tipo, [])
        n = self.n_mostrar.get(tipo, 10)
        partes: list = []
        if not itens:
            return [Static(f"Nenhum resultado em {dict(FILTROS)[tipo]}.", id="nada")]
        if tipo == "track":
            cols = self._cols()
            l = Lista(lambda it, i, e: cols.linha(it, i, e), id="musicas", classes="-auto")
            l.ao_clicar = lambda i, x: self._clique_musica(l, i, x)
            l.definir(itens[:n])
            partes.append(Static(""))
            partes.append(l)
        else:
            por_linha = 5
            mostrar = itens[:n]
            for k in range(0, len(mostrar), por_linha):
                partes.append(Horizontal(*[Cartao(i, "grande", sub=self._sub(i)) for i in mostrar[k:k + por_linha]],
                                         classes="fileira"))
        partes.append(Botao("mais 5 ›", id="mais-lista", classes="link"))
        return partes

    def _sub(self, i: Item) -> str:
        if i.tipo == "album":
            return " · ".join(x for x in (i.ano, GRUPOS.get(i.grupo, "álbum")) if x)
        if i.tipo == "playlist":
            return i.sub or "playlist"
        return TIPO_ROTULO.get(i.tipo, "")

    def _melhor(self) -> Item | None:
        q = self.q.lower()
        for tipo in ("artist", "track", "album", "playlist", "show"):
            for i in self.res.get(tipo, []):
                if i.nome.lower() == q or (tipo == "artist" and q in i.nome.lower()):
                    return i
        for tipo in ("track", "artist", "album", "playlist", "show"):
            if self.res.get(tipo):
                return self.res[tipo][0]
        return None

    def _linha_musica(self, it: Item, n: int, e: EstadoLinha, cols: ColunasFaixa) -> list[Text]:
        a = self.app
        w = e.largura
        tocando = a.player is not None and a.player.item is not None and a.player.item.uri == it.uri
        est = f"bold {a.cor('accent')}" if tocando else f"bold {a.cor('forte')}" if e.destacado else a.cor("forte")
        cor = Text(ic("curtida"), style=a.cor("accent")) if it.uri in self.curtidos else \
            Text(ic("nao_curtida"), style=a.cor("mudo")) if e.hover else Text("")
        l1 = colunas([(realcar(it.nome, self.q, est, a.cor("accent")), 0, "left"), (cor, 2, "left"),
                      (Text(mmss(it.dur_ms), style=a.cor("mudo")), 5, "right")], w - 1)
        l2 = colunas([(realcar(it.sub, self.q, a.cor("mudo"), a.cor("accent")), 0, "left")], w - 1)
        return [Text(" ") + l1, Text(" ") + l2]

    def _clique_musica(self, l: Lista, i: int, x: int) -> bool:
        w = l.scrollable_content_region.width
        if self.cat == "tudo" and w - 9 <= x <= w - 6:
            self.app.curtir_itens([l.itens[i]])
            return True
        return False

    def curtidas_mudaram(self, uris: list[str], curtido: bool) -> None:
        for u in uris:
            (self.curtidos.add if curtido else self.curtidos.discard)(u)
        for l in self.query(Lista):
            l.redesenhar()

    @on(Lista.Escolhido, "#musicas")
    def _musica(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        uris = [x.uri for x in ev.lista.itens]
        self.app.tocar_item(ev.item, uris=uris)

    @on(Lista.Menu, "#musicas")
    def _menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes(ev.lista.itens_marcados(), self)

    @on(Abas.Mudou, "#filtros")
    def _filtro(self, ev: Abas.Mudou) -> None:
        ev.stop()
        self.cat = ev.valor
        self.vista = {**self.vista, "cat": self.cat}
        self.app.guardar_vista(self)
        if self.carregado:
            self.mostrar()

    @on(Secao.Mais)
    def _mais(self, ev: Secao.Mais) -> None:
        ev.stop()
        tipo = (ev.secao.id or "").removeprefix("mais-")
        if tipo == "track" and self.cat == "tudo":
            self._mais_de("track", 5)
        elif tipo in TITULOS_BUSCA:
            self.query_one("#filtros", Abas).definir(tipo, avisar=True)

    def _mais_de(self, tipo: str, passo: int) -> None:
        atual = self.n_mostrar.get(tipo, 5 if self.cat == "tudo" else 10)
        novo = atual + passo
        itens = self.res.get(tipo, [])
        self.n_mostrar[tipo] = novo
        if novo <= len(itens):
            self.mostrar()
            return
        c, q = self.app.cliente, self.q
        if len(itens) % 10:
            self.mostrar()
            return

        def trabalho():
            return c.buscar(q, [tipo], len(itens)).get(tipo, [])

        def depois(r, erro):
            if r:
                self.res[tipo] = itens + r
            self.mostrar()
        self.em_thread(trabalho, depois)

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        if ev.botao.id == "melhor-tocar" and getattr(self, "melhor", None) is not None:
            self.app.fazer("tocar", [self.melhor])
        elif ev.botao.id == "mais-lista":
            self._mais_de(self.cat, 5)

    def focar_entrada(self) -> None:
        for sel in ("#musicas", "#melhor-tocar", "Cartao", "#filtros"):
            for w in self.query(sel):
                w.focus()
                return

    def estado_(self) -> dict:
        return {**self.vista, "q": self.q, "cat": self.cat}

    def rodape(self):
        return [("enter", "tocar", "app.enter"), ("f", "fila", "app.item('seguir')"), ("c", "curtir", "app.item('curtir')"),
                ("↑", "filtros", "app.mover(0,-1)"), ("o", "opções", "app.item('opcoes')")]

    def teclas(self):
        return [("nesta janela", [("↑ ↓", "resultados; ↑ no primeiro sobe para os filtros"), ("← →", "filtros e cartões"),
                                  ("enter", "toca ou abre"), ("alt+← →", "página anterior, próxima")])]


# ---------------------------------------------------------------- artista
DISCO = (("tudo", "tudo"), ("album", "álbuns"), ("single", "singles e EPs"), ("appears_on", "aparece em"))


class PaginaArtista(Pagina):
    DEFAULT_CSS = """
    PaginaArtista #rolagem { height: 1fr; }
    PaginaArtista #acoes { height: 1; margin-top: 1; }
    PaginaArtista #acoes Botao { margin-right: 1; }
    PaginaArtista #destaques { margin-top: 1; }
    PaginaArtista #disco-abas { margin-top: 1; }
    PaginaArtista .fileira { height: auto; margin-top: 1; }
    PaginaArtista .fileira Cartao.grande { width: 20%; height: 9; }
    PaginaArtista .fileira Cartao.mini { width: 1fr; max-width: 40; margin-right: 2; }
    PaginaArtista .nada-disco { color: $oma-mudo; height: auto; margin-top: 1; }
    """

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(vista, **kw)
        self.albuns: list[Item] = []
        self.destaques: list[Item] = []
        self.curtidos: set[str] = set()
        self.seguindo = False
        self.grupo = "tudo"
        self.carregado = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="rolagem"):
            yield Cabecalho(self.item, redonda=True, id="cab")
            with Horizontal(id="acoes"):
                yield Botao(f"{ic('tocar')} tocar", id="tocar", classes="cheio")
                yield Botao(f"{ic('adicionar')} seguir", id="seguir", classes="vazado")
                yield Botao(ic("aleatorio"), id="aleatorio", tooltip="tocar em ordem aleatória")
                yield Botao(ic("opcoes"), id="mais", tooltip="opções (o)")
            yield Secao("destaques", id="sec-dest")
            yield Lista(self._linha_dest, id="destaques", classes="-auto")
            yield Secao("discografia", id="sec-disco")
            yield Abas(list(DISCO), "tudo", estilo="chip", focavel=True, id="disco-abas")
            yield Horizontal(id="disco", classes="fileira")
            yield Secao("nas suas playlists", id="sec-pl")
            yield Horizontal(id="nas-playlists", classes="fileira")

    def on_mount(self) -> None:
        self.cols = ColunasFaixa(self.app, self.curtidos, album=True, artista=False)
        self.query_one("#sec-pl").display = False
        self.recarregar()

    def recarregar(self) -> None:
        a = self.app
        if not a.conectado:
            return
        c, i = a.cliente, self.item

        def trabalho():
            dest = c.buscar(f'artist:"{i.nome}"', ["track"], 0, 10).get("track", [])
            dest = [x for x in dest if i.nome.lower() in x.sub.lower()][:5] or dest[:5]
            try:
                albuns = c.albuns_do_artista(i.id)
            except ErroSpotify:
                albuns = []
            uris = [x.uri for x in dest] + [i.uri]
            try:
                vivos = {u for u, ok in zip(uris, c.curtido(uris)) if ok}
            except ErroSpotify:
                vivos = set()
            return dest, albuns, vivos

        def depois(r, erro):
            if erro:
                self.query_one("#sec-dest", Secao).titulo = f"destaques ({erro})"
                return
            self.destaques, self.albuns, vivos = r
            self.seguindo = i.uri in vivos
            self.curtidos.clear()
            self.curtidos |= vivos
            self.carregado = True
            self.mostrar()
            self._contar()
        self.em_thread(trabalho, depois)

    def mostrar(self) -> None:
        self.query_one("#destaques", Lista).definir(self.destaques)
        self.query_one("#sec-dest").display = bool(self.destaques)
        self.query_one("#seguir", Botao).label = f"{ic('ok')} seguindo" if self.seguindo else f"{ic('adicionar')} seguir"
        self._disco()

    def _disco(self) -> None:
        d = self.query_one("#disco", Horizontal)
        d.remove_children()
        itens = [x for x in self.albuns if self.grupo == "tudo" or x.grupo == self.grupo or
                 (self.grupo == "single" and x.grupo in ("single", "compilation"))]
        if itens:
            d.mount_all([Cartao(x, "grande", sub=" · ".join(y for y in (x.ano, GRUPOS.get(x.grupo, "álbum")) if y)) for x in itens[:5]])
        else:
            d.mount(Static("Nada nesta categoria.", classes="nada-disco"))

    def _contar(self) -> None:
        """Quantas músicas dele você curtiu e em quantas playlists suas ele aparece (o app conta)."""
        a, nome = self.app, self.item.nome.lower()
        curt = sum(1 for x in a.curtidas_cache if nome in [s.strip().lower() for s in x.sub.split(",")])
        minhas = [p for p in a.dados_bib if p.tipo == "playlist" and (p.meu or p.colab)][:24]

        def trabalho():
            achou = []
            for p in minhas:
                try:
                    n = sum(1 for x in a.itens_da_playlist(p.id) if nome in [s.strip().lower() for s in x.sub.split(",")])
                except ErroSpotify:
                    continue
                if n:
                    achou.append((p, n))
            return achou

        def depois(r, erro):
            r = r or []
            self.query_one(Cabecalho).definir_meta(Text.assemble(
                ("você curtiu ", a.cor("mudo")), (f"{curt} {'música' if curt == 1 else 'músicas'}", f"bold {a.cor('texto')}"),
                (" dele · aparece em ", a.cor("mudo")), (f"{len(r)} {'playlist sua' if len(r) == 1 else 'playlists suas'}",
                                                          f"bold {a.cor('texto')}")))
            box = self.query_one("#nas-playlists", Horizontal)
            box.remove_children()
            box.mount_all([Cartao(p, "mini", sub=f"{n} {'música' if n == 1 else 'músicas'} dele") for p, n in r[:3]])
            self.query_one("#sec-pl").display = bool(r)
        self.em_thread(trabalho, depois)

    def _linha_dest(self, it, n, e):
        return self.cols.linha(it, n, e)

    @on(Lista.Escolhido, "#destaques")
    def _dest(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.tocar_item(ev.item, uris=[x.uri for x in self.destaques])

    @on(Lista.Menu, "#destaques")
    def _dest_menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes([ev.item], self)

    @on(Abas.Mudou, "#disco-abas")
    def _grupo(self, ev: Abas.Mudou) -> None:
        ev.stop()
        self.grupo = ev.valor
        self._disco()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        a, i = self.app, self.item
        b = ev.botao.id
        if b == "tocar":
            a.tocar_item(i)
        elif b == "aleatorio":
            a.tocar_contexto_aleatorio(i)
        elif b == "seguir":
            a.curtir_itens([i])
        elif b == "mais":
            a.opcoes([i], self)

    def curtidas_mudaram(self, uris: list[str], curtido: bool) -> None:
        if self.item.uri in uris:
            self.seguindo = curtido
            self.query_one("#seguir", Botao).label = f"{ic('ok')} seguindo" if curtido else f"{ic('adicionar')} seguir"
        for u in uris:
            (self.curtidos.add if curtido else self.curtidos.discard)(u)
        self.query_one("#destaques", Lista).redesenhar()

    def focar_entrada(self) -> None:
        l = self.query_one("#destaques", Lista)
        (l if l.itens else self.query_one("#tocar", Botao)).focus()

    def tratar(self, acao: str, itens: list) -> bool:
        if acao == "tocar" and self.app.focused is self.query_one("#destaques", Lista) and itens:
            self.app.tocar_item(itens[0], uris=[x.uri for x in self.destaques])
            return True
        return False

    def rodape(self):
        return [("enter", "tocar", "app.enter"), ("f", "fila", "app.item('seguir')"), ("c", "curtir", "app.item('curtir')"),
                ("p", "playlist", "app.item('playlist')"), ("o", "opções", "app.item('opcoes')")]


# ---------------------------------------------------------------- listas simples: recentes e mais ouvidos
PERIODOS = (("short_term", "últimas 4 semanas"), ("medium_term", "últimos 6 meses"), ("long_term", "desde sempre"))


class PaginaLista(Pagina):
    DEFAULT_CSS = """
    PaginaLista #titulo-pg { text-style: bold; color: $oma-forte; margin-top: 1; height: 1; }
    PaginaLista #chips { margin-top: 1; }
    PaginaLista #lista-pg { margin-top: 1; height: 1fr; }
    PaginaLista #vazio-pg { color: $oma-mudo; height: auto; margin-top: 1; }
    """

    def __init__(self, vista: dict, **kw) -> None:
        super().__init__(vista, **kw)
        self.tipo = vista.get("tipo", "tracks")
        self.per = vista.get("per", "short_term")
        self.curtidos: set[str] = set()

    def compose(self) -> ComposeResult:
        t = self.vista["t"]
        yield Static("tocadas recentemente" if t == "recentes" else "mais ouvidos", id="titulo-pg")
        if t == "top":
            with Horizontal(id="chips", classes="fileira"):
                yield Abas([("tracks", "faixas"), ("artists", "artistas")], self.tipo, focavel=True, id="top-tipo")
                yield Abas(list(PERIODOS), self.per, focavel=True, id="top-per")
        yield Lista(self._linha, id="lista-pg")
        yield Static("", id="vazio-pg")

    def on_mount(self) -> None:
        self.cols = ColunasFaixa(self.app, self.curtidos)
        self.recarregar()

    def recarregar(self) -> None:
        a = self.app
        if not a.conectado:
            return
        c, t = a.cliente, self.vista["t"]

        def trabalho():
            return c.recentes() if t == "recentes" else c.mais_ouvidos(self.tipo, self.per)

        def depois(r, erro):
            self.query_one("#lista-pg", Lista).definir(r or [])
            self.query_one("#vazio-pg", Static).update(str(erro) if erro else "" if r else "Ainda não há dados aqui.")
        self.em_thread(trabalho, depois)

    def _linha(self, it: Item, n: int, e: EstadoLinha) -> list[Text]:
        if it.tipo == "artist":
            a = self.app
            return [colunas([(Text(" "), 1, "left"), (Text(str(n + 1), style=a.cor("mudo")), 3, "right"),
                             (Text(it.nome, style=f"bold {a.cor('forte')}" if e.destacado else a.cor("texto")), 0, "left")], e.largura)]
        return self.cols.linha(it, n, e)

    @on(Lista.Escolhido, "#lista-pg")
    def _enter(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        it = ev.item
        if it.tipo == "artist":
            self.app.abrir_item(it)
        else:
            self.app.tocar_item(it, uris=[x.uri for x in ev.lista.itens])

    @on(Lista.Menu, "#lista-pg")
    def _menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes([ev.item], self)

    @on(Abas.Mudou)
    def _abas(self, ev: Abas.Mudou) -> None:
        ev.stop()
        if ev.abas.id == "top-tipo":
            self.tipo = ev.valor
        else:
            self.per = ev.valor
        self.vista = {**self.vista, "tipo": self.tipo, "per": self.per}
        self.app.guardar_vista(self)
        self.recarregar()

    def focar_entrada(self) -> None:
        self.query_one("#lista-pg", Lista).focus()
