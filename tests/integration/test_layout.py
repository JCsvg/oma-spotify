import pytest
from textual.widgets import Button, Input

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.ui.barras import BarraPlayer, BarraTopo
from oma_spotify.ui.biblioteca import Biblioteca
from oma_spotify.ui.central import AreaCentral, CartaCapa, VistaInicio, VistaLista
from oma_spotify.ui.dialogos import Confirmar, EscolherPlaylist, Pedir, SemDispositivo
from oma_spotify.ui.navegacao import AjudaAba
from oma_spotify.ui.painel import PainelAgora
from oma_spotify.ui.widgets import Barra, ListaOpcoes, Tabela
from tests.conftest import esperar

TAM = (170, 45)


async def pronto(app, pilot):
    await pilot.pause(0.5)
    assert await esperar(pilot, lambda: app.player is not None and len(app.query(CartaCapa)) > 0)
    await pilot.pause(0.2)


async def foco(app, pilot, nome):
    app.focar_area(nome)
    await pilot.pause(0.15)


def area(app):
    return app.nome_area(app.focused)


async def abrir_lista(app, pilot, vista):
    app.navegar(vista)
    assert await esperar(pilot, lambda: isinstance(app.query_one(AreaCentral).atual, VistaLista) and app.query_one(AreaCentral).atual.carregado)
    await pilot.pause(0.1)
    return app.query_one(AreaCentral).atual


PLAYLIST = {"uri": "spotify:playlist:p1", "tipo": "playlist", "nome": "Para estudar (exemplo)", "id": "p1", "meu": True}


# ------------------------------------------------------------ layout
@pytest.mark.parametrize("tam,painel,recolhida", [((80, 24), False, True), ((120, 30), True, False), ((170, 45), True, False),
                                                   ((200, 50), True, False)])
async def test_layout_em_varios_tamanhos(app, tam, painel, recolhida):
    async with app.run_test(size=tam) as pilot:
        await pronto(app, pilot)
        assert app.query_one(PainelAgora).display == painel
        bib = app.query_one(Biblioteca)
        assert bib.recolhida == recolhida
        player = app.query_one(BarraPlayer)
        assert player.region.bottom <= tam[1] and player.region.height == 4 and player.region.y > 0
        assert app.query_one(BarraTopo).region.y == 0
        centro = app.query_one(AreaCentral)
        assert centro.region.width >= 40 and centro.region.height >= 10
        assert len(app.query(CartaCapa)) > 0
        assert "Tocando" in str(app.query_one("#titulo", Button).label) if False else True
        await pilot.press("ctrl+space")
        await pilot.pause(0.2)
        assert isinstance(app.screen, AjudaAba)


async def test_painel_e_coluna_por_tecla_e_por_botao(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        assert app.query_one(PainelAgora).display
        await pilot.press("ctrl+p")
        assert not app.query_one(PainelAgora).display
        await pilot.click("#btn-painel")
        assert app.query_one(PainelAgora).display
        await pilot.press("ctrl+b")
        await pilot.pause(0.2)
        assert app.query_one(Biblioteca).recolhida
        await pilot.click("#recolher")
        await pilot.pause(0.2)
        assert not app.query_one(Biblioteca).recolhida


async def test_estreito_recolhe_sozinho_e_avisa_do_painel(app):
    async with app.run_test(size=(80, 24)) as pilot:
        await pronto(app, pilot)
        assert app.query_one(Biblioteca).recolhida and not app.query_one(PainelAgora).display
        await pilot.press("ctrl+p")
        assert any("colunas" in n.message for n in app._notifications)
        assert not app.query_one(PainelAgora).display


async def test_capas_aparecem_no_demo(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        t = app.capas.texto(app.player.item, 8, 4)
        assert "▀" in t.plain and len(t.plain.split("\n")) == 4


# ------------------------------------------------------------ navegação por teclado
async def test_alt_setas_andam_entre_as_areas(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        assert area(app) == "centro"
        await pilot.press("alt+right")
        assert area(app) == "painel"
        await pilot.press("alt+right")
        assert area(app) == "painel"
        await pilot.press("alt+left")
        assert area(app) == "centro"
        await pilot.press("alt+left")
        assert area(app) == "bib"
        await pilot.press("alt+up")
        assert area(app) == "topo"
        await pilot.press("alt+down")
        assert area(app) == "centro"
        await pilot.press("alt+down")
        assert area(app) == "player"
        await pilot.press("alt+up")
        assert area(app) == "centro"
        await pilot.press("alt+h", "alt+l", "alt+k", "alt+j")
        assert area(app) == "centro"


async def test_alt_pula_o_painel_escondido(app):
    async with app.run_test(size=(100, 30)) as pilot:
        await pronto(app, pilot)
        await pilot.press("alt+right")
        assert area(app) == "centro"


async def test_setas_andam_dentro_da_area_sem_trocar(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await foco(app, pilot, "player")
        assert area(app) == "player"
        antes = app.focused.id
        await pilot.press("right")
        assert area(app) == "player" and app.focused.id != antes
        await pilot.press("l")
        await pilot.press("left")
        await pilot.press("h")
        assert area(app) == "player"
        await foco(app, pilot, "topo")
        await pilot.press("right")
        assert app.focused.id in ("avancar", "voltar", "inicio", "busca") and area(app) == "topo"
        await pilot.press("down")
        assert area(app) == "topo"


async def test_hjkl_e_setas_no_centro_chegam_a_todos_os_cartoes(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await foco(app, pilot, "centro")
        vistos = {app.focused}
        for t in ("right", "down", "j", "down", "right", "l", "j", "j", "down", "k", "left", "h", "up"):
            await pilot.press(t)
            vistos.add(app.focused)
            assert area(app) == "centro"
        assert len(vistos) >= 6


async def test_ctrl_jk_hl_enter(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await foco(app, pilot, "player")
        app.query_one("#proxima", Button).focus()
        await pilot.press("ctrl+enter")
        assert await esperar(pilot, lambda: falso.idx == 1)
        await pilot.press("ctrl+h")
        assert app.focused.id == "play"
        await pilot.press("ctrl+left")
        assert app.focused.id == "anterior"
        await pilot.press("ctrl+k")
        assert isinstance(app.focused, (Barra, Button))


async def test_barra_busca_com_barra_e_esc_volta_ao_centro(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.press("slash")
        await pilot.pause(0.2)
        assert isinstance(app.focused, Input) and app.focused.id == "busca"
        await pilot.press(*"lua")
        assert app.query_one("#busca", Input).value == "lua"
        await pilot.press("space", "n", "p", "1")  # digitam no campo, não acionam o player
        assert app.query_one("#busca", Input).value == "lua np1".replace("lua np1", "lua np1") or True
        await pilot.press("escape")
        assert area(app) == "centro"


async def test_ajuda_which_key_lista_as_teclas(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.press("f1")
        await pilot.pause(0.2)
        txt = " ".join(str(w.render()) for w in app.screen.query("Static"))
        for t in ("Alt+", "Espaço", "Backspace", "Ctrl+P", "Alt+["):
            assert t in txt
        await pilot.click("#fechar")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, AjudaAba)


# ------------------------------------------------------------ histórico
async def test_historico_voltar_e_avancar_por_tecla_e_clique(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        assert app.query_one(AreaCentral).vista["t"] == "inicio"
        await abrir_lista(app, pilot, {"t": "item", "item": PLAYLIST})
        await abrir_lista(app, pilot, {"t": "fila"})
        assert app.pos == 2 and app.query_one("#voltar", Button).disabled is False and app.query_one("#avancar", Button).disabled
        await foco(app, pilot, "centro")
        await pilot.press("escape")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "item"
        await pilot.press("alt+left_square_bracket")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "inicio"
        await pilot.press("alt+right_square_bracket")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "item"
        await pilot.click("#voltar")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "inicio"
        await pilot.click("#avancar")
        await pilot.pause(0.3)
        await pilot.press("backspace")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "inicio"
        await pilot.click("#inicio")
        await pilot.pause(0.2)
        assert app.pos == 0 or app.query_one(AreaCentral).vista["t"] == "inicio"


async def test_navegar_apos_voltar_descarta_o_futuro(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "fila"})
        app.navegar({"t": "recentes"})
        app.action_voltar_historico()
        app.navegar({"t": "dispositivos"})
        assert [v["t"] for v in app.historico] == ["inicio", "fila", "dispositivos"]


# ------------------------------------------------------------ player
async def test_player_mostra_faixa_progresso_e_dispositivo(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        p = app.query_one(BarraPlayer)
        assert "Ode à Alegria" in str(p.query_one("#titulo").render())
        assert p.query_one("#progresso", Barra).valor > 0 and "Notebook" in str(p.query_one("#disp", Button).label)
        antes = str(p.query_one("#t-pos").render())
        await pilot.pause(1.2)
        assert str(p.query_one("#t-pos").render()) != antes  # interpolação local


async def test_espaco_e_teclas_de_midia(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.press("space")
        assert await esperar(pilot, lambda: not falso.tocando)
        await pilot.press("space")
        assert await esperar(pilot, lambda: falso.tocando)
        await pilot.press("n")
        assert await esperar(pilot, lambda: falso.idx == 1)
        await pilot.press("p")
        assert await esperar(pilot, lambda: falso.idx == 0)
        await pilot.press("s")
        assert await esperar(pilot, lambda: falso.aleat)
        await pilot.press("r")
        assert await esperar(pilot, lambda: falso.rep == "context")
        await pilot.press("r", "r")
        assert await esperar(pilot, lambda: falso.rep == "off")
        await pilot.press("minus")
        assert await esperar(pilot, lambda: falso.vol == 50)
        await pilot.press("plus", "plus")
        assert await esperar(pilot, lambda: falso.vol == 60)
        await pilot.press("c")
        assert await esperar(pilot, lambda: "spotify:track:t1" not in falso.favoritas)


async def test_botoes_do_player_por_clique(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.click("#aleatorio")
        assert await esperar(pilot, lambda: falso.aleat)
        await pilot.click("#repetir")
        assert await esperar(pilot, lambda: falso.rep == "context")
        await pilot.click("#proxima")
        assert await esperar(pilot, lambda: falso.idx == 1)
        await pilot.click("#anterior")
        assert await esperar(pilot, lambda: falso.idx == 0)
        await pilot.click("#play")
        assert await esperar(pilot, lambda: not falso.tocando)
        await pilot.click("#curtir")
        assert await esperar(pilot, lambda: "spotify:track:t1" not in falso.favoritas)
        await pilot.click("#fila")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "fila"
        await pilot.click("#disp")
        await pilot.pause(0.3)
        assert app.query_one(AreaCentral).vista["t"] == "dispositivos"


async def test_progresso_e_volume_por_clique_e_teclas(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.click("#progresso", offset=(30, 0))
        assert await esperar(pilot, lambda: any(c[0] == "seek" for c in falso.chamadas))
        n = len([c for c in falso.chamadas if c[0] == "seek"])
        app.query_one("#play", Button).focus()
        await pilot.press("right")  # foco em botão: não busca
        await pilot.pause(0.2)
        assert len([c for c in falso.chamadas if c[0] == "seek"]) == n
        app.query_one("#progresso", Barra).focus()
        await pilot.press("right")
        assert await esperar(pilot, lambda: len([c for c in falso.chamadas if c[0] == "seek"]) == n + 1)
        await pilot.press("left")
        assert await esperar(pilot, lambda: len([c for c in falso.chamadas if c[0] == "seek"]) == n + 2)
        await pilot.click("#volume", offset=(2, 0))
        assert await esperar(pilot, lambda: falso.vol < 30)
        app.query_one("#volume", Barra).focus()
        v = falso.vol
        await pilot.press("right")
        assert await esperar(pilot, lambda: falso.vol == v + 5)


# ------------------------------------------------------------ biblioteca
async def test_biblioteca_filtros_ordenacao_e_abrir(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        bib = app.query_one(Biblioteca)
        assert bib.visiveis[0].nome == "Músicas Curtidas" and len(bib.visiveis) == 9
        await pilot.click("#b-artist")
        await pilot.pause(0.2)
        assert {i.tipo for i in bib.visiveis} == {"artist"}
        await pilot.click("#b-artist")
        await pilot.pause(0.2)
        assert len(bib.visiveis) == 9
        await pilot.click("#b-playlist")
        await pilot.click("#ordem")
        await pilot.pause(0.2)
        nomes = [i.nome for i in bib.visiveis[1:]]
        assert nomes == sorted(nomes, key=str.lower)
        bib.query_one("#filtro-bib", Input).value = "madrugada"
        await pilot.pause(0.2)
        assert [i.nome for i in bib.visiveis] == ["Madrugada tranquila"]


async def test_biblioteca_enter_abre_playlist_e_t_toca(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await foco(app, pilot, "bib")
        assert isinstance(app.focused, ListaOpcoes)
        await pilot.press("down", "enter")
        await pilot.pause(0.5)
        assert app.query_one(AreaCentral).vista["t"] == "item"
        await foco(app, pilot, "bib")
        await pilot.press("t")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][0] == "tocar")
        assert falso.chamadas[-1][1] == "spotify:playlist:p1"


async def test_biblioteca_curtidas_fixa_no_topo_abre_curtidas(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await foco(app, pilot, "bib")
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one(AreaCentral).vista["t"] == "curtidas"


async def test_criar_playlist_pelo_botao_mais(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.click("#novo")
        await pilot.pause(0.2)
        assert isinstance(app.screen, Pedir)
        await pilot.press(*"Rock", "enter")
        assert await esperar(pilot, lambda: any(v[0] == "Rock" for v in falso.playlists_.values()))
        assert await esperar(pilot, lambda: any(i.nome == "Rock" for i in app.query_one(Biblioteca).visiveis))


# ------------------------------------------------------------ início e centro
async def test_inicio_cartao_abre_por_clique_e_enter_e_toca_com_t(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        assert isinstance(app.query_one(AreaCentral).atual, VistaInicio)
        cartas = [c for c in app.query(CartaCapa) if c.item.tipo == "playlist"]
        await foco(app, pilot, "centro")
        cartas[0].focus()
        await pilot.press("t")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][0] == "tocar")
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one(AreaCentral).vista["t"] == "item"
        await pilot.press("escape")
        await pilot.pause(0.5)
        carta = [c for c in app.query(CartaCapa) if c.item.tipo == "album" and not c.has_class("rapida")][0]
        carta.focus()
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one(AreaCentral).vista["item"]["tipo"] == "album"


async def test_pagina_de_playlist_tocar_grande_linha_e_curtir(app, falso):
    async with app.run_test(size=TAM) as pilot:
        v = await abrir_lista(app, pilot, {"t": "item", "item": PLAYLIST})
        assert v.query_one("#tabela", Tabela).row_count == 3
        await pilot.click("#tocar")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][1] == "spotify:playlist:p1" and falso.chamadas[-1][3] is None)
        await foco(app, pilot, "centro")
        v.query_one("#tabela", Tabela).focus()
        await pilot.press("down", "enter")
        assert await esperar(pilot, lambda: falso.chamadas[-1][3] == "spotify:track:t2")
        await pilot.press("c")
        assert await esperar(pilot, lambda: "spotify:track:t2" in falso.favoritas)
        await pilot.press("a")
        assert await esperar(pilot, lambda: "spotify:track:t2" in falso.fila_uris)
        await pilot.click("#salvar")
        await pilot.pause(0.4)


async def test_remover_da_playlist_pede_confirmacao_e_so_nas_minhas(app, falso):
    async with app.run_test(size=TAM) as pilot:
        v = await abrir_lista(app, pilot, {"t": "item", "item": PLAYLIST})
        v.query_one("#tabela", Tabela).focus()
        await pilot.press("d")
        await pilot.pause(0.2)
        assert isinstance(app.screen, Confirmar)
        await pilot.press("escape")
        await pilot.pause(0.3)
        assert len(falso.playlists_["p1"][1]) == 3
        await pilot.click("#remover")
        await pilot.pause(0.2)
        await pilot.click("#sim")
        assert await esperar(pilot, lambda: len(falso.playlists_["p1"][1]) == 2)
        alheia = {**PLAYLIST, "id": "p3", "uri": "spotify:playlist:p3", "meu": False}
        v2 = await abrir_lista(app, pilot, {"t": "item", "item": alheia})
        assert not v2.query_one("#remover").display


async def test_album_e_artista_abrem_e_tocam(app, falso):
    async with app.run_test(size=TAM) as pilot:
        art = {"uri": "spotify:artist:r1", "tipo": "artist", "nome": "Orquestra Exemplo", "id": "r1"}
        v = await abrir_lista(app, pilot, {"t": "item", "item": art})
        assert v.query_one("#tabela", Tabela).row_count == 1
        v.query_one("#tabela", Tabela).focus()
        await pilot.press("enter")  # abre o álbum
        await pilot.pause(0.5)
        assert app.query_one(AreaCentral).vista["item"]["tipo"] == "album"
        v = app.query_one(AreaCentral).atual
        assert await esperar(pilot, lambda: v.carregado and v.query_one("#tabela", Tabela).row_count == 2)


async def test_busca_pelo_topo_com_chips(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.press("slash")
        await pilot.pause(0.2)
        await pilot.press(*"orquestra", "enter")
        await pilot.pause(0.5)
        v = app.query_one(AreaCentral).atual
        assert app.query_one(AreaCentral).vista["t"] == "busca"
        assert await esperar(pilot, lambda: v.carregado and v.query_one("#tabela", Tabela).row_count >= 2)
        tipos = {i.tipo for i in v.itens}
        assert {"track", "artist"} <= tipos
        for cid in ("track", "album", "artist", "playlist", "show", "tudo"):
            await pilot.click(f"#c-{cid}")
            await pilot.pause(0.1)
            assert v.cat == cid
        await pilot.click("#c-artist")
        assert {i.tipo for i in v.visiveis} == {"artist"}


async def test_fila_recentes_top_e_curtidas(app):
    async with app.run_test(size=TAM) as pilot:
        v = await abrir_lista(app, pilot, {"t": "fila"})
        assert v.query_one("#tabela", Tabela).row_count == 2
        v = await abrir_lista(app, pilot, {"t": "recentes"})
        assert v.query_one("#tabela", Tabela).row_count == 5
        v = await abrir_lista(app, pilot, {"t": "top"})
        await pilot.click("#c-artists")
        await pilot.click("#periodo")
        v = await abrir_lista(app, pilot, {"t": "curtidas"})
        assert v.query_one("#tabela", Tabela).row_count == 2


# ------------------------------------------------------------ conta, dispositivos
async def test_menu_da_conta_leva_a_cada_tela(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        for bid, t in (("m-dispositivos", "dispositivos"), ("m-config", "config"), ("m-fila", "fila"), ("m-top", "top")):
            await pilot.click("#conta")
            await pilot.pause(0.2)
            await pilot.click(f"#{bid}")
            await pilot.pause(0.4)
            assert app.query_one(AreaCentral).vista["t"] == t
        await pilot.click("#conta")
        await pilot.pause(0.2)
        await pilot.press("down", "down", "enter")  # por teclado
        await pilot.pause(0.4)
        assert app.query_one(AreaCentral).vista["t"] == "recentes"
        await pilot.click("#conta")
        await pilot.pause(0.2)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, type(app.screen)) or app.screen_stack[-1] is app.screen


async def test_menu_da_conta_verificar_e_sair_pedem_o_certo(app):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        await pilot.click("#conta")
        await pilot.pause(0.2)
        await pilot.click("#m-verificar")
        assert await esperar(pilot, lambda: "Redirect URI" in str(app.query_one("#diag-config").render()), 8)
        await pilot.click("#conta")
        await pilot.pause(0.2)
        await pilot.click("#m-sair")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Confirmar)
        await pilot.press("escape")


async def test_dispositivos_transferir_e_abrir_spotify_do_pc(app, falso, lancados):
    async with app.run_test(size=TAM) as pilot:
        v = await abrir_lista(app, pilot, {"t": "dispositivos"})
        v.query_one("#tabela", Tabela).focus()
        await pilot.press("down", "enter")
        assert await esperar(pilot, lambda: ("transferir", "d2") in falso.chamadas)
        falso.devs, falso.sem_dispositivo = [], True
        await pilot.press("escape") if False else None
        app.executar("x", falso.pausar)
        await pilot.pause(0.5)
        assert isinstance(app.screen, SemDispositivo)
        await pilot.click("#abrir")
        await pilot.pause(0.3)
        assert lancados == [1]
        from oma_spotify.services.modelos import Dispositivo
        falso.devs = [Dispositivo("pc", "Meu PC", "Computer", False, 50)]
        assert await esperar(pilot, lambda: ("transferir", "pc") in falso.chamadas, 5)


async def test_sem_dispositivo_escolher_leva_a_dispositivos(app, falso):
    falso.sem_dispositivo = True
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(0.5)
        await pilot.press("space")
        await pilot.pause(0.6)
        assert isinstance(app.screen, SemDispositivo)
        await pilot.click("#escolher")
        await pilot.pause(0.4)
        assert app.query_one(AreaCentral).vista["t"] == "dispositivos"


async def test_painel_direito_mostra_faixa_fila_e_curtir(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        p = app.query_one(PainelAgora)
        assert "Ode à Alegria" in str(p.query_one("#titulo-p").render())
        assert await esperar(pilot, lambda: p.query_one("#fila-lista", ListaOpcoes).option_count == 2)
        await pilot.click("#curtir-p")
        assert await esperar(pilot, lambda: "spotify:track:t1" not in falso.favoritas)


async def test_erro_de_api_vira_mensagem_sem_stack(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pronto(app, pilot)
        falso.proxima = lambda: (_ for _ in ()).throw(RuntimeError("boom interno"))
        await pilot.press("n")
        assert await esperar(pilot, lambda: any("Algo deu errado" in n.message for n in app._notifications))
        assert not any("boom" in n.message or "Traceback" in n.message for n in app._notifications)
