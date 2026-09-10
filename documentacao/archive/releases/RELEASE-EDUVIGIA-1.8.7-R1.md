# EduVigIA 1.8.7-R1

## Fase 4 — Infraestrutura de Produção, Banco, Observabilidade e Escalabilidade

### Entregas

- endpoints públicos de liveness (`/live`), readiness (`/ready`) e métricas Prometheus (`/metrics`);
- pool PostgreSQL configurável, `pg_stat_statements`, limite de conexões e log de consultas lentas;
- Redis com AOF e `appendfsync everysec`;
- logs HTTP estruturados em JSON com `X-Request-ID`;
- reverse proxy Nginx nas portas 8088/8443;
- certificado TLS local e exclusivo, gerado durante a instalação;
- Prometheus local na porta 19090, com coleta da API e do MediaMTX;
- regras iniciais de alerta para banco, HTTP 5xx e indisponibilidade da API;
- política de rotação dos logs Docker;
- painel de infraestrutura ampliado com prontidão, capacidade, pool, retenção e escalabilidade;
- backup PostgreSQL em formato customizado, hashes e teste de restauração isolada;
- scripts operacionais revisados para backup, validação, inicialização e restauração segura.

### Compatibilidade

- origem suportada: `1.8.6-R1`;
- destino: `1.8.7-R1`;
- caminho homologado: `C:\Users\lecsa\Documents\eduvigia`.

### Observação sobre HTTPS

O certificado gerado é autoassinado e adequado à homologação local/LAN. Para produção pública, substitua os arquivos em `nginx/certs` por certificado emitido por autoridade confiável.

## Revisão de entrega R2

- Corrige falso negativo do `infrastructure_preflight` observado após `/ready` já responder com sucesso.
- A verificação auxiliar agora valida o snapshot retornado pelo processo Uvicorn ativo, incluindo `startup_complete` e os estados de PostgreSQL, Redis, MediaMTX e armazenamento.
- Remove a chamada direta a `collect_readiness()` em um novo interpretador Python, onde o estado de inicialização é corretamente recriado como `False`.
- Adiciona teste automatizado de regressão para esse fluxo.

