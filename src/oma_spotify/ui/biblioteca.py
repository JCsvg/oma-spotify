"""Biblioteca, sem borda (como a lista de workspaces do herdr): 0 é Músicas Curtidas, 1 a 9 os fixados.

Embaixo, os dispositivos do Spotify Connect, cada um com seu estado.
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static

from oma_spotify.services.modelos import Item
from oma_spotify.ui.icones import de_aparelho, ic
from oma_spotify.ui.lista import EstadoLinha, Lista, ajustar
from oma_spotify.ui.widgets import Abas, Botao, Regua

CURTIDAS = Item("oma:curtidas", "curtidas", "Músicas Curtidas", "playlist")
TIPOS = {"playlist": "playlist", "artist": "artista", "album": "álbum", "show": "podcast", "curtidas": "playlist"}


def categorias() -> list[tuple[str, str]]:
    return [("", "tudo"), ("playlist", ic("playlist")), ("artist", ic("artist")), ("album", ic("album")), ("show", ic("show"))]


class Biblioteca(Vertical):
    NOME = "biblioteca"
    DEFAULT_CSS = """
    Biblioteca { padding: 0 1 0 0; }
    Biblioteca > .recuo, Biblioteca > Horizontal { margin-left: 1; }
    Biblioteca #bib-cab { height: 1; }
    Biblioteca #bib-titulo { width: 1fr; color: $oma-mudo; }
    Biblioteca.-foco #bib-titulo { color: $accent; text-style: bold; }
    Biblioteca #novo { padding: 0; color: $oma-mudo; }
    Biblioteca #bib-abas { margin-top: 1; }
    Biblioteca #bib-regua { height: 1; color: $oma-linha; }
    Biblioteca #bib-filtro { height: 1; margin-top: 1; }
    Biblioteca #lupa { width: 2; color: $oma-mudo; }
    Biblioteca #filtro-bib { width: 1fr; background: transparent; padding: 0; }
    Biblioteca #filtro-bib:focus { background: $oma-campo; }
    Biblioteca #ordem { color: $oma-mudo; padding: 0; }
    Biblioteca #lista { margin-top: 1; height: 1fr; }
    Biblioteca #disp-cab { height: 1; margin-top: 1; }
    Biblioteca #disp { height: auto; max-height: 6; }
    Biblioteca.-gaveta #disp-cab, Biblioteca.-gaveta #disp, Biblioteca.-gaveta #bib-titulo { display: none; }
    Biblioteca.-gaveta #bib-cab { align-horizontal: right; }
    """

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.itens: list[Item] = []
        self.cat = ""
        self.ordem = "recentes"
        self.total_curtidas = 0
        self.aberto = ""
        self._filtro_salvo = ""

    def compose(self) -> ComposeResult:
        with Horizontal(id="bib-cab"):
            yield Static("biblioteca", id="bib-titulo")
            yield Botao(ic("adicionar"), id="novo", tooltip="nova playlist (n)")
        yield Abas(categorias(), "", estilo="aba", id="bib-abas", classes="recuo")
        yield Regua(id="bib-regua", classes="recuo")
        with Horizontal(id="bib-filtro"):
            yield Static(ic("filtro"), id="lupa")
            yield Input(placeholder="filtrar", id="filtro-bib", compact=True)
            yield Botao(f"recentes {ic('menu')}", id="ordem", tooltip="ordem")
        yield Lista(self._linha, alturas=lambda it: 3, id="lista")
        yield Static("", id="disp-cab", classes="recuo")
        yield Lista(self._linha_disp, id="disp", classes="-auto")

    def on_mount(self) -> None:
        if self._filtro_salvo:
            self.query_one("#filtro-bib", Input).value = self._filtro_salvo
        self.query_one("#bib-abas", Abas).definir(self.cat)
        self._cab_disp()

    def on_resize(self) -> None:
        self._cab_disp()

    def _cab_disp(self) -> None:
        a = self.app
        w = max(10, self.size.width - 2)
        t = Text("dispositivos", style=a.cor("mudo"))
        t.append(" " * max(1, w - 13) + "d", style=a.cor("mudo"))
        self.query_one("#disp-cab", Static).update(t)

    def marcar_foco(self, ligado: bool) -> None:
        self.set_class(ligado, "-foco")

    # ------------------------------------------------------------ dados
    def definir(self, itens: list[Item], curtidas: int = 0) -> None:
        self.itens, self.total_curtidas = itens, curtidas
        self.reconstruir()

    def reconstruir(self) -> None:
        filtro = self.query_one("#filtro-bib", Input).value.strip().lower()
        fixados = self.app.config.fixados
        base = [i for i in self.itens if (not self.cat or i.tipo == self.cat) and (not filtro or filtro in f"{i.nome} {i.sub}".lower())]
        if self.ordem == "az":
            base = sorted(base, key=lambda i: i.nome.lower())
        presos = sorted([i for i in base if i.uri in fixados], key=lambda i: fixados.index(i.uri))
        resto = [i for i in base if i.uri not in fixados]
        topo = [CURTIDAS] if self.cat in ("", "playlist") and (not filtro or filtro in "músicas curtidas") else []
        lista = self.query_one("#lista", Lista)
        lista.definir(topo + presos + resto)
        self.query_one("#bib-abas", Abas).definir(self.cat)
        self.query_one("#ordem", Botao).label = f"{'recentes' if self.ordem == 'recentes' else 'a a z'} {ic('menu')}"

    @property
    def visiveis(self) -> list[Item]:
        return self.query_one("#lista", Lista).itens

    def numero(self, i: Item) -> str:
        if i.tipo == "curtidas":
            return "0"
        fx = self.app.config.fixados
        return str(fx.index(i.uri) + 1) if i.uri in fx else " "

    def _linha(self, i: Item, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        w = e.largura
        tocando = a.tocando_uri(i.uri)
        barra = Text("▌", style=a.cor("accent")) if e.destacado else Text(" ")
        num = Text(self.numero(i) + " ", style=a.cor("accent") if tocando else a.cor("mudo"))
        nome = Text()
        if i.tipo == "curtidas":
            nome.append(ic("curtida") + " ", style=a.cor("accent"))
        nome.append(i.nome, style=f"bold {a.cor('accent')}" if tocando else f"bold {a.cor('forte')}" if e.destacado else a.cor("texto"))
        eq = Text(a.eq_texto() if tocando else "", style=a.cor("accent"))
        l1 = barra + num + ajustar(nome, w - 4 - 3) + ajustar(eq, 3, "right") + Text(" ")
        if i.tipo == "curtidas":
            sub = f"{a.total_curtidas or self.total_curtidas} faixas" if (a.total_curtidas or self.total_curtidas) else "suas curtidas"
        else:
            sub = " · ".join(x for x in (TIPOS.get(i.tipo, ""), i.sub if i.tipo in ("playlist", "album") else "") if x)
        l2 = Text(" ") + Text("  ") + ajustar(Text(sub, style=a.cor("mudo")), w - 3)
        linhas = [l1, l2, Text("")]
        if i.uri == self.aberto and not e.destacado:
            linhas = [l.copy() for l in linhas[:2]] + [Text("")]
            for l in linhas[:2]:
                l.stylize(f"on {a.cor('hover')}")
        return linhas

    def _linha_disp(self, d, n: int, e: EstadoLinha) -> list[Text]:
        a = self.app
        p = a.player
        tocando = d.ativo and p is not None and p.tocando
        estado = "tocando" if tocando else "pausado" if d.ativo else "pronto"
        t = Text(" ") + Text(de_aparelho(d.tipo) + " ", style=a.cor("accent") if d.ativo else a.cor("mudo"))
        t.append_text(ajustar(Text(d.nome, style=f"bold {a.cor('forte')}" if d.ativo else a.cor("texto")), e.largura - 13))
        t.append_text(ajustar(Text(estado, style=a.cor("accent") if tocando else a.cor("mudo")), 9, "right"))
        return [t]

    def pintar_dispositivos(self, ds: list) -> None:
        self.query_one("#disp", Lista).definir(ds)

    def tocando_mudou(self) -> None:
        self.query_one("#lista", Lista).redesenhar()
        self.query_one("#disp", Lista).redesenhar()

    def pintar_eq(self) -> None:
        lista = self.query_one("#lista", Lista)
        lista.atualizar_itens([n for n, i in enumerate(lista.itens) if self.app.tocando_uri(i.uri)])

    def marcar_aberto(self, uri: str) -> None:
        if uri != self.aberto:
            self.aberto = uri
            self.query_one("#lista", Lista).redesenhar()

    # ------------------------------------------------------------ estado
    def selecionado(self) -> Item | None:
        it = self.query_one("#lista", Lista).item_atual()
        return it if isinstance(it, Item) else None

    def estado_(self) -> dict:
        return {"cat": self.cat, "filtro": self.query_one("#filtro-bib", Input).value, "ordem": self.ordem}

    def restaurar(self, d: dict) -> None:
        if isinstance(d, dict):
            self.cat = d.get("cat", "") if d.get("cat", "") in {c for c, _ in categorias()} else ""
            self.ordem = d.get("ordem", "recentes") if d.get("ordem") in ("recentes", "az") else "recentes"
            if isinstance(d.get("filtro"), str):
                self._filtro_salvo = d["filtro"]
                try:
                    self.query_one("#filtro-bib", Input).value = d["filtro"]
                except Exception:
                    pass
            try:
                self.query_one("#bib-abas", Abas).definir(self.cat)
            except Exception:
                pass

    # ------------------------------------------------------------ janela
    def focar_entrada(self) -> None:
        self.query_one("#lista", Lista).focus()

    def alt_horizontal(self, passo: int) -> None:
        self.query_one("#bib-abas", Abas).trocar(passo)

    def filtrar(self) -> None:
        self.query_one("#filtro-bib", Input).focus()

    def esc(self) -> bool:
        f = self.query_one("#filtro-bib", Input)
        if self.app.focused is f:
            if f.value:
                f.value = ""
            else:
                self.focar_entrada()
            return True
        return False

    def tratar(self, acao: str, itens: list) -> bool:
        if self.app.focused is self.query_one("#disp", Lista):
            return True  # teclas de item não valem nos aparelhos
        return False

    def rodape(self) -> list[tuple[str, str, str]]:
        r = [("enter", "abrir", "app.enter"), ("t", "tocar", "app.item('tocar')"), ("alt+←→", "categoria", "app.alt_h(1)")]
        if self.has_class("-gaveta"):
            return r + [("esc", "fechar", "app.esc")]
        return r + [("P", "fixar", "app.item('fixar')"), ("n", "nova", "app.nova_playlist")]

    def teclas(self) -> list[tuple[str, list[tuple[str, str]]]]:
        return [("nesta janela", [("↑ ↓", "itens"), ("alt+← →", "categoria"), ("enter", "abre na principal"),
                                  ("t", "toca sem abrir"), ("P", "fixa (ganha um número)"), ("n", "nova playlist"),
                                  ("ctrl+f", "filtra"), ("x", "remove (pede confirmação)")])]

    # ------------------------------------------------------------ eventos
    @on(Lista.Escolhido, "#lista")
    def _abrir(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.abrir_item(ev.item)
        if self.has_class("-gaveta"):
            self.app.fechar_gaveta()
        else:
            self.app.focar_janela("principal")

    @on(Lista.Menu, "#lista")
    def _menu(self, ev: Lista.Menu) -> None:
        ev.stop()
        self.app.opcoes([ev.item], self)

    @on(Lista.Escolhido, "#disp")
    def _aparelho(self, ev: Lista.Escolhido) -> None:
        ev.stop()
        self.app.transferir(ev.item)

    @on(Abas.Mudou, "#bib-abas")
    def _cat(self, ev: Abas.Mudou) -> None:
        ev.stop()
        self.cat = ev.valor
        self.reconstruir()
        self.app.guardar("bib", self.estado_())

    @on(Input.Changed, "#filtro-bib")
    def _filtro(self, ev: Input.Changed) -> None:
        ev.stop()
        self.reconstruir()
        self.app.guardar("bib", self.estado_())

    @on(Input.Submitted, "#filtro-bib")
    def _filtro_ok(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.focar_entrada()

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        b = ev.botao.id
        if b == "ordem":
            self.ordem = "az" if self.ordem == "recentes" else "recentes"
            self.reconstruir()
            self.app.guardar("bib", self.estado_())
        elif b == "novo":
            self.app.nova_playlist()

    def on_click(self, ev) -> None:
        if getattr(ev.widget, "id", "") == "disp-cab":
            self.app.action_tocar_em()
