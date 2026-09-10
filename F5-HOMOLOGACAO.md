# EduVigIA 2.0.0-F5-R1 — Matriz de homologação

## HT — Técnica
- VERSION = `2.0.0-F5-R1`
- Compose DEV/PROD válido
- runtime env allowlist preservado
- PostgreSQL saudável
- Alembic head = `20260910_206_f5`
- contratos F2/F3/F3-R2/F4 preservados
- `BACKEND_F5_VIDEO_WALL_CONTRACT`
- `DATABASE_F5_VIDEO_WALL_CONTRACT`
- `F5_VIDEO_WALL_RBAC_CONTRACT`
- `FRONTEND_F5_VIDEO_WALL_CONTRACT`
- `F5_LAYOUT_OWNER_AND_DUPLICATE_GUARD`
- regressão backend isolada
- build Web runtime

## HF — Funcional
Validar no navegador:
1. abrir **Video Wall**;
2. criar layout 2x2;
3. selecionar câmeras de escolas diferentes;
4. quando houver câmera multi-sensor, posicionar VISÍVEL e TÉRMICO em slots distintos;
5. salvar e recarregar a página;
6. confirmar persistência do layout;
7. definir como padrão;
8. testar AUTO/SUB/MAIN;
9. abrir Video Wall em tela cheia;
10. excluir o layout e confirmar remoção.

## HC — Campo
- Monitor físico/TV/video wall real: `PENDING_FIELD_TEST` até validação.
- Térmica/bi-spectrum real continua pendente de teste de campo da F3-R2.

## Critério de aprovação técnica
Esperado:
- `EDUVIGIA_F5_VIDEO_WALL_CORE=APPROVED`
- `EDUVIGIA_F5_VIDEO_WALL_DISPLAY=PENDING_FIELD_TEST`
- `EDUVIGIA_F5_UPDATE=APPROVED`
- `BASELINE=2.0.0-F5-R1`
