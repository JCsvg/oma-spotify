"""Capas e fotos de verdade, desenhadas com meio-blocos (▀) coloridos.

Caminho de uma capa, sem carregar biblioteca de imagem no processo:
1. a URL vem da própria API do Spotify (só https em *.scdn.co e *.spotifycdn.com);
2. numa thread do pool, baixa a menor imagem que serve (até 3 MB) e o `magick` reduz para 64x64 RGB cru;
3. os 12 KB ficam em ~/.cache/oma-spotify/capas (teto de 50 MB, sai o mais antigo) e na memória (64 capas, 0,8 MB);
4. a interface reduz de novo para o tamanho em células e desenha cada célula com ▀ (cor de cima e cor de baixo).

Sem `magick`, sem rede, com capas desligadas ou enquanto carrega, quem chama recebe None e desenha o bloco
com a inicial. No --demo, URLs `demo:` geram capas de mentira aqui mesmo, sem rede e sem arquivo.
"""

from __future__ import annotations

import colorsys
import hashlib
import os
import shutil
import subprocess
import urllib.parse
import urllib.request
import zlib
from collections import OrderedDict, deque
from pathlib import Path

from rich.color import Color
from rich.style import Style
from rich.text import Text

LADO = 64  # pixels da capa guardada (quadrada)
BYTES = LADO * LADO * 3
TETO_DISCO = 50 * 1024 * 1024
TETO_MEMORIA = 64  # 64 capas de 12 KB = 0,8 MB; com 24, o demo regerava capas e o RSS subia
TETO_DESENHOS = 96
MAX_DOWNLOAD = 3 * 1024 * 1024
SIMULTANEAS = 2


def pasta_padrao() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "oma-spotify" / "capas"


def permitida(url: str) -> bool:
    """Só imagens que a API do Spotify devolve: https em i.scdn.co, mosaic.scdn.co, *.spotifycdn.com e parecidos."""
    if url.startswith("demo:"):
        return True
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and (host == "scdn.co" or host.endswith(".scdn.co") or host.endswith(".spotifycdn.com"))


def conversor() -> list[str] | None:
    """O comando do ImageMagick que reduz a imagem (7 é `magick`, 6 é `convert`)."""
    exe = shutil.which("magick") or shutil.which("convert")
    return [exe] if exe else None


def baixar(url: str, tempo: float = 10.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "oma-spotify"})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        dados = r.read(MAX_DOWNLOAD + 1)
    if len(dados) > MAX_DOWNLOAD:
        raise ValueError("imagem grande demais")
    return dados


def converter(dados: bytes, cmd: list[str] | None = None) -> bytes:
    """JPEG, PNG ou WebP para 64x64 RGB cru, cortando no centro. Roda fora do processo."""
    cmd = cmd or conversor()
    if not cmd:
        raise RuntimeError("sem ImageMagick")
    r = subprocess.run([*cmd, "-", "-resize", f"{LADO}x{LADO}^", "-gravity", "center", "-extent", f"{LADO}x{LADO}",
                        "-strip", "-depth", "8", "rgb:-"], input=dados, capture_output=True, timeout=15)
    if r.returncode != 0 or len(r.stdout) != BYTES:
        raise RuntimeError("conversão falhou")
    return r.stdout


# ---------------------------------------------------------------- capas de mentira (demo e testes)
def _hsv(h: float, s: float, v: float) -> tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
    return int(r * 255), int(g * 255), int(b * 255)


ESTILOS_DEMO = {"a1": "bokeh", "a2": "anel", "a5": "listras", "a7": "sol", "a10": "luz", "p1": "anel", "p4": "luz"}


def _mistura(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(x * (1 - t) + y * t for x, y in zip(a, b))


def demo(url: str) -> bytes:
    """Arte abstrata a partir da URL `demo:tipo:id`: bolhas de luz, anel, listras, sol, faixa de luz ou silhueta."""
    import math
    _, _, resto = url.partition(":")
    tipo, _, semente = resto.partition(":")
    n = zlib.crc32(semente.encode())
    h1 = (n % 360) / 360
    h2 = h1 + 0.1 + ((n >> 9) % 25) / 100
    if tipo == "artist":
        estilo = "silhueta"
    elif tipo == "show":
        estilo = ("anel", "sol", "listras")[n % 3]
    else:
        estilo = ESTILOS_DEMO.get(semente) or ("bokeh", "anel", "listras", "sol", "luz")[(n >> 3) % 5]
    c1, c2 = _hsv(h1, 0.55, 0.85), _hsv(h2, 0.65, 0.35)
    bolhas = [((n >> k) % 60 + 2, (n >> (k + 7)) % 44 + 2, 4 + (n >> (k + 3)) % 7, _hsv(h1 + k * 0.13, 0.55, 0.95))
              for k in range(16)]
    # desenhada em 32x32 e ampliada para 64x64: 4 vezes menos conta (e menos lixo de memória) no demo
    M = LADO // 2
    meia = bytearray(M * M * 3)
    c = (LADO - 1) / 2
    for yy in range(M):
        for xx in range(M):
            x, y = xx * 2, yy * 2
            d = math.hypot(x - c, y - c)
            if estilo == "bokeh":
                cor = _mistura((10, 18, 38), (28, 40, 70), y / LADO)
                for bx, by, r, bc in bolhas:
                    a = max(0.0, 1 - math.hypot(x - bx, y - by) / r)
                    if a:
                        cor = _mistura(cor, bc, min(1.0, a * 1.6) * 0.75)
                predio = (x // 9) % 2 == 0 and y > 30 + ((x // 9) * 7 + n) % 16
                if predio:
                    cor = _mistura(cor, (8, 12, 22), 0.75)
            elif estilo == "anel":
                cor = _mistura(_hsv(h1, 0.6, 0.95), _hsv(h1 + 0.03, 0.8, 0.35), d / 45)
                cor = _mistura(cor, (255, 236, 210), max(0.0, 1 - abs(d - 13) / 2.2) * 0.8)
                cor = _mistura(cor, (255, 220, 190), max(0.0, 1 - d / 9) * 0.5)
            elif estilo == "listras":
                faixa = (x // 10) % 3
                cor = _hsv(h1, 0.85, 0.95) if faixa == 0 else (250, 240, 220) if faixa == 1 else _hsv(h1 + 0.02, 0.85, 0.9)
            elif estilo == "sol":
                cor = _mistura(_hsv(h1, 0.7, 0.55), _hsv(h1, 0.8, 0.3), y / LADO)
                cor = _mistura(cor, (240, 220, 160), max(0.0, min(1.0, (22 - d) / 1.5)))
                cor = _mistura(cor, _hsv(h1, 0.7, 0.75), max(0.0, min(1.0, (11 - math.hypot(x - c - 4, y - c + 3)) / 1.5)))
            elif estilo == "luz":
                cor = _mistura(_hsv(h1, 0.3, 0.8), _hsv(h2, 0.4, 0.45), (x + y) / (2 * LADO))
                faixa = math.exp(-(((y - 0.55 * x - 18) / 7) ** 2))
                cor = _mistura(cor, (245, 245, 250), faixa * 0.7)
            else:  # silhueta de artista
                cor = _mistura(_hsv(h1, 0.45, 0.95), _hsv(h1, 0.7, 0.45), d / 40)
                cabeca = math.hypot(x - c, y - 25) - 10
                ombros = math.hypot((x - c) / 1.35, y - 64) - 22
                dentro = min(cabeca, ombros)
                cor = _mistura(cor, _mistura(cor, (25, 25, 30), 0.65), max(0.0, min(1.0, 0.5 - dentro / 1.5)))
            i = (yy * M + xx) * 3
            meia[i:i + 3] = bytes(int(v) for v in cor)
    px = bytearray()
    for yy in range(M):
        linha = bytearray()
        for xx in range(M):
            i = (yy * M + xx) * 3
            linha += meia[i:i + 3] * 2
        px += linha * 2
    return bytes(px)


# ---------------------------------------------------------------- desenho em meio-blocos
def reduzir(px: bytes, w: int, h: int) -> list[tuple[int, int, int]]:
    """Média de área de LADOxLADO para w x h pixels."""
    saida = []
    xs = [(x * LADO // w, max(x * LADO // w + 1, (x + 1) * LADO // w)) for x in range(w)]
    for y in range(h):
        y0, y1 = y * LADO // h, max(y * LADO // h + 1, (y + 1) * LADO // h)
        for x0, x1 in xs:
            r = g = b = n = 0
            for yy in range(y0, y1):
                base = yy * LADO * 3
                for xx in range(x0, x1):
                    i = base + xx * 3
                    r += px[i]
                    g += px[i + 1]
                    b += px[i + 2]
                    n += 1
            saida.append((r // n, g // n, b // n))
    return saida


_ESTILOS: dict[tuple, Style] = {}
Q = 0xF8  # 32 níveis por canal: menos estilos diferentes, sem faixas visíveis em capas pequenas
TETO_ESTILOS = 4096


def _estilo(cima: tuple[int, int, int], baixo: tuple[int, int, int]) -> Style:
    """Um Style por par de cores, reaproveitado entre capas."""
    k = (*cima, *baixo)
    st = _ESTILOS.get(k)
    if st is None:
        if len(_ESTILOS) > TETO_ESTILOS:
            _ESTILOS.clear()
        st = _ESTILOS[k] = Style(color=Color.from_rgb(*k[:3]), bgcolor=Color.from_rgb(*k[3:]))
    return st


def desenhar(px: bytes, w: int, h: int, redonda: bool = False, fundo: str = "#000000") -> list[Text]:
    """h linhas de w células; cada célula é ▀ com o pixel de cima na frente e o de baixo no fundo."""
    w, h = max(1, w), max(1, h)
    alto = 2 * h
    meio = (~Q & 0xFF) // 2
    pts = [((r & Q) | meio, (g & Q) | meio, (b & Q) | meio) for r, g, b in reduzir(px, w, alto)]  # menos cores, mais repetição
    f = Color.parse(fundo).get_truecolor()
    fundo_rgb = (f.red, f.green, f.blue)
    cx, cy = (w - 1) / 2, (alto - 1) / 2
    rx, ry = w / 2, alto / 2

    def dentro(x: int, y: int) -> bool:
        return not redonda or ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0

    linhas = []
    for linha in range(h):
        t = Text(no_wrap=True)
        for x in range(w):
            y0, y1 = 2 * linha, 2 * linha + 1
            cima = pts[y0 * w + x] if dentro(x, y0) else fundo_rgb
            baixo = pts[y1 * w + x] if dentro(x, y1) else fundo_rgb
            t.append("▀", _estilo(cima, baixo))
        linhas.append(t)
    return linhas


# ---------------------------------------------------------------- o serviço
class Capas:
    """Cache de capas em disco e em memória, com pedidos assíncronos e desenho em meio-blocos.

    `agendar(func, depois)` roda func numa thread e chama depois(resultado, erro) na thread da interface.
    `chegou(url)` é chamado na thread da interface quando uma capa fica pronta (para redesenhar).
    """

    def __init__(self, agendar=None, chegou=None, pasta: Path | None = None, baixar_=None, converter_=None,
                 ligado: bool = True, teto_disco: int = TETO_DISCO, teto_memoria: int = TETO_MEMORIA) -> None:
        self.agendar = agendar
        self.chegou = chegou
        self.pasta = pasta or pasta_padrao()
        self.baixar = baixar_ or baixar
        self._converter = converter_
        self.cmd = None if converter_ else conversor()
        self.ligado = ligado
        self.teto_disco, self.teto_memoria = teto_disco, teto_memoria
        self.memoria: OrderedDict[str, bytes] = OrderedDict()
        self.desenhos: OrderedDict[tuple, list[Text]] = OrderedDict()
        self.falhas: set[str] = set()
        self.fila: deque[str] = deque()
        self.rodando: set[str] = set()
        self._gravadas = 0

    # --------------------------------------------------- consulta (thread da interface)
    @property
    def disponivel(self) -> bool:
        return self.ligado and (self._converter is not None or self.cmd is not None)

    def pode(self, url: str) -> bool:
        if not self.ligado or not url or url in self.falhas or not permitida(url):
            return False
        return url.startswith("demo:") or self.disponivel

    def obter(self, url: str, w: int, h: int, redonda: bool = False, fundo: str = "#000000") -> list[Text] | None:
        """As linhas da capa, ou None (o chamador desenha a inicial) e a capa é pedida em segundo plano."""
        if not self.pode(url) or w < 1 or h < 1:
            return None
        chave = (url, w, h, redonda, fundo)
        pronto = self.desenhos.get(chave)
        if pronto is not None:
            self.desenhos.move_to_end(chave)
            return pronto
        px = self.memoria.get(url)
        if px is None:
            self.pedir(url)
            return None
        self.memoria.move_to_end(url)
        linhas = desenhar(px, w, h, redonda, fundo)
        self.desenhos[chave] = linhas
        while len(self.desenhos) > TETO_DESENHOS:
            self.desenhos.popitem(last=False)
        return linhas

    def pedir(self, url: str) -> None:
        if url in self.rodando or url in self.fila or not self.pode(url):
            return
        self.fila.append(url)
        self._andar()

    def cancelar_pendentes(self) -> None:
        """Ao sair da página, o que ainda não começou a baixar é esquecido (quem continua na tela pede de novo)."""
        self.fila.clear()

    def desligar(self, ligado: bool) -> None:
        self.ligado = ligado
        self.fila.clear()
        self.falhas.clear()
        self.desenhos.clear()

    def _andar(self) -> None:
        while self.fila and len(self.rodando) < SIMULTANEAS and self.agendar is not None:
            url = self.fila.popleft()
            self.rodando.add(url)
            self.agendar(lambda u=url: self.carregar(u), lambda r, erro, u=url: self._fim(u, r, erro))

    def _fim(self, url: str, px, erro) -> None:
        self.rodando.discard(url)
        if erro is not None or not px:
            self.falhas.add(url)
        else:
            self.guardar_memoria(url, px)
            if self.chegou is not None:
                self.chegou(url)
        self._andar()

    def guardar_memoria(self, url: str, px: bytes) -> None:
        self.memoria[url] = px
        self.memoria.move_to_end(url)
        while len(self.memoria) > self.teto_memoria:
            velha, _ = self.memoria.popitem(last=False)
            for k in [k for k in self.desenhos if k[0] == velha]:
                del self.desenhos[k]

    # --------------------------------------------------- trabalho (thread do pool)
    def arquivo(self, url: str) -> Path:
        return self.pasta / (hashlib.sha1(url.encode()).hexdigest() + ".rgb")

    def carregar(self, url: str) -> bytes:
        if url.startswith("demo:"):
            return demo(url)
        arq = self.arquivo(url)
        try:
            px = arq.read_bytes()
            if len(px) == BYTES:
                os.utime(arq)  # o mais usado fica por último na limpeza
                return px
        except OSError:
            pass
        dados = self.baixar(url)
        px = self._converter(dados) if self._converter else converter(dados, self.cmd)
        self._gravar(arq, px)
        return px

    def _gravar(self, arq: Path, px: bytes) -> None:
        try:
            self.pasta.mkdir(parents=True, exist_ok=True)
            os.chmod(self.pasta, 0o700)
            tmp = arq.with_suffix(".tmp")
            tmp.write_bytes(px)
            os.replace(tmp, arq)
        except OSError:
            return
        self._gravadas += 1
        if self._gravadas % 20 == 1:
            self.podar()

    def podar(self) -> int:
        """Apaga as capas mais antigas até o disco ficar abaixo do teto. Devolve quantas saíram."""
        try:
            arqs = [(e.stat().st_mtime, e.stat().st_size, e.path) for e in os.scandir(self.pasta) if e.name.endswith(".rgb")]
        except OSError:
            return 0
        total = sum(s for _, s, _ in arqs)
        saiu = 0
        for _, tam, caminho in sorted(arqs):
            if total <= self.teto_disco:
                break
            try:
                os.remove(caminho)
                total -= tam
                saiu += 1
            except OSError:
                pass
        return saiu
