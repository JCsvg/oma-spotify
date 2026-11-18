"""O app com o cliente real (ClienteSpotify) contra um servidor HTTP falso que responde como a API de verdade:
dados parciais, campos nulos, listas vazias, erros 403 e 404 de endpoints do modo de desenvolvimento,
e o contexto salvo pela 0.3.0. Nada pode derrubar o app."""

import json

import pytest

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.services.api import ClienteSpotify, item_de
from oma_spotify.services.auth import Sessao
from oma_spotify.services.letras import LetrasFalsas
from oma_spotify.ui.principal import vista_valida
from tests.conftest import PluginFalso, esperar
from tests.fake_api import ServidorFalso

TAM = (150, 40)
PAGINAS = [
    {"t": "inicio"}, {"t": "curtidas"}, {"t": "recentes"}, {"t": "top"}, {"t": "config"},
    {"t": "busca", "q": "x", "cat": "tudo"}, {"t": "busca", "q": "x", "cat": "track"},
    {"t": "item", "item": {"uri": "spotify:playlist:p1", "tipo": "playlist", "nome": "Minha", "id": "p1", "meu": True}},
    {"t": "item", "item": {"uri": "spotify:playlist:p2", "tipo": "playlist", "nome": "Alheia", "id": "p2"}},
    {"t": "item", "item": {"uri": "spotify:album:a", "tipo": "album", "nome": "Disco", "id": "a"}},
    {"t": "item", "item": {"uri": "spotify:artist:r", "tipo": "artist", "nome": "Banda", "id": "r"}},
    {"t": "item", "item": {"uri": "spotify:show:s", "tipo": "show", "nome": "Programa", "id": "s"}},
]
NULOS = {
    ("GET", "/v1/me"): [(200, {"id": "eu", "display_name": None})],
    ("GET", "/v1/me/player"): [(200, {"is_playing": True, "progress_ms": None, "repeat_state": None, "device": None, "context": None,
                                      "item": {"uri": "spotify:track:n", "type": "track", "name": None, "duration_ms": None,
                                               "artists": [None, {"name": None}], "album": None}})],
    ("GET", "/v1/me/playlists"): [(200, {"items": [None, {"uri": "spotify:playlist:p1", "type": "playlist", "id": "p1", "name": None,
                                                          "owner": None, "description": None, "items": None}], "next": None})],
    ("GET", "/v1/me/player/recently-played"): [(200, {"items": [None, {"track": None},
                                                                {"track": {"uri": "spotify:track:r", "type": "track", "name": "R",
                                                                           "artists": None, "album": {"name": None}},
                                                                 "played_at": None}]})],
    ("GET", "/v1/me/player/devices"): [(200, {"devices": [None, {"id": "d", "name": None, "type": None, "volume_percent": None,
                                                                 "is_active": True}]})],
    ("GET", "/v1/me/player/queue"): [(200, {"queue": None})],
    ("GET", "/v1/me/top/artists"): [(200, {"items": [None, {"uri": "spotify:artist:t", "type": "artist", "name": None}]})],
    ("GET", "/v1/me/shows"): [(200, {"items": [{"show": None}, {"show": {"uri": "spotify:show:s", "type": "show", "name": "S",
                                                                           "publisher": None, "description": None}}]})],
    ("GET", "/v1/search"): [(200, {"tracks": {"items": [None, {"uri": "spotify:track:b", "type": "track", "name": "B"}]},
                                   "artists": None, "albums": {"items": None}})],
    ("GET", "/v1/me/library/contains"): [(200, {"erro": "não é lista"})],
    ("GET", "/v1/playlists/p1/items"): [(200, {"items": [None, {"item": None}, {"track": {"uri": "spotify:track:c", "name": "C"}}],
                                               "next": None})],
}
ERROS = {
    ("GET", "/v1/me/top/artists"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/me/top/tracks"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/me/player/recently-played"): [(404, {"error": {"status": 404}})],
    ("GET", "/v1/me/shows"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/me/following"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/me/albums"): [(404, {"error": {"status": 404}})],
    ("GET", "/v1/me/tracks"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/artists/r/albums"): [(404, {"error": {"status": 404}})],
    ("GET", "/v1/search"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/me/player/queue"): [(404, {"error": {"status": 404}})],
    ("GET", "/v1/me/player/devices"): [(403, {"error": {"status": 403}})],
    ("GET", "/v1/albums/a/tracks"): [(404, {"error": {"status": 404}})],
    ("GET", "/v1/shows/s/episodes"): [(404, {"error": {"status": 404}})],
    ("GET", "/v1/playlists/p1/items"): [(403, {"error": {"status": 403}})],
}
VAZIO = {
    ("GET", "/v1/me/player"): [(204, None)],
    ("GET", "/v1/me/playlists"): [(200, {"items": [], "next": None})],
    ("GET", "/v1/me/player/devices"): [(200, {"devices": []})],
}


@pytest.fixture
def srv():
    s = ServidorFalso()
    yield s
    s.parar()


def app_real(srv, estado, config, armazem):
    armazem.gravar({"access_token": "acesso-1", "refresh_token": "refresh-1", "expira": 9e12})
    config.client_id = "0123456789abcdef0123456789abcdef"
    cli = ClienteSpotify(Sessao(config.client_id, 1, armazem, token_url=srv.token_url), srv.api, dormir=lambda s: None)
    return OmaSpotifyApp(cliente=cli, demo=False, estado=estado, config=config, armazem=armazem, abertura=False,
                         plugin=PluginFalso(None, instalado=False), letras=LetrasFalsas({}))


async def percorrer(app, pilot):
    """Abre todas as páginas, as janelas e os diálogos principais; o app tem de continuar de pé."""
    for v in PAGINAS:
        app.navegar(v)
        await pilot.pause(0.5)
        assert app.is_running
        assert app.query_one("#principal").pagina is not None
        app.focar_janela("principal")
        await pilot.press("down", "o", "escape")
        await pilot.pause(0.1)
    for nome in ("bib", "tocando", "fila", "player"):
        app.focar_janela(nome)
        await pilot.pause(0.1)
    app.query_one("#fila").trocar_aba("letra")
    await pilot.pause(0.3)
    for tecla in ("d", "escape", "ctrl+p", "escape", "f1", "escape"):
        await pilot.press(tecla)
        await pilot.pause(0.2)
    app.focar_janela("tocando")
    await pilot.press("z")
    await pilot.pause(0.4)
    await pilot.press("z")
    await pilot.pause(0.2)
    assert app.is_running
    assert not any("Traceback" in n.message for n in app._notifications)


# ------------------------------------------------------------ unidades
def test_item_de_com_campos_nulos():
    i = item_de({"uri": "spotify:track:x", "type": "track", "name": None, "artists": [None, {"name": None}, {"name": "A"}],
                 "album": None, "duration_ms": None})
    assert (i.nome, i.sub, i.extra, i.dur_ms, i.ano) == ("(sem nome)", "A", "", 0, "")
    p = item_de({"uri": "spotify:playlist:p", "type": "playlist", "name": "P", "owner": None, "description": None, "items": None})
    assert p.sub == "" and p.desc == "" and p.extra == ""
    assert item_de(None) is None and item_de({"uri": None}) is None and item_de("x") is None


def test_vista_valida_descarta_paginas_da_030():
    assert vista_valida({"t": "dispositivos"}) is None and vista_valida({"t": "fila"}) is None
    assert vista_valida({"t": "item", "item": None}) is None
    assert vista_valida({"t": "item", "item": {"uri": "spotify:track:x", "tipo": "track", "nome": "x"}}) is None
    assert vista_valida({"t": "busca", "q": ""}) is None
    assert vista_valida({"t": "top", "per": 1})["per"] == "short_term"
    assert vista_valida({"t": "inicio"}) == {"t": "inicio"}
    assert vista_valida("lixo") is None


# ------------------------------------------------------------ app inteiro
async def test_contexto_da_030_com_pagina_que_nao_existe_mais(srv, estado, config, armazem):
    """O caso do JC: histórico da 0.3.0 terminando em Dispositivos. Abre o início, sem traceback."""
    estado.preparar()
    estado.arquivo.write_text(json.dumps({"versao": 1, "dados": {
        "hist": [{"t": "inicio"}, {"t": "busca", "q": "bruno", "cat": "tudo", "linha": 0}, {"t": "dispositivos", "linha": 0}],
        "pos": 2, "busca": "bruno", "painel": True, "coluna": False, "bib": {"chip": "playlist", "filtro": "", "ordem": "az"},
        "minha_fila": [None, {"uri": 1}, {"uri": "spotify:track:q", "tipo": "track", "nome": None}]}}))
    estado.carregar()
    app = app_real(srv, estado, config, armazem)
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(1.5)
        assert app.is_running
        assert [v["t"] for v in app.historico] == ["inicio", "busca"] and app.pos == 0
        assert app.query_one("#principal").vista["t"] == "inicio"
        assert [i.nome for i in app.minha_fila] == ["(sem nome)"]
        app.avancar_pagina()
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["t"] == "busca"


async def test_contexto_com_paginas_quebradas_no_meio(srv, estado, config, armazem):
    estado.preparar()
    estado.arquivo.write_text(json.dumps({"versao": 1, "dados": {
        "hist": ["lixo", {"t": "fila"}, {"t": "item", "item": None}, {"t": "top", "per": 1, "cat": "tracks"}], "pos": "x",
        "larguras": {"bib": "largo"}, "minha_fila": "nada"}}))
    estado.carregar()
    app = app_real(srv, estado, config, armazem)
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(1.5)
        assert app.is_running
        assert [v["t"] for v in app.historico] == ["top", "inicio"]  # a posição salva não vale: abre o início
        assert app.query_one("#principal").vista["t"] == "inicio" and app.historico[0]["per"] == "short_term"


async def test_dados_parciais_da_api(srv, estado, config, armazem):
    app = app_real(srv, estado, config, armazem)
    async with app.run_test(size=TAM) as pilot:
        assert await esperar(pilot, lambda: app.dados_bib and app.player is not None, 5)
        assert app.query_one("#principal").vista["t"] == "inicio"
        assert [i.nome for i in app.query_one("#bib").visiveis][:3] == ["Músicas Curtidas", "Minha", "Alheia"]
        await percorrer(app, pilot)


async def test_campos_nulos_em_todas_as_respostas(srv, estado, config, armazem):
    srv.respostas.update(NULOS)
    app = app_real(srv, estado, config, armazem)
    async with app.run_test(size=TAM) as pilot:
        assert await esperar(pilot, lambda: app.dados_bib and app.player is not None, 5)
        assert app.player.item.nome == "(sem nome)" and app.player.repetir == "off" and app.player.dispositivo == ""
        assert "(sem nome)" in str(app.query_one("#pl-titulo").render())
        assert app.query_one("#bib").visiveis[1].nome == "(sem nome)"
        await percorrer(app, pilot)


async def test_endpoints_que_respondem_403_e_404(srv, estado, config, armazem):
    srv.respostas.update(ERROS)
    app = app_real(srv, estado, config, armazem)
    async with app.run_test(size=TAM) as pilot:
        assert await esperar(pilot, lambda: app.dados_bib and app.player is not None, 5)
        await percorrer(app, pilot)
        app.navegar(PAGINAS[7])  # playlist sua que responde 403: mostra o erro no lugar da tabela
        await pilot.pause(0.6)
        assert "negou" in str(app.query_one("#principal").pagina.query_one("#cab-tabela").render())


async def test_conta_sem_nada_e_nada_tocando(srv, estado, config, armazem):
    srv.respostas.update(VAZIO)
    srv.respostas.update({k: v for k, v in ERROS.items() if "recently" in k[1] or "/me/top" in k[1] or "/me/shows" in k[1]})
    app = app_real(srv, estado, config, armazem)
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(1.5)
        assert app.is_running and app.player is None
        assert [i.nome for i in app.query_one("#bib").visiveis] == ["Músicas Curtidas"]
        assert "nada tocando" in str(app.query_one("#pl-titulo").render())
        assert await esperar(pilot, lambda: "Toque algo" in str(app.query_one("#vazio-inicio").render()), 5)
        await percorrer(app, pilot)
