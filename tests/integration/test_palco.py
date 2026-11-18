"""Letra (aba da Fila e palco) e o cliente da LRCLIB."""

import io
import json
import urllib.error

from oma_spotify.services.letras import Letras, ler_lrc
from oma_spotify.ui.lista import Lista
from tests.conftest import esperar, janela, pronto

GRANDE = (180, 48)


# ------------------------------------------------------------ cliente LRCLIB (sem rede)
class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_lrc_e_indice():
    linhas = ler_lrc("[00:01.00]um\n[00:03.50]dois\n[00:02.00]\n")
    assert linhas == [(1000, "um"), (2000, "♪"), (3500, "dois")]


def test_lrclib_pede_get_com_faixa_artista_album_e_duracao():
    pedidos = []

    def abrir(req, timeout=0):
        pedidos.append(req)
        return Resp(json.dumps({"syncedLyrics": "[00:01.00]oi\n[00:02.00]tchau"}).encode())
    l = Letras(abrir=abrir)
    r = l.buscar("spotify:track:x", "Cidade Acesa", "Cais 7, Outro", "Faróis", 211_000)
    assert r.sincronizada and r.linhas == [(1000, "oi"), (2000, "tchau")] and r.indice(1500) == 0
    url = pedidos[0].full_url
    assert url.startswith("https://lrclib.net/api/get?") and "track_name=Cidade+Acesa" in url
    assert "artist_name=Cais+7" in url and "Outro" not in url and "album_name=Far" in url and "duration=211" in url
    assert pedidos[0].get_header("User-agent").startswith("oma-spotify/")
    l.buscar("spotify:track:x", "Cidade Acesa", "Cais 7", "Faróis", 211_000)
    assert len(pedidos) == 1  # cache


def test_lrclib_404_rede_e_instrumental():
    def nao_achou(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    def sem_rede(req, timeout=0):
        raise urllib.error.URLError("x")
    assert Letras(abrir=nao_achou).buscar("u", "a", "b", "", 0).motivo == "sem letra para esta faixa"
    l = Letras(abrir=sem_rede)
    assert l.buscar("u", "a", "b", "", 0).motivo == "sem conexão com lrclib.net"
    assert not l._cache  # falha de rede não fica guardada
    instr = Letras(abrir=lambda r, timeout=0: Resp(b'{"instrumental": true}')).buscar("u", "a", "b", "", 0)
    assert instr.vazia and instr.motivo == "instrumental"
    plano = Letras(abrir=lambda r, timeout=0: Resp(b'{"plainLyrics": "a\\nb"}')).buscar("u", "a", "b", "", 0)
    assert not plano.sincronizada and [t for _, t in plano.linhas] == ["a", "b"]


# ------------------------------------------------------------ aba letra
async def test_aba_letra_sincroniza_e_enter_pula(app, falso, letras):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        fila = app.query_one("#fila")
        app.focar_janela("fila")
        await pilot.pause(0.1)
        await pilot.press("alt+right")
        await pilot.pause(0.4)
        assert fila.aba == "letra" and letras.pedidos == ["spotify:track:t1"]
        l = fila.query_one("#letra-lista", Lista)
        assert await esperar(pilot, lambda: l.display and l.itens, 3)
        atual = app.letra.indice(app.player.posicao())
        assert l.itens[atual][1] in ("mas a noite ainda tá do meu lado", "se o farol piscar, eu sei")
        assert janela(app) == "fila"
        l.focus()
        l.mover_cursor(1)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: ("seek", 80_000) in falso.chamadas)
        await pilot.press("alt+left")
        assert fila.aba == "fila"


async def test_clique_no_titulo_troca_a_aba(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        fila = app.query_one("#fila")
        await pilot.click(fila, offset=(10, 0))
        await pilot.pause(0.3)
        assert fila.aba == "letra"
        await pilot.click(fila, offset=(3, 0))
        assert fila.aba == "fila"


async def test_sem_letra_a_aba_diz_isso(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("full_stop")
        assert await esperar(pilot, lambda: app.player.item.nome != "Cidade Acesa")
        fila = app.query_one("#fila")
        fila.trocar_aba("letra")
        assert await esperar(pilot, lambda: app.letra is not None and app.letra.vazia, 3)
        await pilot.pause(0.2)
        assert "sem letra para esta faixa" in str(fila.query_one("#letra-aviso").render())
        assert "sem letra" in str(fila.border_title)


async def test_letra_desligada_nao_chama_a_lrclib(app, config, letras):
    config.letra = False
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.query_one("#fila").trocar_aba("letra")
        await pilot.pause(0.3)
        assert letras.pedidos == [] and "desligada" in app.letra.motivo


# ------------------------------------------------------------ palco
async def test_palco_abre_com_z_e_sai_com_z_e_esc(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("tocando")
        await pilot.pause(0.1)
        await pilot.press("z")
        await pilot.pause(0.6)
        palco = app.query_one("#palco")
        assert app.zoom == "palco" and janela(app) == "palco"
        assert not app.janela_visivel("principal") and not app.janela_visivel("bib")
        assert [p for p, _ in app.query_one("#trilha").partes] == ["tocando", "palco"]
        assert "┏" in str(palco.query_one("#pc-titulo").render())  # título grande
        assert "lrclib.net" in str(palco.query_one("#pc-fonte").render())
        letra = palco.query_one("#pc-letra", Lista)
        assert letra.itens and letra.altura_padrao == 2
        assert "Maré de Neon" in str(palco.query_one("#pc-seguinte").render())
        letra.mover_cursor(2)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: ("seek", 87_000) in falso.chamadas)
        await pilot.press("alt+right")
        assert palco.aba == "fila" and palco.query_one("#pc-fila").display
        await pilot.press("z")
        await pilot.pause(0.3)
        assert app.zoom == "" and not app.query("#palco") and janela(app) == "tocando"
        app.focar_janela("fila")
        await pilot.press("z")
        await pilot.pause(0.3)
        await pilot.press("escape")
        await pilot.pause(0.3)
        assert app.zoom == ""


async def test_palco_sem_letra_mostra_a_fila(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("full_stop")
        assert await esperar(pilot, lambda: app.player.item.nome != "Cidade Acesa")
        app.focar_janela("tocando")
        await pilot.press("z")
        assert await esperar(pilot, lambda: app.letra is not None and app.letra.vazia, 3)
        await pilot.pause(0.3)
        palco = app.query_one("#palco")
        assert palco.aba == "fila" and palco.query_one("#pc-abas").opcoes[0][1] == "sem letra"


async def test_duplo_clique_no_titulo_da_janela_da_zoom(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("principal")
        await pilot.click("#principal", offset=(4, 0), times=2)
        await pilot.pause(0.3)
        assert app.zoom == "principal"
