# Relatório de Continuidade — EduVigIA

## 1. Identificação

- Projeto: EduVigIA
- Ambiente: Windows 11, Docker Desktop, Docker Compose e PowerShell 5.1
- Caminho atual de referência: `C:\Users\ticon\Documents\eduvigia`
- Versão esperada: `v1.8.3`
- A versão deve ser confirmada pelo código, API e interface antes de atualizar.

## 2. Serviços e acessos

| Serviço | Container | Porta | Finalidade |
|---|---|---:|---|
| Frontend | `eduvigia_web` | 5177 | Interface web |
| API | `eduvigia_api` | 8002 | Backend FastAPI |
| PostgreSQL | `eduvigia_postgres` | 5437 local | Banco |
| Redis | `eduvigia_redis` | 6382 local | Cache |
| MediaMTX | `eduvigia_mediamtx` | 18554, 18888, 18889, 18189/UDP | RTSP, HLS, WebRTC |
| Vídeo de teste | `eduvigia_video_teste` | interno | Stream `teste` |

Acessos:
- Painel: `http://localhost:5177`
- Health: `http://localhost:8002/health`
- Swagger: `http://localhost:8002/docs`
- HLS teste: `http://localhost:18888/teste/index.m3u8`
- WebRTC teste: `http://localhost:18889/teste`
- RTSP teste: `rtsp://localhost:18554/teste`
- MediaMTX API: `http://localhost:19997`
- Métricas: `http://localhost:19998/metrics`

## 3. Credencial inicial conhecida

- E-mail: `admin@eduvigia.local`
- Senha temporária: `Eduvigia@2026`

A senha deve ser alterada no primeiro acesso.

## 4. Funcionalidades presentes

- login e sessão;
- usuários, perfis e vínculo com escola;
- ativação/desativação e redefinição administrativa de senha;
- escolas;
- câmeras IP;
- NVR/DVR;
- integração Hikvision por ISAPI;
- streams MAIN e SUB;
- provisionamento no MediaMTX;
- monitoramento multi-escola;
- painel geral;
- central operacional;
- alertas;
- ocorrências;
- despacho;
- evidências e snapshots;
- equipamentos;
- relatórios;
- auditoria;
- notificações;
- segurança e sessões;
- criptografia de credenciais;
- infraestrutura;
- homologação;
- formulário público de suporte;
- scripts operacionais e documentação.

## 5. Itens parciais

### Suporte
O formulário e a API existem. Falta painel administrativo completo para atendimento, respostas, solução, encerramento e SLA.

### Recuperação de senha
Existe recuperação assistida via suporte. Falta fluxo por e-mail com token temporário, validade e tela de redefinição.

### PTZ
A câmera PTZ entrega vídeo, mas ainda faltam pan, tilt, zoom, presets e rondas dentro do EduVigIA.

### Produção web
O frontend usa build e `vite preview`. Para produção definitiva, recomenda-se Nginx, HTTPS, cache e cabeçalhos de segurança.

## 6. Itens planejados

- módulo Bem-Estar;
- servidor de IA;
- painel técnico da IA;
- análise automática de vídeo;
- aplicativo móvel;
- login Google;
- reconhecimento facial;
- análise emocional;
- diagnóstico psicológico.

Reconhecimento facial e biometria exigem base legal, análise de impacto e governança específica.

## 7. Câmera Hikvision em teste

- IP da câmera: `192.168.1.64`
- IP do host EduVigIA: `192.168.1.100`
- Porta 80: aprovada
- Porta 554: aprovada
- Porta 8000: aprovada
- MAIN: `/Streaming/Channels/101`
- SUB: `/Streaming/Channels/102`
- Camera ID: `5`
- Nome: `DOME`
- Caminho atual: `esc-marechal-consta-cam-recife-main`

Existe possível erro de digitação em `consta`. Não renomear sem migração coordenada.

## 8. Estado confirmado do MediaMTX

Foi confirmado:
- `Provisionado: True`
- `ready: true`
- `available: true`
- `online: true`
- H.264, 1920×1080
- tráfego de entrada e saída
- zero erros de quadro no teste

A imagem no navegador e no mosaico ainda precisa de confirmação final.

## 9. Correções já aplicadas

- Control API autorizada;
- métricas autorizadas;
- permissões `publish`, `read` e `playback`;
- reprovisionamento das câmeras;
- leitura do stream `teste`;
- leitura do stream real da câmera.

## 10. Próximo passo imediato

1. confirmar `webrtcAdditionalHosts`;
2. confirmar UDP 18189 no Firewall;
3. testar WebRTC local e pelo IP do host;
4. observar logs de ICE;
5. se necessário, usar SUB `102`;
6. padronizar H.264 Main/Baseline, sem H.264+, Smart Codec ou SVC.

## 11. Configuração recomendada

MAIN:
- H.264, perfil Main
- 1920×1080
- 15 FPS
- 2048–4096 Kbps
- I-frame 30
- H.264+, Smart Codec e SVC desativados

SUB:
- H.264, Main ou Baseline
- 704×480 ou 640×360
- 10 FPS
- 512–1024 Kbps
- I-frame 20
- H.264+, Smart Codec e SVC desativados

O mosaico deve usar SUB.

## 12. Histórico de risco

Uma tentativa anterior de salto para v2.0.0 causou indisponibilidade. Até a homologação física completa, usar atualizações pequenas em `v1.8.x` ou revisões controladas.
