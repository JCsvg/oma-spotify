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

## 5. Navegação (decisão do JC, mensagem de 17/11/2026, implementada pelo agente)

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
