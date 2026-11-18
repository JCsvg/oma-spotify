"""Diálogos: ir para, opções (o e botão direito), tocar em, adicionar à playlist, teclas, ajuda, conta e confirmar."""

from oma_spotify.ui.dialogos import (AdicionarPlaylist, AjudaCompleta, Confirmar, IrPara, MenuConta, Opcoes, Pedir, Teclas,
                                     TocarEm, casar)
from oma_spotify.ui.lista import Lista
from tests.conftest import esperar, janela, pronto

GRANDE = (180, 48)
P1 = {"uri": "spotify:playlist:p1", "tipo": "playlist", "nome": "Mesa de sexta", "id": "p1", "meu": True, "sub": "demo"}


def test_casar_letras_em_ordem():
    assert casar("Mesa de sexta", "mesa") == [0, 1, 2, 3]
    assert casar("Mesa de sexta", "mdx") == [0, 5, 10]
    assert casar("Mesa", "z") is None


async def test_ir_para_filtra_e_abre(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("ctrl+p")
        await pilot.pause(0.3)
        assert isinstance(app.screen, IrPara)
        await pilot.press(*"estrada")
        await pilot.pause(0.2)
        res = app.screen.query_one("#res", Lista)
        item = res.item_atual()
        assert item[1] == "Estrada"
        assert "de" in str(app.screen.query_one("#conta-q").render())
        assert res.itens[-1][1].startswith("buscar “estrada”")
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["item"]["nome"] == "Estrada" and janela(app) == "principal"


async def test_ir_para_comando_e_busca_no_catalogo(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("ctrl+p")
        await pilot.pause(0.3)
        await pilot.press(*"aleat")
        await pilot.pause(0.2)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: falso.aleat)
        await pilot.press("ctrl+p")
        await pilot.pause(0.3)
        await pilot.press(*"zzz")
        await pilot.pause(0.2)
        await pilot.press("enter")
        await pilot.pause(0.6)
        assert app.query_one("#principal").vista == {"t": "busca", "q": "zzz", "cat": "tudo"}


async def test_ir_para_t_toca_pela_lista(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("ctrl+p")
        await pilot.pause(0.3)
        await pilot.press(*"madru")
        app.screen.query_one("#res").focus()
        await pilot.press("t")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][1] == "spotify:playlist:p3")


async def test_opcoes_por_tecla_e_por_botao_direito(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "item", "item": P1})
        await pilot.pause(0.8)
        await pilot.press("o")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Opcoes)
        ids = [o[0] for o in app.screen.opcoes if o]
        assert ids[:4] == ["tocar", "seguir", "curtir", "playlist"] and ids[-1] == "remover"
        assert app.screen.opcoes[-1][4] is True  # remover em vermelho, por último
        await pilot.press("f")
        await pilot.pause(0.3)
        assert len(app.minha_fila) == 1
        lista = app.query_one("#faixas", Lista)
        await pilot.click(lista, offset=(20, 3), button=3)
        await pilot.pause(0.3)
        assert isinstance(app.screen, Opcoes)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, Opcoes)


async def test_opcoes_fixar_na_biblioteca(app, config):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("bib")
        bib = app.query_one("#lista", Lista)
        i = next(n for n, x in enumerate(bib.itens) if x.nome == "Faróis")
        bib.mover_cursor(i)
        await pilot.pause(0.1)
        await pilot.press("o")
        await pilot.pause(0.3)
        assert any(o and o[0] == "fixar" for o in app.screen.opcoes)
        await pilot.press("P")
        await pilot.pause(0.3)
        assert config.fixados[-1] == "spotify:album:a1" and len(config.fixados) == 7
        assert any(x.nome == "Faróis" and app.query_one("#bib").numero(x) == "7" for x in bib.itens)
        await pilot.press("P")
        await pilot.pause(0.3)
        assert "spotify:album:a1" not in config.fixados


async def test_tocar_em_transfere_e_ajusta_volume(app, falso, plugin):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("d")
        await pilot.pause(0.4)
        assert isinstance(app.screen, TocarEm)
        l = app.screen.query_one("#aparelhos", Lista)
        nomes = [getattr(d, "nome", None) or d[1] for d in l.itens]
        assert nomes[:4] == ["OmaSpotify", "celular", "sala", "tv do quarto"]
        await pilot.press("down", "right")
        assert await esperar(pilot, lambda: ("volume", 45, "d2") in falso.chamadas)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: ("transferir", "d2") in falso.chamadas)
        assert not isinstance(app.screen, TocarEm)


async def test_tocar_em_oferece_iniciar_o_plugin(app, falso, plugin):
    falso.devs = [falso.devs[1]]
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("d")
        await pilot.pause(0.4)
        l = app.screen.query_one("#aparelhos", Lista)
        i = next(n for n, d in enumerate(l.itens) if isinstance(d, tuple) and d[0] == "plugin")
        l.mover_cursor(i)
        await pilot.press("enter")
        assert await esperar(pilot, lambda: plugin.iniciou == 1 and ("transferir", "oma") in falso.chamadas, 5)


async def test_clicar_num_aparelho_da_biblioteca_transfere(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        disp = app.query_one("#disp", Lista)
        assert len(disp.itens) == 4
        await pilot.click(disp, offset=(3, 2))
        await pilot.click(disp, offset=(3, 2))
        assert await esperar(pilot, lambda: ("transferir", "d3") in falso.chamadas)


async def test_adicionar_a_playlist_com_ja_tem(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "item", "item": P1})
        await pilot.pause(0.8)
        await pilot.press("shift+down", "p")
        await pilot.pause(0.5)
        assert isinstance(app.screen, AdicionarPlaylist)
        assert app.screen.query_one("#caixa").border_title == "adicionar 2 faixas a…"
        assert await esperar(pilot, lambda: app.screen.tem.get("p1") == 2, 3)
        l = app.screen.query_one("#pls", Lista)
        nomes = [x.nome for x in l.itens if hasattr(x, "nome")]
        assert "Ordem de outra pessoa" not in nomes  # só as suas
        await pilot.press("ctrl+f")
        await pilot.press(*"estudar", "enter")
        await pilot.pause(0.2)
        await pilot.press("down")
        await pilot.press("enter")
        assert await esperar(pilot, lambda: len(falso.playlists_["p2"][1]) == 8)


async def test_adicionar_em_nova_playlist(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "curtidas"})
        await pilot.pause(0.6)
        await pilot.press("p")
        await pilot.pause(0.4)
        app.screen.query_one("#pls", Lista).mover_cursor(0)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Pedir)
        await pilot.press(*"Rock", "enter")
        assert await esperar(pilot, lambda: any(v[0] == "Rock" and len(v[1]) == 1 for v in falso.playlists_.values()))
        assert await esperar(pilot, lambda: any(i.nome == "Rock" for i in app.query_one("#bib").visiveis))


async def test_nova_playlist_pela_biblioteca(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("bib")
        await pilot.pause(0.1)
        await pilot.press("n")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Pedir)
        await pilot.press("escape")
        await pilot.click("#novo")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Pedir)


async def test_teclas_da_janela_e_ajuda_completa(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.navegar({"t": "item", "item": P1})
        await pilot.pause(0.8)
        await pilot.press("ctrl+space")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Teclas)
        assert app.screen.query_one("#caixa").border_title == "teclas · principal (playlist)"
        txt = " ".join(str(s.render()) for s in app.screen.query(".col"))
        assert "janela ao lado" in txt and "move as marcadas" in txt and "tocar / pausar" in txt
        await pilot.press("question_mark")
        await pilot.pause(0.4)
        assert isinstance(app.screen, AjudaCompleta)
        await pilot.press("escape")
        await pilot.pause(0.2)
        await pilot.press("f1")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Teclas)
        await pilot.press("f1")
        await pilot.pause(0.2)
        assert len(app.screen_stack) == 1


async def test_menu_da_conta(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.click("#conta")
        await pilot.pause(0.3)
        assert isinstance(app.screen, MenuConta)
        await pilot.press("enter")
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["t"] == "config"
        await pilot.click("#conta")
        await pilot.pause(0.3)
        l = app.screen.query_one("#opcoes", Lista)
        l.mover_cursor(len(l.itens) - 1)
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Confirmar)
        await pilot.press("escape")


async def test_remover_da_biblioteca_pede_confirmacao(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("bib")
        bib = app.query_one("#lista", Lista)
        i = next(n for n, x in enumerate(bib.itens) if x.nome == "Faróis")
        bib.mover_cursor(i)
        await pilot.press("x")
        await pilot.pause(0.3)
        assert isinstance(app.screen, Confirmar)
        await pilot.click("#sim")
        assert await esperar(pilot, lambda: "spotify:album:a1" not in falso.seguidos)
