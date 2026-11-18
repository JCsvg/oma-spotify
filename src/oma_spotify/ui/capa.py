"""Capas de álbum, playlist e artista desenhadas em meio-blocos (▀ com cor de 24 bits).

Cada célula do terminal mostra 2 pixels na vertical (cor de frente e de fundo).
Sem Pillow ou sem rede, cai para um quadrado com as iniciais. No --demo as capas são procedurais.
Nunca há log: a URL da imagem não sai daqui.
"""

from __future__ import annotations

import colorsys
import hashlib
import os
import threading
import urllib.request
from functools import lru_cache
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual.widget import Widget

try:  # Pillow é dependência do pacote, mas o app funciona sem ele
    from PIL import Image
except Exception:  # pragma: no cover - depende do ambiente
    Image = None  # type: ignore[assignment]

Pixels = list[list[tuple[int, int, int]]]
LIMITE_BYTES = 3_000_000


def pasta_cache() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "oma-spotify"


def _rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return int(r * 255), int(g * 255), int(b * 255)


@lru_cache(maxsize=256)
def procedural(semente: str, w: int, h: int) -> Pixels:
    """Capa fictícia (gradiente, anéis, listras ou xadrez) a partir de uma semente. h em células."""
    d = hashlib.md5(semente.encode()).digest()
    h1, h2, tipo = d[0] / 255, (d[1] / 255 + 0.3) % 1, d[2] % 4
    alt = h * 2
    pix: Pixels = []
    for y in range(alt):
        linha = []
        for x in range(w):
            u, v = x / max(w - 1, 1), y / max(alt - 1, 1)
            if tipo == 0:
                t = (u + v) / 2
                cor = _rgb(h1 + (h2 - h1) * t, 0.65, 0.55 + 0.4 * t)
            elif tipo == 1:
                dist = ((u - 0.5) ** 2 + (v - 0.5) ** 2) ** 0.5
                cor = _rgb(h1 if int(dist * 7) % 2 else h2, 0.7, 0.45 + 0.5 * (1 - dist))
            elif tipo == 2:
                cor = _rgb(h1 if int((u + v) * 6) % 2 else h2, 0.6, 0.75 - 0.25 * v)
            else:
                cor = _rgb(h1 if (int(u * 4) + int(v * 4)) % 2 else h2, 0.55, 0.7)
            linha.append(cor)
        pix.append(linha)
    return pix


def para_texto(pix: Pixels, w: int, h: int) -> Text:
    t = Text(no_wrap=True, overflow="crop")
    for r in range(h):
        topo, base = pix[min(2 * r, len(pix) - 1)], pix[min(2 * r + 1, len(pix) - 1)]
        for c in range(w):
            a, b = topo[c], base[c]
            t.append("▀", Style(color=f"rgb({a[0]},{a[1]},{a[2]})", bgcolor=f"rgb({b[0]},{b[1]},{b[2]})"))
        if r < h - 1:
            t.append("\n")
    return t


def iniciais(nome: str, w: int, h: int, cor: str = "#7aa2f7") -> Text:
    ini = "".join(p[0] for p in nome.split()[:2]).upper() or "♪"
    linhas = []
    for r in range(h):
        linhas.append(ini.center(w) if r == h // 2 else " " * w)
    return Text("\n".join(linhas), style=f"bold {cor} on #2a2f45")


def pixels_de_arquivo(caminho: Path, w: int, h: int) -> Pixels | None:
    """Lê e reduz a imagem para w x 2h pixels. None se não houver Pillow ou o arquivo não abrir."""
    if Image is None:
        return None
    try:
        with Image.open(caminho) as im:
            im = im.convert("RGB").resize((w, h * 2), Image.LANCZOS)
            dados = list(im.getdata())
    except Exception:
        return None
    return [[dados[y * w + x] for x in range(w)] for y in range(h * 2)]


class Capas:
    """Cache de capas: em memória (por tamanho) e em disco com limite de tamanho."""

    def __init__(self, demo: bool, pasta: Path | None = None, limite_mb: int = 50, baixar=None, chamar=None) -> None:
        self.demo = demo
        self.pasta = pasta or pasta_cache()
        self.limite = limite_mb * 1_000_000
        self.baixar = baixar or self._baixar
        self.chamar = chamar or (lambda f, *a: f(*a))  # volta para a thread da interface
        self.pix: dict[tuple, Pixels | bool] = {}
        self.pendentes: set[tuple] = set()
        self._trava = threading.Lock()

    def texto(self, item, w: int, h: int, ao_chegar=None, cor: str = "#7aa2f7") -> Text:
        if self.demo:
            return para_texto(procedural(item.uri, w, h), w, h)
        chave = (item.capa, w, h)
        if item.capa:
            p = self.pix.get(chave)
            if p:
                return para_texto(p, w, h)
            if p is None and chave not in self.pendentes:
                self.pendentes.add(chave)
                threading.Thread(target=self._trabalho, args=(chave, ao_chegar), daemon=True).start()
        return iniciais(item.nome, w, h, cor)

    def _trabalho(self, chave, ao_chegar) -> None:
        url, w, h = chave
        pix: Pixels | bool = False
        try:
            arq = self._arquivo(url)
            pix = pixels_de_arquivo(arq, w, h) or False
        except Exception:
            pix = False
        with self._trava:
            self.pix[chave] = pix
            self.pendentes.discard(chave)
        if pix and ao_chegar:
            try:
                self.chamar(ao_chegar)
            except Exception:
                pass

    def _arquivo(self, url: str) -> Path:
        self.pasta.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.pasta, 0o700)
        except OSError:
            pass
        arq = self.pasta / (hashlib.sha1(url.encode()).hexdigest() + ".img")
        if not arq.exists():
            dados = self.baixar(url)
            arq.write_bytes(dados)
            self.podar()
        else:
            os.utime(arq)
        return arq

    @staticmethod
    def _baixar(url: str) -> bytes:
        if not url.startswith("https://"):
            raise ValueError("só https")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "oma-spotify"}), timeout=10) as r:
            dados = r.read(LIMITE_BYTES + 1)
        if len(dados) > LIMITE_BYTES:
            raise ValueError("imagem grande demais")
        return dados

    def podar(self) -> None:
        """Apaga as mais antigas até o cache caber no limite."""
        arqs = sorted((a for a in self.pasta.glob("*.img")), key=lambda a: a.stat().st_mtime)
        total = sum(a.stat().st_size for a in arqs)
        while arqs and total > self.limite:
            a = arqs.pop(0)
            total -= a.stat().st_size
            try:
                a.unlink()
            except OSError:
                pass


class Capa(Widget):
    """Capa grande de tamanho fixo (cabeçalhos e painel)."""

    DEFAULT_CSS = "Capa { width: 16; height: 8; }"

    def __init__(self, w: int = 16, h: int = 8, **kw) -> None:
        super().__init__(**kw)
        self.w, self.h = w, h
        self.item = None
        self.styles.width, self.styles.height = w, h

    def definir(self, item) -> None:
        self.item = item
        self.refresh()

    def tamanho(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.styles.width, self.styles.height = w, h
        self.refresh()

    def render(self) -> Text:
        if self.item is None:
            return iniciais("", self.w, self.h)
        return self.app.capas.texto(self.item, self.w, self.h, self.refresh, self.app.cor("accent"))
