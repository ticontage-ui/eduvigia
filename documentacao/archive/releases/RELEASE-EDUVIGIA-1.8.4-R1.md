# EduVigIA 1.8.4-R1

## Fase 1 — Segurança, Perfis e Isolamento Escolar

Esta atualização preserva o layout e os dados existentes e concentra as mudanças na camada de autorização, auditoria e autenticação.

### Implementado

- autorização efetiva no backend, além das restrições visuais do frontend;
- isolamento por escola para escolas, câmeras, gravadores, alertas, ocorrências, evidências, equipamentos, manutenções, relatórios e operação;
- exigência de unidade escolar para os perfis ESCOLA, OPERADOR e TÉCNICO;
- bloqueio seguro de perfis operacionais sem unidade vinculada;
- migração transacional de credenciais técnicas legadas pelo instalador, após a validação do ambiente;
- bloqueio de alterações em recursos pertencentes a outra escola;
- proteção das configurações globais e da auditoria;
- trilha de auditoria com usuário, e-mail, perfil, escola, IP, navegador e resultado;
- troca de senha temporária obrigatória antes de liberar o ambiente;
- revogação das demais sessões após a troca ou redefinição de senha;
- política de senha forte no backend e frontend;
- suporte e recuperação de senha acessíveis na tela pública de login;
- correção do erro `active=True` durante a importação de canais do NVR;
- mascaramento de URLs RTSP e segredos nas respostas de homologação;
- vínculo `school_id` para alertas e ocorrências, com retrocompatibilidade por nome;
- remoção da criação automática de alertas fictícios, salvo quando `EDUVIGIA_SEED_DEMO_DATA=true`;
- versão unificada como `1.8.4-R1`.

### Testes incluídos

- isolamento entre Escola A e Escola B;
- bloqueio de configurações e auditoria para perfil escolar;
- bloqueio de ocorrência de outra escola para operador vinculado;
- isolamento de evidências e equipamentos;
- troca obrigatória de senha;
- revogação de sessões antigas;
- identificação correta do operador na auditoria;
- escopo escolar nos relatórios;
- bloqueio de perfil operacional sem escola vinculada.

### Critério de aceite

- backend: 12 testes aprovados;
- frontend: build Vite aprovado;
- arquivos Python compilados sem erro;
- Docker Compose deve subir `postgres`, `redis`, `mediamtx`, `api` e `web` saudáveis;
- usuário de uma escola recebe HTTP 404 ao tentar consultar recurso de outra escola;
- usuário sem permissão recebe HTTP 403 em configurações e auditoria;
- conta temporária só acessa troca de senha, logout e identificação da própria sessão.

### Não incluído nesta fase

A autenticação de leitura e publicação do MediaMTX, URLs temporárias de vídeo, MAIN/SUB simultâneos e endurecimento do WebRTC pertencem à Fase 2.


### Revisão técnica R4 da entrega

- adicionada a dependência `httpx==0.28.1`, exigida pelo `fastapi.testclient.TestClient`;
- o preflight agora compila os arquivos Python antes de executar os testes;
- a limpeza da stack temporária não usa `docker compose down -v`;
- os volumes criados exclusivamente pela simulação são removidos pelos nomes exatos do projeto temporário;
- nenhuma mudança funcional adicional foi introduzida no escopo da versão 1.8.4-R1.


## Revisão de entrega R5

- corrigido o healthcheck do frontend para usar Node.js e `127.0.0.1`;
- removida a dependência do `wget` na validação do container Web;
- adicionada validação HTTP real do frontend na simulação;
- adicionados diagnósticos automáticos de `ps`, logs e estado do container em falhas;
- mantidos build integral, compilação Python e 12 testes automatizados.

## Revisão de entrega R6

- adicionada verificação de saúde HTTP ao serviço `api` no Docker Compose;
- o preflight aguarda a API concluir integralmente o startup antes de validar a versão;
- removida a validação única e imediata que podia produzir `ConnectionRefusedError`;
- adicionadas tentativas controladas e diagnóstico automático da API em caso de falha;
- mantidos o isolamento da simulação, o build integral, a compilação Python, os 12 testes e a validação HTTP do frontend.
