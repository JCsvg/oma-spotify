"""Verificação da configuração de login. Nada autenticado, nada de token."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

from oma_spotify.services.auth import validar_client_id

HOST_SPOTIFY = "https://accounts.spotify.com"


def mascarar(cid: str) -> str:
    """Primeiros 4 e últimos 4 caracteres; o resto nunca sai."""
    cid = (cid or "").strip()
    if not cid:
        return "não definido"
    if len(cid) < 12:
        return f"curto demais ({len(cid)} caracteres)"
    return f"{cid[:4]}...{cid[-4:]} ({len(cid)} caracteres)"


def porta_livre(porta: int) -> bool:
    with socket.socket() as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", porta))
            return True
        except OSError:
            return False


def rede_ok(url: str = HOST_SPOTIFY, timeout: float = 4.0) -> bool:
    """Qualquer resposta HTTP (até 4xx) prova que a conexão existe."""
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=timeout)
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def verificar(client_id: str, porta: int, redirect: str, url_rede: str = HOST_SPOTIFY) -> list[str]:
    _, erro = validar_client_id(client_id)
    return [
        f"Client ID: {mascarar(client_id)}" + (f" - {erro}" if erro else " - formato válido"),
        f"Redirect URI que o app envia: {redirect}",
        f"Porta do callback: {porta}",
        f"Porta {porta} livre neste computador: {'sim' if porta_livre(porta) else 'NÃO (algo já usa essa porta)'}",
        f"Conexão com accounts.spotify.com: {'ok' if rede_ok(url_rede) else 'SEM RESPOSTA (confira a internet)'}",
    ]
