from __future__ import annotations

import asyncio

import pytest

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.config import Config
from oma_spotify.estado import Estado
from oma_spotify.services.auth import Armazem
from oma_spotify.services.falso import ClienteFalso
from oma_spotify.services.modelos import Dispositivo
from oma_spotify.services.plugin import PluginOmaSpotify


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    """Nenhum teste toca em config, tokens ou estado reais."""
    for k, v in (("XDG_CONFIG_HOME", "cfg"), ("XDG_STATE_HOME", "state"), ("XDG_RUNTIME_DIR", "run"), ("XDG_CACHE_HOME", "cache")):
        monkeypatch.setenv(k, str(tmp_path / v))
        (tmp_path / v).mkdir()


@pytest.fixture
def estado(tmp_path):
    return Estado(tmp_path / "estado")


@pytest.fixture
def config(tmp_path):
    return Config(tmp_path / "config")


@pytest.fixture
def armazem(tmp_path):
    return Armazem(tmp_path / "tokens")


@pytest.fixture
def falso():
    return ClienteFalso()


@pytest.fixture
def lancados():
    return []


@pytest.fixture
def abertos():
    return []


class PluginFalso:
    """Serviço systemd falso do plugin: ao iniciar, o dispositivo OmaSpotify aparece no cliente falso."""

    eh_dispositivo = staticmethod(PluginOmaSpotify.eh_dispositivo)

    def __init__(self, falso, instalado=True, ativo=False, inicia=True, aparece=True):
        self.falso, self._inst, self._ativo, self._inicia, self._aparece = falso, instalado, ativo, inicia, aparece
        self.iniciou = 0

    def instalado(self):
        return self._inst

    def ativo(self):
        return self._ativo

    def iniciar(self):
        self.iniciou += 1
        if self._inicia:
            self._ativo = True
            if self._aparece:
                self.falso.devs.append(Dispositivo("oma", "OmaSpotify", "Computer", False, 70))
        return self._inicia


@pytest.fixture
def plugin(falso):
    return PluginFalso(falso)


@pytest.fixture
def letras():
    from oma_spotify.services.falso import LETRAS
    from oma_spotify.services.letras import LetrasFalsas
    return LetrasFalsas(LETRAS)


@pytest.fixture
def app(falso, estado, config, armazem, lancados, abertos, plugin, letras):
    a = OmaSpotifyApp(cliente=falso, demo=True, estado=estado, config=config, armazem=armazem, abertura=False,
                      abridor=abertos.append, lancador=lambda: lancados.append(1) or True, espera_dispositivo=0.05, plugin=plugin,
                      letras=letras, copiador=lambda t: True)
    a.espera_max = 1.5
    return a


async def pronto(app, pilot):
    """Biblioteca, player e início carregados."""
    await pilot.pause(0.3)
    assert await esperar(pilot, lambda: app.player is not None and app.dados_bib and app.query("#recentes")
                         and app.query_one("#recentes").itens, 5)
    await pilot.pause(0.2)


def janela(app) -> str:
    return app.nome_janela(app.focused)


async def esperar(pilot, cond, tempo=3.0):
    """Espera uma condição (as chamadas à API rodam em threads)."""
    fim = asyncio.get_event_loop().time() + tempo
    while asyncio.get_event_loop().time() < fim:
        await pilot.pause(0.05)
        if cond():
            return True
    return cond()
