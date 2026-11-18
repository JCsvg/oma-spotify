import base64
import hashlib
import json
import os
import stat
import threading
import urllib.parse
import urllib.request

import pytest

from oma_spotify.services import auth
from oma_spotify.services.modelos import ErroSpotify
from tests.fake_api import ServidorFalso


@pytest.fixture
def srv():
    s = ServidorFalso()
    yield s
    s.parar()


def test_pkce_verifier_e_desafio():
    v = auth.novo_verifier()
    assert 43 <= len(v) <= 128
    esperado = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    assert auth.desafio(v) == esperado and "=" not in auth.desafio(v)
    assert auth.novo_verifier() != v


def test_url_de_autorizacao_usa_ip_literal_e_s256():
    u = urllib.parse.urlparse(auth.url_autorizacao("cid123", 8888, "DESAFIO", "est"))
    q = urllib.parse.parse_qs(u.query)
    assert q["redirect_uri"] == ["http://127.0.0.1:8888/callback"]
    assert "localhost" not in u.query
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] == ["DESAFIO"]
    assert q["state"] == ["est"] and q["response_type"] == ["code"] and "client_secret" not in q
    assert "playlist-modify-private" in q["scope"][0]


def test_armazem_0600_e_apagar(tmp_path):
    a = auth.Armazem(tmp_path / "x")
    assert not a.logado()
    a.gravar({"access_token": "a", "refresh_token": "r", "expira": 1})
    assert stat.S_IMODE(os.stat(a.arquivo).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(a.pasta).st_mode) == 0o700
    assert a.logado()
    a.apagar()
    assert not a.logado()


def _porta_livre():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_servidor_de_retorno_aceita_state_certo():
    porta = _porta_livre()
    s = auth.ServidorRetorno(porta, "abc")
    s.iniciar()
    try:
        threading.Timer(0.1, lambda: urllib.request.urlopen(f"http://127.0.0.1:{porta}/callback?code=zzz&state=abc").read()).start()
        assert s.esperar(5) == "zzz"
    finally:
        s.parar()


def test_servidor_de_retorno_recusa_state_errado():
    porta = _porta_livre()
    s = auth.ServidorRetorno(porta, "abc")
    s.iniciar()
    try:
        threading.Timer(0.1, lambda: urllib.request.urlopen(f"http://127.0.0.1:{porta}/callback?code=zzz&state=outro").read()).start()
        with pytest.raises(ErroSpotify):
            s.esperar(5)
    finally:
        s.parar()


def test_login_completo_com_troca_de_codigo(srv, tmp_path):
    porta = _porta_livre()
    arm = auth.Armazem(tmp_path / "t")
    ses = auth.Sessao("cid", porta, arm, token_url=srv.token_url)

    def navegador(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        def volta():
            urllib.request.urlopen(f"{q['redirect_uri'][0]}?code=codigo-bom&state={q['state'][0]}").read()
        threading.Timer(0.1, volta).start()

    ses.entrar(abrir=navegador, tempo=5)
    f = srv.forms[0]
    assert f["grant_type"] == "authorization_code" and f["client_id"] == "cid"
    assert f["redirect_uri"] == f"http://127.0.0.1:{porta}/callback" and f["code_verifier"] and "client_secret" not in f
    assert arm.ler()["refresh_token"] == "refresh-1"


def test_renovacao_automatica_e_refresh_invalido(srv, tmp_path):
    arm = auth.Armazem(tmp_path / "t")
    arm.gravar({"access_token": "velho", "refresh_token": "refresh-1", "expira": 0})
    ses = auth.Sessao("cid", 1, arm, token_url=srv.token_url)
    assert ses.token() == "acesso-r1"
    assert arm.ler()["refresh_token"] == "refresh-1"  # mantém o refresh quando a resposta não traz outro
    arm.gravar({"access_token": "velho", "refresh_token": "ruim", "expira": 0})
    with pytest.raises(ErroSpotify) as e:
        ses.token()
    assert e.value.sem_login


def test_sem_login_pede_login(tmp_path):
    ses = auth.Sessao("cid", 1, auth.Armazem(tmp_path / "t"))
    with pytest.raises(ErroSpotify) as e:
        ses.token()
    assert e.value.sem_login
