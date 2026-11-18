"""Layout por tamanho, foco e navegação entre janelas (Ctrl+setas, Ctrl+hjkl, Tab), gavetas e zoom."""

import pytest

from oma_spotify.ui.biblioteca import Biblioteca
from oma_spotify.ui.lista import Lista
from tests.conftest import janela, pronto

GRANDE = (180, 48)


@pytest.mark.parametrize("tam,bib,direita", [((180, 48), True, True), ((150, 40), True, True), ((130, 40), True, False),
                                             ((90, 30), False, False)])
async def test_layout_por_largura(app, tam, bib, direita):
    async with app.run_test(size=tam) as pilot:
        await pronto(app, pilot)
        assert app.janela_visivel("bib") == bib
        assert app.janela_visivel("tocando") == direita and app.janela_visivel("fila") == direita
        assert app.janela_visivel("principal") and app.janela_visivel("player") and app.janela_visivel("topo")
        topo, player = app.query_one("#topo"), app.query_one("#player")
        assert topo.region.y == 0 and topo.region.height == 1
        assert player.region.bottom == tam[1] - 1  # o rodapé fica na última linha
        if bib:
            assert app.query_one("#bib").region.width == (34 if tam[0] >= 150 else 30)
        if direita:
            assert app.query_one("#direita").region.width == 41


async def test_bordas_so_nas_janelas_de_conteudo(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        for n in ("principal", "tocando", "fila"):
            assert app.janela(n).has_class("janela")
        for n in ("topo", "bib", "player"):
            assert not app.janela(n).has_class("janela")
        assert app.query_one("#principal").border_title == "início"
        assert app.query_one("#tocando").border_title == "tocando"
        assert "fila" in str(app.query_one("#fila").border_title) and "letra" in str(app.query_one("#fila").border_title)


async def test_foco_acende_a_janela(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        assert janela(app) == "principal"
        p, t = app.query_one("#principal"), app.query_one("#tocando")
        assert p.styles.border_top[1] != t.styles.border_top[1]
        app.focar_janela("bib")
        await pilot.pause(0.2)
        assert app.query_one(Biblioteca).has_class("-foco")


@pytest.mark.parametrize("de,tecla,para", [
    ("bib", "ctrl+right", "principal"), ("bib", "ctrl+up", "topo"), ("bib", "ctrl+down", "player"),
    ("principal", "ctrl+left", "bib"), ("principal", "ctrl+up", "topo"), ("principal", "ctrl+down", "player"),
    ("tocando", "ctrl+left", "principal"), ("tocando", "ctrl+down", "fila"), ("tocando", "ctrl+up", "topo"),
    ("fila", "ctrl+left", "principal"), ("fila", "ctrl+up", "tocando"), ("fila", "ctrl+down", "player"),
    ("bib", "ctrl+l", "principal"), ("principal", "ctrl+h", "bib"), ("tocando", "ctrl+j", "fila"), ("fila", "ctrl+k", "tocando"),
])
async def test_ctrl_setas_seguem_a_tabela_do_design(app, de, tecla, para):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela(de)
        await pilot.pause(0.15)
        assert janela(app) == de
        await pilot.press(tecla)
        await pilot.pause(0.15)
        assert janela(app) == para


async def test_principal_para_a_direita_escolhe_pela_linha_do_cursor(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        await pilot.pause(0.6)
        lista = app.query_one("#faixas", Lista)
        lista.focus()
        lista.mover_cursor(0)
        await pilot.pause(0.1)
        await pilot.press("ctrl+right")
        assert janela(app) == "tocando"  # o cursor está na altura do Tocando
        app.focar_janela("principal")
        lista.mover_cursor(len(lista.itens) - 1)
        await pilot.pause(0.1)
        y = lista.region.y + lista._y[lista.cursor] - int(lista.scroll_offset.y)
        alvo = "fila" if y >= app.query_one("#fila").region.y else "tocando"
        await pilot.press("ctrl+right")
        assert janela(app) == alvo


async def test_player_e_topo_voltam_para_a_ultima_janela(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("fila")
        await pilot.pause(0.1)
        await pilot.press("ctrl+down")
        assert janela(app) == "player"
        await pilot.press("ctrl+up")
        assert janela(app) == "fila"
        app.focar_janela("bib")
        await pilot.pause(0.1)
        await pilot.press("ctrl+up")
        assert janela(app) == "topo"
        await pilot.press("ctrl+down")
        assert janela(app) == "bib"


async def test_tab_passa_pelas_janelas_na_ordem(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("topo")
        await pilot.pause(0.1)
        vistos = [janela(app)]
        for _ in range(5):
            await pilot.press("tab")
            await pilot.pause(0.1)
            vistos.append(janela(app))
        assert vistos == ["topo", "bib", "principal", "tocando", "fila", "player"]
        await pilot.press("tab")
        assert janela(app) == "topo"
        await pilot.press("shift+tab")
        assert janela(app) == "player"


async def test_ctrl_setas_no_campo_de_busca_andam_por_palavra(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("slash")
        await pilot.pause(0.2)
        await pilot.press(*"cais sete")
        campo = app.query_one("#busca")
        assert campo.cursor_position == 9
        await pilot.press("ctrl+left")
        assert janela(app) == "topo" and campo.cursor_position == 5


async def test_clique_foca_a_janela(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.click("#lista")
        assert janela(app) == "bib"
        await pilot.click("#fila-lista")
        assert janela(app) == "fila"
        await pilot.click("#recentes")
        assert janela(app) == "principal"
        await pilot.click("#play")
        assert janela(app) == "player"


async def test_colchetes_escondem_e_mostram_as_laterais(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("left_square_bracket")
        assert not app.janela_visivel("bib")
        await pilot.press("left_square_bracket")
        assert app.janela_visivel("bib")
        await pilot.press("right_square_bracket")
        assert not app.janela_visivel("tocando")
        await pilot.press("right_square_bracket")
        assert app.janela_visivel("tocando")


async def test_meia_tela_gavetas_por_teclado_e_esc(app):
    async with app.run_test(size=(90, 30)) as pilot:
        await pronto(app, pilot)
        assert not app.janela_visivel("bib")
        await pilot.press("left_square_bracket")
        await pilot.pause(0.3)
        assert app.gaveta == "bib" and app.query_one("#bib").has_class("-gaveta") and janela(app) == "bib"
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert app.gaveta == "" and janela(app) == "principal"
        await pilot.press("right_square_bracket")
        await pilot.pause(0.3)
        assert app.gaveta == "dir" and janela(app) == "tocando"
        await pilot.press("escape")
        assert app.gaveta == ""


async def test_gaveta_enter_abre_e_fecha(app):
    async with app.run_test(size=(90, 30)) as pilot:
        await pronto(app, pilot)
        await pilot.press("left_square_bracket")
        await pilot.pause(0.3)
        await pilot.press("down", "enter")
        await pilot.pause(0.5)
        assert app.gaveta == "" and app.query_one("#principal").vista["t"] == "item"


async def test_meia_tela_sem_coluna_de_album_e_player_encolhido(app):
    async with app.run_test(size=(90, 30)) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        await pilot.pause(0.6)
        pg = app.query_one("#principal").pagina
        assert pg.cols.album is False
        assert app.query_one("#player").has_class("-estreito")
        assert app.query_one("#player #aleatorio").region.width == 0 and app.query_one("#play").region.width > 0


async def test_baixo_player_numa_linha_e_tocando_sem_capa(app):
    async with app.run_test(size=(180, 28)) as pilot:
        await pronto(app, pilot)
        assert app.query_one("#player").region.height == 1
        assert not app.query_one("#tc-capa").display


async def test_zoom_na_principal_e_na_biblioteca(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("z")
        assert app.zoom == "principal" and not app.janela_visivel("bib") and not app.janela_visivel("tocando")
        await pilot.press("z")
        assert app.zoom == "" and app.janela_visivel("bib")
        app.focar_janela("bib")
        await pilot.pause(0.1)
        await pilot.press("z")
        assert app.zoom == "bib" and not app.janela_visivel("principal")
        await pilot.press("escape")
        assert app.zoom == ""


async def test_numeros_abrem_curtidas_e_fixados(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("0")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "curtidas" and janela(app) == "principal"
        await pilot.press("2")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["item"]["nome"] == "Para estudar (exemplo)"
        await pilot.press("9")
        await pilot.pause(0.2)
        assert any("Nada fixado no 9" in n.message for n in app._notifications)


async def test_numeros_e_letras_digitam_no_campo(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("slash")
        await pilot.pause(0.2)
        await pilot.press("1", "2", "space", "q", "c")
        assert app.query_one("#busca").value == "12 qc" and janela(app) == "topo"
        assert falso.tocando and app.is_running


async def test_alt_setas_voltam_e_avancam_paginas(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        await pilot.pause(0.4)
        app.navegar({"t": "recentes"})
        await pilot.pause(0.4)
        app.focar_janela("principal")
        await pilot.press("alt+left")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "curtidas"
        await pilot.press("alt+h")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "inicio"
        await pilot.press("alt+right")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "curtidas"
        await pilot.click("#voltar")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "inicio"
        await pilot.click("#avancar")
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "curtidas"


async def test_trilha_clicavel(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        await pilot.pause(0.4)
        trilha = app.query_one("#trilha")
        assert [p for p, _ in trilha.partes] == ["início", "Músicas Curtidas"]
        await pilot.click("#trilha", offset=(1, 0))
        await pilot.pause(0.3)
        assert app.query_one("#principal").vista["t"] == "inicio"


async def test_navegar_apos_voltar_descarta_o_futuro(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        app.navegar({"t": "recentes"})
        app.voltar_pagina()
        app.navegar({"t": "top"})
        await pilot.pause(0.3)
        assert [v["t"] for v in app.historico] == ["inicio", "curtidas", "top"]


async def test_rodape_mostra_as_teclas_da_janela_e_e_clicavel(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        rod = app.query_one("#rodape")
        txt = str(rod.render())
        assert "enter abrir" in txt and "ctrl+hjkl janelas" in txt and "ctrl+espaço ajuda" in txt
        app.focar_janela("player")
        await pilot.pause(0.3)
        assert "controles" in str(rod.render())
        x = next(a for a, b, acao in rod._x if acao.endswith("teclas"))
        await pilot.click("#rodape", offset=(x, 0))
        await pilot.pause(0.3)
        from oma_spotify.ui.dialogos import Teclas
        assert isinstance(app.screen, Teclas)


async def test_arrastar_a_divisa_muda_a_largura(app, estado):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.mudar_largura("bib", 40)
        await pilot.pause(0.2)
        assert app.query_one("#bib").region.width == 40
        assert estado.dados["larguras"]["bib"] == 40
        app.mudar_largura("dir", 10)
        await pilot.pause(0.2)
        assert app.query_one("#direita").region.width == 24  # mínimo
