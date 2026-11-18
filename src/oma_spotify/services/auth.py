"""Login OAuth 2.0 com PKCE (sem client secret) e guarda dos tokens.

Os tokens ficam num arquivo 0600 em $XDG_STATE_HOME/oma-spotify. Este módulo
não usa log nem imprime nada com token.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from oma_spotify.services.modelos import ErroSpotify

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
ESCOPOS = (
    "user-read-playback-state user-modify-playback-state user-read-currently-playing "
    "user-read-recently-played user-top-read user-library-read user-library-modify user-follow-read "
    "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"
)


def pasta_estado() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(base) / "oma-spotify"


def redirect_uri(porta: int) -> str:
    return f"http://127.0.0.1:{porta}/callback"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def novo_verifier() -> str:
    return secrets.token_urlsafe(64)[:96]  # 43 a 128 caracteres


def desafio(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode()).digest())


def url_autorizacao(client_id: str, porta: int, challenge: str, state: str, base: str = AUTH_URL) -> str:
    q = {"client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri(porta), "state": state,
         "code_challenge_method": "S256", "code_challenge": challenge, "scope": ESCOPOS}
    return f"{base}?{urllib.parse.urlencode(q)}"


class Armazem:
    """Arquivo de tokens, sempre 0600."""

    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = pasta or pasta_estado()
        self.arquivo = self.pasta / "tokens.json"

    def ler(self) -> dict:
        try:
            d = json.loads(self.arquivo.read_text())
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def gravar(self, d: dict) -> None:
        self.pasta.mkdir(parents=True, exist_ok=True)
        os.chmod(self.pasta, 0o700)
        tmp = self.arquivo.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(d, f)
        os.replace(tmp, self.arquivo)
        os.chmod(self.arquivo, 0o600)

    def apagar(self) -> None:
        try:
            self.arquivo.unlink()
        except OSError:
            pass

    def logado(self) -> bool:
        return bool(self.ler().get("refresh_token"))


def _post_token(url: str, dados: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):
            raise ErroSpotify("O Spotify recusou o login. Confira o Client ID e o Redirect URI no painel e entre de novo.",
                              e.code, sem_login=True) from None
        raise ErroSpotify(f"O Spotify respondeu com erro {e.code} no login.", e.code) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise ErroSpotify("Sem conexão com o Spotify. Confira a internet.") from None


class Sessao:
    """Tokens em uso. token() renova sozinho com o refresh token."""

    def __init__(self, client_id: str, porta: int = 8888, armazem: Armazem | None = None,
                 token_url: str = TOKEN_URL, auth_url: str = AUTH_URL) -> None:
        self.client_id = client_id
        self.porta = porta
        self.armazem = armazem or Armazem()
        self.token_url = token_url
        self.auth_url = auth_url
        self._lock = threading.Lock()

    def _guardar(self, r: dict, antigo: dict | None = None) -> None:
        d = {"access_token": r["access_token"],
             "refresh_token": r.get("refresh_token") or (antigo or {}).get("refresh_token", ""),
             "expira": time.time() + int(r.get("expires_in", 3600))}
        self.armazem.gravar(d)

    def token(self, forcar: bool = False) -> str:
        with self._lock:
            d = self.armazem.ler()
            if not d.get("refresh_token"):
                raise ErroSpotify("Você não está conectado. Entre com o Spotify na tela de configuração.", 401, sem_login=True)
            if forcar or time.time() > float(d.get("expira", 0)) - 30 or not d.get("access_token"):
                r = _post_token(self.token_url, {"grant_type": "refresh_token", "refresh_token": d["refresh_token"],
                                                 "client_id": self.client_id})
                self._guardar(r, d)
                d = self.armazem.ler()
            return d["access_token"]

    def entrar(self, abrir=webbrowser.open, tempo: float = 180.0, ao_url=None) -> None:
        """Fluxo completo: abre o navegador, espera o retorno em 127.0.0.1 e troca o código."""
        verifier, state = novo_verifier(), secrets.token_urlsafe(16)
        url = url_autorizacao(self.client_id, self.porta, desafio(verifier), state, self.auth_url)
        srv = ServidorRetorno(self.porta, state)
        try:
            srv.iniciar()
        except OSError:
            raise ErroSpotify(f"Não consegui abrir a porta {self.porta} neste computador. Troque a porta nas configurações.") from None
        try:
            if ao_url:
                ao_url(url)
            abrir(url)
            codigo = srv.esperar(tempo)
        finally:
            srv.parar()
        self.trocar_codigo(codigo, verifier)

    def trocar_codigo(self, codigo: str, verifier: str) -> None:
        r = _post_token(self.token_url, {"grant_type": "authorization_code", "code": codigo,
                                         "redirect_uri": redirect_uri(self.porta), "client_id": self.client_id,
                                         "code_verifier": verifier})
        self._guardar(r)


PAGINA = ("<!doctype html><meta charset=utf-8><title>oma-spotify</title>"
          "<body style='font-family:sans-serif;text-align:center;margin-top:20vh'><h2>{}</h2>"
          "<p>Pode fechar esta aba e voltar ao terminal.</p></body>")


class ServidorRetorno:
    def __init__(self, porta: int, state: str) -> None:
        self.porta, self.state = porta, state
        self.codigo = ""
        self.erro = ""
        self.fim = threading.Event()
        self.httpd: HTTPServer | None = None

    def iniciar(self) -> None:
        srv = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                u = urllib.parse.urlparse(self.path)
                if u.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    return
                q = urllib.parse.parse_qs(u.query)
                if q.get("state", [""])[0] != srv.state:
                    srv.erro = "Resposta de login inválida (state diferente). Tente entrar de novo."
                    msg = "Login recusado"
                elif "error" in q:
                    srv.erro = "Você não autorizou o acesso no Spotify."
                    msg = "Login cancelado"
                else:
                    srv.codigo = q.get("code", [""])[0]
                    msg = "Pronto, login feito"
                body = PAGINA.format(msg).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                srv.fim.set()

            def log_message(self, *a) -> None:  # sem log: a URL carrega o código
                pass

        self.httpd = HTTPServer(("127.0.0.1", self.porta), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def esperar(self, tempo: float) -> str:
        if not self.fim.wait(tempo):
            raise ErroSpotify("O login demorou demais e foi cancelado. Tente de novo.")
        if self.erro or not self.codigo:
            raise ErroSpotify(self.erro or "O Spotify não devolveu o código de login.")
        return self.codigo

    def parar(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
