# EduVigIA 2.0.0-F8-R1 — HF2 SOS Audible Operational Alert

## Objetivo

Adicionar alerta sonoro operacional ao SOS da F8 sem alterar o contrato de backend, banco, migration, RBAC ou estados do incidente.

## Regras

- `GESTOR_ESCOLA` e `OPERADOR_ESCOLA` continuam com acionamento silencioso.
- O alerta sonoro global existe somente para quem possui `sos:operate`.
- Estados que exigem alarme até atendimento: `ACTIVE` e `CANCEL_REQUESTED`.
- `ACKNOWLEDGED` interrompe o alarme.
- `RESOLVED` e `FALSE_ALARM` não emitem alarme.
- Novo SOS gera disparo sonoro imediato.
- Incremento de `repeat_count` gera novo disparo imediato.
- Enquanto houver SOS não reconhecido, o alerta repete em ciclos.
- O operador pode silenciar o som por 60 segundos sem alterar qualquer estado do SOS.
- O navegador precisa liberar Web Audio por interação do usuário; o cabeçalho mostra claramente quando o áudio ainda precisa ser ativado.
- Nenhum arquivo de áudio externo é necessário: o sinal é sintetizado localmente pela Web Audio API.

## Escopo técnico

Arquivos alterados/criados:

- `frontend/src/app/App.jsx`
- `frontend/src/styles/main.css`
- `frontend/src/components/SosAudibleAlert.jsx`
- `F8-R1-HF2-SOS-AUDIBLE-ALERT.md`

Nenhuma alteração em:

- `backend/`
- migration `20260915_210_f8_sos`
- PostgreSQL
- Redis
- nginx
- MediaMTX
- permissões RBAC
- endpoints SOS existentes

## Gate

A F8 permanece **não homologada** até:

1. regressão backend `107 passed`;
2. build Web aprovado;
3. deploy controlado somente do Web;
4. Browser QA validar áudio na Central/Guarda;
5. acionamento da escola permanecer silencioso;
6. reforço (`repeat_count`) gerar novo som;
7. ACK interromper o som;
8. silenciamento temporário não alterar o estado do SOS.