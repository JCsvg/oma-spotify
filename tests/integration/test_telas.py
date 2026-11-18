import pytest
from textual.widgets import Button, Input, TabbedContent

from oma_spotify.app import OmaSpotifyApp
from oma_spotify.ui.dialogos import Confirmar, EscolherPlaylist, Pedir, SemDispositivo
from oma_spotify.ui.navegacao import AjudaAba
from oma_spotify.ui.setup import TelaSetup
from oma_spotify.ui.telas import ListaDetalhe, PaginaBiblioteca, PaginaBusca, PaginaDispositivos, PaginaFila, PaginaPlaylists, PaginaTocando, TelaItens
from oma_spotify.ui.widgets import Barra, Tabela
from tests.conftest import esperar

TAM = (130, 42)


async def ir(app, pilot, tecla, cls):
    await pilot.press(tecla)
    pg = app.query_one(cls)
    assert await esperar(pilot, lambda: pg.carregado and (not pg.itens or pg.query_one("#tabela", Tabela).row_count > 0))
    await pilot.pause(0.1)
    return pg


async def test_tocando_agora_mostra_faixa_e_progresso(app):
    async with app.run_test(size=TAM) as pilot:
        pg = app.query_one(PaginaTocando)
        assert await esperar(pilot, lambda: pg.player is not None)
        assert "Ode à Alegria" in str(pg.query_one("#titulo").render())
        assert "Orquestra Exemplo" in str(pg.query_one("#artista").render())
        assert pg.query_one("#progresso", Barra).valor > 0
        assert await esperar(pilot, lambda: pg.query_one("#tabela", Tabela).row_count >= 2)


async def test_abas_so_com_alt_e_numeros_setas_nao_trocam(app):
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(0.3)
        assert app.aba_atual() == "tocando"
        for t in ("right", "left", "l", "h", "down", "up"):
            await pilot.press(t)
            await pilot.pause(0.05)
            assert app.aba_atual() == "tocando", t
        await pilot.press("alt+right")
        await pilot.pause(0.2)
        assert app.aba_atual() == "playlists"
        await pilot.press("alt+l")
        await pilot.pause(0.2)
        assert app.aba_atual() == "biblioteca"
        await pilot.press("alt+left")
        await pilot.press("alt+h")
        await pilot.pause(0.3)
        assert app.aba_atual() == "tocando"
        await pilot.press("4")
        await pilot.pause(0.2)
        assert app.aba_atual() == "busca"


async def test_alt_setas_funcionam_com_foco_em_campo_de_texto(app):
    async with app.run_test(size=TAM) as pilot:
        await pilot.press("4")
        await pilot.pause(0.2)
        app.query_one("#q", Input).focus()
        await pilot.press("alt+right")
        await pilot.pause(0.2)
        assert app.aba_atual() == "fila"


async def test_numeros_digitam_no_campo_sem_trocar_de_aba(app):
    async with app.run_test(size=TAM) as pilot:
        await pilot.press("4")
        await pilot.pause(0.2)
        app.query_one("#q", Input).focus()
        await pilot.press("1", "2", "h", "l")
        assert app.query_one("#q", Input).value == "12hl" and app.aba_atual() == "busca"


async def test_clique_na_aba(app):
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(0.3)
        await pilot.click("Tab#--content-tab-playlists")
        await pilot.pause(0.3)
        assert app.aba_atual() == "playlists"


async def test_setas_andam_entre_botoes_e_a_lista(app):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "2", PaginaPlaylists)
        assert isinstance(app.focused, Tabela)
        await pilot.press("right")
        assert isinstance(app.focused, Button)
        primeiro = app.focused.id
        await pilot.press("l")
        assert app.focused.id != primeiro
        await pilot.press("left")
        assert app.focused.id == primeiro
        await pilot.press("up")
        assert isinstance(app.focused, Tabela)
        assert app.aba_atual() == "playlists"


async def test_espaco_alterna_play_pause_global(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pilot.pause(0.3)
        assert falso.tocando
        await pilot.press("space")
        assert await esperar(pilot, lambda: not falso.tocando)
        await pilot.press("2")
        await pilot.press("space")
        assert await esperar(pilot, lambda: falso.tocando)


async def test_espaco_no_campo_de_texto_digita(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pilot.press("4")
        await pilot.pause(0.2)
        app.query_one("#q", Input).focus()
        await pilot.press("a", "space", "b")
        assert app.query_one("#q", Input).value == "a b" and falso.tocando


async def test_busca_na_barra_de_progresso_so_com_foco_nela(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = app.query_one(PaginaTocando)
        assert await esperar(pilot, lambda: pg.player is not None)
        await pilot.press("right")  # foco no botão: não busca
        await pilot.pause(0.2)
        assert not [c for c in falso.chamadas if c[0] == "seek"]
        pg.query_one("#progresso", Barra).focus()
        await pilot.press("right")
        assert await esperar(pilot, lambda: any(c[0] == "seek" for c in falso.chamadas))
        antes = falso.chamadas[-1][1]
        await pilot.press("left")
        assert await esperar(pilot, lambda: falso.chamadas[-1][1] < antes + 1 and len([c for c in falso.chamadas if c[0] == "seek"]) == 2)


async def test_clique_na_barra_de_progresso_busca(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = app.query_one(PaginaTocando)
        assert await esperar(pilot, lambda: pg.player is not None)
        await pilot.click("#progresso", offset=(30, 0))
        assert await esperar(pilot, lambda: any(c[0] == "seek" for c in falso.chamadas))


async def test_botoes_de_reproducao_por_clique(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = app.query_one(PaginaTocando)
        assert await esperar(pilot, lambda: pg.player is not None)
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


async def test_teclas_de_reproducao(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = app.query_one(PaginaTocando)
        assert await esperar(pilot, lambda: pg.player is not None)
        await pilot.press("n")
        assert await esperar(pilot, lambda: falso.idx == 1)
        await pilot.press("s")
        assert await esperar(pilot, lambda: falso.aleat)
        await pilot.press("minus")
        assert await esperar(pilot, lambda: falso.vol == 50)
        await pilot.press("c")
        assert await esperar(pilot, lambda: "spotify:track:t2" in falso.favoritas)


async def test_playlists_abrir_e_tocar_faixa(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "2", PaginaPlaylists)
        await pilot.press("o")
        await pilot.pause(0.3)
        assert isinstance(app.screen, TelaItens)
        lista = app.screen.lista
        assert await esperar(pilot, lambda: lista.carregado and lista.query_one("#tabela", Tabela).row_count == 3)
        await pilot.press("down", "enter")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][0] == "tocar")
        assert falso.chamadas[-1][1] == "spotify:playlist:p1" and falso.chamadas[-1][3] == "spotify:track:t2"
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, TelaItens)


async def test_tocar_playlist_inteira(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "2", PaginaPlaylists)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][1] == "spotify:playlist:p1")


async def test_criar_playlist_por_botao(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "2", PaginaPlaylists)
        await pilot.click("#nova")
        await pilot.pause(0.2)
        assert isinstance(app.screen, Pedir)
        await pilot.press(*"Rock", "enter")
        assert await esperar(pilot, lambda: any(v[0] == "Rock" for v in falso.playlists_.values()))


async def test_remover_faixa_pede_confirmacao(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "2", PaginaPlaylists)
        await pilot.press("o")
        lista = app.screen.lista
        assert await esperar(pilot, lambda: lista.query_one("#tabela", Tabela).row_count == 3)
        await pilot.press("r")
        await pilot.pause(0.2)
        assert isinstance(app.screen, Confirmar)
        await pilot.press("escape")  # cancelar não remove
        await pilot.pause(0.3)
        assert len(falso.playlists_["p1"][1]) == 3
        await pilot.press("r")
        await pilot.pause(0.2)
        await pilot.click("#sim")
        assert await esperar(pilot, lambda: len(falso.playlists_["p1"][1]) == 2)


async def test_playlist_de_outra_pessoa_nao_tem_remover(app):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "2", PaginaPlaylists)
        pg.query_one("#tabela", Tabela).move_cursor(row=2)
        await pilot.press("o")
        lista = app.screen.lista
        await pilot.pause(0.3)
        assert not lista.query_one("#remover").display


async def test_biblioteca_categorias_por_clique(app):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "3", PaginaBiblioteca)
        assert pg.query_one("#tabela", Tabela).row_count == 2  # curtidas
        await pilot.click("#cat-albuns")
        assert await esperar(pilot, lambda: pg.itens and pg.itens[0].tipo == "album")
        await pilot.click("#cat-artistas")
        assert await esperar(pilot, lambda: pg.itens and pg.itens[0].tipo == "artist")
        await pilot.click("#cat-podcasts")
        assert await esperar(pilot, lambda: pg.itens and pg.itens[0].tipo == "show")


async def test_busca_resultados_em_abas_e_acoes(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await pilot.press("4")
        await pilot.pause(0.2)
        app.query_one("#q", Input).focus()
        await pilot.press(*"lua", "enter")
        pg = app.query_one(PaginaBusca)
        assert await esperar(pilot, lambda: pg.query_one("#tabela", Tabela).row_count == 1)
        assert pg.itens[0].nome == "Valsa da Lua de Papel"
        await pilot.press("a")
        assert await esperar(pilot, lambda: "spotify:track:t3" in falso.fila_uris[2:])
        await pilot.press("c")
        assert await esperar(pilot, lambda: "spotify:track:t3" in falso.favoritas)
        await pilot.click("#cat-playlist")
        assert await esperar(pilot, lambda: pg.categoria == "playlist")


async def test_busca_botao_buscar_e_barra_para_foco(app):
    async with app.run_test(size=TAM) as pilot:
        await pilot.press("4")
        await pilot.pause(0.2)
        assert isinstance(app.focused, Input) and app.focused.id == "q"  # a Busca abre no campo
        await pilot.press(*"orquestra")
        await pilot.click("#buscar")
        pg = app.query_one(PaginaBusca)
        await pilot.click("#cat-artist")
        assert await esperar(pilot, lambda: pg.categoria == "artist" and pg.itens)


async def test_adicionar_a_playlist_pelo_dialogo(app, falso):
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "3", PaginaBiblioteca)
        await pilot.press("p")
        await pilot.pause(0.5)
        assert isinstance(app.screen, EscolherPlaylist)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: len(falso.playlists_["p1"][1]) == 4)


async def test_fila_e_recentes(app):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "5", PaginaFila)
        assert pg.query_one("#tabela", Tabela).row_count == 2
        await pilot.press("7")
        await pilot.pause(0.5)
        assert app.aba_atual() == "recentes"
        await pilot.press("8")
        await pilot.pause(0.3)
        await pilot.click("#cat-artists")
        await pilot.click("#periodo")


async def test_dispositivos_transferir_por_enter_e_clique(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "6", PaginaDispositivos)
        await pilot.press("down", "enter")
        assert await esperar(pilot, lambda: ("transferir", "d2") in falso.chamadas)
        assert await esperar(pilot, lambda: any(d.ativo and d.id == "d2" for d in falso.devs))


async def test_abrir_spotify_do_pc_espera_dispositivo(app, falso, lancados):
    falso.devs, falso.sem_dispositivo = [], True
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "6", PaginaDispositivos)
        await pilot.click("#pc")
        await pilot.pause(0.2)
        assert lancados == [1]
        from oma_spotify.services.modelos import Dispositivo
        falso.devs = [Dispositivo("pc", "Meu PC", "Computer", False, 50)]
        assert await esperar(pilot, lambda: ("transferir", "pc") in falso.chamadas, 5)


async def test_sem_dispositivo_mostra_dialogo_amigavel_e_repete(app, falso, lancados):
    falso.sem_dispositivo = True
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "3", PaginaBiblioteca)
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert isinstance(app.screen, SemDispositivo)
        falso.devs[0].ativo = False
        await pilot.click("#abrir")
        await pilot.pause(0.3)
        assert lancados == [1]
        assert await esperar(pilot, lambda: ("transferir", "d1") in falso.chamadas, 5)
        assert await esperar(pilot, lambda: falso.chamadas[-1][0] == "tocar" or any(c[0] == "tocar" for c in falso.chamadas), 5)


async def test_sem_dispositivo_escolher_leva_a_tela(app, falso):
    falso.sem_dispositivo = True
    async with app.run_test(size=TAM) as pilot:
        await ir(app, pilot, "3", PaginaBiblioteca)
        await pilot.press("enter")
        await pilot.pause(0.5)
        await pilot.click("#escolher")
        await pilot.pause(0.4)
        assert app.aba_atual() == "dispositivos"


async def test_ajuda_which_key_por_teclas_e_botao(app):
    async with app.run_test(size=TAM) as pilot:
        await pilot.press("2")
        await pilot.pause(0.3)
        await pilot.press("f1")
        await pilot.pause(0.2)
        assert isinstance(app.screen, AjudaAba)
        texto = " ".join(str(w.render()) for w in app.screen.query("Static"))
        assert "Alt+" in texto and "Espaço" in texto
        await pilot.click("#fechar")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, AjudaAba)
        await pilot.press("ctrl+@")
        await pilot.pause(0.2)
        assert isinstance(app.screen, AjudaAba)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, AjudaAba)


async def test_ctrl_enter_aperta_botao_e_ctrl_jk_mudam_de_secao(app, falso):
    async with app.run_test(size=TAM) as pilot:
        pg = app.query_one(PaginaTocando)
        assert await esperar(pilot, lambda: pg.player is not None)
        pg.query_one("#proxima", Button).focus()
        await pilot.press("ctrl+enter")
        assert await esperar(pilot, lambda: falso.idx == 1)
        await pilot.press("ctrl+k")
        assert isinstance(app.focused, Barra)
        await pilot.press("ctrl+j")
        assert isinstance(app.focused, Button)


async def test_filtro_de_lista_com_barra(app):
    async with app.run_test(size=TAM) as pilot:
        pg = await ir(app, pilot, "3", PaginaBiblioteca)
        await pilot.press("slash")
        assert isinstance(app.focused, Input)
        await pilot.press(*"zzz")
        await pilot.pause(0.2)
        assert pg.query_one("#vazio").display
        await pilot.press("escape")
        assert isinstance(app.focused, Tabela) or isinstance(app.focused, Button)


async def test_erro_de_api_vira_mensagem_sem_stack(app, falso):
    async with app.run_test(size=TAM) as pilot:
        from oma_spotify.services.modelos import ErroSpotify
        def estourar():
            raise ErroSpotify("O Spotify negou o acesso.", 403)
        falso.curtidas = estourar
        pg = await ir(app, pilot, "3", PaginaBiblioteca)
        assert await esperar(pilot, lambda: "negou" in str(pg.query_one("#vazio").render()))
        falso.proxima = lambda: (_ for _ in ()).throw(RuntimeError("boom interno"))
        await pilot.press("1")
        await pilot.pause(0.3)
        await pilot.press("n")
        assert await esperar(pilot, lambda: any("Algo deu errado" in n.message for n in app._notifications))
        assert not any("boom" in n.message or "Traceback" in n.message for n in app._notifications)
