"""Login OAuth 2.0 com PKCE (sem client secret) e guarda dos tokens.

Os tokens ficam num arquivo 0600 em $XDG_STATE_HOME/oma-spotify. Este módulo
não usa log nem imprime nada com token.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
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


def _erro_token(status: int, corpo: bytes, dados: dict) -> ErroSpotify:
    """Mensagem específica conforme o `error` que o Spotify devolve (nunca inclui token)."""
    try:
        tipo = str(json.loads(corpo).get("error", ""))
    except (ValueError, AttributeError):
        tipo = ""
    renovando = dados.get("grant_type") == "refresh_token"
    redirect = dados.get("redirect_uri", "")
    if tipo == "invalid_client":
        msg = ("O Spotify não reconheceu o Client ID (invalid_client). Copie de novo em Settings do app no painel, "
               "são 32 caracteres, sem espaços.")
    elif tipo == "invalid_grant":
        msg = ("A sessão foi revogada ou expirou (invalid_grant). Entre de novo." if renovando else
               "O código de login expirou, já foi usado, ou o Redirect URI da troca não bate com o do pedido "
               "(invalid_grant). Entre de novo.")
    elif tipo == "invalid_request":
        msg = "O Spotify recusou o pedido de login (invalid_request)."
        if redirect:
            msg += f" Confira se o Redirect URI no painel é exatamente {redirect}"
    elif status in (400, 401):
        msg = f"O Spotify recusou o login ({tipo or status})."
    else:
        return ErroSpotify(f"O Spotify respondeu com erro {status} no login.", status)
    return ErroSpotify(msg, status, sem_login=True)


def _post_token(url: str, dados: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(dados).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            corpo = e.read()
        except Exception:
            corpo = b""
        raise _erro_token(e.code, corpo, dados) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise ErroSpotify("Sem conexão com o Spotify. Confira a internet.") from None


_HEX32 = re.compile(r"[0-9a-fA-F]{32}")


def validar_client_id(bruto: str) -> tuple[str, str]:
    """Devolve (client_id limpo, erro). Erro vazio quando o formato é válido (32 hexadecimais)."""
    cid = (bruto or "").strip()
    if not cid:
        return cid, "Cole o Client ID do seu app (passo 3)."
    if re.search(r"\s", cid):
        return cid, "O Client ID tem espaço no meio. Copie de novo, sem espaços."
    if len(cid) != 32:
        return cid, f"O Client ID tem {len(cid)} caracteres e precisa ter 32. Copie inteiro, de Settings do app."
    if not _HEX32.fullmatch(cid):
        return cid, "O Client ID só tem números e letras de a a f. Confira se copiou o certo."
    return cid, ""


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

    def iniciar_login(self, abrir=webbrowser.open, tempo: float = 180.0) -> "Login":
        """Sobe o servidor de retorno, abre o navegador e devolve o login em andamento."""
        verifier, state = novo_verifier(), secrets.token_urlsafe(16)
        url = url_autorizacao(self.client_id, self.porta, desafio(verifier), state, self.auth_url)
        srv = ServidorRetorno(self.porta, state)
        try:
            srv.iniciar()
        except OSError:
            raise ErroSpotify(f"A porta {self.porta} está ocupada neste computador. Feche o que a usa "
                              "ou troque a porta nas configurações.") from None
        login = Login(self, srv, verifier, url, tempo)
        login.abrir(abrir)
        return login

    def entrar(self, abrir=webbrowser.open, tempo: float = 180.0, ao_url=None) -> None:
        """Fluxo completo e bloqueante (sem tela de espera)."""
        login = self.iniciar_login(abrir, tempo)
        if ao_url:
            ao_url(login.url)
        login.concluir()

    def trocar_codigo(self, codigo: str, verifier: str) -> None:
        r = _post_token(self.token_url, {"grant_type": "authorization_code", "code": codigo,
                                         "redirect_uri": redirect_uri(self.porta), "client_id": self.client_id,
                                         "code_verifier": verifier})
        self._guardar(r)


class Login:
    """Um login em andamento: dá para reabrir o navegador, ver o link e cancelar."""

    def __init__(self, sessao: Sessao, srv: "ServidorRetorno", verifier: str, url: str, tempo: float) -> None:
        self.sessao, self.srv, self.verifier, self.url, self.tempo = sessao, srv, verifier, url, tempo
        self.inicio = time.monotonic()

    def restante(self) -> float:
        return max(0.0, self.tempo - (time.monotonic() - self.inicio))

    def abrir(self, abrir=webbrowser.open) -> None:
        try:
            abrir(self.url)
        except Exception:
            pass

    def concluir(self) -> None:
        try:
            codigo = self.srv.esperar(self.restante())
        finally:
            self.srv.parar()
        self.sessao.trocar_codigo(codigo, self.verifier)

    def cancelar(self) -> None:
        """Fecha o servidor da porta na hora."""
        self.srv.cancelar()


PAGINA = ("<!doctype html><meta charset=utf-8><title>oma-spotify</title>"
          "<body style='font-family:sans-serif;text-align:center;margin-top:20vh'><h2>{}</h2>"
          "<p>Pode fechar esta aba e voltar ao terminal.</p></body>")


class ServidorRetorno:
    def __init__(self, porta: int, state: str) -> None:
        self.porta, self.state = porta, state
        self.codigo = ""
        self.erro = ""
        self.fim = threading.Event()
        self.cancelado = False
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
                    err = q["error"][0]
                    srv.erro = ("Você não autorizou o acesso no Spotify." if err == "access_denied"
                                else f"O Spotify devolveu o erro {err[:40]} no login.")
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
        ok = self.fim.wait(tempo)
        if self.cancelado:
            raise ErroSpotify("Espera cancelada. A porta foi liberada.")
        if not ok:
            raise ErroSpotify("O login demorou demais e foi cancelado. Tente de novo.")
        if self.erro or not self.codigo:
            raise ErroSpotify(self.erro or "O Spotify não devolveu o código de login.")
        return self.codigo

    def cancelar(self) -> None:
        self.cancelado = True
        self.fim.set()
        self.parar()

    def parar(self) -> None:
        h, self.httpd = self.httpd, None
        if h:
            h.shutdown()
            h.server_close()
