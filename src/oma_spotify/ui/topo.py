"""Topo, sem borda: marca, voltar e avançar, a trilha, a busca com `/` e a conta."""

from __future__ import annotations

from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Input, Static

from oma_spotify.ui.icones import ic
from oma_spotify.ui.widgets import Botao, Trilha


class CampoBusca(Input):
    """Campo da busca. ↓, Enter e Ctrl+↓ descem para os resultados; Esc limpa e, de novo, volta."""

    BINDINGS = [Binding("down", "resultados", show=False), Binding("escape", "limpar", show=False)]

    def action_resultados(self) -> None:
        self.app.focar_janela("principal")

    def action_limpar(self) -> None:
        if self.value:
            self.value = ""
        else:
            self.app.voltar_da_busca()


class Topo(Horizontal):
    NOME = "topo"
    DEFAULT_CSS = """
    Topo { height: 1; background: $oma-escuro; }
    Topo #marca { width: auto; padding: 0 1; }
    Topo .nav { padding: 0 0; width: 2; color: $oma-mudo; }
    Topo .nav:disabled { color: $oma-linha; }
    Topo #trilha { margin: 0 2 0 1; }
    Topo .espaco { width: 1fr; }
    Topo #caixa-busca { width: 56; height: 1; background: $oma-campo; }
    Topo #prompt { width: 2; padding-left: 1; color: $oma-mudo; }
    Topo.-buscando #prompt { color: $accent; text-style: bold; }
    Topo #busca { width: 1fr; background: $oma-campo; padding: 0 1; }
    Topo #busca:focus { background: $oma-campo; }
    Topo #dica-busca { width: auto; color: $oma-mudo; padding: 0 1; display: none; }
    Topo.-buscando #dica-busca { display: block; }
    Topo #conta { color: $oma-mudo; }
    Topo.-estreito #caixa-busca { width: 24; }
    Topo.-estreito #conta, Topo.-estreito #nome-app { display: none; }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="marca")
        yield Botao("‹", id="voltar", classes="nav", tooltip="voltar (Alt+←)")
        yield Botao("›", id="avancar", classes="nav", tooltip="avançar (Alt+→)")
        yield Trilha(id="trilha")
        yield Static("", classes="espaco")
        with Horizontal(id="caixa-busca"):
            yield Static("/", id="prompt")
            yield CampoBusca(placeholder="buscar músicas, artistas, podcasts", id="busca", compact=True)
            yield Static("esc limpa", id="dica-busca")
        yield Static("", classes="espaco")
        yield Botao(f"{ic('conta')} ", id="conta", tooltip="conta: configurações, mais ouvidos, sair")

    def on_mount(self) -> None:
        cor = self.app.cor("accent")
        self.query_one("#marca", Static).update(Text.assemble((ic("nota"), f"bold {cor}"), "  ", ("oma-spotify", "bold")))

    def ajustar(self, largura: int) -> None:
        self.set_class(largura < 110, "-estreito")
        marca = self.query_one("#marca", Static)
        cor = self.app.cor("accent")
        if largura < 110:
            marca.update(Text(ic("nota"), style=f"bold {cor}"))
        else:
            marca.update(Text.assemble((ic("nota"), f"bold {cor}"), "  ", ("oma-spotify", "bold")))
        self.query_one("#busca", Input).placeholder = "buscar" if largura < 110 else "buscar músicas, artistas, podcasts"

    def pintar(self, partes, pode_voltar: bool, pode_avancar: bool) -> None:
        self.query_one(Trilha).definir(partes)
        self.query_one("#voltar", Botao).disabled = not pode_voltar
        self.query_one("#avancar", Botao).disabled = not pode_avancar

    def pintar_conta(self, nome: str) -> None:
        self.query_one("#conta", Botao).label = f"{ic('conta')} {nome or 'conta'}"

    def focar_entrada(self) -> None:
        self.query_one("#busca", Input).focus()

    def definir_busca(self, q: str) -> None:
        b = self.query_one("#busca", Input)
        with b.prevent(Input.Changed):
            b.value = q

    def rodape(self) -> list[tuple[str, str, str]]:
        return [("enter", "ver resultados", "app.focar_janela('principal')"), ("↓", "resultados", "app.focar_janela('principal')"),
                ("alt+←", "voltar", "app.alt_h(-1)"), ("esc", "limpar", "app.esc")]

    def teclas(self) -> list[tuple[str, list[tuple[str, str]]]]:
        return [("busca", [("digitar", "busca ao vivo"), ("enter ↓ ctrl+↓", "vai para os resultados"),
                           ("esc", "limpa; de novo, volta"), ("ctrl+← →", "anda por palavra"), ("alt+← →", "voltar, avançar")])]

    @on(Botao.Apertado)
    def _botao(self, ev: Botao.Apertado) -> None:
        ev.stop()
        a = self.app
        {"voltar": a.voltar_pagina, "avancar": a.avancar_pagina, "conta": a.abrir_menu_conta}.get(ev.botao.id or "", lambda: None)()

    @on(Input.Changed, "#busca")
    def _mudou(self, ev: Input.Changed) -> None:
        ev.stop()
        self.app.buscar_ao_vivo(ev.value)

    @on(Input.Submitted, "#busca")
    def _enter(self, ev: Input.Submitted) -> None:
        ev.stop()
        q = ev.value.strip()
        if q:
            self.app._buscar_agora(q)
        self.app.call_after_refresh(self.app.focar_janela, "principal")

    def on_descendant_focus(self, ev) -> None:
        self.set_class(isinstance(ev.widget, Input), "-buscando")

    def on_descendant_blur(self, ev) -> None:
        self.remove_class("-buscando")

    def on_click(self, ev: events.Click) -> None:
        if ev.widget is self or getattr(ev.widget, "id", "") in ("prompt", "caixa-busca"):
            self.focar_entrada()
