# Checklist — EduVigIA 1.8.5-R1

## Segurança de mídia

- [ ] MediaMTX inicializa com `authMethod: http`.
- [ ] Leitura anônima por WebRTC é negada.
- [ ] Publicação anônima em caminhos de câmera é negada.
- [ ] Token expirado é rejeitado.
- [ ] Token de uma câmera é rejeitado em outro caminho.
- [ ] Usuário de uma escola não recebe token para outra escola.
- [ ] API e logs não exibem credenciais RTSP.

## Operação

- [ ] MAIN e SUB estão provisionados para a câmera física.
- [ ] SUB reproduz no mosaico.
- [ ] MAIN reproduz quando selecionado.
- [ ] O player renova a autorização sem intervenção do operador.
- [ ] Snapshot permanece funcional.
- [ ] Reconexão após indisponibilidade temporária foi testada.

## Rede

- [ ] `18889/TCP` acessível aos postos autorizados.
- [ ] `18189/UDP` liberada para WebRTC.
- [ ] `18888/TCP` disponível para HLS autenticado.
- [ ] API de controle `19997/TCP` continua restrita a localhost.
