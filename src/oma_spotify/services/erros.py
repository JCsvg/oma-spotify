"""Tradução de erros HTTP da API em mensagens claras."""

from __future__ import annotations

from oma_spotify.services.modelos import ErroSpotify


def de_status(status: int, razao: str = "") -> ErroSpotify:
    r = (razao or "").upper()
    if status == 401:
        return ErroSpotify("A sessão expirou. Entre de novo nas configurações.", 401, sem_login=True)
    if status == 403:
        if "PREMIUM" in r:
            return ErroSpotify("Essa ação exige Spotify Premium.", 403)
        return ErroSpotify("O Spotify negou o acesso. Pode ser permissão a mais que o app não tem, "
                           "sua conta fora da lista do app (modo de desenvolvimento) ou o dono do app sem Premium.", 403)
    if status == 404:
        if "NO_ACTIVE_DEVICE" in r:
            return ErroSpotify("Nenhum dispositivo do Spotify está ativo.", 404, sem_dispositivo=True)
        return ErroSpotify("O Spotify não encontrou isso (404). O recurso pode ter sido removido da API.", 404)
    if status == 429:
        return ErroSpotify("Muitas requisições ao Spotify. Espere um instante.", 429)
    if status >= 500:
        return ErroSpotify(f"O Spotify está com problema agora ({status}). Tente de novo daqui a pouco.", status)
    return ErroSpotify(f"O Spotify respondeu com erro {status}.", status)
