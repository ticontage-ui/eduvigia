# EduVigIA Chat — Commercial Security Hardening

## R3.1 — Perímetro comercial

Esta fase endurece o perímetro do Chat sem integrar ainda a identidade do Core.

Implementado nesta fase:

- PostgreSQL sem `ports` publicados no host;
- Redis sem `ports` publicados no host;
- Chat API sem `ports` publicados no host;
- signaling/API interno do LiveKit sem `ports` publicados no host;
- ICE do LiveKit permanece publicado, pois é necessário ao WebRTC;
- frontend exposto somente por HTTPS (`16443`) e WSS LiveKit (`16444`);
- HTTP legado `15187` deixa de ser publicado;
- TLS 1.2/1.3;
- HSTS;
- `nosniff`;
- `X-Frame-Options`;
- Referrer Policy;
- Permissions Policy com microfone restrito ao próprio origin;
- CSP;
- FastAPI Swagger/ReDoc/OpenAPI públicos desabilitados;
- secrets reais continuam somente nos arquivos locais ignorados pelo Git;
- nenhum volume é apagado;
- nenhum histórico é apagado;
- nenhum secret é rotacionado automaticamente.

## Estado de segurança após R3.1

R3.1 NÃO significa release comercial final.

Ainda é obrigatório concluir:

1. R3.2 — Identity & Session Hardening
   - remover `identity_provider=mock`;
   - eliminar seletor manual de identidade;
   - não aceitar `identity_id` como autoridade vinda do browser;
   - autenticar REST e WebSocket;
   - ticket curto para WebSocket;
   - vincular PTT, mensagens e Crisis à sessão autenticada.

2. R3.3 — Media Authorization Hardening
   - token LiveKit derivado exclusivamente da sessão autenticada;
   - publicação somente por `GESTOR_ESCOLA`;
   - subscription somente por atores autorizados;
   - testes negativos de spoofing.

3. R3.4 — Commercial Release Gate
   - testes automatizados;
   - Browser QA;
   - isolamento escolar;
   - secret scan;
   - backup/restore;
   - dependency scan;
   - checklist de implantação.

## Regra permanente

O Chat comercial não terá senha própria de usuário.
A autoridade de autenticação será o EduVigIA Core após a integração.

## R3.2-R2 — Server-Derived Identity Backend Cutover

Esta subfase corta a autoridade de identidade no backend quando
`CHAT_AUTH_MODE=core`, mantendo compatibilidade somente para o runtime
`standalone_qa`.

Garantias desta fase:

- REST deriva a identidade efetiva da sessao server-side em modo `core`;
- `identity_id` legado pode existir no contrato de compatibilidade, mas nao
  possui autoridade e qualquer divergencia da sessao resulta em HTTP 403;
- o endpoint de enumeracao de identidades mock retorna 404 em modo `core`;
- WebSocket principal usa ticket curto, opaco e de uso unico;
- PTT WebSocket usa ticket `PTT` vinculado ao `channel_id`;
- tickets de outra finalidade ou canal sao rejeitados;
- PTT REST deriva o ator da sessao;
- Sala de Crise deriva o ator da sessao;
- token LiveKit e alteracao de estado de audio derivam o ator da sessao;
- o browser nao pode elevar role, trocar escola ou impersonar outro usuario
  quando o modo `core` estiver ativo;
- roles legadas do Core sao canonicalizadas de forma compativel com o Core;
- `TECNICO` permanece sem acesso ao Chat;
- nenhum password store foi introduzido no Chat;
- o runtime standalone permanece disponivel apenas para QA isolado.

A interface standalone ainda envia `identity_id` durante esta fase porque o
Core nao esta unido ao mesmo origin nesta bancada. O corte do frontend ocorre
na fase seguinte, depois da integracao same-origin com o shell EduVigIA.
## R3.2-R2-HF1 — Message Write Regression

Hotfix aberto após revisão pós-fechamento do R3.2-R2.

Foram identificadas duas regressões introduzidas no cutover de identidade:

- a rota de mensagem de texto referenciava `identity["id"]` antes da
  resolução da identidade efetiva;
- a rota de mensagem com anexos recebeu uma substituição indevida dentro
  do SQL, trocando o identificador de coluna `sender_identity_id` por uma
  expressão Python literal e persistindo o hint legado em vez da
  identidade efetiva.

O HF1 restaura o contrato correto:

- em `standalone_qa`, `sender_identity_id` continua sendo apenas o hint
  legado esperado pelo adapter;
- em `core`, a sessão permanece a autoridade e qualquer divergência do
  hint legado continua retornando HTTP 403;
- toda gravação persiste `identity["id"]`, a identidade efetiva validada
  pelo servidor;
- nenhum schema é alterado;
- testes permanentes cobrem texto e anexos;
- QA mutante cria e remove mensagens reais para comprovar o fluxo.
## R3.2-R2-HF2 — PTT Floor Identity Regression

Hotfix aberto durante a revisão posterior ao fechamento do HF1.

Foi identificada uma regressão na solicitação de floor do PTT:
`effective_identity_id` era enviado ao adapter de autenticação antes de
receber qualquer valor.

O HF2 restaura o contrato correto:

- o campo legado `payload.identity_id` é utilizado apenas como hint em
  `standalone_qa`;
- em modo `core`, a sessão continua sendo a autoridade e divergências do
  hint são rejeitadas;
- após autorização, `effective_identity_id` recebe a identidade efetiva
  validada pelo servidor;
- Redis, gravação PTT e broadcast utilizam somente a identidade efetiva;
- nenhum schema é alterado;
- QA real solicita e libera o floor PTT e remove o registro de gravação
  QA produzido pelo teste.

## R3.2-R3 — Frontend Session Cutover + Same-Origin Integration Prep

Esta etapa move o frontend comercial para o contrato de sessão criado nas
etapas R3.2-R1/R2.

Contrato de frontend em modo `core`:

- o seletor de identidade standalone não participa do fluxo comercial;
- a identidade visível no navegador é somente contexto de apresentação;
- `identity_id`, `sender_identity_id`, role e escola não são enviados como
  autoridade para REST, WebSocket, PTT, Sala de Crise ou LiveKit;
- requisições mutantes usam `X-CSRF-Token`, obtido do contexto da sessão e
  mantido apenas em memória;
- WebSocket principal e PTT usam tickets curtos de uso único emitidos por
  `/api/session/ws-ticket`;
- o ticket PTT permanece vinculado ao `channel_id`;
- anexos, histórico PTT e mídia de crise usam o cookie HttpOnly da sessão;
- o bearer do Core pode ser entregue ao adapter `EduVigIAChatAuth.exchange`
  pelo shell EduVigIA, mas não é persistido pelo Chat;
- quando não existe sessão Chat válida, o frontend emite o evento
  `eduvigia:chat-auth-required` e permanece fail-closed;
- quando a sessão é criada/restaurada, o frontend emite
  `eduvigia:chat-auth-ready`.

A sessão comercial usa renovação deslizante. O endpoint
`/api/session/context` devolve o CSRF token da sessão para o JavaScript
same-origin, renova a expiração Redis e reemite o cookie HttpOnly/Secure.

Preparação same-origin:

- standalone mantém `/api` e `/ws`;
- o shell integrado pode definir antes dos scripts:

  `window.EduVigIAChatConfig = { apiBase: "/api/chat", wsBase: "/ws/chat" }`;

- nenhum segredo ou token de sessão é incorporado nesses caminhos;
- a integração final continua sem iframe e sem banco compartilhado.

Compatibilidade:

- `standalone_qa` mantém o seletor mock/localStorage exclusivamente para
  bancada;
- o modo comercial `core` não consulta `/api/emergency/identities`;
- a ativação real de `CHAT_AUTH_MODE=core` continua bloqueada até a
  conectividade controlada com o Core estar disponível.
## R3.2-R5.1 — Persistent Topology + Same-Origin Ingress

Objetivo desta subfase: tornar persistente a conectividade entre Core e Chat
sem ativar ainda o `CHAT_AUTH_MODE=core` no runtime principal.

Contrato:

- rede Docker externa compartilhada: `eduvigia_integration`;
- Core API publica o alias interno `eduvigia-core-api`;
- Chat API publica o alias interno `eduvigia-chat-api`;
- LiveKit publica o alias interno `eduvigia-chat-livekit`;
- o proxy principal participa da rede de integração;
- REST do Chat fica preparado em `/api/chat/...`;
- WebSocket principal/PTT ficam preparados em `/ws/chat` e `/ws/chat/...`;
- mídia autenticada possui alias `/media/chat/...`;
- signaling LiveKit fica preparado em `/rtc/chat/...`;
- o proxy principal permite microfone somente para `self`;
- Docker DNS é resolvido em runtime para não tornar a disponibilidade do
  Core dependente da disponibilidade momentânea do Chat;
- `CHAT_AUTH_MODE` do runtime principal permanece `standalone_qa`;
- o cutover para `core` e a alteração do `CRISIS_LIVEKIT_PUBLIC_URL` para
  o endpoint same-origin pertencem às próximas subfases;
- nenhuma base de dados é compartilhada entre Core e Chat;
- nenhum segredo é movido para o Git.
