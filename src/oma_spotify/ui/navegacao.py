"""Navegação por teclado e mouse, igual em todas as telas e diálogos (como no oma-docker).

Esquema (adaptado do omarchy-manager):
- Ctrl+j/k (ou Ctrl+↓/↑): próxima/anterior zona; Ctrl+h/l (ou Ctrl+←/→): entre botões;
- Ctrl+Enter aperta o botão em foco; Ctrl+Espaço ou F1: painel de ajuda; Esc volta para a lista.
Uma zona é um controle focável. Botões em sequência formam uma zona só, e a fileira
de botões logo abaixo de uma tabela entra na zona da tabela.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Input, Label, OptionList, Select, Static
from textual.widgets._footer import FooterKey

NOMES = {"question_mark": "?", "slash": "/", "space": "Espaço", "escape": "Esc", "enter": "Enter",
         "left": "←", "right": "→", "up": "↑", "down": "↓"}

COMUM = """[b]Navegação (igual em todas as telas)[/b]
  Alt+← → / Alt+h l    tela anterior / próxima (ou clique na aba)
  1 a 9                ir direto para a tela
  ↑ ↓ / j k            linhas da lista
  ← → / h l            entre botões e painéis da mesma tela
  Enter                abrir ou tocar o item
  Espaço               play/pausa (fora de campos de texto)
  /                    buscar ou filtrar
  Ctrl+j / Ctrl+k      próxima / anterior seção
  Ctrl+h / Ctrl+l      entre os botões
  Ctrl+Enter           aperta o botão em foco
  Esc                  volta para a lista
  Clique               seleciona a linha; de novo, ação principal"""
FINAL = """
[b]Geral[/b]
  q                    sair (o contexto da tela fica guardado)"""


def nome_tecla(tecla: str) -> str:
    partes = []
    for p in tecla.split("+"):
        if p in NOMES:
            partes.append(NOMES[p])
        elif p in ("ctrl", "alt", "shift"):
            partes.append(p.capitalize())
        else:
            partes.append(p.upper() if len(p) == 1 and not p.islower() else p)
    return "+".join(partes)


def eh_controle(w: Widget) -> bool:
    if not w.focusable:
        return False
    if isinstance(w, ScrollableContainer) and not isinstance(w, (DataTable, OptionList, Input)):
        return False
    return not any(isinstance(a, Select) for a in w.ancestors)


class AjudaAba(ModalScreen):
    """Painel de teclas, estilo which-key. Esc, q, Ctrl+Espaço ou F1 fecham. O X fecha com o mouse."""

    DEFAULT_CSS = """
    AjudaAba { align: center middle; }
    AjudaAba #caixa { width: 88; height: auto; max-height: 95%; background: $surface; border: round $accent; padding: 0 2; }
    AjudaAba .titulo { text-style: bold; color: $accent; }
    AjudaAba .mudo { color: $text-muted; }
    AjudaAba #fechar { margin-top: 1; }
    """
    BINDINGS = [Binding("escape,q,ctrl+@,ctrl+space,ctrl+at,f1", "fechar", "Fechar", priority=True)]

    def __init__(self, titulo: str, texto: str) -> None:
        super().__init__()
        self._titulo, self._texto = titulo, texto

    def compose(self) -> ComposeResult:
        with Vertical(id="caixa"):
            yield Label(f"Teclas: {self._titulo}", classes="titulo")
            yield Static(self._texto)
            yield Button("Fechar", id="fechar")

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        self.dismiss(None)

    def action_fechar(self) -> None:
        self.dismiss(None)


class NavegacaoMixin:
    SECOES: tuple[tuple[str, ...], ...] = ()
    RODAPE: tuple[str, ...] = ()
    TITULO_AJUDA = ""
    AJUDA_EXTRA = ""

    def zonas(self) -> list[list[Widget]]:
        if self.SECOES:
            saida = []
            for seletores in self.SECOES:
                z = [w for s in seletores for w in self.query(s) if w.focusable]  # type: ignore[attr-defined]
                if z:
                    saida.append(z)
            return saida
        zonas: list[list[Widget]] = []
        for w in self.query("*"):  # type: ignore[attr-defined]
            if not eh_controle(w) or not w.display:
                continue
            if isinstance(w, Button) and zonas:
                ult = zonas[-1]
                if isinstance(ult[-1], Button) and ult[-1].parent is w.parent:
                    ult.append(w)
                    continue
                if isinstance(ult[0], DataTable) and len(ult) == 1:
                    ult.append(w)
                    continue
            zonas.append([w])
        return zonas

    def _foco(self) -> Widget | None:
        return self.screen.focused if hasattr(self, "screen") else None  # type: ignore[attr-defined]

    def zona_atual(self, zonas: list[list[Widget]] | None = None) -> int:
        zonas = zonas if zonas is not None else self.zonas()
        f = self._foco()
        for n, z in enumerate(zonas):
            if f in z:
                return n
        return -1

    def focar_zona(self, n: int) -> None:
        zonas = self.zonas()
        if zonas:
            zonas[max(0, min(len(zonas) - 1, n))][0].focus()

    def mover_secao(self, passo: int) -> None:
        zonas = self.zonas()
        if not zonas:
            return
        atual = self.zona_atual(zonas)
        self.focar_zona(0 if atual < 0 else atual + passo)

    def focar_entrada(self) -> None:
        zonas = self.zonas()
        for z in zonas:
            if isinstance(z[0], DataTable):
                z[0].focus()
                return
        for z in zonas:  # sem lista, o primeiro botão (um campo de texto engoliria as teclas de atalho)
            if isinstance(z[0], Button):
                z[0].focus()
                return
        if zonas:
            zonas[0][0].focus()

    def fileira(self) -> list[Widget]:
        zonas = self.zonas()
        n = self.zona_atual(zonas)
        if n < 0:
            return []
        z = zonas[n]
        if isinstance(z[0], Button):
            return []
        resto = z[1:] if isinstance(z[0], (DataTable, OptionList)) else z
        return resto if len(resto) > 1 or (resto and resto[0] is not self._foco()) else []

    def acoes_do_rodape(self) -> list[str]:
        f = self._foco()
        if isinstance(f, Button):
            return ["botao_acionar", "botao(1)", "aba_relativa(1)", "ajuda_aba"]
        if isinstance(f, (Input, Select)):
            return ["aba_relativa(1)", "ajuda_aba"]
        return list(self.RODAPE)[:3] + ["aba_relativa(1)", "ajuda_aba"]

    def texto_ajuda(self) -> str:
        linhas = []
        for b in type(self).BINDINGS:  # type: ignore[attr-defined]
            if isinstance(b, Binding) and b.description and b.key not in ("j", "k") and not b.action.startswith("app."):
                teclas = b.key_display or " / ".join(nome_tecla(k.strip()) for k in b.key.split(","))
                linhas.append(f"  {teclas:<20} {b.description}")
        meio = "\n[b]Nesta tela (cada tecla tem um botão igual)[/b]\n" + "\n".join(linhas) + "\n" if linhas else "\n"
        return COMUM + "\n" + meio + (self.AJUDA_EXTRA + "\n" if self.AJUDA_EXTRA else "") + FINAL


class RodapeEnxuto(Footer):
    """Só as teclas da zona focada (no máximo 5). Em diálogo, o rodapé padrão."""

    def compose(self) -> ComposeResult:
        aba = None
        try:
            if len(self.app.screen_stack) == 1:
                aba = self.app.nav_da_aba()
        except Exception:
            aba = None
        if aba is None:
            yield from super().compose()
            return
        if not self._bindings_ready:
            return
        permitidas = aba.acoes_do_rodape()
        vistos: dict[str, tuple] = {}
        for _, b, enabled, tooltip in self.screen.active_bindings.values():
            if b.action in permitidas and b.action not in vistos and b.show:
                vistos[b.action] = (b, enabled, tooltip)
        ordem = [vistos[n] for n in permitidas if n in vistos]
        self.styles.grid_size_columns = max(len(ordem), 1)
        for b, enabled, tooltip in ordem:
            yield FooterKey(b.key, self.app.get_key_display(b), b.description, b.action,
                            disabled=not enabled, tooltip=tooltip).data_bind(compact=Footer.compact)
