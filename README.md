# EduVigIA 2.0 — Baseline F7

Versão atual: **2.0.0-F7-R3**

## F7-R3 — Camera Events & Health

A revisão `2.0.0-F7-R3` completa o núcleo de eventos e telemetria de câmeras/gravadores antes da F8 SOS Digital:

- catálogo canônico e vendor-agnostic de eventos de vídeo, saúde e I/O;
- ingestão normalizada para adapters `GENERIC`, `HIKVISION_ISAPI`, `ONVIF` e `EDUVIGIA_HEALTH`;
- parser de `EventNotificationAlert` Hikvision para o endpoint de integração;
- deduplicação de eventos ativos com `repeat_count`, correlação por escola/câmera/gravador/canal/tipo e lock transacional em PostgreSQL;
- geração automática de Alertas e Notificações para eventos operacionais relevantes, sem campos de IA/confiança;
- fechamento automático apenas de alertas técnicos recuperáveis (offline, vídeo/RTSP, gravação, storage, gravador);
- saúde consolidada por câmera e gravador, incluindo RTSP, MAIN/SUB, gravação, armazenamento, tamper, motion, NTP, FPS, bitrate, resolução e codec quando disponíveis;
- transições online/offline oriundas dos testes internos passam pelo mesmo motor de eventos;
- nova tela `Eventos & Saúde` para operação e diagnóstico;
- proteção de startup: uma API F7-R3 não inicia sobre banco com Alembic anterior, impedindo repetição do schema drift observado na tentativa F8;
- migration F7-R3: `20260911_209_f7r3`.

O núcleo é independente de fabricante. Hikvision entra como adapter ISAPI; ONVIF usa a mesma normalização. A ativação de streams/eventos reais em equipamentos permanece sujeita ao teste de campo do modelo/firmware instalado.

## F7-R2 — Estabilização operacional

A revisão `2.0.0-F7-R2` estabiliza módulos já existentes antes da F8 SOS Digital:

- edição completa de escolas no frontend, com validação de código duplicado no backend;
- kits escolares de `KIT_01` (4 câmeras) até `KIT_16` (64 câmeras), em incrementos de 4;
- código automático e persistente de câmera no formato `CAM-000001`, gerado pelo backend;
- testes em lote ampliados para até 64 câmeras/canais;
- notificações com escopo por escola e leitura individual por usuário, sem que um usuário marque a notificação como lida para todos;
- ativação/inativação de escola gera notificação operacional no sino respeitando o escopo da escola;
- clique em notificação navega para o módulo correspondente;
- Central de Alertas passa a permitir criação manual para perfis com `alerts:operate`;
- interface e contrato público de Alertas deixam de expor `Origem / Confiança` ligados ao escopo antigo de IA;
- remoção do resíduo funcional `BEM_ESTAR` na conversão alerta → ocorrência;
- protocolo de ocorrência passa a usar sequência transacional no PostgreSQL, eliminando `count()+1`;
- migration F7-R2: `20260911_208_f7r2`.

A migration deve ser aplicada **antes** de iniciar o runtime F7-R2. O runtime F7-R1 permanece operacional durante a preparação e validação isolada da candidata.


A F2 consolida o **VMS Básico** sobre a F1 homologada, mantendo a separação de acesso entre Secretaria de Educação, Guarda Municipal e Escola.

## Entregas F2

- cadastro e inventário de NVR/DVR;
- descoberta Hikvision/ISAPI;
- câmera direta, canal NVR/DVR e RTSP customizado;
- dois perfis independentes por câmera: `MAIN` e `SUB`;
- metadados separados por perfil: codec, resolução, FPS, bitrate e status;
- MAIN Hikvision em `x01` e SUB em `x02`;
- mosaicos 1/4/9/16;
- qualidade `AUTO`, `SUB` e `MAIN`;
- em `AUTO`: SUB nos mosaicos 4/9/16 e MAIN em grade 1/fullscreen;
- favoritos persistidos por usuário;
- status online/offline atualizado para as câmeras visíveis em lotes de até 16;
- reconexão do player;
- proteção contra exposição de credenciais RTSP nas respostas da API.

## Migrations

- F0: `20260908_200_f0`
- F1: `20260908_201_f1`
- F2: `20260908_202_f2`

## Ambiente local

Painel oficial de desenvolvimento:

```text
http://localhost:5177
```

WebRTC/HLS em DEV permanecem em HTTP para evitar bloqueio por certificado autoassinado. O Compose de produção mantém mídia em HTTPS.

## Homologação

Após a atualização execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File ".\scripts\HOMOLOGAR-EDUVIGIA-F2.ps1" `
    -ProjectPath "$PWD"
```

Gate esperado:

```text
EDUVIGIA_F2_VMS_BASIC=APPROVED
```

## Próxima fase após homologação

**F3 — VMS Media / Fundação de mídia em escala**, conforme o roadmap vigente.


## F3 — PTZ Operacional

A F3 adiciona controle PTZ Hikvision/ISAPI com pan/tilt/zoom, STOP, velocidade 1–7, presets persistidos, lease de controle para evitar dois operadores comandando a mesma câmera simultaneamente, auditoria e RBAC `ptz:control`.

- O controle aparece no Monitoramento somente em câmeras com `ptz_enabled=true`.
- Em câmera IP direta, o ISAPI usa IP/credenciais da própria câmera e a porta PTZ configurada.
- Em câmera vinculada a NVR/DVR, o controle usa as credenciais/portas do gravador e o canal PTZ da câmera.
- O suporte homologado nesta fase é Hikvision ISAPI. A abstração de dados deixa espaço para ONVIF futuro, mas ONVIF PTZ não é declarado como homologado.
- O software pode ser homologado sem movimentar hardware; o gate de campo permanece pendente até existir uma câmera PTZ disponível para teste supervisionado.

## F3-R2 — Multi-Channel / Multi-Sensor Foundation

A F3-R2 separa o equipamento físico dos canais lógicos de vídeo. Um único IP/credencial pode expor múltiplos sensores, por exemplo uma câmera Hikvision bi-spectrum com canal óptico e canal térmico.

Modelo operacional:

```text
VideoDevice (1 IP / 1 credencial)
  ├─ Camera CH1 — VISIBLE — MAIN/SUB
  ├─ Camera CH2 — THERMAL — MAIN/SUB
  └─ Camera CHn — FUSION/GENERIC — MAIN/SUB quando suportado
```

- tabela física `video_devices`;
- `cameras` passa a representar canal/sensor lógico quando `device_id` estiver definido;
- tipos de sensor: `VISIBLE`, `THERMAL`, `FUSION`, `GENERIC`;
- descoberta Hikvision normaliza canais `101/102`, `201/202`, etc.;
- MAIN/SUB permanecem independentes;
- credenciais pertencem ao dispositivo físico e não são duplicadas nos canais;
- canais do mesmo dispositivo podem aparecer lado a lado no Monitoramento;
- PTZ F3 permanece preservado e pode usar as credenciais compartilhadas do dispositivo.

Migration: `20260909_204_f3r2`.

Homologação:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File ".\scripts\HOMOLOGAR-EDUVIGIA-F3R2.ps1" `
    -ProjectPath "$PWD"
```

Gates principais esperados:

```text
EDUVIGIA_F3R2_MULTICHANNEL_CORE=APPROVED
EDUVIGIA_F3R2_THERMAL_HARDWARE=PENDING_FIELD_TEST
```

O teste físico de uma câmera térmica/bi-spectrum permanece obrigatório antes de considerar o comportamento de hardware homologado.

## F5 — Video Wall Operacional
A F5 adiciona layouts persistentes de Video Wall por operador, grades 1/4/9/16, seleção de canais lógicos multi-sensor, perfil AUTO/SUB/MAIN e tela cheia. A gravação/playback da F4 permanece independente do Video Wall.

## F6 — Mapas Operacionais

A F6 adiciona o mapa geográfico multi-escola da operação municipal, reutilizando as coordenadas já existentes no cadastro de escolas e sem criar migration artificial.

- marcador por escola georreferenciada;
- estados `NORMAL`, `ATTENTION` e `CRITICAL` derivados de saúde de vídeo, alertas e ocorrências abertas;
- agregação de câmeras online/offline/pendentes;
- filtro por situação e busca por escola/endereço/cidade;
- painel lateral da escola e atalho para Monitoramento;
- escolas sem coordenadas são listadas separadamente para saneamento cadastral;
- escopo RBAC: perfis municipais veem o município; perfis escolares veem apenas a escola vinculada;
- tiles configuráveis por `EDUVIGIA_MAP_TILE_URL` e `EDUVIGIA_MAP_ATTRIBUTION`;
- DEV usa OpenStreetMap por padrão; produção on-prem pode apontar para servidor cartográfico interno.

A F6 não altera o schema. O Alembic permanece no head `20260910_206_f5`.

## F7 — Plantas Baixas / Floor Plans

A F7 introduz plantas operacionais por escola, prédio e pavimento. A planta é armazenada no diretório persistente de dados e os canais de câmera são posicionados em coordenadas percentuais, preservando a separação VISÍVEL/TÉRMICO da F3-R2.

- upload autenticado de JPG, PNG e WebP de até 15 MB;
- validação de assinatura real do arquivo e bloqueio de SVG;
- tabelas `floor_plans` e `floor_plan_cameras`;
- posição `x_percent` / `y_percent` e orientação `rotation_deg`;
- uma mesma câmera não pode aparecer duas vezes na mesma planta;
- câmera e planta devem pertencer à mesma escola;
- `floorplans:view` para perfis operacionais e `floorplans:write` apenas para gestão/implantação autorizada;
- gestor escolar edita somente plantas da própria escola;
- canais óptico e térmico podem ser posicionados separadamente.

Migration: `20260910_207_f7`.
