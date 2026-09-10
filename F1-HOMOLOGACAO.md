# Matriz de Homologação — F1

A F1 é aprovada somente quando todos os itens abaixo estiverem em PASS:

- VERSION
- COMPOSE_DEV_CONFIG
- COMPOSE_PROD_CONFIG
- RUNTIME_ENDPOINTS
- ALEMBIC_F1_HEAD
- BACKEND_F1_ROLE_CONTRACT
- DATABASE_F1_ROLE_CONTRACT
- FRONTEND_F1_ROLE_CONTRACT
- LEGACY_ROLE_COMPATIBILITY

## Validações funcionais recomendadas no navegador
1. Administrador da Secretaria entra e visualiza administração completa.
2. Gestor da Secretaria não visualiza Central Operacional/Despacho da Guarda.
3. Operador da Guarda visualiza Central Operacional, câmeras, alertas e ocorrências, mas não administra escolas/câmeras.
4. Usuário de Escola visualiza somente sua unidade, suas câmeras e suas ocorrências.
5. Tentar acessar diretamente recurso de outra escola retorna 404/403 conforme o tipo de operação.
6. Cadastro de usuário de Escola sem escola vinculada deve ser recusado.

Gate final: `EDUVIGIA_F1_ACCESS=APPROVED`.
