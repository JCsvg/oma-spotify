"""Integração com o plugin Omarchy OmaSpotify (outro autor, MIT), só por fora.

O plugin tem um motor de reprodução local (serviço systemd de usuário `omaspotify.service`) que aparece
para o Spotify como um dispositivo Connect chamado "OmaSpotify". O oma-spotify só:
- confere se a unidade existe e o binário do plugin está instalado (nenhum conteúdo é lido);
- inicia o serviço do próprio usuário, se pedido;
- depois usa a Web API (/me/player/devices, transferência e play) como com qualquer dispositivo.
Credenciais, chaveiro e arquivos do plugin nunca são lidos, copiados ou alterados.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

UNIDADE = "omaspotify.service"
NOME_DISPOSITIVO = "omaspotify"  # comparado em minúsculas, o nome padrão é "OmaSpotify"
DICA_CONFIGURAR = "Abra o OmaSpotify e conclua a autorização de reprodução (Finish playback setup)."


def _rodar(args: list[str], tempo: float = 8.0) -> int:
    try:
        return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=tempo).returncode
    except (OSError, subprocess.SubprocessError):
        return 127


class PluginOmaSpotify:
    def __init__(self, rodar=_rodar, pasta_binario: Path | None = None) -> None:
        self.rodar = rodar
        base = os.environ.get("OMASPOTIFY_RUNTIME_DIR") or str(Path.home() / ".local/lib/omaspotify")
        self.binario = (pasta_binario or Path(base)) / "omaspotify-backend"

    def instalado(self) -> bool:
        """A unidade do usuário existe e o binário foi instalado pelo plugin."""
        return self.binario.exists() and self.rodar(["systemctl", "--user", "cat", UNIDADE]) == 0

    def ativo(self) -> bool:
        return self.rodar(["systemctl", "--user", "is-active", "--quiet", UNIDADE]) == 0

    def iniciar(self) -> bool:
        return self.rodar(["systemctl", "--user", "start", UNIDADE], 20.0) == 0

    @staticmethod
    def eh_dispositivo(d) -> bool:
        return NOME_DISPOSITIVO in (d.nome or "").lower()
