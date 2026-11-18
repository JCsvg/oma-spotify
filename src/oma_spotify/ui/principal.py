"""Janela Principal: mostra a página aberta (início, playlist, álbum, artista, busca, podcast...)."""

from __future__ import annotations

from dataclasses import asdict

from textual.containers import Vertical
from textual.css.query import NoMatches

from oma_spotify.services.modelos import Item


def serializar(i: Item) -> dict:
    d = asdict(i)
    return {k: v for k, v in d.items() if v not in ("", 0, False) or k in ("uri", "tipo", "nome")}


def item_de_dict(d: dict) -> Item | None:
    """Item salvo no histórico ou na sua fila. Campos estranhos são ignorados; texto nulo vira vazio."""
    if not isinstance(d, dict):
        return None
    campos = {k: v for k, v in d.items() if k in Item.__dataclass_fields__}
    for k in ("sub", "extra", "id", "ano", "grupo", "desc", "quando"):
        if k in campos and not isinstance(campos[k], str):
            campos[k] = ""
    if "dur_ms" in campos and not isinstance(campos["dur_ms"], int):
        campos["dur_ms"] = 0
    if not isinstance(campos.get("uri"), str) or not isinstance(campos.get("tipo"), str):
        return None
    if not isinstance(campos.get("nome"), str):
        campos["nome"] = "(sem nome)"
    try:
        return Item(**campos)
    except TypeError:
        return None


TIPOS_ITEM = ("playlist", "album", "artist", "show")
PERIODOS_TOP = ("short_term", "medium_term", "long_term")


def vista_valida(v) -> dict | None:
    """Confere uma página vinda do histórico salvo (inclusive de versões antigas). Inválida vira None."""
    if not isinstance(v, dict):
        return None
    t = v.get("t")
    if t in ("inicio", "curtidas", "recentes", "config"):
        return v
    if t == "top":
        return {**v, "tipo": v.get("tipo") if v.get("tipo") in ("tracks", "artists") else "tracks",
                "per": v.get("per") if v.get("per") in PERIODOS_TOP else "short_term"}
    if t == "busca":
        q = v.get("q")
        return v if isinstance(q, str) and q.strip() else None
    if t == "item":
        d = v.get("item")
        it = item_de_dict(d) if isinstance(d, dict) else None
        if it is None or it.tipo not in TIPOS_ITEM or not isinstance(it.uri, str) or not it.uri:
            return None
        return v
    return None  # páginas que deixaram de existir (fila, dispositivos da 0.3.0)


def titulo_vista(v: dict, curto: bool = False) -> str:
    t = v.get("t")
    if t == "item":
        return (v.get("item") or {}).get("nome", "")
    if t == "busca":
        return "busca" if curto else f"busca · “{v.get('q', '')}”"
    return {"inicio": "início", "curtidas": "Músicas Curtidas", "recentes": "tocadas recentemente", "top": "mais ouvidos",
            "config": "configurações"}.get(t, "")


class Principal(Vertical):
    NOME = "principal"

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.vista: dict = {"t": "inicio"}
        self.pagina = None

    def mostrar(self, vista: dict, foco: bool = True) -> None:
        from oma_spotify.ui import paginas
        if self.pagina is not None:
            self.pagina.remove()
        capas = getattr(self.app, "capas", None)
        if capas is not None:
            capas.cancelar_pendentes()  # as capas da página que saiu não são mais baixadas
        vista = vista_valida(vista) or {"t": "inicio"}
        self.vista = vista
        t = vista["t"]
        if t == "inicio":
            w = paginas.PaginaInicio(vista)
        elif t == "config":
            from oma_spotify.ui.setup import PaginaConfig
            w = PaginaConfig(vista)
        elif t == "busca":
            w = paginas.PaginaBusca(vista)
        elif t in ("recentes", "top"):
            w = paginas.PaginaLista(vista)
        elif t == "item" and (vista.get("item") or {}).get("tipo") == "artist":
            w = paginas.PaginaArtista(vista)
        else:
            w = paginas.PaginaColecao(vista)
        self.pagina = w
        self.mount(w)
        self.border_title = titulo_vista(vista)
        uri = (vista.get("item") or {}).get("uri", "") if t == "item" else "oma:curtidas" if t == "curtidas" else ""
        try:
            self.app.query_one("#bib").marcar_aberto(uri)
        except NoMatches:
            pass
        if foco:
            self.call_after_refresh(self.focar_entrada)

    def focar_entrada(self) -> None:
        try:
            if self.pagina is not None:
                self.pagina.focar_entrada()
        except NoMatches:
            pass

    def ajustar(self, largura: int) -> None:
        if self.pagina is not None and hasattr(self.pagina, "ajustar"):
            self.pagina.ajustar(largura)

    def _repassar(self, nome: str, *args) -> None:
        p = self.pagina
        if p is not None and p.is_mounted and hasattr(p, nome):
            try:
                getattr(p, nome)(*args)
            except NoMatches:
                pass

    def pintar_eq(self) -> None:
        self._repassar("pintar_eq")

    def tocando_mudou(self) -> None:
        self._repassar("tocando_mudou")

    def dados_mudaram(self) -> None:
        self._repassar("dados_mudaram")

    def curtidas_mudaram(self, uris: list[str], curtido: bool) -> None:
        self._repassar("curtidas_mudaram", uris, curtido)

    def playlist_mudou(self, pid: str) -> None:
        self._repassar("playlist_mudou", pid)

    def recarregar(self) -> None:
        self._repassar("recarregar")

    def rodape(self):
        return self.pagina.rodape() if self.pagina is not None and hasattr(self.pagina, "rodape") else []

    def teclas(self):
        return self.pagina.teclas() if self.pagina is not None and hasattr(self.pagina, "teclas") else []

    def on_click(self, ev) -> None:
        # duplo clique no título da janela (a linha da borda) dá zoom
        if ev.widget is self and ev.y == 0 and ev.chain >= 2:
            self.app.action_zoom()
