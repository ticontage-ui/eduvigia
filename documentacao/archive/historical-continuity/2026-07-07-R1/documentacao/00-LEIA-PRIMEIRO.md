# EduVigIA — Continuidade Técnica e Operacional

**Data de consolidação:** 2026-07-07  
**Revisão:** R1  
**Versão esperada:** EduVigIA v1.8.3  
**Projeto de referência:** `C:\Users\ticon\Documents\eduvigia`

Este pacote registra o estado real do projeto, o que já foi feito, o que ainda falta e o padrão obrigatório de entrega para os próximos atendimentos.

## Ordem de leitura

1. `01-RELATORIO-CONTINUIDADE-EDUVIGIA.md`
2. `02-MATRIZ-STATUS-FUNCIONALIDADES.md`
3. `03-PADRAO-OBRIGATORIO-DE-ENTREGA.md`
4. `04-INSTRUCOES-PARA-O-PROXIMO-CHAT.md`
5. `05-CHECKLIST-DE-ATUALIZACAO.md`
6. `06-PADRAO-HIKVISION-E-MEDIATMX.md`
7. `07-ARQUITETURA-ATUAL-E-VISAO-FINAL.md`
8. `PROMPT-PROXIMO-CHAT.txt`

## Regras centrais

- Confirmar a versão atual antes de qualquer alteração.
- Não saltar diretamente para v2.0.0.
- Não apagar banco, volumes, `.env`, evidências ou configurações.
- Toda atualização deve ter ZIP completo, PowerShell 5.1, preflight, SHA-256, backup, validação e rollback.
- O stream da câmera Hikvision já chega ao MediaMTX; a reprodução no navegador ainda precisa de confirmação final.
