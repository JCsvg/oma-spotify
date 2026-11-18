"""Cliente da Web API do Spotify (só biblioteca padrão).

Endpoints vigentes em 2026: biblioteca por /me/library (uris), itens de playlist
em /playlists/{id}/items, criação em /me/playlists, busca com limit máximo 10.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from oma_spotify.services.erros import de_status
from oma_spotify.services.modelos import Dispositivo, ErroSpotify, Item, Player

BASE = "https://api.spotify.com/v1"
TIPOS_BUSCA = ("track", "album", "artist", "playlist", "show")


def _nomes(lst) -> str:
    return ", ".join(a.get("name", "") for a in (lst or []) if a)


def _texto(html: str | None) -> str:
    """Descrição de playlist vem com entidades HTML e às vezes com tags."""
    if not html:
        return ""
    import html as _h
    return re.sub(r"<[^>]+>", "", _h.unescape(html)).strip()


def item_de(o: dict | None, meu_id: str = "") -> Item | None:
    if not o or not o.get("uri"):
        return None
    t = o.get("type", "track")
    base = dict(uri=o["uri"], tipo=t, nome=o.get("name", "(sem nome)"), id=o.get("id", ""))
    if t == "track":
        alb = o.get("album") or {}
        return Item(**base, sub=_nomes(o.get("artists")), extra=alb.get("name", ""), dur_ms=o.get("duration_ms", 0),
                    ano=(alb.get("release_date") or "")[:4])
    if t == "episode":
        return Item(**base, sub=(o.get("show") or {}).get("name", ""), dur_ms=o.get("duration_ms", 0),
                    ano=(o.get("release_date") or "")[:10])
    if t == "album":
        n = o.get("total_tracks")
        return Item(**base, sub=_nomes(o.get("artists")), extra=f"{n} faixas" if n else "",
                    ano=(o.get("release_date") or "")[:4], grupo=o.get("album_group") or o.get("album_type") or "")
    if t == "artist":
        return Item(**base)
    if t == "playlist":
        cont = o.get("items") or o.get("tracks") or {}
        n = cont.get("total") if isinstance(cont, dict) else None
        dono = o.get("owner") or {}
        return Item(**base, sub=dono.get("display_name") or "", extra=f"{n} faixas" if n is not None else "",
                    meu=bool(meu_id) and dono.get("id") == meu_id, desc=_texto(o.get("description")),
                    colab=bool(o.get("collaborative")))
    if t == "show":
        return Item(**base, sub=o.get("publisher", ""), desc=_texto(o.get("description")))
    return Item(**base)


class ClienteSpotify:
    def __init__(self, sessao, base: str = BASE, dormir=time.sleep) -> None:
        self.sessao = sessao
        self.base = base.rstrip("/")
        self._dormir = dormir
        self._eu = ""
        self._nome = ""

    # ------------------------------------------------------------ HTTP
    def _req(self, metodo: str, caminho: str, params: dict | None = None, corpo: dict | None = None):
        url = self.base + caminho
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        dados = json.dumps(corpo).encode() if corpo is not None else None
        renovado = False
        for tentativa in range(4):
            req = urllib.request.Request(url, data=dados, method=metodo)
            req.add_header("Authorization", "Bearer " + self.sessao.token())
            if dados is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=15) as r:
                    bruto = r.read()
                    return json.loads(bruto) if bruto else None
            except urllib.error.HTTPError as e:
                if e.code == 401 and not renovado:
                    renovado = True
                    self.sessao.token(forcar=True)
                    continue
                if e.code == 429 and tentativa < 3:
                    try:
                        espera = float(e.headers.get("Retry-After", "1"))
                    except ValueError:
                        espera = 1.0
                    self._dormir(min(max(espera, 0.5), 10.0))
                    continue
                razao = ""
                try:
                    razao = (json.loads(e.read()).get("error") or {}).get("reason", "")
                except Exception:
                    pass
                raise de_status(e.code, razao) from None
            except (urllib.error.URLError, OSError, TimeoutError):
                raise ErroSpotify("Sem conexão com o Spotify. Confira a internet.") from None
        raise de_status(429)

    def _paginas(self, caminho: str, params: dict, chave: str = "items", maximo: int = 200) -> list:
        saida, off = [], 0
        while off < maximo:
            r = self._req("GET", caminho, {**params, "limit": 50, "offset": off}) or {}
            lote = r.get(chave, []) if isinstance(r, dict) else []
            saida += lote
            if not r.get("next") or not lote:
                break
            off += 50
        return saida

    # ------------------------------------------------------------ player
    def player(self) -> Player | None:
        r = self._req("GET", "/me/player", {"additional_types": "track,episode"})
        if not r:
            return None
        dev = r.get("device") or {}
        return Player(item=item_de(r.get("item")), progresso_ms=r.get("progress_ms") or 0, tocando=bool(r.get("is_playing")),
                      aleatorio=bool(r.get("shuffle_state")), repetir=r.get("repeat_state", "off"),
                      volume=dev.get("volume_percent"), dispositivo=dev.get("name", ""),
                      contexto=(r.get("context") or {}).get("uri", ""))

    def tocar(self, contexto: str | None = None, uris: list[str] | None = None, desde: str | None = None,
              device_id: str | None = None) -> None:
        corpo: dict = {}
        if contexto:
            corpo["context_uri"] = contexto
            if desde:
                corpo["offset"] = {"uri": desde}
        elif uris:
            corpo["uris"] = uris[:100]
            if desde:
                corpo["offset"] = {"uri": desde}
        self._req("PUT", "/me/player/play", {"device_id": device_id}, corpo or None)

    def retomar(self) -> None:
        self._req("PUT", "/me/player/play")

    def pausar(self) -> None:
        self._req("PUT", "/me/player/pause")

    def proxima(self) -> None:
        self._req("POST", "/me/player/next")

    def anterior(self) -> None:
        self._req("POST", "/me/player/previous")

    def buscar_posicao(self, ms: int) -> None:
        self._req("PUT", "/me/player/seek", {"position_ms": max(0, int(ms))})

    def volume(self, pct: int, device_id: str | None = None) -> None:
        self._req("PUT", "/me/player/volume", {"volume_percent": max(0, min(100, int(pct))), "device_id": device_id})

    def aleatorio(self, ligado: bool) -> None:
        self._req("PUT", "/me/player/shuffle", {"state": "true" if ligado else "false"})

    def repetir(self, modo: str) -> None:
        self._req("PUT", "/me/player/repeat", {"state": modo})

    def fila(self) -> list[Item]:
        r = self._req("GET", "/me/player/queue") or {}
        return [i for i in (item_de(x) for x in r.get("queue", [])) if i]

    def enfileirar(self, uri: str) -> None:
        self._req("POST", "/me/player/queue", {"uri": uri})

    def dispositivos(self) -> list[Dispositivo]:
        r = self._req("GET", "/me/player/devices") or {}
        return [Dispositivo(d["id"], d.get("name", ""), d.get("type", ""), bool(d.get("is_active")), d.get("volume_percent"))
                for d in r.get("devices", []) if d.get("id")]

    def transferir(self, device_id: str, tocar: bool = True) -> None:
        self._req("PUT", "/me/player", corpo={"device_ids": [device_id], "play": tocar})

    # ------------------------------------------------------------ biblioteca
    def _meu_id(self) -> str:
        if not self._eu:
            r = self._req("GET", "/me") or {}
            self._eu, self._nome = r.get("id", ""), r.get("display_name") or r.get("id", "")
        return self._eu

    def nome_usuario(self) -> str:
        self._meu_id()
        return self._nome

    def playlists(self) -> list[Item]:
        eu = self._meu_id()
        return [i for i in (item_de(p, eu) for p in self._paginas("/me/playlists", {})) if i]

    def itens_playlist(self, pid: str) -> list[Item]:
        saida = []
        for x in self._paginas(f"/playlists/{pid}/items", {"additional_types": "track,episode"}):
            i = item_de(x.get("item") or x.get("track"))
            if i:
                saida.append(i)
        return saida

    def criar_playlist(self, nome: str) -> Item:
        r = self._req("POST", "/me/playlists", corpo={"name": nome, "public": False})
        return item_de(r, self._meu_id())  # type: ignore[return-value]

    def adicionar_a_playlist(self, pid: str, uri: str) -> None:
        self._req("POST", f"/playlists/{pid}/items", corpo={"uris": [uri]})

    def remover_da_playlist(self, pid: str, uri: str) -> None:
        self._req("DELETE", f"/playlists/{pid}/items", corpo={"items": [{"uri": uri}]})

    def inserir_na_playlist(self, pid: str, uris: list[str], posicao: int) -> None:
        """Devolve faixas a uma posição (desfazer remoção)."""
        self._req("POST", f"/playlists/{pid}/items", corpo={"uris": uris[:100], "position": max(0, int(posicao))})

    def mover_na_playlist(self, pid: str, inicio: int, antes: int, n: int = 1) -> None:
        """Reordena: n faixas a partir de `inicio` vão para antes da posição `antes` (índices da playlist atual)."""
        self._req("PUT", f"/playlists/{pid}/items", corpo={"range_start": inicio, "insert_before": antes, "range_length": n})

    def curtidas(self) -> list[Item]:
        return [i for i in (item_de(x.get("track")) for x in self._paginas("/me/tracks", {}, maximo=100)) if i]

    def albuns_salvos(self) -> list[Item]:
        return [i for i in (item_de(x.get("album")) for x in self._paginas("/me/albums", {}, maximo=100)) if i]

    def artistas_seguidos(self) -> list[Item]:
        r = self._req("GET", "/me/following", {"type": "artist", "limit": 50}) or {}
        return [i for i in (item_de(a) for a in (r.get("artists") or {}).get("items", [])) if i]

    def podcasts(self) -> list[Item]:
        return [i for i in (item_de(x.get("show")) for x in self._paginas("/me/shows", {}, maximo=100)) if i]

    def faixas_do_album(self, aid: str, nome: str = "") -> list[Item]:
        itens = []
        for t in self._paginas(f"/albums/{aid}/tracks", {}):
            i = item_de({**t, "album": {"name": nome}})
            if i:
                itens.append(i)
        return itens

    def episodios_do_show(self, sid: str) -> list[Item]:
        return [i for i in (item_de(x) for x in self._paginas(f"/shows/{sid}/episodes", {}, maximo=100)) if i]

    def albuns_do_artista(self, aid: str) -> list[Item]:
        r = self._paginas(f"/artists/{aid}/albums", {"include_groups": "album,single,appears_on"}, maximo=50)
        return [i for i in (item_de(a) for a in r) if i]

    def curtido(self, uris: list[str]) -> list[bool]:
        if not uris:
            return []
        r = self._req("GET", "/me/library/contains", {"uris": ",".join(uris[:40])})
        return [bool(x) for x in (r or [])]

    def curtir(self, uri: str) -> None:
        self._req("PUT", "/me/library", {"uris": uri})

    def descurtir(self, uri: str) -> None:
        self._req("DELETE", "/me/library", {"uris": uri})

    # ------------------------------------------------------------ busca e histórico
    def buscar(self, q: str, tipos=TIPOS_BUSCA, offset: int = 0, limite: int = 10) -> dict[str, list[Item]]:
        """No máximo 10 por tipo e por página (limite da API desde fevereiro de 2026)."""
        tipos = tuple(tipos)
        r = self._req("GET", "/search", {"q": q, "type": ",".join(tipos), "limit": min(10, limite),
                                         "offset": offset or None}) or {}
        eu = self._meu_id()
        return {t: [i for i in (item_de(x, eu) for x in (r.get(t + "s") or {}).get("items", []) if x) if i] for t in tipos}

    def recentes(self) -> list[Item]:
        r = self._req("GET", "/me/player/recently-played", {"limit": 50}) or {}
        saida = []
        for x in r.get("items", []):
            i = item_de(x.get("track"))
            if i:
                i.quando = x.get("played_at", "")
                saida.append(i)
        return saida

    def mais_ouvidos(self, tipo: str = "tracks", periodo: str = "medium_term") -> list[Item]:
        r = self._req("GET", f"/me/top/{tipo}", {"limit": 50, "time_range": periodo}) or {}
        return [i for i in (item_de(x) for x in r.get("items", [])) if i]
