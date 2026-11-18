"""Cliente falso, com dados fictícios, para --demo e para os testes de interface.

Artistas, faixas, playlists e podcasts são inventados. "Cidade Acesa", da Cais 7, e a
letra dela vêm do mockup do design, que também é inventado.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from oma_spotify.services.modelos import Dispositivo, ErroSpotify, Item, Player

ARTISTAS = [Item(f"spotify:artist:r{n}", "artist", nome, id=f"r{n}") for n, nome in enumerate(
    ("Cais 7", "Orquestra Exemplo", "Coro Imaginário", "Trio Domínio Público", "Banda Farol", "Maré Alta", "Os Vagalumes",
     "Lua de Papel"), 1)]
_ART = {a.nome: a for a in ARTISTAS}

# id, nome, artista, ano, grupo
_ALBUNS = [("a1", "Faróis", "Cais 7", "2025", "album"), ("a2", "Sinfonias de Mentira", "Orquestra Exemplo", "2011", "album"),
           ("a3", "Noites Sem Estrela", "Coro Imaginário", "2016", "album"), ("a4", "Cantigas Antigas", "Trio Domínio Público", "2010", "album"),
           ("a5", "Luz de Garagem", "Banda Farol", "2019", "album"), ("a6", "Ressaca", "Maré Alta", "2024", "single"),
           ("a7", "Vagalume Elétrico", "Os Vagalumes", "2012", "album"), ("a8", "Papel Machê", "Lua de Papel", "2021", "album"),
           ("a9", "Cais ao Vivo", "Cais 7", "2023", "album"), ("a10", "Farol Baixo", "Cais 7", "2024", "single"),
           ("a11", "Coletânea do Porto", "Vários artistas", "2015", "appears_on")]
ALBUNS = [Item(f"spotify:album:{i}", "album", n, a, id=i, ano=y, grupo=g) for i, n, a, y, g in _ALBUNS]
_ALB = {a.id: a for a in ALBUNS}

# nome, álbum, duração em segundos
_FAIXAS = [("Cidade Acesa", "a1", 211), ("Maré de Neon", "a1", 233), ("Farol Baixo", "a1", 253), ("Porto Inteiro", "a1", 178),
           ("Última Barca", "a1", 187), ("Ode à Alegria (exemplo)", "a2", 240), ("Canção do Vale", "a2", 205),
           ("Valsa da Lua de Papel", "a3", 187), ("Marcha das Formigas", "a3", 153), ("Greensleeves (domínio público)", "a4", 172),
           ("Barcarola do Rio Seco", "a4", 221), ("Garagem", "a5", 292), ("Amplificador", "a5", 178), ("Fusível", "a5", 195),
           ("Ressaca", "a6", 169), ("Pisca-Pisca", "a7", 272), ("Curto-Circuito", "a7", 208), ("Faísca", "a7", 201),
           ("Origami", "a8", 200), ("Dobradura", "a8", 230), ("Recorte", "a8", 312), ("Cola Branca", "a8", 214),
           ("Tesoura", "a8", 202), ("Colagem", "a8", 187)]
FAIXAS = [Item(f"spotify:track:t{n}", "track", nome, _ALB[a].sub, _ALB[a].nome, s * 1000, f"t{n}", ano=_ALB[a].ano)
          for n, (nome, a, s) in enumerate(_FAIXAS, 1)]

SHOWS = [Item("spotify:show:s1", "show", "Conversa de Exemplo", "Estúdio Fictício", id="s1", desc="Papo semanal inventado."),
         Item("spotify:show:s2", "show", "Rádio Fictícia", "Coletivo Imaginário", id="s2", desc="Notícias que não aconteceram."),
         Item("spotify:show:s3", "show", "Café com Dados", "Laboratório Exemplo", id="s3", desc="Números e café.")]

LETRA_CIDADE_ACESA = """[00:00.00]
[01:20.00]a cidade acende devagar
[01:27.00]cada janela é um rádio ligado
[01:34.00]e eu perdi a hora de voltar
[01:41.00]mas a noite ainda tá do meu lado
[01:48.00]se o farol piscar, eu sei
[01:55.00]que alguém lá longe também não dormiu
[02:02.00]a gente se encontra no refrão
[02:09.00]no volume que ninguém ouviu
[02:30.00]a cidade acende devagar
[02:37.00]cada janela é um rádio ligado
[02:44.00]e eu perdi a hora de voltar
[02:51.00]mas a noite ainda tá do meu lado
"""
LETRAS = {"spotify:track:t1": LETRA_CIDADE_ACESA}
FIXADOS = ["spotify:playlist:p1", "spotify:playlist:p2", "spotify:playlist:p3", "spotify:playlist:p4", "spotify:playlist:p5",
           "spotify:playlist:p6"]


def _t(n: int) -> str:
    return f"t{n}"


class ClienteFalso:
    def __init__(self) -> None:
        self.faixas = list(FAIXAS)
        self.tocando = True
        self.pos = 102_000
        self.marca = time.monotonic()
        self.aleat = False
        self.rep = "off"
        self.vol = 62
        self.favoritas = {f"spotify:track:t{n}" for n in (1, 2, 3, 6, 12, 16, 19, 22)}
        self.seguidos = {"spotify:artist:r1", "spotify:artist:r5", "spotify:artist:r8", "spotify:album:a1", "spotify:album:a2",
                         "spotify:album:a5"}
        self.fila_uris: list[str] = []
        # id: (nome, faixas, minha, dono, descrição)
        self.playlists_ = {
            "p1": ("Mesa de sexta", [_t(n) for n in (12, 13, 14, 1, 2, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 3, 4, 5, 6, 7, 8, 9, 10, 11)],
                   True, "demo", "trilha das sessões de RPG de sexta"),
            "p2": ("Para estudar (exemplo)", [_t(n) for n in (6, 7, 10, 11, 8, 9)], True, "demo", "sem letra, de preferência"),
            "p3": ("Madrugada tranquila", [_t(n) for n in (8, 1, 11, 19, 20)], True, "demo", ""),
            "p4": ("Estrada", [_t(n) for n in (12, 16, 2, 3, 17, 18, 13, 15)], True, "demo", "para a BR-369"),
            "p5": ("Ordem de outra pessoa", [_t(n) for n in (1, 2)], False, "Júlia", "playlist de uma amiga"),
            "p6": ("Viagem longa", [_t(n) for n in (19, 20, 21, 22, 23, 24, 1, 4)], True, "demo", ""),
        }
        self.contexto = "spotify:playlist:p1"
        self.idx = 3  # Cidade Acesa, a 4ª da Mesa de sexta
        self.devs = [Dispositivo("d1", "OmaSpotify", "Computer", True, 62), Dispositivo("d2", "celular", "Smartphone", False, 40),
                     Dispositivo("d3", "sala", "Speaker", False, 80), Dispositivo("d4", "tv do quarto", "TV", False, None)]
        self.sem_dispositivo = False
        self.chamadas: list[tuple] = []
        self._ids = itertools.count(7)

    # ------------------------------------------------------------ ajuda
    def _f(self, tid: str) -> Item:
        return next(f for f in self.faixas if f.id == tid)

    def _ctx(self) -> list[str]:
        """Faixas do contexto atual (ids)."""
        tipo, _, cid = self.contexto.rpartition(":")
        if tipo.endswith("playlist") and cid in self.playlists_:
            return list(self.playlists_[cid][1])
        if tipo.endswith("album"):
            return [f.id for f in self.faixas_do_album(cid)]
        return [f.id for f in self.faixas]

    def _atual(self) -> Item:
        ctx = self._ctx()
        return self._f(ctx[self.idx % len(ctx)]) if ctx else self.faixas[0]

    def _atualizar(self) -> None:
        agora = time.monotonic()
        if self.tocando:
            self.pos += int((agora - self.marca) * 1000)
        self.marca = agora
        while self.pos >= self._atual().dur_ms:
            self.pos -= self._atual().dur_ms
            self._avancar()

    def _avancar(self) -> None:
        if self.fila_uris:
            uri = self.fila_uris.pop(0)
            ctx = self._ctx()
            tid = uri.split(":")[-1]
            if tid in ctx:
                self.idx = ctx.index(tid)
                return
        self.idx = (self.idx + 1) % max(1, len(self._ctx()))

    def _exigir(self) -> None:
        if self.sem_dispositivo:
            raise ErroSpotify("Nenhum dispositivo do Spotify está ativo.", 404, sem_dispositivo=True)

    # ------------------------------------------------------------ player
    def player(self) -> Player | None:
        if self.sem_dispositivo:
            return None
        self._atualizar()
        d = next((x for x in self.devs if x.ativo), None)
        return Player(self._atual(), self.pos, self.tocando, self.aleat, self.rep, self.vol, d.nome if d else "",
                      contexto=self.contexto)

    def tocar(self, contexto=None, uris=None, desde=None, device_id=None) -> None:
        self._exigir()
        self.chamadas.append(("tocar", contexto, tuple(uris or ()), desde))
        if contexto and contexto.split(":")[1] in ("playlist", "album"):
            self.contexto = contexto
        elif uris:
            self.contexto = ""
        alvo = desde or (uris[0] if uris else None)
        ctx = self._ctx()
        self.idx = 0
        if alvo and alvo.split(":")[-1] in ctx:
            self.idx = ctx.index(alvo.split(":")[-1])
        self.pos, self.marca, self.tocando = 0, time.monotonic(), True

    def retomar(self) -> None:
        self._exigir()
        self._atualizar()
        self.tocando = True

    def pausar(self) -> None:
        self._exigir()
        self._atualizar()
        self.tocando = False

    def proxima(self) -> None:
        self._exigir()
        self.chamadas.append(("proxima",))
        self._avancar()
        self.pos, self.marca = 0, time.monotonic()

    def anterior(self) -> None:
        self._exigir()
        self.idx, self.pos, self.marca = (self.idx - 1) % max(1, len(self._ctx())), 0, time.monotonic()

    def buscar_posicao(self, ms: int) -> None:
        self._exigir()
        self._atualizar()
        self.pos = max(0, ms)
        self.chamadas.append(("seek", ms))

    def volume(self, pct: int, device_id: str | None = None) -> None:
        self._exigir()
        pct = max(0, min(100, pct))
        alvo = next((d for d in self.devs if d.id == device_id), None) if device_id else None
        if alvo is not None and not alvo.ativo:
            alvo.volume = pct
        else:
            self.vol = pct
            for d in self.devs:
                if d.ativo:
                    d.volume = pct
        self.chamadas.append(("volume", pct, device_id))

    def aleatorio(self, ligado: bool) -> None:
        self._exigir()
        self.aleat = ligado

    def repetir(self, modo: str) -> None:
        self._exigir()
        self.rep = modo

    def fila(self) -> list[Item]:
        """Como a API: primeiro o que foi posto na fila, depois o resto do contexto."""
        ctx = self._ctx()
        resto = [self._f(ctx[(self.idx + n) % len(ctx)]) for n in range(1, min(len(ctx), 8))] if ctx else []
        return [self._f(u.split(":")[-1]) for u in self.fila_uris] + resto

    def enfileirar(self, uri: str) -> None:
        self._exigir()
        self.fila_uris.append(uri)
        self.chamadas.append(("enfileirar", uri))

    def dispositivos(self) -> list[Dispositivo]:
        return [Dispositivo(d.id, d.nome, d.tipo, d.ativo, self.vol if d.ativo else d.volume) for d in self.devs]

    def transferir(self, device_id: str, tocar: bool = True) -> None:
        for d in self.devs:
            d.ativo = d.id == device_id
        self.sem_dispositivo = False
        self.chamadas.append(("transferir", device_id))

    # ------------------------------------------------------------ biblioteca
    def nome_usuario(self) -> str:
        return "demo"

    def playlists(self) -> list[Item]:
        return [Item(f"spotify:playlist:{k}", "playlist", n, dono, f"{len(t)} faixas", id=k, meu=m, desc=d)
                for k, (n, t, m, dono, d) in self.playlists_.items()]

    def itens_playlist(self, pid: str) -> list[Item]:
        n, t, meu, *_ = self.playlists_[pid]
        if not meu:
            raise ErroSpotify("O Spotify negou o acesso.", 403)
        return [self._f(x) for x in t]

    def criar_playlist(self, nome: str) -> Item:
        k = f"p{next(self._ids)}"
        self.playlists_[k] = (nome, [], True, "demo", "")
        return Item(f"spotify:playlist:{k}", "playlist", nome, "demo", "0 faixas", id=k, meu=True)

    def adicionar_a_playlist(self, pid: str, uri: str) -> None:
        self.playlists_[pid][1].append(uri.split(":")[-1])
        self.chamadas.append(("adicionar", pid, uri))

    def remover_da_playlist(self, pid: str, uri: str) -> None:
        t = self.playlists_[pid][1]
        tid = uri.split(":")[-1]
        t[:] = [x for x in t if x != tid]
        self.chamadas.append(("remover", pid, uri))

    def inserir_na_playlist(self, pid: str, uris: list[str], posicao: int) -> None:
        t = self.playlists_[pid][1]
        t[posicao:posicao] = [u.split(":")[-1] for u in uris]
        self.chamadas.append(("inserir", pid, tuple(uris), posicao))

    def mover_na_playlist(self, pid: str, inicio: int, antes: int, n: int = 1) -> None:
        t = self.playlists_[pid][1]
        bloco = t[inicio:inicio + n]
        del t[inicio:inicio + n]
        destino = antes if antes <= inicio else antes - n
        t[destino:destino] = bloco
        self.chamadas.append(("mover", pid, inicio, antes, n))

    def curtidas(self) -> list[Item]:
        return [f for f in self.faixas if f.uri in self.favoritas]

    def albuns_salvos(self) -> list[Item]:
        return [a for a in ALBUNS if a.uri in self.seguidos]

    def artistas_seguidos(self) -> list[Item]:
        return [a for a in ARTISTAS if a.uri in self.seguidos]

    def podcasts(self) -> list[Item]:
        return list(SHOWS)

    def faixas_do_album(self, aid: str, nome: str = "") -> list[Item]:
        alb = _ALB.get(aid)
        return [f for f in self.faixas if alb and f.extra == alb.nome]

    def episodios_do_show(self, sid: str) -> list[Item]:
        show = next((s for s in SHOWS if s.id == sid), SHOWS[0])
        return [Item(f"spotify:episode:{sid}e{n}", "episode", f"Episódio {n} (exemplo)", show.nome, dur_ms=d * 60_000,
                     id=f"{sid}e{n}", ano=f"2026-11-{18 - n * 2:02d}") for n, d in ((1, 42), (2, 38), (3, 51))]

    def albuns_do_artista(self, aid: str) -> list[Item]:
        nome = next(a.nome for a in ARTISTAS if a.id == aid)
        proprios = [a for a in ALBUNS if a.sub == nome]
        return proprios + ([_ALB["a11"]] if nome == "Cais 7" else [])

    def curtido(self, uris: list[str]) -> list[bool]:
        return [u in self.favoritas or u in self.seguidos for u in uris]

    def curtir(self, uri: str) -> None:
        (self.favoritas if ":track:" in uri or ":episode:" in uri else self.seguidos).add(uri)

    def descurtir(self, uri: str) -> None:
        self.favoritas.discard(uri)
        self.seguidos.discard(uri)

    def buscar(self, q: str, tipos=("track", "album", "artist", "playlist", "show"), offset: int = 0,
               limite: int = 10) -> dict[str, list[Item]]:
        q = q.strip()
        self.chamadas.append(("buscar", q, tuple(tipos), offset))
        if q.lower().startswith('artist:"'):
            nome = q[8:].rstrip('"').lower()
            achados = {"track": [f for f in self.faixas if nome in f.sub.lower()]}
        else:
            q = q.lower()
            achados = {"track": [f for f in self.faixas if q in f.nome.lower() or q in f.sub.lower()],
                       "album": [a for a in ALBUNS if q in a.nome.lower() or q in a.sub.lower()],
                       "artist": [a for a in ARTISTAS if q in a.nome.lower()],
                       "playlist": [p for p in self.playlists() if q in p.nome.lower()],
                       "show": [p for p in SHOWS if q in p.nome.lower()]}
        return {t: achados.get(t, [])[offset:offset + min(10, limite)] for t in tipos}

    def recentes(self) -> list[Item]:
        agora = datetime.now(timezone.utc)
        saida = []
        for tid, minutos in ((13, 6), (16, 9), (12, 14), (2, 200), (3, 1500), (21, 1600), (8, 1700)):
            saida.append(replace(self._f(_t(tid)), quando=(agora - timedelta(minutes=minutos)).isoformat()))
        return saida

    def mais_ouvidos(self, tipo: str = "tracks", periodo: str = "medium_term") -> list[Item]:
        if tipo == "tracks":
            return self.faixas[:10]
        return [_ART[n] for n in ("Cais 7", "Banda Farol", "Os Vagalumes", "Lua de Papel", "Coro Imaginário")]
