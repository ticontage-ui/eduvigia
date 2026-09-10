# Camada de banco

A v1.3.0 introduz Alembic e a estrutura modular. Os modelos existentes continuam
em `app.application` para preservar integralmente o banco atual. A migração dos
modelos para arquivos separados será feita de forma incremental e testada.
