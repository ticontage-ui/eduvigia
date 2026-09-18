# EduVigIA Chat — V0.8-R1 Crisis Room Foundation

## Ator escolar

O ator escolar da Sala de Crise é `GESTOR_ESCOLA`.

`OPERADOR_ESCOLA` não recebe acesso à Sala de Crise nesta fase e não é ator do
aplicativo móvel.

## Escopo R1

- lifecycle: `READY`, `ACTIVE`, `ENDED`;
- isolamento por `school_code`;
- RBAC para Gestor Escolar, Guarda e Secretaria;
- participantes e auditoria;
- criação manual para QA;
- UI web básica;
- campos preparados para futura integração SOS;
- estado de mídia persistido como `OFF`, mas sem WebRTC nesta fase;
- sem gravação.

## Integração SOS futura

Campos disponíveis:

- `incident_id`
- `incident_source`
- `external_reference`
- `triggered_by_identity_id`
- `triggered_at`

O SOS continuará como sistema de registro do incidente. O Chat será responsável
pela Sala de Crise. Não haverá compartilhamento de banco.

## Áudio futuro

A V0.8-R2 implementará:

- `school_audio_state=OFF|PTT|LIVE`;
- `GESTOR_ESCOLA` como publisher escolar;
- Guarda/Secretaria como subscribers;
- auto-subscribe dos operadores autorizados quando `LIVE`;
- nenhuma confirmação adicional por operador depois que o gestor iniciar `LIVE`;
- áudio do operador para o celular desligado por padrão;
- sem gravação inicialmente.
