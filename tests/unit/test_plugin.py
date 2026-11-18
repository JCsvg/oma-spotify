from oma_spotify.services.modelos import Dispositivo
from oma_spotify.services.plugin import DICA_CONFIGURAR, UNIDADE, PluginOmaSpotify


def teste(tmp_path, rc=0, binario=True):
    chamadas = []

    def rodar(args, tempo=8.0):
        chamadas.append(args)
        return rc(args) if callable(rc) else rc
    if binario:
        (tmp_path / "omaspotify-backend").write_text("x")
    return PluginOmaSpotify(rodar, tmp_path), chamadas


def test_instalado_precisa_da_unidade_e_do_binario(tmp_path):
    p, ch = teste(tmp_path)
    assert p.instalado() and ch == [["systemctl", "--user", "cat", UNIDADE]]
    assert not teste(tmp_path, rc=1)[0].instalado()
    assert not teste(tmp_path / "vazio", binario=False)[0].instalado()


def test_ativo_e_iniciar_usam_o_systemctl_do_usuario(tmp_path):
    p, ch = teste(tmp_path)
    assert p.ativo() and p.iniciar()
    assert ch == [["systemctl", "--user", "is-active", "--quiet", UNIDADE], ["systemctl", "--user", "start", UNIDADE]]
    assert not teste(tmp_path, rc=3)[0].ativo()


def test_reconhece_o_dispositivo_do_plugin():
    assert PluginOmaSpotify.eh_dispositivo(Dispositivo("a", "OmaSpotify"))
    assert PluginOmaSpotify.eh_dispositivo(Dispositivo("a", "omaspotify (sala)"))
    assert not PluginOmaSpotify.eh_dispositivo(Dispositivo("a", "Notebook"))


def test_nao_le_nada_do_plugin_alem_da_existencia_do_binario(tmp_path):
    import inspect
    from oma_spotify.services import plugin
    src = inspect.getsource(plugin)
    for proibido in ("read_text", "read_bytes", "keyring", "credentials.json", "open("):
        assert proibido not in src.split('"""', 2)[2]
    assert "Finish playback setup" in DICA_CONFIGURAR
