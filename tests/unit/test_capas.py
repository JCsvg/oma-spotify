"""Capas: URLs permitidas, cache em memória e em disco com teto, fallback e desenho em meio-blocos."""

from oma_spotify.services import capas as mod
from oma_spotify.services.api import _imagem
from oma_spotify.services.capas import BYTES, Capas, demo, desenhar, permitida

URL = "https://i.scdn.co/image/ab67616d00004851aaaa"


def sincrono():
    """agendar que roda na hora, como se a thread já tivesse voltado."""
    def agendar(func, depois):
        try:
            r, erro = func(), None
        except Exception as e:  # noqa: BLE001
            r, erro = None, e
        depois(r, erro)
    return agendar


def falsa(pasta, **kw):
    baixados, chegaram = [], []

    def baixar(url):
        baixados.append(url)
        return b"jpeg"
    c = Capas(agendar=sincrono(), chegou=chegaram.append, pasta=pasta, baixar_=baixar,
              converter_=lambda dados: bytes([120]) * BYTES, **kw)
    return c, baixados, chegaram


def test_so_baixa_imagem_da_api_do_spotify():
    for ok in (URL, "https://mosaic.scdn.co/640/abc", "https://image-cdn-ak.spotifycdn.com/image/x", "demo:album:a1"):
        assert permitida(ok)
    for nao in ("http://i.scdn.co/x", "https://exemplo.com/x.jpg", "https://scdn.co.evil.com/x", "file:///etc/passwd", ""):
        assert not permitida(nao)


def test_menor_imagem_que_serve():
    imgs = [{"url": "a", "width": 640}, {"url": "b", "width": 300}, {"url": "c", "width": 64}]
    assert _imagem(imgs) == "c"
    assert _imagem([{"url": "a", "width": 640}, {"url": "b", "width": 300}]) == "b"
    assert _imagem([{"url": "a", "width": 32}]) == "a" and _imagem([{"url": "x", "width": None}]) == "x"
    assert _imagem(None) == "" and _imagem([None, {"url": None}]) == ""


def test_primeiro_pede_depois_desenha(tmp_path):
    c, baixados, chegaram = falsa(tmp_path)
    assert c.obter(URL, 6, 3) is None  # ainda não: o chamador desenha a inicial
    assert baixados == [URL] and chegaram == [URL]
    linhas = c.obter(URL, 6, 3)
    assert len(linhas) == 3 and all(l.cell_len == 6 and l.plain == "▀" * 6 for l in linhas)
    assert c.obter(URL, 6, 3) is linhas  # desenho guardado
    assert len(baixados) == 1


def test_cache_em_disco_evita_baixar_de_novo(tmp_path):
    c, baixados, _ = falsa(tmp_path)
    c.obter(URL, 4, 2)
    arq = c.arquivo(URL)
    assert arq.exists() and arq.stat().st_size == BYTES and (tmp_path.stat().st_mode & 0o777) == 0o700
    c2, baixados2, _ = falsa(tmp_path)
    c2.obter(URL, 4, 2)
    assert baixados2 == [] and c2.obter(URL, 4, 2) is not None


def test_teto_da_memoria(tmp_path):
    c, _, _ = falsa(tmp_path, teto_memoria=3)
    urls = [f"{URL}{n}" for n in range(5)]
    for u in urls:
        c.obter(u, 4, 2)
        c.obter(u, 4, 2)
    assert list(c.memoria) == urls[2:]
    assert all(k[0] in urls[2:] for k in c.desenhos)


def test_teto_do_disco_tira_as_mais_antigas(tmp_path):
    import os
    c, _, _ = falsa(tmp_path, teto_disco=3 * BYTES)
    for n in range(5):
        c.carregar(f"{URL}{n}")
        os.utime(c.arquivo(f"{URL}{n}"), (1000 + n, 1000 + n))
    assert c.podar() == 2
    restam = sorted(p.name for p in tmp_path.glob("*.rgb"))
    assert restam == sorted(c.arquivo(f"{URL}{n}").name for n in (2, 3, 4))


def test_falha_desligado_e_url_estranha_voltam_para_a_inicial(tmp_path):
    c, baixados, _ = falsa(tmp_path)
    c.baixar = lambda url: (_ for _ in ()).throw(OSError("sem rede"))
    assert c.obter(URL, 4, 2) is None and URL in c.falhas
    assert c.obter(URL, 4, 2) is None  # não insiste
    c2, baixados2, _ = falsa(tmp_path, ligado=False)
    assert c2.obter(URL, 4, 2) is None and baixados2 == []
    assert c2.obter("https://exemplo.com/a.jpg", 4, 2) is None
    c3, baixados3, _ = falsa(tmp_path)
    assert c3.obter("https://exemplo.com/a.jpg", 4, 2) is None and baixados3 == []


def test_sem_imagemagick_so_o_demo_funciona(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.shutil, "which", lambda nome: None)
    c = Capas(agendar=sincrono(), pasta=tmp_path)
    assert not c.disponivel
    assert c.obter(URL, 4, 2) is None and not c.rodando and not c.fila
    c.obter("demo:album:a1", 4, 2)
    assert c.obter("demo:album:a1", 4, 2) is not None


def test_cancelar_pendentes_ao_sair_da_pagina(tmp_path):
    feitos = []
    c = Capas(agendar=lambda f, d: feitos.append((f, d)), pasta=tmp_path, converter_=lambda d: bytes(BYTES),
              baixar_=lambda u: b"x")
    for n in range(5):
        c.obter(f"{URL}{n}", 4, 2)
    assert len(feitos) == 2 and len(c.fila) == 3  # duas por vez
    c.cancelar_pendentes()
    assert not c.fila


def test_desenho_redondo_e_demo():
    px = demo("demo:artist:r1")
    assert len(px) == BYTES and px == demo("demo:artist:r1") and px != demo("demo:artist:r2")
    linhas = desenhar(px, 8, 4, redonda=True, fundo="#102030")
    canto = linhas[0].spans[0].style
    assert canto.bgcolor.get_truecolor() == (0x10, 0x20, 0x30) or canto.color.get_truecolor()[:1] == (0x10,)
    assert len(linhas) == 4 and linhas[0].cell_len == 8


def test_imagemagick_converte_para_64x64(tmp_path):
    import shutil
    import subprocess

    import pytest
    if not (shutil.which("magick") or shutil.which("convert")):
        pytest.skip("sem ImageMagick")
    png = tmp_path / "x.png"
    cmd = shutil.which("magick") or shutil.which("convert")
    subprocess.run([cmd, "-size", "300x200", "gradient:red-blue", str(png)], check=True)
    px = mod.converter(png.read_bytes())
    assert len(px) == BYTES
    assert px[0] > px[2] and px[-1] > px[-3]  # vermelho em cima, azul embaixo
