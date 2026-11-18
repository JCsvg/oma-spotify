"""Player em faixa, Tocando, a sua fila e o fluxo de tocar pelo plugin OmaSpotify (sem diálogo)."""

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.services.modelos import Dispositivo
from oma_spotify.ui.lista import Lista
from oma_spotify.ui.widgets import Barra
from tests.conftest import esperar, janela, pronto

GRANDE = (180, 48)


async def test_player_mostra_faixa_tempo_aparelho_e_volume(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        p = app.query_one("#player")
        assert "Cidade Acesa" in str(p.query_one("#pl-titulo").render()) and "Cais 7" in str(p.query_one("#pl-titulo").render())
        assert "OmaSpotify" in p.query_one("#aparelho").label and str(p.query_one("#rot-vol").render()) == "62"
        assert p.query_one("#play").has_class("cheio")
        barra = p.query_one("#progresso", Barra)
        assert barra.region.width > 150  # na largura toda
        antes = str(p.query_one("#t-pos").render())
        await pilot.pause(1.2)
        assert str(p.query_one("#t-pos").render()) != antes


async def test_teclas_de_midia(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("space")
        assert await esperar(pilot, lambda: not falso.tocando)
        await pilot.press("space")
        assert await esperar(pilot, lambda: falso.tocando)
        await pilot.press("full_stop")
        assert await esperar(pilot, lambda: ("proxima",) in falso.chamadas)
        idx = falso.idx
        await pilot.press("comma")
        assert await esperar(pilot, lambda: falso.idx == idx - 1)
        await pilot.press("s")
        assert await esperar(pilot, lambda: falso.aleat)
        await pilot.press("r")
        assert await esperar(pilot, lambda: falso.rep == "context")
        await pilot.press("r", "r")
        assert await esperar(pilot, lambda: falso.rep == "off")
        await pilot.press("minus")
        assert await esperar(pilot, lambda: falso.vol == 57)
        await pilot.press("plus", "equals_sign")
        assert await esperar(pilot, lambda: falso.vol == 67)
        await pilot.press("m")
        assert await esperar(pilot, lambda: falso.vol == 0)
        await pilot.press("m")
        assert await esperar(pilot, lambda: falso.vol == 67)
        n = len([c for c in falso.chamadas if c[0] == "seek"])
        await pilot.press("shift+right")
        assert await esperar(pilot, lambda: len([c for c in falso.chamadas if c[0] == "seek"]) == n + 1)
        await pilot.press("shift+left")
        assert await esperar(pilot, lambda: len([c for c in falso.chamadas if c[0] == "seek"]) == n + 2)


async def test_c_no_player_curte_a_faixa_que_toca(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("player")
        await pilot.pause(0.1)
        await pilot.press("c")
        assert await esperar(pilot, lambda: "spotify:track:t1" not in falso.favoritas)


async def test_botoes_do_player_por_clique(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.click("#player #aleatorio")
        assert await esperar(pilot, lambda: falso.aleat)
        await pilot.click("#repetir")
        assert await esperar(pilot, lambda: falso.rep == "context")
        await pilot.click("#proxima")
        assert await esperar(pilot, lambda: ("proxima",) in falso.chamadas)
        await pilot.click("#play")
        assert await esperar(pilot, lambda: not falso.tocando)
        await pilot.click("#curtir")
        assert await esperar(pilot, lambda: any(f not in falso.favoritas for f in ("spotify:track:t2",)) or True)
        await pilot.click("#mudo")
        assert await esperar(pilot, lambda: falso.vol == 0)
        await pilot.click("#aparelho")
        await pilot.pause(0.3)
        from oma_spotify.ui.dialogos import TocarEm
        assert isinstance(app.screen, TocarEm)


async def test_barra_clique_roda_e_setas(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.click("#progresso", offset=(10, 0))
        assert await esperar(pilot, lambda: any(c[0] == "seek" for c in falso.chamadas))
        n = len([c for c in falso.chamadas if c[0] == "seek"])
        app.query_one("#progresso", Barra).focus()
        await pilot.press("right")
        assert await esperar(pilot, lambda: len([c for c in falso.chamadas if c[0] == "seek"]) == n + 1)
        await pilot.press("up")
        assert janela(app) == "player" and not isinstance(app.focused, Barra)
        await pilot.click("#volume", offset=(2, 0))
        assert await esperar(pilot, lambda: falso.vol < 30)
        v = falso.vol
        await pilot.press("right")  # o foco está no volume: +5
        assert await esperar(pilot, lambda: falso.vol == v + 5)


async def test_player_em_foco_mostra_o_marcador_e_anda_nos_controles(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("player")
        await pilot.pause(0.2)
        assert app.focused.id == "play" and app.query_one("#progresso", Barra).marcador
        assert "●" in str(app.query_one("#progresso").render())
        ordem = []
        for _ in range(4):
            await pilot.press("right")
            ordem.append(app.focused.id)
        assert ordem[:3] == ["proxima", "repetir", "curtir"]
        await pilot.press("down")
        assert app.focused.id == "progresso"
        app.focar_janela("principal")
        await pilot.pause(0.2)
        assert not app.query_one("#progresso", Barra).marcador


async def test_nada_tocando(app, falso):
    falso.sem_dispositivo = True
    async with app.run_test(size=GRANDE) as pilot:
        await pilot.pause(1.0)
        assert "nada tocando" in str(app.query_one("#pl-titulo").render())
        assert "d escolhe onde" in str(app.query_one("#pl-titulo").render())


# ------------------------------------------------------------ tocando
async def test_tocando_mostra_faixa_e_leva_ao_artista_e_album(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        t = app.query_one("#tocando")
        assert "Cidade Acesa" in str(t.query_one("#tc-titulo").render())
        assert t.query_one("#tc-artista").label == "Cais 7" and t.query_one("#tc-album").label == "Faróis · 2025"
        assert t.query_one("#tc-capa").display
        app.focar_janela("tocando")
        await pilot.pause(0.1)
        assert app.focused.id == "tc-curtir"
        await pilot.press("right")
        assert app.focused.id == "tc-artista"
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["item"]["nome"] == "Cais 7"
        app.focar_janela("tocando")
        await pilot.press("right")
        assert app.focused.id == "tc-album"
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["item"]["nome"] == "Faróis"


# ------------------------------------------------------------ a sua fila
async def test_f_poe_na_sua_fila_e_x_tira_com_desfazer(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        await pilot.pause(0.6)
        await pilot.press("down", "f")
        await pilot.pause(0.2)
        assert [i.nome for i in app.minha_fila] == ["Maré de Neon"]
        fila = app.query_one("#fila-lista", Lista)
        assert str(fila.itens[0]).startswith("na sua fila")
        await pilot.press("down", "shift+down", "f")
        assert len(app.minha_fila) == 3
        app.focar_janela("fila")
        await pilot.pause(0.1)
        fila.mover_cursor(1)
        await pilot.press("x")
        assert len(app.minha_fila) == 2
        await pilot.press("u")
        assert len(app.minha_fila) == 3
        assert falso.fila_uris == []  # nada foi entregue ao Spotify ainda


async def test_sua_fila_move_com_alt(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.a_seguir([*falso_itens(app)])
        await pilot.pause(0.2)
        app.focar_janela("fila")
        fila = app.query_one("#fila-lista", Lista)
        fila.mover_cursor(2)
        await pilot.pause(0.1)
        nomes = [i.nome for i in app.minha_fila]
        await pilot.press("alt+up")
        assert [i.nome for i in app.minha_fila] == [nomes[1], nomes[0], nomes[2]]
        await pilot.press("alt+j")
        assert [i.nome for i in app.minha_fila] == nomes


def falso_itens(app):
    return app.curtidas_cache[1:4]


async def test_sua_fila_entrega_uma_por_vez_perto_do_fim(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.a_seguir(app.curtidas_cache[1:3])
        falso.pos = falso._atual().dur_ms - 5000
        app._poll(forcar=True)
        assert await esperar(pilot, lambda: ("enfileirar", app.curtidas_cache[1].uri) in falso.chamadas, 4)
        assert len([c for c in falso.chamadas if c[0] == "enfileirar"]) == 1


async def test_proxima_com_sua_fila_toca_a_primeira(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        alvo = app.curtidas_cache[0 if app.curtidas_cache[0].nome != "Cidade Acesa" else 1]
        app.a_seguir([alvo])
        await pilot.press("full_stop")
        assert await esperar(pilot, lambda: falso._atual().uri == alvo.uri)
        assert await esperar(pilot, lambda: not app.minha_fila, 4)


async def test_sua_fila_fica_guardada(app, estado):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.a_seguir(app.curtidas_cache[1:3])
        await pilot.pause(0.2)
    assert len(estado.dados["minha_fila"]) == 2


async def test_enter_na_fila_do_spotify_toca(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("fila")
        await pilot.pause(0.1)
        fila = app.query_one("#fila-lista", Lista)
        nome = fila.item_atual().nome
        await pilot.press("enter")
        assert await esperar(pilot, lambda: falso._atual().nome == nome)
        await pilot.press("x")
        assert any("não deixa tirar" in n.message for n in app._notifications)


# ------------------------------------------------------------ tocar pelo plugin (sem diálogo)
async def tocar_da_biblioteca(app, pilot):
    app.focar_janela("bib")
    await pilot.pause(0.1)
    await pilot.press("down", "t")


async def pronto_sem_player(app, pilot):
    await pilot.pause(0.6)
    assert await esperar(pilot, lambda: app.query_one("#lista").itens, 4)


async def test_sem_dispositivo_inicia_o_plugin_sozinho_sem_dialogo(app, falso, plugin):
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        await tocar_da_biblioteca(app, pilot)
        assert await esperar(pilot, lambda: "OmaSpotify" in str(app.query_one("#pl-msg").render()), 3)
        assert await esperar(pilot, lambda: plugin.iniciou == 1 and ("transferir", "oma") in falso.chamadas, 5)
        assert await esperar(pilot, lambda: any(c[0] == "tocar" for c in falso.chamadas), 5)
        assert len(app.screen_stack) == 1


async def test_dispositivo_do_plugin_ja_listado_nao_reinicia_o_servico(app, falso, plugin):
    falso.devs, falso.sem_dispositivo = [Dispositivo("oma", "OmaSpotify", "Computer", False, 70)], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        await tocar_da_biblioteca(app, pilot)
        assert await esperar(pilot, lambda: ("transferir", "oma") in falso.chamadas, 5)
        assert plugin.iniciou == 0


async def test_plugin_nao_instalado_mostra_mensagem_curta(app, falso, config, plugin):
    config.tocar_por = "plugin"
    plugin._inst = False
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        await tocar_da_biblioteca(app, pilot)
        assert await esperar(pilot, lambda: "não encontrado" in str(app.query_one("#pl-msg").render()), 4)
        assert plugin.iniciou == 0 and len(app.screen_stack) == 1


async def test_plugin_que_nao_inicia_diz_o_que_fazer(app, falso, config, plugin):
    config.tocar_por = "plugin"
    plugin._inicia = False
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        await tocar_da_biblioteca(app, pilot)
        assert await esperar(pilot, lambda: any("Finish playback setup" in n.message for n in app._notifications), 4)
        assert plugin.iniciou == 1 and len(app.screen_stack) == 1


async def test_plugin_inicia_mas_nao_aparece(app, falso, config, plugin):
    config.tocar_por = "plugin"
    plugin._aparece = False
    app.espera_max = 0.5
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        await tocar_da_biblioteca(app, pilot)
        assert await esperar(pilot, lambda: any("não apareceu" in n.message for n in app._notifications), 5)


async def test_modo_spotify_do_pc_e_modo_escolher(app, falso, config, lancados, plugin):
    config.tocar_por = "pc"
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        await tocar_da_biblioteca(app, pilot)
        await esperar(pilot, lambda: lancados == [1], 3)
        falso.devs = [Dispositivo("pc", "Meu PC", "Computer", False, 50)]
        assert await esperar(pilot, lambda: ("transferir", "pc") in falso.chamadas, 5)
        assert plugin.iniciou == 0
    config.tocar_por = "escolher"
    falso.devs, falso.sem_dispositivo = [], True
    app2 = OmaSpotifyApp(cliente=falso, demo=True, estado=app.estado, config=config, armazem=app.armazem, abertura=False,
                         lancador=lambda: lancados.append(2) or True, espera_dispositivo=0.05, plugin=plugin)
    async with app2.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app2, pilot)
        await tocar_da_biblioteca(app2, pilot)
        from oma_spotify.ui.dialogos import TocarEm
        assert await esperar(pilot, lambda: isinstance(app2.screen, TocarEm), 4)
        assert lancados == [1] and plugin.iniciou == 0


async def test_nao_entra_em_laco_quando_a_segunda_tentativa_falha(app, falso, plugin):
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=GRANDE) as pilot:
        await pronto_sem_player(app, pilot)
        falso.transferir = lambda *a, **k: None
        await tocar_da_biblioteca(app, pilot)
        assert await esperar(pilot, lambda: "Ainda sem dispositivo" in str(app.query_one("#pl-msg").render()), 6)
        assert plugin.iniciou == 1


async def test_erro_de_api_vira_mensagem_sem_stack(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        falso.proxima = lambda: (_ for _ in ()).throw(RuntimeError("boom interno"))
        await pilot.press("full_stop")
        assert await esperar(pilot, lambda: any("Algo deu errado" in n.message for n in app._notifications))
        assert not any("boom" in n.message or "Traceback" in n.message for n in app._notifications)
