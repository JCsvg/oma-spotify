import json

import pytest
from textual.widgets import Button, Input

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.estado import Estado
from oma_spotify.services.falso import ClienteFalso
from oma_spotify.ui.abertura import Abertura, banner
from oma_spotify.ui.dialogos import Confirmar, Pedir
from oma_spotify.ui.setup import TelaSetup
from oma_spotify.ui.telas import PaginaBiblioteca, PaginaBusca
from oma_spotify.ui.widgets import Tabela
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
    async with a.run_test(size=TAM) as pilot:
        await pilot.press("3")
        pg = a.query_one(PaginaBiblioteca)
        assert await esperar(pilot, lambda: pg.query_one("#tabela", Tabela).row_count == 2)
        await pilot.press("down")
        await pilot.click("#cat-albuns")
        await pilot.pause(0.5)
        await pilot.press("4")
        await pilot.pause(0.3)
        a.query_one("#q", Input).value = "lua"
        await pilot.pause(0.2)
        await a.action_quit()
    assert estado.arquivo.exists()
    b = novo(Estado(estado.pasta), config, armazem)
    async with b.run_test(size=TAM) as pilot:
        await pilot.pause(0.8)
        assert b.aba_atual() == "busca"
        assert b.query_one("#q", Input).value == "lua"
        assert b.query_one(PaginaBiblioteca).categoria == "albuns"


async def test_estado_so_guarda_contexto_nunca_segredos(estado, config, armazem):
    config.client_id = "CLIENTE-ID-SECRETO-1234567890"
    armazem.gravar({"access_token": "TOKEN-ABC", "refresh_token": "REFRESH-XYZ", "expira": 1})
    a = novo(estado, config, armazem)
    async with a.run_test(size=TAM) as pilot:
        await pilot.press("4")
        a.query_one("#q", Input).value = "busca qualquer"
        await pilot.pause(0.3)
        await pilot.press("5", "9")
        await pilot.pause(0.5)
        await pilot.press("alt+h")
        await pilot.pause(0.2)
        a.estado.salvar()
    bruto = estado.arquivo.read_text()
    for segredo in ("TOKEN-ABC", "REFRESH-XYZ", "CLIENTE-ID-SECRETO", "token", "client"):
        assert segredo not in bruto
    assert json.loads(bruto)["dados"]["aba"] in ("biblioteca", "busca")
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
            await pilot.press(*"abcdefghij0123456789", "enter")
            assert await esperar(pilot, lambda: not isinstance(a.screen, TelaSetup), 6)
            assert config.client_id == "abcdefghij0123456789"
            assert armazem.logado() and a.conectado
    finally:
        auth.Sessao.__init__ = orig
        srv.parar()


async def test_setup_esc_e_ctrl_setas(estado, config, armazem):
    a = OmaSpotifyApp(estado=estado, config=config, armazem=armazem, abertura=False)
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.6)
        await pilot.press("ctrl+j")
        assert isinstance(a.focused, Button)
        await pilot.press("ctrl+l")
        assert isinstance(a.focused, Button)
        await pilot.press("down", "up")
        assert isinstance(a.screen, TelaSetup)


async def test_config_opcoes_por_clique_e_teclado(estado, config, armazem):
    a = novo(estado, config, armazem)
    async with a.run_test(size=TAM) as pilot:
        await pilot.press("9")
        await pilot.pause(0.3)
        await pilot.click("#abertura")
        assert config.abertura is False
        assert "não" in str(a.query_one("#abertura", Button).label)
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
    config.client_id = "abcdefghij0123456789"
    armazem.gravar({"access_token": "a", "refresh_token": "r", "expira": 9e12})
    a = OmaSpotifyApp(cliente=ClienteFalso(), estado=estado, config=config, armazem=armazem, abertura=False)
    a.demo = False
    async with a.run_test(size=TAM) as pilot:
        await pilot.pause(0.5)
        await pilot.press("9")
        await pilot.pause(0.3)
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
