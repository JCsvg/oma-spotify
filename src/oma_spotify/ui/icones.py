"""Ícones: Nerd Font, conjunto md (o Omarchy já vem com Nerd Font), ou caracteres simples.

`icones = "simples"` no config.json troca pelos da segunda coluna.
"""

from __future__ import annotations

ICONES: dict[str, tuple[str, str]] = {
    "tocar": ("\U000F040A", "▶"), "pausar": ("\U000F03E4", "‖"),
    "anterior": ("\U000F04AE", "|<"), "proxima": ("\U000F04AD", ">|"),
    "aleatorio": ("\U000F049F", "⇄"), "repetir": ("\U000F0456", "↻"), "repetir1": ("\U000F0458", "↻1"),
    "curtida": ("\U000F02D1", "♥"), "nao_curtida": ("\U000F02D5", "♡"),
    "volume": ("\U000F057E", "vol"), "mudo": ("\U000F0581", "mudo"),
    "buscar": ("\U000F0349", "/"),
    "playlist": ("\U000F0CB8", "≡"), "artist": ("\U000F0803", "@"), "album": ("\U000F0025", "◉"), "show": ("\U000F0994", "◎"),
    "computer": ("\U000F0322", "pc"), "smartphone": ("\U000F011C", "cel"), "speaker": ("\U000F04C3", "som"), "tv": ("\U000F0502", "tv"),
    "nota": ("\U000F0387", "♪"), "a_seguir": ("\U000F0412", "+≡"), "adicionar": ("\U000F0415", "+"),
    "opcoes": ("\U000F01D8", "⋯"), "duracao": ("\U000F0150", "⏱"),
}
# Sem equivalente na tabela do design: caracteres comuns nos dois modos.
FIXOS = {"conta": "◆", "filtro": "⌕", "info": "ⓘ", "aviso": "!", "ok": "✓", "mais": "›", "menu": "˅", "mover": "⇅",
         "remover": "✕", "link": "↗"}

_modo = "nerd"


def definir_modo(modo: str) -> None:
    global _modo
    _modo = "simples" if modo == "simples" else "nerd"


def ic(nome: str) -> str:
    if nome in FIXOS:
        return FIXOS[nome]
    par = ICONES.get(nome)
    if par is None:
        return ""
    return par[1] if _modo == "simples" else par[0]


def de_aparelho(tipo: str) -> str:
    t = (tipo or "").lower()
    return ic("smartphone" if t in ("smartphone", "tablet") else "speaker" if t in ("speaker", "avr", "stb", "audiodongle", "castaudio")
              else "tv" if t in ("tv", "castvideo") else "computer")


# Equalizador: 2 células de braille, um quadro a cada 180 ms. Pausado, fica parado.
EQ = ("⣸⣴", "⣦⣇", "⣴⣸", "⣇⣦")
EQ_PARADO = "⣀⣀"
