"""Servidor HTTP falso em 127.0.0.1 que imita a API e o endpoint de tokens do Spotify."""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

TOKEN_VALIDO = "acesso-1"


class ServidorFalso:
    def __init__(self) -> None:
        self.pedidos: list[tuple[str, str, dict, bytes]] = []  # metodo, caminho, headers, corpo
        self.forms: list[dict] = []
        self.respostas: dict[tuple[str, str], list] = {}  # (metodo, caminho) -> fila de (status, corpo, headers)
        self.token_atual = TOKEN_VALIDO
        self.validos = {TOKEN_VALIDO}
        self.n_refresh = 0
        outer = self

        class H(BaseHTTPRequestHandler):
            def _resp(self, status: int, corpo, headers: dict | None = None) -> None:
                bruto = b"" if corpo is None else json.dumps(corpo).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(bruto)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(bruto)

            def _tratar(self) -> None:
                n = int(self.headers.get("Content-Length") or 0)
                corpo = self.rfile.read(n) if n else b""
                u = urllib.parse.urlparse(self.path)
                outer.pedidos.append((self.command, u.path + ("?" + u.query if u.query else ""), dict(self.headers), corpo))
                if u.path == "/api/token":
                    f = {k: v[0] for k, v in urllib.parse.parse_qs(corpo.decode()).items()}
                    outer.forms.append(f)
                    if f.get("grant_type") == "refresh_token":
                        if f.get("refresh_token") != "refresh-1":
                            return self._resp(400, {"error": "invalid_grant"})
                        outer.n_refresh += 1
                        novo = f"acesso-r{outer.n_refresh}"
                        outer.validos.add(novo)
                        return self._resp(200, {"access_token": novo, "expires_in": 3600})
                    if f.get("code") == "codigo-bom" and f.get("code_verifier"):
                        return self._resp(200, {"access_token": TOKEN_VALIDO, "refresh_token": "refresh-1", "expires_in": 3600})
                    return self._resp(400, {"error": "invalid_grant"})
                fila = outer.respostas.get((self.command, u.path))
                if fila:
                    r = fila.pop(0) if len(fila) > 1 else fila[0]
                    return self._resp(*r) if len(r) == 3 else self._resp(r[0], r[1])
                auth = self.headers.get("Authorization", "")
                if auth.removeprefix("Bearer ") not in outer.validos:
                    return self._resp(401, {"error": {"status": 401, "message": "token expirado"}})
                q = urllib.parse.parse_qs(u.query)
                if (self.command, u.path) == ("GET", "/v1/me/player"):
                    return self._resp(200, {"is_playing": True, "progress_ms": 1000, "shuffle_state": True, "repeat_state": "track",
                                            "device": {"name": "PC", "volume_percent": 30},
                                            "item": {"uri": "spotify:track:x", "type": "track", "id": "x", "name": "Faixa X",
                                                     "duration_ms": 200000, "artists": [{"name": "Banda Y"}], "album": {"name": "Disco Z"}}})
                if (self.command, u.path) == ("GET", "/v1/me"):
                    return self._resp(200, {"id": "eu"})
                if (self.command, u.path) == ("GET", "/v1/me/playlists"):
                    return self._resp(200, {"items": [{"uri": "spotify:playlist:p1", "type": "playlist", "id": "p1", "name": "Minha",
                                                       "owner": {"id": "eu", "display_name": "eu"}, "items": {"total": 3}},
                                                      {"uri": "spotify:playlist:p2", "type": "playlist", "id": "p2", "name": "Alheia",
                                                       "owner": {"id": "outro"}, "items": {"total": 1}}], "next": None})
                if (self.command, u.path) == ("GET", "/v1/playlists/p1/items"):
                    return self._resp(200, {"items": [{"item": {"uri": "spotify:track:x", "type": "track", "id": "x", "name": "Faixa X",
                                                                "duration_ms": 1, "artists": [], "album": {}}}], "next": None})
                if (self.command, u.path) == ("GET", "/v1/search"):
                    return self._resp(200, {"tracks": {"items": [{"uri": "spotify:track:s", "type": "track", "id": "s", "name": "Achada",
                                                                  "duration_ms": 5, "artists": [{"name": "A"}], "album": {"name": "B"}}]},
                                            "albums": {"items": []}, "artists": {"items": []}, "playlists": {"items": [None]}})
                if (self.command, u.path) == ("GET", "/v1/me/library/contains"):
                    return self._resp(200, [True] * len(q["uris"][0].split(",")))
                if (self.command, u.path) in (("PUT", "/v1/me/library"), ("PUT", "/v1/me/player/play"), ("POST", "/v1/me/playlists")):
                    if u.path.endswith("/playlists"):
                        return self._resp(201, {"uri": "spotify:playlist:novo", "type": "playlist", "id": "novo", "name": "Nova",
                                                "owner": {"id": "eu"}})
                    return self._resp(204, None)
                return self._resp(204, None)

            do_GET = do_PUT = do_POST = do_DELETE = _tratar

            def log_message(self, *a) -> None:
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), H)
        self.porta = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def api(self) -> str:
        return f"http://127.0.0.1:{self.porta}/v1"

    @property
    def token_url(self) -> str:
        return f"http://127.0.0.1:{self.porta}/api/token"

    def parar(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
