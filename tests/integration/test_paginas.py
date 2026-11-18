"""Páginas da Principal: início, playlist (marcar, mover, desfazer), busca ao vivo, artista, podcast e listas."""

from datetime import datetime, timedelta, timezone

from oma_spotify.ui.lista import Lista
from oma_spotify.ui.paginas import (PaginaArtista, PaginaBusca, PaginaColecao, PaginaInicio, data_hoje, quando_rel, realcar,
                                    saudacao)
from oma_spotify.ui.widgets import Cartao
from tests.conftest import esperar, janela, pronto

GRANDE = (180, 48)
P1 = {"uri": "spotify:playlist:p1", "tipo": "playlist", "nome": "Mesa de sexta", "id": "p1", "meu": True, "sub": "demo"}
P5 = {"uri": "spotify:playlist:p5", "tipo": "playlist", "nome": "Ordem de outra pessoa", "id": "p5", "sub": "Júlia"}
CAIS = {"uri": "spotify:artist:r1", "tipo": "artist", "nome": "Cais 7", "id": "r1"}


def pagina(app):
    return app.query_one("#principal").pagina


async def abrir(app, pilot, vista, cond=None):
    app.navegar(vista)
    await pilot.pause(0.3)
    assert await esperar(pilot, cond or (lambda: getattr(pagina(app), "carregado", True)), 4)
    await pilot.pause(0.2)
    return pagina(app)


# ------------------------------------------------------------ funções
def test_saudacao_data_e_quando():
    assert saudacao(datetime(2026, 11, 18, 9)) == "bom dia" and saudacao(datetime(2026, 11, 18, 15)) == "boa tarde"
    assert saudacao(datetime(2026, 11, 18, 22)) == "boa noite"
    assert data_hoje(datetime(2026, 11, 18)) == "quarta, 18 de novembro"
    agora = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)
    assert quando_rel((agora - timedelta(minutes=6)).isoformat(), agora) == "há 6 min"
    assert quando_rel((agora - timedelta(days=1)).isoformat(), agora) == "ontem"
    t = realcar("Bruno Mars", "bruno", "", "green")
    assert any("underline" in str(s.style) and (s.start, s.end) == (0, 5) for s in t.spans)


# ------------------------------------------------------------ início
async def test_inicio_tem_atalhos_recentes_repeat_e_podcasts(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = pagina(app)
        assert isinstance(pg, PaginaInicio)
        assert "demo" in str(pg.query_one("#ola").render()) and "novembro" in str(pg.query_one("#data").render()) or True
        atalhos = list(pg.query("#atalhos Cartao"))
        assert len(atalhos) == 6 and atalhos[0].item.nome == "Músicas Curtidas" and atalhos[1].item.nome == "Mesa de sexta"
        rec = pg.query_one("#recentes", Lista)
        assert rec.itens[0].nome == "Cidade Acesa" and len(rec.itens) == 7  # a que toca vem primeiro
        assert "agora" in rec.render_item(rec.itens[0], 0, __import__("oma_spotify.ui.lista", fromlist=["x"]).EstadoLinha(largura=90))[0].plain
        assert len(pg.query("#repeat Cartao")) == 5 and len(pg.query("#podcasts Cartao")) == 3


async def test_inicio_setas_andam_entre_atalhos_e_secoes(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        atalhos = list(pagina(app).query("#atalhos Cartao"))
        assert app.focused is atalhos[0]
        await pilot.press("right")
        assert app.focused is atalhos[1]
        await pilot.press("down")
        assert app.focused is atalhos[4]
        await pilot.press("down")
        assert isinstance(app.focused, Lista) and app.focused.id == "recentes"
        await pilot.press("down", "enter")
        assert await esperar(pilot, lambda: falso.chamadas and falso.chamadas[-1][0] == "tocar")
        app.focused.mover_cursor(len(app.focused.itens) - 1)
        await pilot.press("down")
        assert isinstance(app.focused, Cartao) and app.focused.modo == "grande"


async def test_inicio_enter_no_atalho_abre(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("right", "enter")
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["item"]["nome"] == "Mesa de sexta"


async def test_inicio_clique_de_novo_abre(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        c = list(pagina(app).query("#atalhos Cartao"))[2]
        await pilot.click(c)
        await pilot.pause(0.1)
        assert app.focused is c and app.query_one("#principal").vista["t"] == "inicio"
        await pilot.click(c)
        await pilot.pause(0.5)
        assert app.query_one("#principal").vista["t"] == "item"


# ------------------------------------------------------------ playlist
async def test_playlist_cabecalho_e_tabela(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": P1})
        assert isinstance(pg, PaginaColecao)
        assert "┏" in str(pg.query_one("#cab-titulo").render())  # título grande
        meta = str(pg.query_one("#cab-meta").render())
        assert "demo" in meta and "24 faixas" in meta and "1 h 25 min" in meta
        lista = pg.query_one("#faixas", Lista)
        assert len(lista.itens) == 24
        cab = str(pg.query_one("#cab-tabela").render())
        assert "título" in cab and "artista" in cab and "álbum" in cab
        assert pg.query_one("#tocar").has_class("cheio")


async def test_playlist_tocando_vira_equalizador_e_hover_vira_play(app):
    from oma_spotify.ui.lista import EstadoLinha
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": P1})
        lista = pg.query_one("#faixas", Lista)
        i = next(n for n, x in enumerate(lista.itens) if x.nome == "Cidade Acesa")
        linha = lista.render_item(lista.itens[i], i, EstadoLinha(largura=100))[0].plain
        assert any(q in linha for q in ("⣸⣴", "⣦⣇", "⣴⣸", "⣇⣦", "⣀⣀"))
        hover = lista.render_item(lista.itens[0], 0, EstadoLinha(hover=True, largura=100))[0].plain
        assert "▶" in hover or "\U000F040A" in hover


async def test_playlist_enter_toca_no_contexto_e_t(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await abrir(app, pilot, {"t": "item", "item": P1})
        await pilot.press("down", "enter")
        assert await esperar(pilot, lambda: falso.chamadas[-1][:2] == ("tocar", "spotify:playlist:p1") and falso.chamadas[-1][3])
        await pilot.click("#tocar")
        assert await esperar(pilot, lambda: falso.chamadas[-1] == ("tocar", "spotify:playlist:p1", (), None))


async def test_playlist_marcar_com_shift_e_mover_com_alt_e_desfazer(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": P1})
        lista = pg.query_one("#faixas", Lista)
        antes = list(falso.playlists_["p1"][1])
        await pilot.press("down", "down", "down", "down", "down", "down")  # linha 7
        await pilot.press("shift+down")
        assert lista.marcados == {6, 7}
        assert "fila (2)" in str(app.query_one("#rodape").render())
        await pilot.press("alt+up")
        assert await esperar(pilot, lambda: ("mover", "p1", 6, 5, 2) in falso.chamadas)
        assert falso.playlists_["p1"][1][5:7] == antes[6:8]
        assert lista.marcados == {5, 6}
        assert any("subiram para 6-7" in n.message and "u desfaz" in n.message for n in app._notifications)
        await pilot.press("alt+k")
        assert await esperar(pilot, lambda: falso.playlists_["p1"][1][4:6] == antes[6:8])
        await pilot.press("u")
        assert await esperar(pilot, lambda: falso.playlists_["p1"][1][5:7] == antes[6:8])
        await pilot.press("escape")
        assert not lista.marcados


async def test_playlist_x_remove_e_u_desfaz(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": P1})
        antes = list(falso.playlists_["p1"][1])
        await pilot.press("down", "x")
        assert await esperar(pilot, lambda: len(falso.playlists_["p1"][1]) == 23)
        assert len(pg.query_one("#faixas", Lista).itens) == 23
        assert await esperar(pilot, lambda: any("removida de Mesa de sexta" in n.message for n in app._notifications))
        await pilot.press("u")
        assert await esperar(pilot, lambda: falso.playlists_["p1"][1] == antes)


async def test_playlist_filtro_e_ordem(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": P1})
        await pilot.press("ctrl+f")
        await pilot.pause(0.2)
        await pilot.press(*"farol")
        await pilot.pause(0.2)
        lista = pg.query_one("#faixas", Lista)
        assert lista.itens and all("farol" in f"{x.nome} {x.sub} {x.extra}".lower() for x in lista.itens)
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert len(lista.itens) == 24
        await pilot.click("#principal #ordem")
        await pilot.pause(0.2)
        nomes = [x.nome for x in lista.itens]
        assert nomes == sorted(nomes, key=str.lower)
        await pilot.press("alt+up")
        assert any("ordem personalizada" in n.message for n in app._notifications)


async def test_playlist_de_outra_pessoa_sem_tabela(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": P5})
        assert not pg.query("#faixas") and "playlist alheia" in str(pg.query_one("#aviso").render())
        assert pg.query("#seguir") and pg.query("#tocar")
        await pilot.click("#tocar")
        assert await esperar(pilot, lambda: falso.chamadas[-1][1] == "spotify:playlist:p5")
        await pilot.click("#seguir")
        assert await esperar(pilot, lambda: "spotify:playlist:p5" in falso.seguidos)


async def test_album_curtidas_e_podcast(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        alb = {"uri": "spotify:album:a1", "tipo": "album", "nome": "Faróis", "id": "a1", "sub": "Cais 7", "ano": "2025"}
        pg = await abrir(app, pilot, {"t": "item", "item": alb})
        assert len(pg.query_one("#faixas", Lista).itens) == 5 and pg.cols.album is False
        assert "2025" in str(pg.query_one("#cab-meta").render())
        pg = await abrir(app, pilot, {"t": "curtidas"})
        assert len(pg.query_one("#faixas", Lista).itens) == 8
        show = {"uri": "spotify:show:s1", "tipo": "show", "nome": "Conversa de Exemplo", "id": "s1"}
        pg = await abrir(app, pilot, {"t": "item", "item": show})
        assert len(pg.query_one("#faixas", Lista).itens) == 3
        assert "episódios" in str(pg.query_one("#cab-meta").render())


# ------------------------------------------------------------ busca
async def test_busca_ao_vivo_sem_enter(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await pilot.press("slash")
        await pilot.pause(0.2)
        await pilot.press(*"cais")
        assert await esperar(pilot, lambda: isinstance(pagina(app), PaginaBusca) and pagina(app).carregado, 3)
        assert janela(app) == "topo"  # o foco continua no campo
        buscas = [c for c in falso.chamadas if c[0] == "buscar"]
        assert len(buscas) == 1  # 300 ms sem tecla: uma busca só
        pg = pagina(app)
        assert pg.query("#melhor") and pg.melhor.nome == "Cais 7"
        assert len(pg.query_one("#musicas", Lista).itens) == 5
        assert app.query_one("#principal").border_title == "busca · “cais”"
        await pilot.press("enter")
        await pilot.pause(0.3)
        assert janela(app) == "principal"


async def test_busca_continua_e_esc_limpa_e_volta(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        app.focar_janela("bib")
        await pilot.pause(0.1)
        await pilot.press("slash")
        await pilot.pause(0.2)
        await pilot.press(*"cais")
        await pilot.pause(0.5)
        await pilot.press(*" 7")
        assert await esperar(pilot, lambda: pagina(app).q == "cais 7", 3)
        assert [v["t"] for v in app.historico].count("busca") == 1  # troca a busca sem empilhar páginas
        await pilot.press("escape")
        assert app.query_one("#busca").value == ""
        await pilot.press("escape")
        await pilot.pause(0.2)
        assert janela(app) == "bib"


async def test_busca_filtros_e_mais(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "busca", "q": "a", "cat": "tudo"})
        filtros = pg.query_one("#filtros")
        filtros.focus()
        await pilot.press("right")
        await pilot.pause(0.4)
        assert pg.cat == "track" and len(pg.query_one("#musicas", Lista).itens) == 10
        await pilot.click("#mais-lista")
        assert await esperar(pilot, lambda: any(c[0] == "buscar" and c[3] == 10 for c in falso.chamadas), 3)
        await pilot.press("right")
        await pilot.pause(0.4)
        assert pg.cat == "artist" and pg.query(Cartao)


async def test_busca_seta_para_cima_sobe_para_os_filtros(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "busca", "q": "cais", "cat": "tudo"})
        await pilot.pause(0.3)
        musicas = pg.query_one("#musicas", Lista)
        musicas.focus()
        musicas.mover_cursor(0)
        await pilot.press("up")
        assert app.focused is pg.query_one("#filtros")


async def test_busca_sem_resultado(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "busca", "q": "zzzz", "cat": "tudo"})
        await pilot.pause(0.3)
        assert "Nada encontrado" in str(pg.query_one("#nada").render())


# ------------------------------------------------------------ artista
async def test_artista_destaques_discografia_e_playlists(app, falso):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "item", "item": CAIS})
        assert isinstance(pg, PaginaArtista)
        assert ("buscar", 'artist:"Cais 7"', ("track",), 0) in falso.chamadas  # destaques por busca
        assert len(pg.query_one("#destaques", Lista).itens) == 5
        assert len(pg.query("#disco Cartao")) == 4
        assert await esperar(pilot, lambda: "você curtiu" in str(pg.query_one("#cab-meta").render()), 4)
        meta = str(pg.query_one("#cab-meta").render())
        assert "3 músicas" in meta and "playlists suas" in meta
        assert pg.query("#nas-playlists Cartao")
        assert "seguindo" in pg.query_one("#seguir").label
        pg.query_one("#disco-abas").definir("single", avisar=True)
        await pilot.pause(0.3)
        assert [c.item.nome for c in pg.query("#disco Cartao")] == ["Farol Baixo"]
        pg.query_one("#disco-abas").definir("appears_on", avisar=True)
        await pilot.pause(0.3)
        assert [c.item.nome for c in pg.query("#disco Cartao")] == ["Coletânea do Porto"]
        await pilot.click("#seguir")
        assert await esperar(pilot, lambda: "spotify:artist:r1" not in falso.seguidos)


async def test_a_vai_para_o_artista_da_faixa(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        await abrir(app, pilot, {"t": "curtidas"})
        await pilot.press("a")
        assert await esperar(pilot, lambda: isinstance(pagina(app), PaginaArtista), 3)
        assert pagina(app).item.nome == "Cais 7"


async def test_recentes_e_mais_ouvidos(app):
    async with app.run_test(size=GRANDE) as pilot:
        await pronto(app, pilot)
        pg = await abrir(app, pilot, {"t": "recentes"})
        await pilot.pause(0.3)
        assert len(pg.query_one("#lista-pg", Lista).itens) == 7
        pg = await abrir(app, pilot, {"t": "top"})
        await pilot.pause(0.3)
        assert len(pg.query_one("#lista-pg", Lista).itens) == 10
        pg.query_one("#top-tipo").definir("artists", avisar=True)
        await pilot.pause(0.4)
        assert pg.query_one("#lista-pg", Lista).itens[0].tipo == "artist"
