# QA — 10 escolas adicionais

Este seed existe exclusivamente para o ambiente standalone/QA do módulo Chat.

## Escopo

São adicionadas dez escolas de teste, de `SCHOOL-01` a `SCHOOL-10`.

Cada escola possui:

- um `GESTOR_ESCOLA`;
- um `OPERADOR_ESCOLA` (operador de câmeras);
- um canal institucional `emergency:SCHOOL-XX`;
- Guarda Municipal como membro;
- Secretaria de Educação como membro.

As escolas `SCHOOL-A` e `SCHOOL-B` já existentes são preservadas.

## Isolamento

Uma identidade de escola só pode participar do canal de emergência cujo
`school_code` coincide com o seu. O trigger de isolamento do Chat continua
sendo a proteção de banco, e o seed não desabilita nem contorna esse trigger.

Guarda e Secretaria permanecem institucionais e podem participar dos canais
autorizados.

## Natureza

Este arquivo NÃO é migration de produção. Deve ser executado apenas em
standalone/QA.
