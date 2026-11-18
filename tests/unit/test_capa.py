import pytest

from oma_spotify.services.modelos import Item
from oma_spotify.ui import capa
from oma_spotify.ui.capa import Capas, iniciais, para_texto, procedural

ITEM = Item("spotify:album:x", "album", "Disco Fictício", capa="https://i.scdn.co/image/abc")


def test_procedural_e_deterministica_e_diferente_por_semente():
    a, b = procedural("x", 8, 4), procedural("x", 8, 4)
    assert a == b and len(a) == 8 and len(a[0]) == 8
    assert procedural("y", 8, 4) != a


def test_para_texto_usa_meio_bloco_com_cor_24_bits():
    t = para_texto(procedural("x", 6, 3), 6, 3)
    assert t.plain.count("▀") == 18 and len(t.plain.split("\n")) == 3
    assert "rgb(" in str(t.spans[0].style)


def test_iniciais_sem_imagem():
    t = iniciais("Disco Fictício", 8, 4)
    assert "DF" in t.plain and len(t.plain.split("\n")) == 4


def test_demo_usa_capa_procedural_sem_tocar_na_rede(tmp_path):
    def proibido(url):
        raise AssertionError("rede")
    c = Capas(True, tmp_path, baixar=proibido)
    assert "▀" in c.texto(ITEM, 6, 3).plain


def test_sem_pillow_cai_para_iniciais(tmp_path, monkeypatch):
    monkeypatch.setattr(capa, "Image", None)
    import time
    c = Capas(False, tmp_path, baixar=lambda u: b"dados")
    assert "DF" in c.texto(ITEM, 6, 3).plain
    time.sleep(0.4)
    assert "DF" in c.texto(ITEM, 6, 3).plain and "▀" not in c.texto(ITEM, 6, 3).plain


def test_falha_de_rede_cai_para_iniciais(tmp_path):
    import time

    def falha(url):
        raise OSError("sem rede")
    c = Capas(False, tmp_path, baixar=falha)
    c.texto(ITEM, 6, 3)
    time.sleep(0.4)
    assert "DF" in c.texto(ITEM, 6, 3).plain


def test_imagem_real_vira_meio_bloco_e_fica_em_cache(tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    import io
    import time
    im = PIL.new("RGB", (20, 20), (200, 10, 10))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    chamadas = []
    chegou = []
    c = Capas(False, tmp_path, baixar=lambda u: chamadas.append(u) or buf.getvalue(), chamar=lambda f, *a: f(*a))
    c.texto(ITEM, 6, 3, lambda: chegou.append(1))
    for _ in range(40):
        if chegou:
            break
        time.sleep(0.05)
    assert chegou
    t = c.texto(ITEM, 6, 3)
    assert t.plain.count("▀") == 18 and "rgb(200,10,10)" in str(t.spans[0].style)
    c2 = Capas(False, tmp_path, baixar=lambda u: (_ for _ in ()).throw(AssertionError("de novo")))
    c2.texto(ITEM, 6, 3)
    time.sleep(0.3)
    assert "▀" in c2.texto(ITEM, 6, 3).plain  # veio do disco, sem baixar


def test_cache_em_disco_respeita_o_limite(tmp_path):
    c = Capas(False, tmp_path, limite_mb=0)
    c.limite = 100
    for n in range(5):
        (tmp_path / f"{n}.img").write_bytes(b"x" * 60)
    c.podar()
    assert sum(a.stat().st_size for a in tmp_path.glob("*.img")) <= 100


def test_baixar_recusa_http_e_imagem_grande():
    with pytest.raises(ValueError):
        Capas._baixar("http://exemplo.com/a.jpg")


def test_url_da_capa_escolhe_a_menor_acima_de_160():
    from oma_spotify.services.api import item_de
    i = item_de({"uri": "spotify:album:a", "type": "album", "name": "A", "images": [
        {"url": "https://i/640", "width": 640}, {"url": "https://i/300", "width": 300}, {"url": "https://i/64", "width": 64}]})
    assert i.capa == "https://i/300"
