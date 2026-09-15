# EduVigIA 2.0.0-F7-R3 — HF7 Global Action Feedback

## Objetivo

Padronizar o retorno visual das ações explícitas do operador.

Toda atualização, teste ou publicação coberta por este hotfix passa a apresentar
uma faixa fina no topo da aplicação:

- verde: ação concluída com sucesso;
- vermelha: ação falhou ou terminou com falhas operacionais;
- sucesso permanece 5 segundos;
- falha permanece 8 segundos;
- ambas podem ser fechadas manualmente;
- uma nova mensagem substitui a anterior;
- ações de teste/publicação de câmeras e gravadores ficam temporariamente
  desabilitadas enquanto estão em execução.

## Escopo inicial do padrão global

- teste de equipamento gravador;
- teste MAIN/SUB dos canais do gravador;
- reprovisionamento do gravador;
- teste individual de câmera;
- teste em lote de até 64 câmeras;
- publicação de streams no MediaMTX;
- publicação em lote no Monitoramento;
- Atualizar / Atualizar saúde em Eventos & Saúde;
- teste controlado de evento;
- Atualizar agora na Central Operacional;
- Atualizar na Central de Alertas;
- Atualizar diagnóstico de Infraestrutura;
- Atualizar mapa;
- Atualizar diagnóstico de Homologação;
- salvamento de escola e configurações.

O componente é global no `App`, mas mensagens locais antigas permanecem
disponíveis para fluxos ainda não migrados. Isso evita uma alteração massiva e
arriscada em uma única revisão.

## Contrato visual

Componente: `ActionFeedbackBanner`.

Durações:
- success: 5000 ms;
- error: 8000 ms.

O banner fica logo abaixo da topbar e acima da área operacional.

## Banco/backend

- nenhuma migration;
- nenhum endpoint novo;
- backend funcional inalterado;
- Alembic permanece `20260911_209_f7r3`.

## Base obrigatória

`feature/f7-r3-camera-events-health`
HEAD base:
`27a876502929c782b803a3c0ff9a97a67fc07d00`

O runtime HF6 deve estar implantado antes da preparação.
