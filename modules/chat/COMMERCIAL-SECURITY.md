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
## R3.2-R1 — Session Authority Foundation

Esta subfase prepara a autoridade comercial de sessão sem quebrar o
runtime standalone antes da integração com o Core.

Contratos adicionados:

- o Chat continua sem senha própria de usuário;
- `CHAT_AUTH_MODE=core` é o alvo comercial;
- `standalone_qa` existe somente para QA isolado enquanto Core e Chat
  ainda estão em runtimes separados;
- o token Bearer do Core é usado apenas no exchange inicial;
- o Chat cria sessão opaca própria em Redis;
- o cookie do Chat é `HttpOnly`, `Secure` e `SameSite=Strict`;
- o cookie não contém identidade, role, escola ou token do Core;
- o Redis armazena somente a sessão do Chat, nunca a senha do usuário;
- mutações autenticadas terão CSRF vinculado à sessão;
- WebSocket comercial utilizará ticket opaco, curto e de uso único;
- tickets WebSocket são armazenados por hash e consumidos atomicamente;
- `Origin` WebSocket deve ser HTTPS e same-origin;
- identidade comercial é derivada de `/auth/me` do Core;
- escola é resolvida pelo Core e precisa de código institucional;
- identidades comerciais usam `core:user:<id>`;
- a sincronização server-side provisiona memberships sem confiar no browser;
- `TECNICO` não recebe acesso ao Chat por este adapter;
- nenhum secret de assinatura é enviado ao navegador.

R3.2-R1 ainda NÃO substitui os parâmetros `identity_id` dos endpoints
legados. A troca efetiva de REST, WebSocket, PTT, Crisis e LiveKit ocorre
em R3.2-R2 após a fundação ser validada.

O runtime atual permanece `standalone_qa`; uma release comercial só pode
ser certificada com `CHAT_AUTH_MODE=core`.
