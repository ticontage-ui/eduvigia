# EduVigIA 2.0.0-F1-R1-HF2 — Resultado de Implementação

## Escopo
F1 — Escola / Secretaria / Guarda + Permissões.

## Implementado
- perfis canônicos separados por ambiente;
- migração automática dos perfis legados;
- isolamento obrigatório dos perfis de Escola por `school_id`;
- escopo municipal para Guarda e Secretaria;
- Técnico global ou opcionalmente restrito a uma escola;
- permissões do frontend por ambiente;
- Central Operacional restrita à Guarda/Administrador;
- administração de escolas/câmeras/NVRs/equipamentos restrita à Secretaria/Técnico;
- operação de alertas/ocorrências restrita à Guarda/Administrador;
- criação de usuários aceita somente os novos perfis;
- validação de vínculo escolar conforme o perfil;
- compatibilidade de leitura para perfis legados durante a migration.

## Testes locais
- backend: 40/40 testes aprovados;
- inclui 4 testes novos específicos de F1 (Escola, Guarda, Secretaria e criação de perfis).

## Gate de campo/runtime
Executar `scripts/HOMOLOGAR-EDUVIGIA-F1.ps1` após instalação no Windows/Docker.

Resultado esperado: `EDUVIGIA_F1_ACCESS=APPROVED`.
