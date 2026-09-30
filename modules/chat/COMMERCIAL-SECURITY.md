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