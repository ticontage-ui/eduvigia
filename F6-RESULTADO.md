# EduVigIA 2.0.0-F6-R1 — Resultado de preparação

Fase: **F6 — Mapas Operacionais**  
Baseline de origem: `2.0.0-F5-R1`  
Candidata: `2.0.0-F6-R1`

## Implementado

- mapa geográfico multi-escola sem dependência de biblioteca cartográfica no frontend;
- raster tiles por Web Mercator;
- `EDUVIGIA_MAP_TILE_URL` configurável para OSM em DEV ou tile server interno on-prem;
- marcador por escola com estados Normal / Atenção / Crítica;
- agregação de câmeras online/offline/pendentes, alertas ativos e ocorrências abertas;
- lista de escolas sem latitude/longitude;
- busca e filtro operacional;
- painel lateral com atalho para Monitoramento e cadastro da escola;
- endpoint `/maps/overview` com escopo por escola/perfil;
- permissão `maps:view` sem elevar privilégios de escrita;
- coordenadas com vírgula decimal são normalizadas; coordenadas inválidas não viram marcador.

## Banco

Nenhuma migration nova foi criada. Os campos `schools.latitude` e `schools.longitude` já existiam antes da F6. O head esperado permanece `20260910_206_f5`.

## Validação local

- Backend: **80/80 testes PASS**;
- contratos F2/F3/F3-R2/F4/F5 preservados;
- `vms_f6_preflight.py`: PASS;
- Python compile: PASS;
- JSX parse (TypeScript parser): PASS;
- Compose DEV YAML: PASS;
- Compose PROD YAML: PASS;
- preflight de infraestrutura tornado version-agnostic para impedir falso negativo por versão futura.

O build Docker do frontend permanece gate obrigatório no Windows do ambiente alvo.

## Estado

`2.0.0-F6-R1` é candidata e **não deve ser considerada homologada antes da execução do instalador/homologador no Windows**.
