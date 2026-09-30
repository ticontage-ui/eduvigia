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
