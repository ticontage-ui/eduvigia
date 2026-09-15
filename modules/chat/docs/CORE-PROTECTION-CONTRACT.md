# CORE PROTECTION CONTRACT

1. O modulo Chat nao altera o docker-compose.yml principal.
2. O modulo Chat nao utiliza o PostgreSQL do Core.
3. O modulo Chat nao utiliza o Redis do Core.
4. O modulo Chat nao importa implementacoes internas de outros modulos.
5. Falha do Chat nao pode impedir o Core de iniciar ou operar.
6. O Chat permanece standalone ate homologacao propria.
7. Integracao futura deve ocorrer por contratos explicitos de identidade/RBAC/contexto.
8. Todo commit desta fase deve permanecer confinado a modules/chat/**.
