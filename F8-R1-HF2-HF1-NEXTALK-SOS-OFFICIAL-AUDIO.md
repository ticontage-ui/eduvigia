# EduVigIA 2.0.0-F8-R1 — HF2-HF1 NexTalk SOS Official Audio

## Objetivo

Substituir a sirene sintetizada do HF2 pelo asset oficial de SOS do NexTalk.

## Asset canônico

- NexTalk: sos.mp3
- finalidade: Alerta SOS / Sirene oficial de emergência
- tamanho: 63509 bytes
- SHA-256: $ExpectedAudioSha
- destino EduVigIA: $TargetAudioRel

O binário é copiado sem regeneração, reamostragem ou síntese.

## Regras preservadas

- áudio somente para usuários com sos:operate;
- perfis de escola permanecem silenciosos;
- ACTIVE e CANCEL_REQUESTED geram alerta;
- novo SOS ou incremento de epeat_count gera novo disparo;
- repetição periódica a cada 12 segundos;
- mute temporário de 60 segundos;
- ACK retira o evento da condição sonora no próximo poll;
- sem alteração de backend, banco, Alembic, Redis, nginx ou MediaMTX.

## Gate de homologação

Browser QA deve confirmar reprodução do mesmo sos.mp3 oficial do NexTalk.