# Decisões técnicas, oma-spotify

Fatos sobre as escolhas do projeto. Cada decisão diz quem a tomou.

## 1. O que a API do Spotify oferece hoje (levantamento do agente, 17/11/2026)

Fontes lidas: changelog de fevereiro de 2026, regras de redirect URI e modos de cota em developer.spotify.com/documentation/web-api. A página de changelog geral e as de março em diante não puderam ser lidas (404 na busca). Nada abaixo foi testado contra a conta real.

- Modo de desenvolvimento: o dono do app precisa ter Premium; até 5 usuários autenticados, cada um cadastrado em User Management (fora da lista, a API responde 403); cota compartilhada entre os apps do mesmo desenvolvedor, 429 com motivo QUOTA_EXCEEDED. O modo estendido só é concedido a organizações com mais de 250 mil usuários ativos, então não é opção para uso pessoal.
- Redirect URI: HTTPS, exceto loopback. Loopback só com IP literal (`http://127.0.0.1:PORTA/...` ou `[::1]`), `localhost` não é aceito. Precisa ser idêntico ao registrado, exceto a porta quando o registro é sem porta. O app registra e usa `http://127.0.0.1:<porta>/callback`, porta padrão 8888, configurável.
- Removidos em fevereiro de 2026, e o que o app usa no lugar: salvar, remover e conferir itens da biblioteca e seguir artistas passam por `PUT/DELETE /me/library` e `GET /me/library/contains` (parâmetro `uris`); itens de playlist em `/playlists/{id}/items` (o campo da resposta virou `item`, o app lê `item` e, por compatibilidade, `track`); criar playlist em `POST /me/playlists`.
- `GET /search`: `limit` máximo caiu de 50 para 10. O app pede 10.
- Itens de playlist só vêm para as playlists do próprio usuário.
- Campos removidos que o app não usa: popularidade, seguidores, `available_markets`, `product`, e-mail e país do usuário.
- Mantido sem alteração no changelog de fevereiro (usado pelo app, mas não conferido ao vivo): `/me/player` e subrotas, `/me/player/queue`, `/me/player/recently-played`, `/me/top/{tipo}`, `/me/tracks`, `/me/albums`, `/me/following` (lista), `/me/shows`, `/me/playlists` (GET), `/albums/{id}/tracks`, `/artists/{id}/albums`.

### O que NÃO foi implementado por restrição da API

- Recomendações, features de áudio, artistas relacionados e playlists editoriais: restritos para apps novos desde novembro de 2024 (conhecimento prévio, não relido na documentação desta data). Não há tela para eles.
- Músicas mais tocadas de um artista (`/artists/{id}/top-tracks`) e lançamentos (`/browse/new-releases`), categorias (`/browse/categories`): removidos em fevereiro de 2026. Abrir um artista lista os álbuns e singles dele.
- Seguir ou deixar de seguir artista pelo app: o endpoint existe (`PUT/DELETE /me/library` com URI de artista) e a tecla `c` o chama em artistas, mas isso não foi conferido ao vivo.
- Tocar a partir de um ponto da fila: a API só adiciona à fila e pula (próxima). A tecla Enter na fila do Tocando agora explica isso.
- Capa do álbum: não implementada. O pacote `python-pillow` não está instalado nem é dependência. A capa é um quadrado com as iniciais da faixa.

## 2. HTTP com a biblioteca padrão (decisão do agente)

`python-httpx` não está no Arch deste computador e `python-requests` é uma dependência a mais sem necessidade. O cliente usa `urllib.request`, então a única dependência de execução é `python-textual`. 429: espera o `Retry-After` (mínimo 0,5 s, máximo 10 s) e tenta até 4 vezes. 401: renova o token uma vez e repete.

## 3. Login (decisão do agente)

Authorization Code com PKCE (S256), sem client secret. Servidor de retorno em `127.0.0.1:<porta>` só durante o login, com validação do `state`; ele não escreve log (a URL de retorno traz o código). Escopos pedidos: leitura e modificação do player, leitura do que está tocando e de recentes, mais ouvidos, leitura e escrita da biblioteca, leitura de quem o usuário segue, leitura e escrita de playlists (públicas e privadas, e colaborativas na leitura).

Tokens: `$XDG_STATE_HOME/oma-spotify/tokens.json`, arquivo 0600 numa pasta 0700, gravado por arquivo temporário e `os.replace`. O Client ID fica em `$XDG_CONFIG_HOME/oma-spotify/config.json`. O app não usa `logging` e não imprime tokens. O estado de contexto recusa chaves que pareçam token, Client ID, e-mail ou conta.

## 4. Cliente fino e falso (decisão do agente, no molde do oma-docker)

`services/api.py` (`ClienteSpotify`) e `services/falso.py` (`ClienteFalso`) têm a mesma interface, sem classe base. A interface só conhece essa forma. `--demo` usa o falso, com artistas e faixas fictícios ou de domínio público. Os testes de API usam um servidor HTTP falso em 127.0.0.1 (`tests/fake_api.py`); nenhum teste fala com a rede.

## 5. Navegação por abas (0.1, SUPERADA pela seção 11)

Trocar de aba só com Alt+←/→ ou Alt+h/l (valem também em campo de texto), números 1 a 9 fora de campo de texto, e clique na aba. As abas não recebem foco, então as setas não as trocam. ↑ ↓ j k andam nas linhas; ← → h l andam entre botões e painéis da mesma tela. No Tocando agora, ← → só buscam a posição quando a barra de progresso está em foco. Demais teclas: Ctrl+j/k, Ctrl+h/l, Ctrl+Enter, Esc, Ctrl+Espaço e F1, `/`. Espaço é play/pausa global fora de campo de texto. O código de `ui/navegacao.py` e a tela de abertura vêm do oma-docker.

## 6. Atualização do Tocando agora (decisão do agente)

Consulta a `/me/player` a cada 2 s, só quando a aba está visível e nenhum diálogo está aberto, numa thread. A barra é interpolada localmente a cada 0,25 s. A fila é buscada quando a faixa muda e a cada 15 s. Cada ação (próxima, curtir, volume...) força uma consulta logo depois.

## 7. Abertura e contexto (pedido do JC, igual ao oma-docker)

Marcador `abertura-mostrada` e `estado.json` (versão 1) em `$XDG_RUNTIME_DIR/oma-spotify/`. Dados salvos: aba, linha, filtro, categoria e texto da busca de cada aba. A opção "Mostrar a abertura" fica em `config.json` e vem ligada.

## 8. Sem dispositivo ativo (decisão do agente)

404 com motivo `NO_ACTIVE_DEVICE` abre um diálogo com "Abrir o Spotify do PC" e "Escolher dispositivo". O primeiro roda `spotify` (desacoplado do terminal), consulta `/me/player/devices` a cada 1,5 s por até 45 s, transfere a reprodução para o primeiro dispositivo do tipo Computer (ou o primeiro que aparecer) e repete a ação que falhou.

## 9. Marcas e texto (decisão do agente)

Marcas como o coração de curtida usam `rich.text.Text`, nunca strings com colchetes interpretadas como markup.

## 10. Login com tela de espera (0.1.1, pedido do JC após erro real)

Fato relatado: o Spotify mostrou "redirect_uri: Not matching configuration" enquanto o app esperava em silêncio por até 180 s. Mudanças: `Sessao.iniciar_login` devolve um `Login` (url, tempo restante, reabrir, cancelar); cancelar fecha o servidor da porta na hora (idempotente). A tela mostra contagem regressiva, copiar link (wl-copy se existir, senão mostra o link), ajuda de erros comuns depois de 15 s ou por botão, e "Verificar configuração" (`services/diagnostico.py`: Client ID mascarado com 4 e 4 caracteres, Redirect URI, porta livre, HEAD em accounts.spotify.com; nenhuma chamada autenticada). Client ID validado como 32 hexadecimais após trim (antes exigia 10 caracteres). Erros da troca de código por tipo (`invalid_client`, `invalid_grant`, `invalid_request`), sem texto genérico.

## 11. Redesign 0.2.0: uma tela, como o Spotify Web (pedido do JC, SUPERADO pela seção 12)

Pedido: interface com a localização das coisas do Spotify Web, sem abas, navegável por teclado e mouse. Referência: captura do Spotify Web do JC.

- **Estrutura** (`ui/`): `BarraTopo`, `Biblioteca`, `AreaCentral` (com `VistaInicio` e `VistaLista`, e `PaginaConfig` para as configurações), `PainelAgora`, `BarraPlayer`, `CartaCapa` e `Capa`. As telas das abas antigas (Fila, Recentes, Mais ouvidos, Dispositivos, Configurações) continuam, agora alcançáveis pelo menu Conta e pelos botões do player (Fila, Dispositivos).
- **Navegação** (decisão do JC): Alt+←/→ entre biblioteca, centro e painel; Alt+↑/↓ entre barra superior, centro e player; ↑↓←→ e hjkl andam por posição na tela dentro da área; Enter abre ou toca; Espaço play/pausa; `/` busca; Esc, Backspace, Alt+[ e Alt+] no histórico. O código de movimento (`App.action_mover`) escolhe o controle vizinho pela geometria da tela, então vale para qualquer layout.
- **Conflito do pedido, resolvido pelo agente:** o pedido listou "l curtir" e também h/l como setas. Mantive h/l como setas (esquerda e direita, como no nvim) e deixei `c` para curtir. Outras teclas de lista que colidiam com as de mídia: remover da playlist virou `d` (só dentro de listas), adicionar a playlist `m`.
- **Layout adaptável:** painel direito some abaixo de 120 colunas, a biblioteca recolhe abaixo de 100 (só miniaturas). Ctrl+P e Ctrl+B alternam por preferência.
- **Capas** (`ui/capa.py`): meio-bloco ▀ com cor de frente e de fundo de 24 bits (2 pixels por célula na vertical), reduzidas pelo Pillow (LANCZOS). Imagens baixadas por https, no máximo 3 MB, cache em `$XDG_CACHE_HOME/oma-spotify` (pasta 0700, nome é o SHA-1 da URL, poda dos mais antigos acima de 50 MB). A URL da imagem nunca vai para log nem para o estado. Fallback para quadrado com iniciais se faltar Pillow, rede ou o download falhar. Sixel do foot não foi avaliado: o meio-bloco funciona igual em qualquer terminal. No `--demo` as capas são procedurais (gradiente, anéis, listras e xadrez a partir do URI), sem imagem de terceiros. Pillow virou dependência do pacote.
- **Início:** só com o que a API entrega: acesso rápido (Músicas Curtidas e 7 playlists e álbuns da biblioteca), tocados recentemente, seus programas, seus artistas, suas playlists, seus álbuns, mais ouvidos (artistas, quando a API deixa). Não há feed Home, novos lançamentos, categorias nem recomendações (ver seção 1). "Novo lançamento de" e "Prévia da letra" do Spotify Web não existem aqui.
- **Estado salvo** (`$XDG_RUNTIME_DIR`, sem segredos): histórico de páginas (até 30, com linha selecionada), painel aberto, biblioteca recolhida, filtro e chip da biblioteca, texto da busca.
- **Busca:** a caixa fica na barra superior; o centro mostra os resultados com chips Tudo, Músicas, Álbuns, Artistas, Playlists e Podcasts (`show` entrou nos tipos pedidos, limit 10).
- **Prints:** o de 80x24 foi gerado pelo próprio Textual (`save_screenshot`, convertido com ImageMagick), porque a janela do foot no Hyprland ocupa a workspace inteira e não dá para reduzi-la sem mexer no gerenciador de janelas.

## 12. 0.3.0: janelas, sem capas, tocar pelo plugin (pedido do JC; a parte de janelas e navegação foi SUPERADA pela seção 13, o plugin continua valendo)

Feedback do JC sobre a 0.2.0: não quer algo idêntico ao Spotify Web, não quer imagens de álbum, quer cada parte como uma janela com borda e título, Ctrl+setas entre as janelas, e não gostou do diálogo "Nenhum dispositivo do Spotify ativo".

- **Capas e Pillow removidos** (código, cache em `~/.cache/oma-spotify`, dependência, testes). As listas são só texto.
- **Janelas** (`.janela` no CSS, `border_title` numerado): [1] Busca, [2] Biblioteca, [3] Principal, [4] Fila (antigo painel direito, alternável) e [5] Player. A janela com foco (`:focus-within`) tem borda e título na cor de destaque; as outras ficam discretas. O subtítulo da [3] mostra a página aberta. O Início é uma lista de texto com seções (acesso rápido, tocados recentemente, programas, artistas, playlists, álbuns, mais ouvidos).
- **Navegação** (decisão do JC, substitui a da seção 11): Ctrl+setas e Ctrl+h/j/k/l movem o foco para a janela mais próxima na direção (`App.action_janela`, por geometria da tela, preferindo janelas que se sobrepõem no eixo perpendicular); Alt+setas e Alt+hjkl são apelidos; 1 a 5 saltam direto (a 4 e a 2 mostram a janela se estiver escondida). Dentro da janela, ↑↓ andam nas linhas e ←→ nos botões da mesma fileira. No player os botões (aleatório, anterior, play, próxima, repetir, curtir, fila, dispositivos, vol−, vol+) são alcançáveis por ←→, a barra de progresso é focável (←→ buscam 5 s), a barra de volume só responde a clique, a `+`/`-` e aos botões vol−/vol+. Em diálogos, os mesmos atalhos andam entre botões e seções.
- **Janelas em 80x24:** a [4] some (precisa de 120 colunas), a [2] estreita (24 colunas) e linhas longas são cortadas com reticências na largura da janela. A [5] tem altura 5 (borda e 3 linhas).
- **Ctrl+h, j, k, l:** os terminais mandam Ctrl+h como Backspace e Ctrl+j como Enter em alguns casos. No foot do JC o Textual os distingue; não foi testado em outros terminais.

### Tocar pelo plugin OmaSpotify

Investigação (somente leitura) de `~/.config/omarchy/plugins/io.github.jeremylanger.omaspotify`, licença MIT, README, docs e scripts. Achados:

- O plugin tem um backend em Rust sobre librespot, instalado em `~/.local/lib/omaspotify/omaspotify-backend`, e a unidade de usuário `omaspotify.service` (`systemctl --user cat omaspotify.service` funciona neste PC; o serviço está parado). Ele aparece como dispositivo Spotify Connect chamado "OmaSpotify" (`device_name` em `config/playback.conf`).
- Há um protocolo local em `$XDG_RUNTIME_DIR/omaspotify/backend.sock` (JSON por linha, versão 1: `load`, `play`, `pause`, `seek`, `set_volume`...), mas o próprio plugin o descreve como interno e só o usa junto com MPRIS e Web API. **Decisão do agente:** não usar o socket. Pela Web API, o dispositivo Connect responde a tocar, pausar, volume, buscar e fila como qualquer outro, então um único caminho serve para o plugin, o celular e o Spotify do PC, e não depende de detalhes internos instáveis do plugin.
- A autorização de reprodução do plugin é separada da de conta e fica no chaveiro dele. **O oma-spotify não lê nem copia credenciais, tokens ou chaveiro do plugin** (há um teste que confere que o módulo não lê arquivos além de checar a existência do binário).

Desenho (`services/plugin.py`, `App.garantir`):

1. Alvo de reprodução = o dispositivo "OmaSpotify" listado em `/me/player/devices`. Achado, o app transfere (`play=false`) e toca.
2. Não achado e plugin instalado (a unidade existe e o binário existe): `systemctl --user start omaspotify.service`, se ainda não estiver ativo, e espera o dispositivo por até 30 s (consulta a cada 1,5 s).
3. Plugin ausente, serviço que não inicia ou dispositivo que não aparece: mensagem curta na janela [5] e aviso, dizendo o que fazer ("Abra o OmaSpotify e conclua a autorização de reprodução (Finish playback setup)"). Sem diálogo.
4. Fallback: Spotify de desktop (`/usr/bin/spotify`) como segunda opção. Em Configurações, "Tocar por": automático (padrão; plugin se instalado, senão Spotify do PC, senão escolher), plugin OmaSpotify, Spotify do PC, escolher o dispositivo (abre a página Dispositivos).
5. Sem dispositivo ativo (404 `NO_ACTIVE_DEVICE`): o diálogo antigo foi removido. O app executa o passo acima sozinho e repete a ação pedida; se a segunda tentativa também falhar em até 10 s, mostra "Ainda sem dispositivo ativo" em vez de entrar em laço.

Não testado com conta real: iniciar o serviço de verdade, o dispositivo aparecer para o Spotify e tocar por ele. Nos testes o serviço é falso (`PluginFalso`) e o cliente do Spotify também.

## 13. 0.4.0: interface do design do JC (pedido do JC)

Fonte: o README de design que o JC trouxe (mockup em 180x48, no modelo do herdr) e as imagens dele. O que o JC decidiu para esta rodada: sem imagens (texto ou glifo no lugar de capa e foto, com um ponto único para pôr imagem depois), tocar continua pelo plugin OmaSpotify como na 0.3.0, sem diálogo de "nenhum dispositivo", tudo em português do Brasil, respeitar os limites do modo de desenvolvimento e manter o app leve.

### Estrutura (decisão do agente)

- Janelas: `Topo`, `Biblioteca`, `Principal` (hospeda uma página por vez), `Tocando`, `FilaLetra`, `Player` e `Rodape`, em `ui/`. Topo, Biblioteca, Player e Rodapé sem borda; Principal, Tocando e Fila com `border: solid` na cor linha e, com foco, na cor de destaque (`:focus-within`). A Biblioteca mostra o foco no título.
- `ui/lista.py`: uma lista virtualizada própria (Line API do Textual), usada em todas as listas e tabelas. Só desenha as linhas visíveis, aceita itens de mais de uma linha, cabeçalhos não selecionáveis, hover, marcação com Shift e Ctrl+clique, botão direito, clique de novo ou duplo clique para escolher. Substitui `DataTable` e `OptionList`, que não deixavam pintar a linha inteira com a barra `▌` e o fundo de seleção.
- `ui/capa.py` é o ponto único das capas. Hoje desenha um bloco na cor do item (tirada das cores do tema por hash do URI) com a inicial, em letra grande quando cabe; artistas são redondos. Para imagem (Sixel, kitty, meio-bloco), basta trocar `linhas_capa` e `Capa.render`. Nenhuma URL de imagem é lida ou guardada.
- `ui/fonte.py`: a fonte de 3 linhas do design, copiada do README de design, usada nos títulos grandes e no palco. Acentos somem.
- `ui/icones.py`: os códigos Nerd Font da tabela do design e os caracteres simples (`"icones": "simples"`).
- Botões são um widget próprio (`Botao`), não o `Button` do Textual, para ter uma linha só e as cores do design sem brigar com o CSS padrão.
- `tema.py` calcula `oma-linha`, `oma-painel`, `oma-campo`, `oma-forte`, `oma-hover` e `oma-escuro` pelas misturas da tabela de cores. O texto mudo usa `dark_foreground` quando o tema tem (no tema atual o `muted` fica escuro demais para ler); sem ele, `muted`.

### Navegação (pedido do JC, substitui a da seção 12)

Ctrl+setas e Ctrl+hjkl vão para a janela daquele lado, escolhendo a que cruza a linha do cursor; do player para cima e do topo para baixo, a última janela de cima que teve foco. Tab e Shift+Tab na ordem topo, biblioteca, principal, tocando, fila, player. Setas e hjkl andam dentro da janela pela posição dos controles; numa lista, a ponta passa para o controle vizinho. Alt+←/→ troca aba ou página; Alt+↑/↓ move itens. As teclas de item (`t f p a y o P x u c`) valem em qualquer lista e cada janela ou página pode tratar do seu jeito (por exemplo, `x` tira da playlist sua, da sua fila, ou pede confirmação na biblioteca). No campo de busca, Ctrl+←/→ andam por palavra.

Mudaram teclas da 0.3.0: anterior e próxima viraram `,` e `.` (o `p` agora é adicionar à playlist e o `n` é nova playlist), fila a seguir é `f`, remover é `x`, os números 1 a 9 abrem os itens fixados (não pulam mais para janelas) e o painel de dispositivos virou o diálogo `d`.

### Decisões do agente que o JC pode vetar

- **A sua fila**: a API não tira nem reordena a fila do Spotify, então o app tem a própria fila (como o design pede). Entrega uma faixa por vez com `POST /me/player/queue` quando faltam 12 s, ou antes de pular com `.`. A primeira já entregue não pode mais sair. Guardada no `estado.json` (até 50 faixas, só URI e nomes).
- **Letra**: LRCLIB `GET /api/get` com o primeiro artista (com a lista inteira, a LRCLIB costuma não achar), só quando a aba letra ou o palco estão abertos. User-Agent `oma-spotify/0.4.0 (+https://github.com/JCsvg/oma-spotify)`, sem dado da conta. Falha de rede não fica em cache; 404 e instrumental ficam. Botão nas Configurações para desligar (`"letra": false`).
- **Itens fixados** ficam em `config.json` (sobrevivem ao reboot; o `estado.json` mora num tmpfs). Até 9, só itens da biblioteca. No `--demo`, as seis playlists vêm fixadas e nada é gravado.
- **`--demo` isolado**: usa `config.json` temporário e `estado.json` em `$XDG_RUNTIME_DIR/oma-spotify-demo`, para a demonstração não sujar o contexto nem a configuração reais.
- **Contagens da página do artista** ("você curtiu N músicas dele, aparece em M playlists suas"): o app conta nas curtidas que já carregou (até 100) e nas faixas das suas playlists (até 24 playlists, com cache LRU). Com muitas playlists, a primeira abertura faz uma chamada por playlist.
- **Ir para o artista ou álbum de uma faixa**: o modelo da faixa não guarda o id do artista; o app procura na biblioteca e, se não achar, faz uma busca `artist:"Nome"` (1 chamada).
- **Acréscimos à API** (nada mudou no que já existia nem na autenticação): `nome_usuario` (`/me`), `mover_na_playlist` (`PUT /playlists/{id}/items` com `range_start`, `insert_before`, `range_length`), `inserir_na_playlist` (desfazer remoção, `POST` com `position`), `buscar` com tipos e `offset`, `volume` com `device_id`, `contexto` no player, `played_at` nas recentes, ano, grupo do álbum, descrição e colaborativa nos itens, e `appears_on` na discografia. Nada disso foi conferido ao vivo.

### O que difere do design e por quê

- **Sem imagens** (decisão do JC): capas e fotos são blocos com a inicial. O Tocando mantém o tamanho do design (32x16) para a proporção das janelas não mudar.
- **Redirect URI com porta**: o design cadastra `http://127.0.0.1/callback` sem porta e escolhe uma porta livre na hora. Isso muda a autenticação, que o JC pediu para manter; o app continua mandando `http://127.0.0.1:8888/callback` (porta configurável).
- **Token**: o design diz `~/.config/oma-spotify/`; o app guarda em `$XDG_STATE_HOME/oma-spotify/tokens.json` (como na 0.3.0), e a tela de primeiro acesso mostra o caminho real.
- **Seus podcasts no início** mostram nome e editora, sem "quanto falta" nem "novo": isso exige o escopo `user-read-playback-position`, que o login não pede (pedir mudaria a autenticação e obrigaria a entrar de novo).
- **Títulos no canto direito da borda** ("só na primeira vez", "z sai do zoom", "ctrl+p"): o Textual só põe o subtítulo embaixo, então eles aparecem no canto de baixo à direita.
- **Carregando**: sem linhas pulsando; a página aparece quando os dados chegam (no demo é instantâneo).
- **Sem internet**: não há aviso fixo no topo; cada chamada que falha mostra "Sem conexão com o Spotify" no aviso do canto.
- **Arrastar faixas até uma playlist** (fase 2 no design) não foi feito.

### Memória (pedido do JC durante a rodada)

Medido com `--demo` num pseudo-terminal 180x48, lendo `VmRSS`: 0.3.0 com 48 a 51 MB em repouso e 95 MB depois de 25 rodadas de navegação e busca; 0.4.0 com 50 MB em repouso, 68 MB depois de 80 páginas e 20 buscas e 69 MB com o dobro (parou de crescer). Práticas: lista virtualizada, uma página montada por vez, histórico de 30, caches com teto (letras 12, playlists 24, busca refeita a cada página), imports preguiçosos (login, diálogos, palco, API real, LRCLIB, cliente falso), pool de 4 threads no lugar de uma thread por chamada (fechado ao sair), equalizador pausado quando a faixa para ou o terminal perde o foco, consulta ao player a cada 2 s com foco e a cada 10 s sem foco ou com diálogo aberto. `tests/integration/test_memoria.py` mede o processo real (tetos de 75 e 100 MB) e confere que navegar 50 páginas e buscar 20 vezes não deixa widgets nem mais de 25 MB para trás.

### Capturas

Geradas pelo próprio Textual (`save_screenshot`) e convertidas com `rsvg-convert`, trocando a fonte do SVG pela JetBrainsMono Nerd Font e marcando `xml:space="preserve"` (sem isso o rsvg come o espaço do começo de cada trecho e as colunas se juntam). Nenhuma captura da tela pessoal do JC.
