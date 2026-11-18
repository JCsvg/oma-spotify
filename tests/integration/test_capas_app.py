"""Capas de verdade na interface (no demo, imagens de mentira geradas na hora, sem rede)."""

import json

from oma_spotify.ui.capa import Capa
from oma_spotify.ui.widgets import Cartao
from tests.conftest import esperar, pronto

GRANDE = (180, 48)


def tem_imagem(w) -> bool:
    return "▀" in str(w.render())


async def test_tocando_inicio_e_cabecalho_com_capas(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        assert await esperar(pilot, lambda: tem_imagem(app.query_one("#tc-capa")), 4)
        assert await esperar(pilot, lambda: all(tem_imagem(c) for c in app.query("#repeat Cartao")), 4)
        atalhos = list(app.query("#atalhos Cartao"))
        assert not tem_imagem(atalhos[0])  # Músicas Curtidas não tem imagem: fica o coração
        assert await esperar(pilot, lambda: tem_imagem(atalhos[1]), 4)
        app.navegar({"t": "item", "item": {"uri": "spotify:playlist:p1", "tipo": "playlist", "nome": "Mesa de sexta", "id": "p1",
                                           "meu": True}})
        await pilot.pause(0.5)
        cab = app.query_one("#cab-capa", Capa)
        assert cab.imagem == "demo:playlist:p1"  # veio da biblioteca: o histórico não guarda a URL
        assert await esperar(pilot, lambda: tem_imagem(cab), 4)


async def test_capas_desligadas_voltam_para_a_inicial(app, config):
    config.capas = False
    app.capas.desligar(False)  # a fixture cria o app antes do teste mexer na config
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.pause(0.5)
        assert not tem_imagem(app.query_one("#tc-capa"))
        assert not any(tem_imagem(c) for c in app.query(Cartao))


async def test_interruptor_nas_configuracoes(app, config):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        assert await esperar(pilot, lambda: tem_imagem(app.query_one("#tc-capa")), 4)
        app.navegar({"t": "config"})
        await pilot.pause(0.5)
        await pilot.click("#capas")
        await pilot.pause(0.3)
        assert config.capas is False and "mostrar capas: não" in app.query_one("#capas").label
        assert not tem_imagem(app.query_one("#tc-capa"))
        await pilot.click("#capas")
        assert await esperar(pilot, lambda: tem_imagem(app.query_one("#tc-capa")), 4)


async def test_url_da_imagem_nao_vai_para_o_estado(app, estado):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "item", "item": {"uri": "spotify:album:a1", "tipo": "album", "nome": "Faróis", "id": "a1",
                                           "img": "demo:album:a1"}})
        app.a_seguir(app.curtidas_cache[:2])
        await pilot.pause(0.5)
        estado.salvar()
    bruto = estado.arquivo.read_text()
    assert '"img"' not in bruto and "demo:album" not in bruto
    assert json.loads(bruto)["dados"]["hist"][-1]["item"]["nome"] == "Faróis"


async def test_sair_da_pagina_cancela_as_capas_pendentes(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.capas.fila.extend(["demo:album:zz1", "demo:album:zz2"])
        app.navegar({"t": "curtidas"})
        assert not app.capas.fila


async def test_capas_na_busca_e_no_player_estreito(app):
    async with app.run_test(size=(90, 30)) as pilot:
        await pronto(app, pilot)
        assert await esperar(pilot, lambda: tem_imagem(app.query_one("#pl-capa")), 4)
        app.navegar({"t": "busca", "q": "cais", "cat": "tudo"})
        assert await esperar(pilot, lambda: app.query("#musicas") and "▀" in app.query_one("#musicas").render_line(0).text, 5)
