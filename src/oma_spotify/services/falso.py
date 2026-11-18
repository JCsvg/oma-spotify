"""Cliente falso, com dados fictícios, para --demo e para os testes de interface."""

from __future__ import annotations

import itertools
import time

from oma_spotify.services.modelos import Dispositivo, ErroSpotify, Item, Player

A1, A2, A3 = "Orquestra Exemplo", "Coro Imaginário", "Trio Domínio Público"
FAIXAS = [
    Item("spotify:track:t1", "track", "Ode à Alegria (exemplo)", A1, "Sinfonias de Mentira", 240_000, "t1"),
    Item("spotify:track:t2", "track", "Canção do Vale", A1, "Sinfonias de Mentira", 205_000, "t2"),
    Item("spotify:track:t3", "track", "Valsa da Lua de Papel", A2, "Noites Sem Estrela", 187_000, "t3"),
    Item("spotify:track:t4", "track", "Greensleeves (domínio público)", A3, "Cantigas Antigas", 172_000, "t4"),
    Item("spotify:track:t5", "track", "Barcarola do Rio Seco", A3, "Cantigas Antigas", 221_000, "t5"),
    Item("spotify:track:t6", "track", "Marcha das Formigas", A2, "Noites Sem Estrela", 153_000, "t6"),
]
ALBUNS = [Item("spotify:album:a1", "album", "Sinfonias de Mentira", A1, "2 faixas", id="a1"),
          Item("spotify:album:a2", "album", "Noites Sem Estrela", A2, "2 faixas", id="a2"),
          Item("spotify:album:a3", "album", "Cantigas Antigas", A3, "2 faixas", id="a3")]
ARTISTAS = [Item("spotify:artist:r1", "artist", A1, id="r1"), Item("spotify:artist:r2", "artist", A2, id="r2"),
            Item("spotify:artist:r3", "artist", A3, id="r3")]


class ClienteFalso:
    def __init__(self) -> None:
        self.faixas = list(FAIXAS)
        self.idx = 0
        self.tocando = True
        self.pos = 61_000
        self.marca = time.monotonic()
        self.aleat = False
        self.rep = "off"
        self.vol = 55
        self.favoritas = {"spotify:track:t1", "spotify:track:t4"}
        self.fila_uris: list[str] = ["spotify:track:t3", "spotify:track:t5"]
        self.playlists_ = {"p1": ("Para estudar (exemplo)", ["t1", "t2", "t4"], True),
                           "p2": ("Madrugada tranquila", ["t3", "t5", "t6"], True),
                           "p3": ("Salva de outra pessoa", ["t6", "t2"], False)}
        self.devs = [Dispositivo("d1", "Notebook (exemplo)", "Computer", True, 55),
                     Dispositivo("d2", "Celular (exemplo)", "Smartphone", False, 40)]
        self.sem_dispositivo = False
        self.chamadas: list[tuple] = []
        self._ids = itertools.count(4)

    def _t(self, tid: str) -> Item:
        return next(f for f in self.faixas if f.id == tid)

    def _atualizar(self) -> None:
        agora = time.monotonic()
        if self.tocando:
            self.pos += int((agora - self.marca) * 1000)
        self.marca = agora
        while self.pos >= self.faixas[self.idx].dur_ms:
            self.pos -= self.faixas[self.idx].dur_ms
            self.idx = (self.idx + 1) % len(self.faixas)

    def _exigir(self) -> None:
        if self.sem_dispositivo:
            raise ErroSpotify("Nenhum dispositivo do Spotify está ativo.", 404, sem_dispositivo=True)

    # player
    def player(self) -> Player | None:
        if self.sem_dispositivo:
            return None
        self._atualizar()
        d = next((x for x in self.devs if x.ativo), None)
        return Player(self.faixas[self.idx], self.pos, self.tocando, self.aleat, self.rep, self.vol, d.nome if d else "")

    def tocar(self, contexto=None, uris=None, desde=None, device_id=None) -> None:
        self._exigir()
        self.chamadas.append(("tocar", contexto, tuple(uris or ()), desde))
        alvo = desde or (uris[0] if uris else None)
        for n, f in enumerate(self.faixas):
            if f.uri == alvo:
                self.idx = n
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
        self.idx, self.pos, self.marca = (self.idx + 1) % len(self.faixas), 0, time.monotonic()

    def anterior(self) -> None:
        self._exigir()
        self.idx, self.pos, self.marca = (self.idx - 1) % len(self.faixas), 0, time.monotonic()

    def buscar_posicao(self, ms: int) -> None:
        self._exigir()
        self._atualizar()
        self.pos = max(0, ms)
        self.chamadas.append(("seek", ms))

    def volume(self, pct: int) -> None:
        self._exigir()
        self.vol = max(0, min(100, pct))

    def aleatorio(self, ligado: bool) -> None:
        self._exigir()
        self.aleat = ligado

    def repetir(self, modo: str) -> None:
        self._exigir()
        self.rep = modo

    def fila(self) -> list[Item]:
        return [self._t(u.split(":")[-1]) for u in self.fila_uris]

    def enfileirar(self, uri: str) -> None:
        self._exigir()
        self.fila_uris.append(uri)

    def dispositivos(self) -> list[Dispositivo]:
        return list(self.devs)

    def transferir(self, device_id: str, tocar: bool = True) -> None:
        for d in self.devs:
            d.ativo = d.id == device_id
        self.sem_dispositivo = False
        self.chamadas.append(("transferir", device_id))

    # biblioteca
    def playlists(self) -> list[Item]:
        return [Item(f"spotify:playlist:{k}", "playlist", n, "você" if m else "outra pessoa", f"{len(t)} faixas", id=k, meu=m)
                for k, (n, t, m) in self.playlists_.items()]

    def itens_playlist(self, pid: str) -> list[Item]:
        return [self._t(t) for t in self.playlists_[pid][1]]

    def criar_playlist(self, nome: str) -> Item:
        k = f"p{next(self._ids)}"
        self.playlists_[k] = (nome, [], True)
        return Item(f"spotify:playlist:{k}", "playlist", nome, "você", "0 faixas", id=k, meu=True)

    def adicionar_a_playlist(self, pid: str, uri: str) -> None:
        self.playlists_[pid][1].append(uri.split(":")[-1])

    def remover_da_playlist(self, pid: str, uri: str) -> None:
        self.playlists_[pid][1].remove(uri.split(":")[-1])

    def curtidas(self) -> list[Item]:
        return [f for f in self.faixas if f.uri in self.favoritas]

    def albuns_salvos(self) -> list[Item]:
        return ALBUNS[:2]

    def artistas_seguidos(self) -> list[Item]:
        return ARTISTAS[:2]

    def podcasts(self) -> list[Item]:
        return [Item("spotify:show:s1", "show", "Conversa de Exemplo", "Estúdio Fictício", id="s1")]

    def faixas_do_album(self, aid: str, nome: str = "") -> list[Item]:
        return [f for f in self.faixas if f.extra == next(a.nome for a in ALBUNS if a.id == aid)]

    def episodios_do_show(self, sid: str) -> list[Item]:
        return [Item("spotify:episode:e1", "episode", "Episódio 1 (exemplo)", "Conversa de Exemplo", dur_ms=1_800_000, id="e1"),
                Item("spotify:episode:e2", "episode", "Episódio 2 (exemplo)", "Conversa de Exemplo", dur_ms=1_500_000, id="e2")]

    def albuns_do_artista(self, aid: str) -> list[Item]:
        nome = next(a.nome for a in ARTISTAS if a.id == aid)
        return [a for a in ALBUNS if a.sub == nome]

    def curtido(self, uris: list[str]) -> list[bool]:
        return [u in self.favoritas for u in uris]

    def curtir(self, uri: str) -> None:
        self.favoritas.add(uri)

    def descurtir(self, uri: str) -> None:
        self.favoritas.discard(uri)

    def buscar(self, q: str) -> dict[str, list[Item]]:
        q = q.lower()
        return {"track": [f for f in self.faixas if q in f.nome.lower() or q in f.sub.lower()],
                "album": [a for a in ALBUNS if q in a.nome.lower() or q in a.sub.lower()],
                "artist": [a for a in ARTISTAS if q in a.nome.lower()],
                "playlist": [p for p in self.playlists() if q in p.nome.lower()],
                "show": [p for p in self.podcasts() if q in p.nome.lower()]}

    def recentes(self) -> list[Item]:
        return list(reversed(self.faixas[:5]))

    def mais_ouvidos(self, tipo: str = "tracks", periodo: str = "medium_term") -> list[Item]:
        return self.faixas[:4] if tipo == "tracks" else ARTISTAS
