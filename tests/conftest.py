from __future__ import annotations

import asyncio

import pytest

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.config import Config
from oma_spotify.estado import Estado
from oma_spotify.services.auth import Armazem
from oma_spotify.services.falso import ClienteFalso


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    """Nenhum teste toca em config, tokens ou estado reais."""
    for k, v in (("XDG_CONFIG_HOME", "cfg"), ("XDG_STATE_HOME", "state"), ("XDG_RUNTIME_DIR", "run")):
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


@pytest.fixture
def app(falso, estado, config, armazem, lancados, abertos):
    return OmaSpotifyApp(cliente=falso, demo=True, estado=estado, config=config, armazem=armazem, abertura=False,
                         abridor=abertos.append, lancador=lambda: lancados.append(1) or True, espera_dispositivo=0.05)


async def esperar(pilot, cond, tempo=3.0):
    """Espera uma condição (as chamadas à API rodam em threads)."""
    fim = asyncio.get_event_loop().time() + tempo
    while asyncio.get_event_loop().time() < fim:
        await pilot.pause(0.05)
        if cond():
            return True
    return cond()
