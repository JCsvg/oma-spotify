"""Janela [2] Biblioteca, em texto."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, OptionList
from textual.widgets.option_list import Option

from oma_spotify.services.modelos import Item
from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import ListaOpcoes

CHIPS = (("playlist", "Playlists"), ("artist", "Artistas"), ("album", "Álbuns"), ("show", "Podcasts"))
TIPOS_ROTULO = {"playlist": "Playlist", "artist": "Artista", "album": "Álbum", "show": "Podcast", "curtidas": "Playlist"}
CURTIDAS = Item("oma:curtidas", "curtidas", "Músicas Curtidas", "Playlist")


def linha_item(i: Item, muted: str, total_curtidas: int = 0, largura: int = 0) -> Text:
    """Uma linha de texto: nome em destaque e detalhe discreto, cortada com reticências na largura dada."""
    if i.tipo == "curtidas":
        sub = f"{total_curtidas} músicas" if total_curtidas else "suas curtidas"
        t = Text.assemble(("♥ ", "bold"), (i.nome, "bold"), (f" · {sub}", muted))
    else:
        detalhe = " · ".join(x for x in (TIPOS_ROTULO.get(i.tipo, ""), i.sub if i.tipo in ("playlist", "album") else "") if x)
        t = Text.assemble((i.nome, "bold"), (f" · {detalhe}" if detalhe else "", muted))
    t.no_wrap = True
    if largura > 4:
        t.truncate(largura, overflow="ellipsis")
    return t


class Biblioteca(NavegacaoMixin, Vertical):
    NOME = "Biblioteca"
    RODAPE = ("select", "tocar_sel", "novo")
    DEFAULT_CSS = """
    Biblioteca { padding: 0 1; }
    Biblioteca .chips { height: 1; }
    Biblioteca .chips Button { margin-right: 1; }
    Biblioteca .chips Button.ligado { background: $accent; color: $background; text-style: bold; }
    Biblioteca #busca-linha { height: 1; margin-top: 1; }
    Biblioteca #filtro-bib { width: 1fr; }
    Biblioteca #lista { height: 1fr; margin-top: 1; }
    """
    BINDINGS = [Binding("t", "tocar_sel", "Tocar"), Binding("ctrl+n", "novo", "Nova playlist")]

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.itens: list[Item] = []
        self.visiveis: list[Item] = []
        self.chip = ""
        self.ordem = "recentes"
        self.total_curtidas = 0

    def compose(self) -> ComposeResult:
        with Horizontal(classes="chips"):
            yield Button("Playlists", id="b-playlist", compact=True)
            yield Button("Artistas", id="b-artist", compact=True)
        with Horizontal(classes="chips"):
            yield Button("Álbuns", id="b-album", compact=True)
            yield Button("Podcasts", id="b-show", compact=True)
            yield Button("+ Nova", id="novo", compact=True, tooltip="Nova playlist (Ctrl+N)")
        with Horizontal(id="busca-linha"):
            yield Input(placeholder="Filtrar", id="filtro-bib", compact=True)
            yield Button("Recentes", id="ordem", compact=True)
        yield ListaOpcoes(id="lista")

    def focar_entrada(self) -> None:
        self.query_one("#lista", ListaOpcoes).focus()

    def definir(self, itens: list[Item], curtidas: int = 0) -> None:
        self.itens, self.total_curtidas = itens, curtidas
        self.reconstruir()

    def reconstruir(self) -> None:
        filtro = self.query_one("#filtro-bib", Input).value.strip().lower()
        base = [i for i in self.itens if (not self.chip or i.tipo == self.chip) and (not filtro or filtro in f"{i.nome} {i.sub}".lower())]
        if self.ordem == "az":
            base = sorted(base, key=lambda i: i.nome.lower())
        fixa = [CURTIDAS] if (not self.chip or self.chip == "playlist") and (not filtro or filtro in "músicas curtidas") else []
        self.visiveis = fixa + base
        lista = self.query_one("#lista", ListaOpcoes)
        atual = lista.highlighted
        lista.clear_options()
        muted = self.app.cor("muted")
        larg = max(self.size.width - 4, 10)
        lista.add_options([Option(linha_item(i, muted, self.total_curtidas, larg), id=str(n)) for n, i in enumerate(self.visiveis)])
        if self.visiveis:
            lista.highlighted = min(atual or 0, len(self.visiveis) - 1)
        for cid, _ in CHIPS:
            self.query_one(f"#b-{cid}", Button).set_class(self.chip == cid, "ligado")
        self.query_one("#ordem", Button).label = "Recentes" if self.ordem == "recentes" else "A a Z"

    def on_resize(self, ev=None) -> None:
        if self.is_mounted and self.itens:
            self.reconstruir()

    def selecionado(self) -> Item | None:
        n = self.query_one("#lista", ListaOpcoes).highlighted
        return self.visiveis[n] if n is not None and 0 <= n < len(self.visiveis) else None

    def estado_(self) -> dict:
        return {"chip": self.chip, "filtro": self.query_one("#filtro-bib", Input).value, "ordem": self.ordem}

    def restaurar(self, d: dict) -> None:
        if isinstance(d, dict):
            self.chip = d.get("chip", "") if d.get("chip", "") in {c for c, _ in CHIPS} else ""
            self.ordem = d.get("ordem", "recentes") if d.get("ordem") in ("recentes", "az") else "recentes"
            if isinstance(d.get("filtro"), str):
                self.query_one("#filtro-bib", Input).value = d["filtro"]

    @on(OptionList.OptionSelected, "#lista")
    def _abrir(self, ev: OptionList.OptionSelected) -> None:
        ev.stop()
        i = self.selecionado()
        if i is not None:
            self.app.abrir_item(i)

    @on(Input.Changed, "#filtro-bib")
    def _filtro(self, ev: Input.Changed) -> None:
        ev.stop()
        self.reconstruir()
        self.app.guardar("bib", self.estado_())

    @on(Input.Submitted, "#filtro-bib")
    def _filtro_ok(self, ev: Input.Submitted) -> None:
        ev.stop()
        self.focar_entrada()

    @on(Button.Pressed)
    def _botao(self, ev: Button.Pressed) -> None:
        ev.stop()
        b = ev.button.id or ""
        if b.startswith("b-"):
            self.chip = "" if self.chip == b[2:] else b[2:]
            self.reconstruir()
            self.app.guardar("bib", self.estado_())
        elif b == "ordem":
            self.ordem = "az" if self.ordem == "recentes" else "recentes"
            self.reconstruir()
            self.app.guardar("bib", self.estado_())
        elif b == "novo":
            self.action_novo()

    def action_tocar_sel(self) -> None:
        i = self.selecionado()
        if i is not None:
            self.app.tocar_item(i)

    def action_novo(self) -> None:
        self.app.nova_playlist()
