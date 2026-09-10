# EduVigIA 1.8.5-R1

## Fase 2 — Vídeo Seguro, WebRTC e MediaMTX

### Objetivo

Eliminar o acesso anônimo aos vídeos, disponibilizar MAIN e SUB simultaneamente e integrar o player do navegador a autorizações temporárias emitidas pela API.

### Alterações

1. O MediaMTX utiliza `authMethod: http` e consulta a API em `/internal/mediamtx-auth`.
2. Cada URL de reprodução recebe um token HMAC temporário.
3. O token contém usuário, câmera, escola, caminho, perfil e expiração.
4. Tokens não podem ser reutilizados em outra câmera ou caminho.
5. Usuários de uma escola não conseguem obter autorização para câmeras de outra escola.
6. MAIN e SUB são provisionados como caminhos distintos para cada câmera.
7. O monitor oferece seleção de qualidade econômica ou alta qualidade.
8. O frontend renova o token antes do vencimento.
9. A API não retorna URLs RTSP com credenciais.
10. Streams antigos recebem nomes protegidos com sufixo aleatório na primeira inicialização.

### Critérios de aceite

- build da API e do frontend aprovado;
- compilação Python aprovada;
- testes de Fase 1 preservados;
- testes de vídeo seguro aprovados;
- MediaMTX inicializado com autenticação HTTP;
- leitura anônima do caminho de teste negada;
- login, troca inicial de senha e emissão de token aprovados na simulação;
- reprodução autenticada do caminho de teste aprovada;
- API `/health` na versão `1.8.5-R1`;
- frontend respondendo por HTTP;
- backup e rollback preservados.

### Observações

A versão usa WebRTC como player principal. HLS é disponibilizado como endereço autenticado para uso futuro como fallback do player. HTTPS e reverse proxy unificado permanecem na fase de infraestrutura e produção.
