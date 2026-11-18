import json

import pytest

from oma_spotify.services.api import ClienteSpotify
from oma_spotify.services.auth import Armazem, Sessao
from oma_spotify.services.modelos import ErroSpotify
from tests.fake_api import ServidorFalso


@pytest.fixture
def srv():
    s = ServidorFalso()
    yield s
    s.parar()


@pytest.fixture
def cli(srv, tmp_path):
    arm = Armazem(tmp_path / "t")
    arm.gravar({"access_token": "acesso-1", "refresh_token": "refresh-1", "expira": 9e12})
    esperas = []
    c = ClienteSpotify(Sessao("cid", 1, arm, token_url=srv.token_url), srv.api, dormir=esperas.append)
    c.esperas = esperas
    return c


def test_player_normalizado(cli):
    p = cli.player()
    assert p.item.nome == "Faixa X" and p.item.sub == "Banda Y" and p.item.extra == "Disco Z"
    assert p.aleatorio and p.repetir == "track" and p.volume == 30 and p.dispositivo == "PC"


def test_playlists_marca_as_minhas_e_itens_novos(cli):
    ps = cli.playlists()
    assert [(p.nome, p.meu, p.extra) for p in ps] == [("Minha", True, "3 faixas"), ("Alheia", False, "1 faixas")]
    assert cli.itens_playlist("p1")[0].nome == "Faixa X"  # lê o campo novo `item`


def test_endpoints_vigentes_de_biblioteca_e_playlist(cli, srv):
    cli.curtir("spotify:track:x")
    cli.descurtir("spotify:track:x")
    cli.criar_playlist("Nova")
    cli.adicionar_a_playlist("p1", "spotify:track:x")
    cli.remover_da_playlist("p1", "spotify:track:x")
    cam = [(m, c.split("?")[0]) for m, c, *_ in srv.pedidos if "/api/token" not in c]
    assert ("PUT", "/v1/me/library") in cam and ("DELETE", "/v1/me/library") in cam
    assert ("POST", "/v1/me/playlists") in cam
    assert ("POST", "/v1/playlists/p1/items") in cam and ("DELETE", "/v1/playlists/p1/items") in cam
    assert not any("/me/tracks" in c and m != "GET" for m, c in cam)
    rem = [p for p in srv.pedidos if p[0] == "DELETE" and p[1].startswith("/v1/playlists")][0]
    assert json.loads(rem[3]) == {"items": [{"uri": "spotify:track:x"}]}


def test_busca_limite_10_e_ignora_nulos(cli, srv):
    r = cli.buscar("x")
    assert r["track"][0].nome == "Achada" and r["playlist"] == []
    q = [c for m, c, *_ in srv.pedidos if c.startswith("/v1/search")][0]
    assert "limit=10" in q


def test_curtido(cli):
    assert cli.curtido(["spotify:track:a", "spotify:track:b"]) == [True, True]


def test_401_renova_o_token_e_repete(cli, srv):
    srv.validos.discard("acesso-1")
    assert cli.player().item.nome == "Faixa X"
    assert srv.n_refresh == 1


def test_429_espera_retry_after_e_repete(cli, srv):
    srv.respostas[("PUT", "/v1/me/player/pause")] = [(429, {"error": {}}, {"Retry-After": "2"}), (204, None)]
    cli.pausar()
    assert cli.esperas == [2.0]


def test_429_sem_fim_vira_erro_claro(cli, srv):
    srv.respostas[("POST", "/v1/me/player/next")] = [(429, {"error": {}}, {"Retry-After": "1"})]
    with pytest.raises(ErroSpotify) as e:
        cli.proxima()
    assert "Muitas requisições" in str(e.value) and len(cli.esperas) == 3


def test_404_sem_dispositivo(cli, srv):
    srv.respostas[("PUT", "/v1/me/player/play")] = [(404, {"error": {"status": 404, "reason": "NO_ACTIVE_DEVICE"}})]
    with pytest.raises(ErroSpotify) as e:
        cli.tocar(uris=["spotify:track:x"])
    assert e.value.sem_dispositivo and "dispositivo" in str(e.value)


@pytest.mark.parametrize("status,razao,trecho", [(403, "PREMIUM_REQUIRED", "Premium"), (403, "", "negou"), (500, "", "problema"),
                                                  (404, "", "404"), (400, "", "erro 400")])
def test_erros_em_portugues_sem_stack(cli, srv, status, razao, trecho):
    srv.respostas[("POST", "/v1/me/player/next")] = [(status, {"error": {"reason": razao}})]
    with pytest.raises(ErroSpotify) as e:
        cli.proxima()
    assert trecho in str(e.value) and "Traceback" not in str(e.value)


def test_rede_fora_do_ar(tmp_path):
    arm = Armazem(tmp_path / "t")
    arm.gravar({"access_token": "a", "refresh_token": "r", "expira": 9e12})
    c = ClienteSpotify(Sessao("cid", 1, arm), "http://127.0.0.1:1/v1")
    with pytest.raises(ErroSpotify) as e:
        c.player()
    assert "Sem conexão" in str(e.value)


def test_token_nao_vaza_em_logs_nem_saida(cli, srv, caplog, capsys):
    import logging
    caplog.set_level(logging.DEBUG)
    cli.player()
    cli.curtir("spotify:track:x")
    saida = capsys.readouterr()
    for txt in (caplog.text, saida.out, saida.err):
        assert "acesso-1" not in txt and "refresh-1" not in txt
