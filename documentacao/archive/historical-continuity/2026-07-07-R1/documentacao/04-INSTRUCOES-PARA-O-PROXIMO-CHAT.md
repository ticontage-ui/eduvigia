# Instruções para o Próximo Chat

## Primeira ação obrigatória

Antes de desenvolver:

1. pedir o ZIP atual ou inventário do projeto;
2. confirmar o caminho;
3. confirmar a versão;
4. ler Compose;
5. ler `.env` com segredos mascarados;
6. inspecionar API, frontend, MediaMTX e scripts;
7. comparar com este relatório;
8. apresentar plano pequeno e reversível.

## Estado esperado

- Windows 11;
- Docker Desktop;
- projeto em `Documents\eduvigia`;
- versão esperada `v1.8.3`;
- frontend 5177;
- API 8002;
- MediaMTX 18554/18888/18889/18189;
- PostgreSQL 5437 local;
- Redis 6382 local.

## Prioridade

Finalizar a reprodução da Hikvision no navegador.

Já confirmado:
- RTSP aprovado;
- provisionamento aprovado;
- `ready=true`;
- `available=true`;
- H.264 1920×1080.

Ainda verificar:
- `webrtcAdditionalHosts`;
- UDP 18189;
- ICE;
- compatibilidade H.264;
- substream 102.

## Não fazer

- não recomeçar o projeto;
- não saltar para v2.0.0;
- não trocar MediaMTX sem PoC;
- não apagar banco/volumes;
- não expor credenciais;
- não alterar identidade visual sem pedido;
- não declarar IA, Bem-Estar ou PTZ como prontos;
- não entregar apenas trechos.

## Ordem recomendada

1. fechar WebRTC;
2. padronizar SUB;
3. corrigir healthcheck;
4. testar backup/restauração;
5. homologar NVR real;
6. painel de suporte;
7. recuperação por e-mail;
8. HTTPS;
9. PTZ;
10. Bem-Estar;
11. servidor de IA.
