"""Base das páginas que moram na área central."""

from __future__ import annotations

from textual.containers import Vertical

from oma_spotify.ui.navegacao import NavegacaoMixin


class Pagina(NavegacaoMixin, Vertical):
    ID = ""
    NOME = ""

    def restaurar(self, d: dict) -> None: ...

    def recarregar(self) -> None: ...

    def salvar(self, d: dict) -> None:
        self.app.guardar("pagina_" + self.ID, d)
