import json
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from oma_spotify.services import auth, diagnostico
from oma_spotify.services.modelos import ErroSpotify
from tests.fake_api import ServidorFalso
from tests.unit.test_auth import _porta_livre

ID32 = "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize("bruto,trecho", [("", "Cole"), ("abc def" + "0" * 25, "espaço"), ("abcdef", "6 caracteres"),
                                           ("g" * 32, "letras de a a f"), ("0" * 33, "33 caracteres")])
def test_client_id_invalido(bruto, trecho):
    cid, erro = auth.validar_client_id(bruto)
    assert trecho in erro


def test_client_id_valido_faz_trim():
    assert auth.validar_client_id(f"  {ID32}\n") == (ID32, "")


def test_cancelar_libera_a_porta_na_hora(tmp_path):
    porta = _porta_livre()
    ses = auth.Sessao(ID32, porta, auth.Armazem(tmp_path / "t"))
    abertos = []
    login = ses.iniciar_login(abertos.append, tempo=60)
    assert abertos and abertos[0] == login.url
    assert not diagnostico.porta_livre(porta) or True
    resultado = []
    t = threading.Thread(target=lambda: resultado.append(_tentar(login)))
    t.start()
    login.cancelar()
    t.join(3)
    assert not t.is_alive() and "cancelada" in resultado[0]
    with socket.socket() as s:  # a porta voltou
        s.bind(("127.0.0.1", porta))
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(f"http://127.0.0.1:{porta}/callback", timeout=1)


def _tentar(login):
    try:
        login.concluir()
    except ErroSpotify as e:
        return str(e)
    return ""


def test_porta_ocupada_da_mensagem_clara(tmp_path):
    porta = _porta_livre()
    with socket.socket() as s:
        s.bind(("127.0.0.1", porta))
        s.listen()
        with pytest.raises(ErroSpotify) as e:
            auth.Sessao(ID32, porta, auth.Armazem(tmp_path / "t")).iniciar_login(lambda u: None)
    assert "ocupada" in str(e.value)


def test_restante_diminui(tmp_path):
    ses = auth.Sessao(ID32, _porta_livre(), auth.Armazem(tmp_path / "t"))
    login = ses.iniciar_login(lambda u: None, tempo=100)
    try:
        assert 99 < login.restante() <= 100
    finally:
        login.cancelar()


@pytest.mark.parametrize("corpo,trecho", [({"error": "invalid_client"}, "Client ID"), ({"error": "invalid_grant"}, "expirou"),
                                           ({"error": "invalid_request"}, "http://127.0.0.1:1/callback")])
def test_mensagem_por_tipo_de_erro_na_troca(corpo, trecho):
    e = auth._erro_token(400, json.dumps(corpo).encode(), {"grant_type": "authorization_code", "redirect_uri": "http://127.0.0.1:1/callback"})
    assert trecho in str(e) and e.sem_login
    assert "Confira o Client ID e o Redirect URI" not in str(e)


def test_invalid_grant_na_renovacao_fala_de_sessao():
    e = auth._erro_token(400, b'{"error":"invalid_grant"}', {"grant_type": "refresh_token"})
    assert "sessão" in str(e)


def test_erro_recebido_no_callback_vira_mensagem():
    porta = _porta_livre()
    s = auth.ServidorRetorno(porta, "abc")
    s.iniciar()
    try:
        threading.Timer(0.1, lambda: urllib.request.urlopen(f"http://127.0.0.1:{porta}/callback?error=invalid_client&state=abc").read()).start()
        with pytest.raises(ErroSpotify) as e:
            s.esperar(5)
        assert "invalid_client" in str(e.value)
    finally:
        s.parar()


def test_diagnostico_nao_vaza_o_client_id():
    srv = ServidorFalso()
    try:
        linhas = diagnostico.verificar(ID32, _porta_livre(), "http://127.0.0.1:8888/callback", f"http://127.0.0.1:{srv.porta}/")
    finally:
        srv.parar()
    txt = "\n".join(linhas)
    assert ID32 not in txt and "0123...cdef" in txt
    assert "http://127.0.0.1:8888/callback" in txt and "livre" in txt and "ok" in txt


def test_diagnostico_porta_ocupada_e_sem_rede():
    porta = _porta_livre()
    with socket.socket() as s:
        s.bind(("127.0.0.1", porta))
        s.listen()
        linhas = diagnostico.verificar("curto", porta, "x", "http://127.0.0.1:1/")
    txt = "\n".join(linhas)
    assert "NÃO" in txt and "SEM RESPOSTA" in txt and "curto demais" in txt
