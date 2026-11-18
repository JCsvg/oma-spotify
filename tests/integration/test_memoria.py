"""Memória: o app em repouso fica leve e não cresce ao navegar e buscar.

Medição de referência (180x48, --demo, Python 3.13, Textual 8.2): 0.3.0 com 48 a 51 MB em repouso e 95 MB depois de
25 rodadas de navegação e busca; 0.4.0 com 50 MB em repouso e 68 a 69 MB depois de 80 a 160 páginas e 20 a 40 buscas;
0.5.0, com capas de verdade em meio-blocos, 53 a 55 MB em repouso e 80 a 81 MB depois de 80 a 160 páginas e 20 a 40
buscas (a meta era no máximo 15 MB acima da 0.4.0). Os tetos abaixo deixam folga para variação entre máquinas.
"""

import fcntl
import gc
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

import pytest

from tests.conftest import pronto

TETO_REPOUSO_MB = 70
TETO_USO_MB = 95
TETO_CRESCIMENTO_MB = 25

P1 = {"uri": "spotify:playlist:p1", "tipo": "playlist", "nome": "Mesa de sexta", "id": "p1", "meu": True, "sub": "demo"}
CAIS = {"uri": "spotify:artist:r1", "tipo": "artist", "nome": "Cais 7", "id": "r1"}
PAGINAS = [{"t": "inicio"}, {"t": "curtidas"}, {"t": "item", "item": P1}, {"t": "item", "item": CAIS},
           {"t": "busca", "q": "cais", "cat": "tudo"}, {"t": "recentes"}]


def rss_mb(pid: str = "self") -> float:
    for linha in Path(f"/proc/{pid}/status").read_text().splitlines():
        if linha.startswith("VmRSS"):
            return int(linha.split()[1]) / 1024
    return 0.0


async def test_navegar_e_buscar_nao_acumula_widgets_nem_memoria(app):
    async with app.run_test(size=(180, 48)) as pilot:
        await pronto(app, pilot)
        for v in PAGINAS * 2:  # aquece caches e imports preguiçosos
            app.navegar(v)
            await pilot.pause(0.15)
        app.navegar({"t": "inicio"})
        await pilot.pause(0.5)
        gc.collect()
        n_widgets, base = len(list(app.query("*"))), rss_mb()
        for n in range(50):
            app.navegar(PAGINAS[n % len(PAGINAS)])
            await pilot.pause(0.08)
        for n in range(20):
            app._buscar_agora(("cais", "farol", "lua")[n % 3])
            await pilot.pause(0.12)
        app.navegar({"t": "inicio"})
        await pilot.pause(0.8)
        gc.collect()
        assert abs(len(list(app.query("*"))) - n_widgets) <= 5
        assert rss_mb() - base < TETO_CRESCIMENTO_MB
        assert len(app.historico) <= 30 and len(app.pl_cache) <= 24


@pytest.mark.skipif(not Path("/proc/self/status").exists(), reason="precisa de /proc")
def test_rss_do_processo_em_repouso_e_depois_de_usar(tmp_path):
    """Roda `python -m oma_spotify --demo` num pseudo-terminal de 180x48 e lê o VmRSS."""
    env = dict(os.environ, TERM="xterm-256color", PYTHONPATH=str(Path(__file__).parents[2] / "src"))
    for k in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR", "XDG_CACHE_HOME"):
        env[k] = str(tmp_path / k)
        os.makedirs(env[k])
    fd, escravo = pty.openpty()
    fcntl.ioctl(escravo, termios.TIOCSWINSZ, struct.pack("HHHH", 48, 180, 0, 0))
    proc = subprocess.Popen([sys.executable, "-m", "oma_spotify", "--demo"], stdin=escravo, stdout=escravo, stderr=escravo,
                            env=env, start_new_session=True)
    os.close(escravo)
    pid = proc.pid

    def drenar(seg: float) -> None:
        fim = time.time() + seg
        while time.time() < fim:
            if select.select([fd], [], [], 0.05)[0]:
                try:
                    os.read(fd, 65536)
                except OSError:
                    return
    try:
        drenar(6)
        repouso = rss_mb(str(pid))
        for _ in range(10):
            for t in ("1", "2", "3", "0", "/", "\x1b", "c", "a", "i", "s", "\r"):
                os.write(fd, t.encode())
                drenar(0.15)
        drenar(3)
        uso = rss_mb(str(pid))
        print(f"\nRSS: repouso {repouso:.0f} MB, depois de 40 páginas e 10 buscas {uso:.0f} MB")
        assert 0 < repouso < TETO_REPOUSO_MB
        assert uso < TETO_USO_MB
    finally:
        os.write(fd, b"q")
        drenar(1)
        proc.kill()
        proc.wait(5)
        os.close(fd)
