import json

import pytest
from textual.widgets import Input

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.estado import Estado
from oma_spotify.services.falso import ClienteFalso
from oma_spotify.ui.abertura import Abertura, banner
from oma_spotify.ui.dialogos import Confirmar, Pedir
from oma_spotify.ui.setup import TelaSetup
from oma_spotify.ui.biblioteca import Biblioteca
from oma_spotify.ui.widgets import Botao
from tests.conftest import esperar

TAM = (130, 42)


def novo(estado, config, armazem, abertura=False, **kw):
    return OmaSpotifyApp(cliente=ClienteFalso(), demo=True, estado=estado, config=config, armazem=armazem, abertura=abertura, **kw)


async def test_abertura_so_na_primeira_vez_do_boot(estado, config, armazem):
    a1 = novo(estado, config, armazem, True)
    async with a1.run_test(size=TAM) as pilot:
        await pilot.pause(0.4)
        assert isinstance(a1.screen, Abertura)
        assert "█" in str(a1.screen.query_one("#logo").render())
        await pilot.press("x")
        await pilot.pause(0.3)
        assert not isinstance(a1.screen, Abertura)
    assert estado.ja_abriu() and estado.marcador.parent.name == "estado"
    a2 = novo(Estado(estado.pasta), config, armazem, True)
    async with a2.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        assert not isinstance(a2.screen, Abertura)


async def test_abertura_passa_com_clique_e_com_tempo(estado, config, armazem):
    a = novo(estado, config, armazem, True)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.4)
        await pilot.click("#logo")
        await pilot.pause(0.3)
        assert not isinstance(a.screen, Abertura)
    estado.marcador.unlink()
    b = novo(estado, config, armazem, True)
    async with b.run_test(size=TAM) as pilot:
        await pilot.pause(0.4)
        assert isinstance(b.screen, Abertura)
        assert await esperar(pilot, lambda: not isinstance(b.screen, Abertura), 3)


async def test_abertura_desligada_na_configuracao(estado, config, armazem):
    config.abertura = False
    a = novo(estado, config, armazem, True)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        assert not isinstance(a.screen, Abertura)


@pytest.mark.parametrize("tam,grande", [((80, 24), True), ((200, 50), True), ((50, 20), False)])
async def test_banner_em_varios_tamanhos(estado, config, armazem, tam, grande):
    a = novo(estado, config, armazem, True)
    async with a.run_test(size=tam) as pilot:
        await pilot.pause(0.4)
        logo = str(a.screen.query_one("#logo").render())
        assert ("█" in logo) == grande
        if not grande:
            assert "OMA SPOTIFY" in logo
        assert len(banner(*tam)) == (5 if grande else 1)


async def test_contexto_restaurado_ao_reabrir(estado, config, armazem):
    a = novo(estado, config, armazem)
    async with a.run_test(size=(180, 48)) as pilot:
        await pilot.pause(0.8)
        a.query_one("#bib-abas").definir("album", avisar=True)
        a.query_one("#filtro-bib", Input).value = "noites"
        a.navegar({"t": "busca", "q": "lua", "cat": "track"})
        a.guardar("busca", "lua")
        await pilot.pause(0.6)
        a.focar_janela("principal")
        await pilot.press("left_square_bracket", "right_square_bracket")
        await pilot.pause(0.3)
        await a.action_quit()
    assert estado.arquivo.exists()
    b = novo(Estado(estado.pasta), config, armazem)
    async with b.run_test(size=(180, 48)) as pilot:
        await pilot.pause(1.0)
        assert b.query_one("#principal").vista["t"] == "busca" and b.query_one("#principal").vista["q"] == "lua"
        assert b.query_one("#principal").vista["cat"] == "track"
        assert b.query_one(Biblioteca).cat == "album" and b.query_one("#filtro-bib", Input).value == "noites"
        assert b.pref_bib is False and b.pref_dir is False


async def test_estado_so_guarda_contexto_nunca_segredos(estado, config, armazem):
    config.client_id = "CLIENTE-ID-SECRETO-1234567890"
    armazem.gravar({"access_token": "TOKEN-ABC", "refresh_token": "REFRESH-XYZ", "expira": 1})
    a = novo(estado, config, armazem)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        a.guardar("busca", "busca qualquer")
        a.navegar({"t": "busca", "q": "busca qualquer", "cat": "tudo"})
        await pilot.pause(0.5)
        a.estado.salvar()
    bruto = estado.arquivo.read_text()
    for segredo in ("TOKEN-ABC", "REFRESH-XYZ", "CLIENTE-ID-SECRETO", "token", "client"):
        assert segredo not in bruto
    assert json.loads(bruto)["dados"]["busca"] == "busca qualquer"
    assert not (estado.pasta / "tokens.json").exists()


def test_estado_recusa_chaves_de_segredo(estado):
    estado.definir("access_token", "x")
    estado.definir("client_id", "y")
    estado.definir("conta_email", "z")
    assert estado.dados == {}


async def test_sem_client_id_mostra_configuracao_guiada_sem_quebrar(estado, config, armazem, abertos):
    a = OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False, abridor=abertos.append)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        assert isinstance(a.screen, TelaSetup)
        texto = " ".join(str(w.render()) for w in a.screen.query("Static"))
        assert "http://127.0.0.1:8888/callback" in texto and "Premium" in texto
        await pilot.click("#abrir-painel")
        await pilot.click("#abrir-criar")
        assert abertos == ["https://developer.spotify.com/dashboard", "https://developer.spotify.com/dashboard/create"]
        await pilot.click("#copiar")
        await pilot.click("#entrar")  # sem Client ID: avisa, não quebra
        await pilot.pause(0.2)
        assert "Client ID" in str(a.screen.query_one("#status").render())
        assert isinstance(a.screen, TelaSetup)


async def test_setup_por_teclado_e_login_pelo_fluxo_real_contra_servidor_falso(estado, config, armazem, tmp_path):
    import threading
    import urllib.parse
    import urllib.request
    from oma_spotify.services import auth
    from tests.fake_api import ServidorFalso
    srv = ServidorFalso()
    config.porta = 18765
    orig = auth.Sessao.__init__

    def init(self, *a, **kw):
        orig(self, *a, **{**kw, "token_url": srv.token_url})
    auth.Sessao.__init__ = init

    def navegador(url):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        threading.Timer(0.2, lambda: urllib.request.urlopen(f"{q['redirect_uri'][0]}?code=codigo-bom&state={q['state'][0]}").read()).start()
    try:
        a = OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False, abridor=navegador)
        async with a.run_test(size=TAM) as pilot:
            await pilot.pause(0.6)
            assert isinstance(a.screen, TelaSetup)
            assert isinstance(a.focused, Input)
            await pilot.press(*"0123456789abcdef0123456789abcdef", "enter")
            assert await esperar(pilot, lambda: not isinstance(a.screen, TelaSetup), 6)
            assert config.client_id == "0123456789abcdef0123456789abcdef"
            assert armazem.logado() and a.conectado
    finally:
        auth.Sessao.__init__ = orig
        srv.parar()


async def test_setup_esc_e_ctrl_setas(estado, config, armazem):
    a = OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        await pilot.press("ctrl+j")
        assert isinstance(a.focused, Botao)
        await pilot.press("ctrl+l")
        assert isinstance(a.focused, Botao)
        await pilot.press("tab")
        assert a.focused is not None
        await pilot.press("down", "up")
        assert isinstance(a.screen, TelaSetup)


async def test_config_opcoes_por_clique_e_teclado(estado, config, armazem):
    a = novo(estado, config, armazem)
    async with a.run_test(size=TAM) as pilot:
        a.navegar({"t": "config"})
        await pilot.pause(0.5)
        await pilot.click("#abertura")
        assert config.abertura is False
        assert "não" in a.query_one("#abertura", Botao).label
        await pilot.click("#letra")
        assert config.letra is False
        await pilot.click("#icones")
        assert config.icones == "simples"
        await pilot.click("#porta")
        await pilot.pause(0.2)
        assert isinstance(a.screen, Pedir)
        a.screen.query_one("#campo", Input).value = "9000"
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert config.porta == 9000 and "9000" in str(a.query_one("#resumo").render())
        await pilot.click("#cid")
        await pilot.pause(0.2)
        await pilot.press(*"meuid", "enter")
        await pilot.pause(0.2)
        assert config.client_id == "meuid"
        assert (config.arquivo).exists()


async def test_sair_da_conta_apaga_tokens_com_confirmacao(estado, config, armazem):
    config.client_id = "0123456789abcdef0123456789abcdef"
    armazem.gravar({"access_token": "a", "refresh_token": "r", "expira": 9e12})
    a = OmaSpotifyApp(cliente=ClienteFalso(), estado=estado, config=config, armazem=armazem, abertura=False)
    a.demo = False
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.5)
        a.navegar({"t": "config"})
        await pilot.pause(0.5)
        await pilot.click("#sair-conta")
        await pilot.pause(0.2)
        assert isinstance(a.screen, Confirmar)
        await pilot.press("escape")  # cancelar mantém
        await pilot.pause(0.2)
        assert armazem.logado()
        await pilot.click("#sair-conta")
        await pilot.pause(0.2)
        await pilot.click("#sim")
        await pilot.pause(0.5)
        assert not armazem.logado()
        assert isinstance(a.screen, TelaSetup)


# ---------------------------------------------------------------- espera do login (0.1.1)
async def _abrir_espera(a, pilot, porta):
    await pilot.pause(0.6)
    assert isinstance(a.screen, TelaSetup)
    a.screen.query_one("#client-id", Input).value = "0123456789abcdef0123456789abcdef"
    await pilot.click("#entrar")
    await pilot.pause(0.4)
    assert a.screen.login is not None and a.screen.query_one("#espera").display


def _app(estado, config, armazem, porta, abertos, copias, copiou=True, tempo=30.0, ajuda=15.0):
    config.porta = porta
    return OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False, abridor=abertos.append,
                         copiador=lambda t: copias.append(t) or copiou, tempo_login=tempo, tempo_ajuda=ajuda)


async def test_espera_mostra_contagem_regressiva_e_botoes(estado, config, armazem):
    from tests.unit.test_auth import _porta_livre
    abertos, copias = [], []
    a = _app(estado, config, armazem, _porta_livre(), abertos, copias, tempo=10)
    async with a.run_test(size=TAM) as pilot:
        await _abrir_espera(a, pilot, 0)
        tx = lambda: str(a.screen.query_one("#contagem").render())
        assert "Esperando você autorizar no navegador (0:" in tx() and len(abertos) == 1
        antes = tx()
        await pilot.pause(1.3)
        assert tx() != antes
        await pilot.click("#reabrir")
        assert len(abertos) == 2 and abertos[1] == abertos[0]
        await pilot.click("#cancelar")
        await pilot.pause(0.5)


async def test_copiar_link_e_mostrar_quando_nao_ha_wl_copy(estado, config, armazem):
    from tests.unit.test_auth import _porta_livre
    abertos, copias = [], []
    a = _app(estado, config, armazem, _porta_livre(), abertos, copias, copiou=False)
    async with a.run_test(size=TAM) as pilot:
        await _abrir_espera(a, pilot, 0)
        await pilot.click("#copiar-link")
        await pilot.pause(0.2)
        assert copias[-1] == abertos[0] and copias[-1].startswith("https://accounts.spotify.com/authorize?")
        assert abertos[0] in str(a.screen.query_one("#link").render())
        await pilot.press("u")  # tecla: copiar Redirect URI
        assert copias[-1] == config.redirect
        await pilot.press("x")
        await pilot.pause(0.4)


async def test_cancelar_por_clique_e_por_teclado_libera_a_porta(estado, config, armazem):
    import socket
    from tests.unit.test_auth import _porta_livre
    for modo in ("clique", "tecla", "esc"):
        porta = _porta_livre()
        abertos, copias = [], []
        cfg = type(config)(config.pasta)
        a = _app(estado, cfg, armazem, porta, abertos, copias)
        async with a.run_test(size=TAM) as pilot:
            await _abrir_espera(a, pilot, porta)
            if modo == "clique":
                await pilot.click("#cancelar")
            elif modo == "tecla":
                await pilot.press("x")
            else:
                await pilot.press("escape")
            await pilot.pause(0.6)
            assert isinstance(a.screen, TelaSetup) and a.screen.login is None
            assert a.screen.query_one("#passos").display
            assert "cancelada" in str(a.screen.query_one("#status").render())
            with socket.socket() as s:
                s.bind(("127.0.0.1", porta))


async def test_ajuda_de_erros_aparece_apos_15s_e_por_botao(estado, config, armazem):
    from tests.unit.test_auth import _porta_livre
    a = _app(estado, config, armazem, _porta_livre(), [], [], ajuda=1.0)
    async with a.run_test(size=TAM) as pilot:
        await _abrir_espera(a, pilot, 0)
        ajuda = a.screen.query_one("#ajuda-texto")
        assert not ajuda.display
        assert await esperar(pilot, lambda: ajuda.display, 4)
        txt = str(ajuda.render())
        assert "Not matching configuration" in txt and config.redirect in txt and "User Management" in txt
        assert "127.0.0.1" in txt and "32 caracteres" in txt and "SAVE" in txt
        await pilot.click("#cancelar")
        await pilot.pause(0.4)
    b = _app(estado, config, armazem, _porta_livre(), [], [], ajuda=999)
    async with b.run_test(size=TAM) as pilot:
        await _abrir_espera(b, pilot, 0)
        assert not b.screen.query_one("#ajuda-texto").display
        await pilot.click("#ajuda-erros")
        assert b.screen.query_one("#ajuda-texto").display
        await pilot.press("x")
        await pilot.pause(0.4)


@pytest.mark.parametrize("valor,trecho", [("abc", "3 caracteres"), ("0123456789abcdef 123456789abcdef", "espaço"), ("z" * 32, "letras de a a f")])
async def test_setup_valida_client_id_e_nao_inicia_login(estado, config, armazem, valor, trecho):
    abertos = []
    a = OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False, abridor=abertos.append)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        a.screen.query_one("#client-id", Input).value = valor
        await pilot.click("#entrar")
        await pilot.pause(0.2)
        assert trecho in str(a.screen.query_one("#status").render())
        assert abertos == [] and a.screen.login is None and config.client_id == ""


async def test_verificar_configuracao_no_setup_e_na_config(estado, config, armazem):
    from tests.fake_api import ServidorFalso
    from tests.unit.test_auth import _porta_livre
    srv = ServidorFalso()
    id32 = "0123456789abcdef0123456789abcdef"
    config.porta = _porta_livre()
    a = OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False, url_rede=f"http://127.0.0.1:{srv.porta}/")
    try:
        async with a.run_test(size=TAM) as pilot:
            await pilot.pause(0.6)
            a.screen.query_one("#client-id", Input).value = id32
            await pilot.click("#verificar")
            assert await esperar(pilot, lambda: "Conexão" in str(a.screen.query_one("#diag").render()))
            txt = str(a.screen.query_one("#diag").render())
            assert id32 not in txt and "0123...cdef" in txt and config.redirect in txt and "ok" in txt
            await pilot.press("escape", "escape")
        # Configurações do app já conectado
        config.client_id = id32
        b = OmaSpotifyApp(cliente=ClienteFalso(), demo=True, estado=estado, config=config, armazem=armazem, abertura=False,
                          url_rede=f"http://127.0.0.1:{srv.porta}/")
        async with b.run_test(size=TAM) as pilot:
            b.navegar({"t": "config"})
            await pilot.pause(0.5)
            await pilot.click("#verificar")
            assert await esperar(pilot, lambda: "Conexão" in str(b.query_one("#diag-config").render()))
            assert id32 not in str(b.query_one("#diag-config").render())
    finally:
        srv.parar()
