"""Letra sincronizada pela LRCLIB (https://lrclib.net), porque a Web API do Spotify não tem letra.

Uma chamada `GET /api/get` com faixa, artista, álbum e duração. Só vai para a LRCLIB o
que identifica a faixa; nenhum dado da conta. Cache pequeno em memória (LRU de 12 faixas).
Qualquer falha (404, rede, JSON) vira "sem letra", nunca exceção para a interface.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass, field

from oma_spotify import __version__

URL = "https://lrclib.net/api/get"
AGENTE = f"oma-spotify/{__version__} (+https://github.com/JCsvg/oma-spotify)"
TAM_CACHE = 12
_TEMPO = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


@dataclass(slots=True)
class Letra:
    linhas: list[tuple[int, str]] = field(default_factory=list)  # (ms, texto); ms = -1 sem sincronia
    sincronizada: bool = False
    instrumental: bool = False
    motivo: str = ""  # por que não há letra (vazio quando há)

    @property
    def vazia(self) -> bool:
        return not self.linhas

    def indice(self, ms: int) -> int:
        """Linha que está tocando em `ms` (-1 antes da primeira)."""
        if not self.sincronizada:
            return -1
        n = -1
        for i, (t, _) in enumerate(self.linhas):
            if t <= ms:
                n = i
            else:
                break
        return n


def ler_lrc(texto: str) -> list[tuple[int, str]]:
    saida = []
    for linha in (texto or "").splitlines():
        marcas = list(_TEMPO.finditer(linha))
        if not marcas:
            continue
        resto = _TEMPO.sub("", linha).strip()
        for m in marcas:
            saida.append((int((int(m.group(1)) * 60 + float(m.group(2))) * 1000), resto))
    saida.sort(key=lambda x: x[0])
    return [(t, s or "♪") for t, s in saida]  # linha vazia no LRC é trecho instrumental


def de_json(d: dict) -> Letra:
    if d.get("instrumental"):
        return Letra(instrumental=True, motivo="instrumental")
    sinc = ler_lrc(d.get("syncedLyrics") or "")
    if sinc:
        return Letra(sinc, True)
    plano = [(-1, s.strip()) for s in (d.get("plainLyrics") or "").splitlines()]
    if any(s for _, s in plano):
        return Letra(plano, False)
    return Letra(motivo="sem letra para esta faixa")


class Letras:
    """Cliente da LRCLIB com cache. `abrir` é injetável nos testes."""

    def __init__(self, base: str = URL, abrir=None, tempo: float = 8.0) -> None:
        self.base = base
        self.abrir = abrir or urllib.request.urlopen
        self.tempo = tempo
        self._cache: OrderedDict[str, Letra] = OrderedDict()

    def buscar(self, uri: str, faixa: str, artista: str, album: str, dur_ms: int) -> Letra:
        if uri in self._cache:
            self._cache.move_to_end(uri)
            return self._cache[uri]
        letra = self._buscar(faixa, artista, album, dur_ms)
        if letra.motivo != "sem conexão com lrclib.net":  # falha de rede não fica em cache
            self._cache[uri] = letra
            while len(self._cache) > TAM_CACHE:
                self._cache.popitem(last=False)
        return letra

    def _buscar(self, faixa: str, artista: str, album: str, dur_ms: int) -> Letra:
        q = {"track_name": faixa, "artist_name": artista.split(",")[0].strip()}
        if album:
            q["album_name"] = album
        if dur_ms:
            q["duration"] = str(round(dur_ms / 1000))
        req = urllib.request.Request(f"{self.base}?{urllib.parse.urlencode(q)}", headers={"User-Agent": AGENTE})
        try:
            with self.abrir(req, timeout=self.tempo) as r:
                return de_json(json.loads(r.read() or b"{}"))
        except urllib.error.HTTPError as e:
            return Letra(motivo="sem letra para esta faixa" if e.code == 404 else f"lrclib.net respondeu {e.code}")
        except (urllib.error.URLError, OSError, TimeoutError):
            return Letra(motivo="sem conexão com lrclib.net")
        except ValueError:
            return Letra(motivo="resposta estranha de lrclib.net")

    def limpar(self) -> None:
        self._cache.clear()


class LetrasFalsas:
    """Para --demo e testes: letras em memória, por URI."""

    def __init__(self, letras: dict[str, str] | None = None) -> None:
        self.letras = letras or {}
        self.pedidos: list[str] = []

    def buscar(self, uri: str, faixa: str, artista: str, album: str, dur_ms: int) -> Letra:
        self.pedidos.append(uri)
        lrc = self.letras.get(uri)
        if not lrc:
            return Letra(motivo="sem letra para esta faixa")
        return Letra(ler_lrc(lrc), True)

    def limpar(self) -> None:
        pass
