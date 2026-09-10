# EduVigIA 1.8.6-R1

## Fase 3 — Integração Hikvision, Câmeras e NVR

### Correções estruturais

- Corrigido o carregamento de gravadores no frontend.
- Adicionadas validações de IP, portas, gravador duplicado e canal duplicado.
- Teste de câmera passou a usar corretamente as credenciais do NVR vinculado.
- Testes MAIN e SUB agora são independentes e retornam metadados reais.
- Importação de canais agora possui modelo tipado, atualização opcional e proteção contra duplicidade.

### Integração Hikvision

- Teste completo de HTTP, HTTPS, RTSP, SDK e ISAPI.
- Suporte a autenticação Digest e Basic no ISAPI.
- Suporte a HTTPS local com certificado próprio do equipamento.
- Inventário automático: modelo, série, firmware, data do firmware, tipo e MAC.
- Descoberta de canais com estado, IP, vínculo existente e perfis MAIN/SUB.
- Normalização dos IDs Hikvision de streaming para o número lógico do canal.

### Operação

- Edição de gravadores e câmeras.
- Teste individual e em lote.
- Reprovisionamento em lote.
- Importação e sincronização seletiva de canais.
- Limite seguro de 32 testes físicos por execução.
- Auditoria das operações técnicas.

### Validações automatizadas

- compilação Python;
- 24 testes automatizados;
- build Vite de produção;
- validação de rotas da Fase 3;
- validação da presença do `ffprobe`;
- stack temporária completa no modo `-PreflightOnly`.

### Limite desta fase

A detecção automática de dispositivos por varredura de rede, ONVIF, PTZ e atualização remota de firmware permanecem fora do escopo desta versão.
