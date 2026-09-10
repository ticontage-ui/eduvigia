# Padrão Obrigatório de Entrega

## Entregáveis

Toda atualização deve conter:

1. ZIP completo;
2. PowerShell 5.1 completo;
3. parâmetro `-PreflightOnly`;
4. SHA-256;
5. manifesto;
6. backup;
7. rollback;
8. validação;
9. log em Downloads;
10. instruções completas.

## Caminhos

Usar sempre:

```powershell
$Downloads = Join-Path $env:USERPROFILE "Downloads"
$ProjectPath = Join-Path $env:USERPROFILE "Documents\eduvigia"
```

## Preflight

O preflight deve localizar projeto e ZIP, validar hash, Docker, Compose, espaço, portas, versão e simular todas as alterações sem tocar no projeto.

## Preservação

Preservar obrigatoriamente:

- `.env`;
- `EDUVIGIA_CREDENTIAL_KEY`;
- banco PostgreSQL;
- volumes;
- Redis;
- `data`;
- `data/evidence`;
- MediaMTX;
- credenciais;
- escolas;
- usuários;
- documentos;
- identidade visual.

Nunca usar `docker compose down -v` em atualização normal.

## Patch seguro

- âncoras estruturais;
- idempotência;
- UTF-8 sem BOM;
- sem duplicar configuração;
- validar JSON, YAML, Python e frontend;
- não depender de bloco antigo exato.

## Docker

1. `docker compose config`;
2. build dos serviços afetados;
3. subida controlada;
4. health checks;
5. testes HTTP;
6. testes MediaMTX;
7. rollback em falha crítica.

## Testes mínimos

- frontend HTTP 200;
- API health 200;
- Swagger 200;
- PostgreSQL e Redis saudáveis;
- MediaMTX API e métricas;
- stream `teste`;
- câmera real, quando disponível;
- login;
- isolamento escolar;
- evidência;
- backup.

## MediaMTX

Preservar:
- `publish`, `read`, `playback`;
- `api`, `metrics`, `pprof` restritos;
- `webrtcAdditionalHosts`;
- UDP 18189;
- caminhos dinâmicos.

Não validar pela raiz de HLS/WebRTC. Usar um caminho existente.

## Versionamento

- correção: `v1.8.x`;
- revisão: `v1.8.x-Rn`;
- funcionalidade controlada: `v1.9.x`;
- `v2.0.0` somente após homologação completa.

Não declarar produção homologada sem evidência física e aceite.
