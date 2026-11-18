"""Coluna esquerda "Sua Biblioteca"."""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, OptionList
from textual.widgets.option_list import Option

from oma_spotify.services.modelos import Item
from oma_spotify.ui.navegacao import NavegacaoMixin
from oma_spotify.ui.widgets import ListaOpcoes

CHIPS = (("playlist", "Playlists"), ("artist", "Artistas"), ("album", "Álbuns"), ("show", "Podcasts"))
TIPOS_ROTULO = {"playlist": "Playlist", "artist": "Artista", "album": "Álbum", "show": "Podcast", "curtidas": "Playlist"}
CURTIDAS = Item("oma:curtidas", "curtidas", "Músicas Curtidas", "Playlist")


class Biblioteca(NavegacaoMixin, Vertical):
    NOME = "Biblioteca"
    RODAPE = ("select", "tocar_sel", "novo", "recolher")
    DEFAULT_CSS = """
    Biblioteca { width: 34; background: $surface; padding: 0 1; }
    Biblioteca.recolhida { width: 10; }
    Biblioteca #cab { height: 1; }
    Biblioteca #rot { width: 1fr; text-style: bold; }
    Biblioteca .chips { height: 1; }
    Biblioteca .chips Button { margin-right: 1; }
    Biblioteca .chips Button.ligado { background: $accent; color: $background; text-style: bold; }
    Biblioteca #busca-linha { height: 3; }
    Biblioteca #filtro-bib { width: 1fr; }
    Biblioteca #lista { height: 1fr; background: $surface; }
    Biblioteca.recolhida .chips, Biblioteca.recolhida #busca-linha, Biblioteca.recolhida #rot, Biblioteca.recolhida #novo { display: none; }
    """
    BINDINGS = [Binding("t", "tocar_sel", "Tocar"), Binding("ctrl+n", "novo", "Nova playlist"),
                Binding("ctrl+b", "recolher", "Recolher")]

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.itens: list[Item] = []
        self.visiveis: list[Item] = []
        self.chip = ""
        self.ordem = "recentes"
        self.total_curtidas = 0
        self.recolhida = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="cab"):
            yield Label("Sua Biblioteca", id="rot")
            yield Button("+", id="novo", compact=True, tooltip="Nova playlist (Ctrl+N)")
            yield Button("⇔", id="recolher", compact=True, tooltip="Recolher ou expandir (Ctrl+B)")
        with Horizontal(classes="chips"):
            yield Button("Playlists", id="b-playlist", compact=True)
            yield Button("Artistas", id="b-artist", compact=True)
        with Horizontal(classes="chips"):
            yield Button("Álbuns", id="b-album", compact=True)
            yield Button("Podcasts", id="b-show", compact=True)
        with Horizontal(id="busca-linha"):
            yield Input(placeholder="Buscar", id="filtro-bib")
            yield Button("Recentes", id="ordem", compact=True)
        yield ListaOpcoes(id="lista")

    def focar_entrada(self) -> None:
        self.query_one("#lista", ListaOpcoes).focus()

    # ------------------------------------------------------------ dados
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
        lista.add_options([Option(self.prompt(i, n), id=str(n)) for n, i in enumerate(self.visiveis)])
        if self.visiveis:
            lista.highlighted = min(atual or 0, len(self.visiveis) - 1)
        for cid, _ in CHIPS:
            self.query_one(f"#b-{cid}", Button).set_class(self.chip == cid, "ligado")
        self.query_one("#ordem", Button).label = "Recentes" if self.ordem == "recentes" else "A a Z"

    def prompt(self, i: Item, n: int):
        thumb = self.app.capas.texto(i, 6, 3, lambda: self.atualizar_miniatura(n, i), self.app.cor("accent")) \
            if i.tipo != "curtidas" else self.miniatura_curtidas()
        if self.recolhida:
            return thumb
        sub = i.sub
        if i.tipo == "curtidas" and self.total_curtidas:
            sub = f"Playlist • {self.total_curtidas} músicas"
        elif i.tipo != "curtidas":
            sub = " • ".join(x for x in (TIPOS_ROTULO.get(i.tipo, ""), i.sub if i.tipo in ("playlist", "album") else "", i.extra if i.tipo == "playlist" else "") if x)
        g = Table.grid(padding=(0, 1), expand=True)
        g.add_column(width=6)
        g.add_column(ratio=1, no_wrap=True, overflow="ellipsis")
        g.add_row(thumb, Text.assemble((i.nome + "\n", "bold"), (sub, self.app.cor("muted")), "\n"))
        return g

    def miniatura_curtidas(self) -> Text:
        t = Text(no_wrap=True)
        cor = self.app.cor("accent")
        for r in range(3):
            t.append(("  ♥   " if r == 1 else "      "), style=f"bold white on {cor}")
            if r < 2:
                t.append("\n")
        return t

    def atualizar_miniatura(self, n: int, i: Item) -> None:
        try:
            self.query_one("#lista", ListaOpcoes).replace_option_prompt(str(n), self.prompt(i, n))
        except Exception:
            pass

    def selecionado(self) -> Item | None:
        n = self.query_one("#lista", ListaOpcoes).highlighted
        return self.visiveis[n] if n is not None and 0 <= n < len(self.visiveis) else None

    def alternar_recolhida(self, valor: bool | None = None) -> None:
        self.recolhida = (not self.recolhida) if valor is None else valor
        self.set_class(self.recolhida, "recolhida")
        self.reconstruir()

    # ------------------------------------------------------------ estado
    def estado_(self) -> dict:
        return {"chip": self.chip, "filtro": self.query_one("#filtro-bib", Input).value, "ordem": self.ordem}

    def restaurar(self, d: dict) -> None:
        if isinstance(d, dict):
            self.chip = d.get("chip", "") if d.get("chip", "") in {c for c, _ in CHIPS} else ""
            self.ordem = d.get("ordem", "recentes") if d.get("ordem") in ("recentes", "az") else "recentes"
            if isinstance(d.get("filtro"), str):
                self.query_one("#filtro-bib", Input).value = d["filtro"]

    # ------------------------------------------------------------ eventos
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
        elif b == "recolher":
            self.action_recolher()

    def action_tocar_sel(self) -> None:
        i = self.selecionado()
        if i is not None:
            self.app.tocar_item(i)

    def action_novo(self) -> None:
        self.app.nova_playlist()

    def action_recolher(self) -> None:
        self.app.action_coluna()
