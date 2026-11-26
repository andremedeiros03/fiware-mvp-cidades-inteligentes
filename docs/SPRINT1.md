# Sprint 1 — Natal Smart Traffic

**Objetivo:** malha real direcionada, rota convencional, três modelos NGSI-LD e expansão de telemetria sintética. Este pacote complementa o repositório `andremedeiros03/fiware-mvp-cidades-inteligentes` sem substituir nenhum arquivo existente. A referência é o README, Docker Compose e código Python da branch `main` consultados durante o planejamento.

## 1. Preparação no Windows (PowerShell)

Na raiz do repositório original, confirme que não há mudanças locais que precisem ser preservadas:

```powershell
git status
git switch main
git pull --ff-only
git switch -c feature/smart-routing
```

Se a branch já existir, use `git switch feature/smart-routing`. Extraia o ZIP da Sprint 1 dentro da raiz do repositório (os diretórios `geodata`, `sprint1`, `tests` e `docs` devem aparecer ao lado de `docker-compose.yml`). Não apague volumes nem sobrescreva o código da versão anterior.

```powershell
py -3.12 -m venv .venv-sprint1
$python = ".\.venv-sprint1\Scripts\python.exe"
& $python -m pip install -r geodata/requirements.txt
& $python -m pytest -q tests/test_sprint1.py
```

Caso o launcher `py` não esteja disponível, use `python -m venv .venv-sprint1` com Python 3.11 ou 3.12 instalado. Não versionar o ambiente virtual: adicione `.venv-sprint1/` ao `.gitignore` da raiz antes do commit.

## 2. Extrair mapa e calcular rota

```powershell
& $python -m geodata.extract_network
& $python -m geodata.route_demo --origem -5.820513 -35.207869 --destino -5.807503 -35.203107
```

A extração usa uma área retangular configurável de Lagoa Nova e arredores e requer internet e acesso ao serviço Overpass. Não é necessário abrir Docker para esta etapa. Os valores de origem e destino são coordenadas de exemplo retiradas da modelagem anterior da Avenida Salgado Filho, e o comando exige que estejam próximos da malha. Para uma nova tentativa, use pontos próximos a ruas dentro do retângulo. Se o Overpass falhar, tente novamente quando estiver disponível; se já houver GraphML OSMnx salvo, `python -m geodata.extract_network --graph CAMINHO` pode reutilizá-lo. Não substitua um snapshot já provisionado sem planejar a migração dos IDs.

Saídas em `geodata/output/`:

| Arquivo | Conteúdo |
|---|---|
| `natal.graphml` | MultiDiGraph OSMnx, dirigido, com pesos de distância e tempo de referência |
| `roads.geojson` | Arestas da malha viária |
| `intersections.geojson` | Nós do grafo, não necessariamente cruzamentos semaforizados |
| `monitored_roads.geojson` | Segmentos selecionados para sensores |
| `signals.geojson` | Posições virtuais; `osm_tagged_signal` distingue nós marcados no OSM |
| `road_segments.json` | Inventário de segmentos, sensores, semáforos e fingerprint do grafo |
| `route.geojson`, `route.json` | Rota calculada e métricas de referência |

Visualize GeoJSON em QGIS ou em um visualizador local compatível. A atribuição **© OpenStreetMap contributors** deve ser exibida ao reutilizar os dados. O grafo não implementa todas as restrições de conversão e não é adequado para navegação real. O roteamento desta sprint não usa dados observados nem previsão: isso será feito nas próximas sprints.

### Seleção e identidade

Por padrão, até três arestas direcionadas por corredor (cinco corredores), priorizando comprimento e dispersão espacial. O limite de 15 sensores e dez semáforos é uma meta, não um resultado garantido. Revise o relatório de cobertura e o GeoJSON, especialmente ruas homônimas, sentido de circulação e conectividade. IDs `osm-u-v-k` dependem do snapshot congelado do grafo. Uma nova extração pode produzir IDs diferentes. Nenhum dado real de sensor é obtido do OSM.

## 3. Provisionamento FIWARE

Execute apenas depois de validar a geometria e cobertura. O ambiente original usa portas locais e credenciais de desenvolvimento; **não publique estas portas na AWS**. As instruções a seguir destinam-se ao ambiente local.

```powershell
docker compose up -d
docker compose ps
docker compose --profile setup run --rm provisionamento
& $python -m sprint1.provision --dry-run
& $python -m sprint1.provision
```

A expansão utiliza o tenant `transito`, o service group `chave-trafego` existente e as subscriptions originais para `TrafficFlowObserved`. Cria `RoadSegment`, `Device` (sensores e semáforos) no Orion-LD e registra sensores adicionais no IoT Agent. Cada observação referencia o segmento; cada entidade Device referencia o segmento e, para sensores, sua observação. O contexto JSON-LD próprio define as extensões `osmEdge`, `referenceSpeed`, `corridorId`, `signalState`, `simulated`, `osmTaggedSignal` e `refObservation`. `referenceSpeed` é velocidade de referência, não necessariamente limite legal. `corridorId` é o agrupamento lógico, não uma entidade Smart Data Model adicional. `Device` é descrito no catálogo oficial; a compatibilidade de todas as propriedades e dos contextos com o broker precisa ser confirmada no teste real.

O provisionamento evita recriar registros IoT existentes e tenta atualizar atributos de entidades já existentes. Ele não remove dispositivos antigos. Utilize um snapshot fixo e, se houver alteração de inventário, planeje explicitamente a migração antes de republicar. Os sensores A/B originais permanecem no tenant, mas não fazem parte do novo inventário; consultas futuras devem filtrar os sensores `s1-sensor-` para evitar duplicidade conceitual.

## 4. Teste curto do simulador e histórico

Escolha um intervalo inédito para os novos sensores. O exemplo abaixo gera 3 observações por sensor, em horários simulados, sem aguardar cinco minutos reais entre amostras.

```powershell
$inicio = "2026-11-26T07:00:00-03:00"
& $python -m sprint1.simulate --inicio $inicio --passos 3 --dry-run
& $python -m sprint1.simulate --inicio $inicio --passos 3 --spacing 0.5
& $python -m sprint1.signals --tick 0
& $python -m sprint1.validate --inicio $inicio --passos 3
```

Aguarde o processamento assíncrono de subscriptions antes de repetir `validate`, caso o histórico ainda esteja chegando. Não repita a simulação do mesmo período no banco, pois QuantumLeap pode duplicar registros. Se o histórico não usar `time_index` correspondente à observação, inspecione `dateObserved`, `observedAt` e as colunas da tabela antes de alterar o validador. O script valida o Orion e o CrateDB, não comprova por si só a entrega no Draco.

Para conferir também o PostgreSQL do Draco:

```powershell
docker exec postgres-db psql -U draco_user -d fiware_data -c "SELECT entityid, count(*) FROM transito.trafficflowobserved WHERE entityid LIKE '%s1-sensor-%' GROUP BY entityid;"
```

Adapte usuário e banco se alterados no `.env` original. A tabela de histórico do Grafana existente continua disponível, mas o dashboard antigo está associado aos sensores A/B e deverá ser expandido posteriormente. O CrateDB deve registrar os novos sensores via subscription por tipo de entidade já existente. Observe o espaço em disco e o intervalo de publicação.

`signals --tick 4` altera estados virtuais diretamente no Orion-LD. Não representa controle físico, coordenação de fases nem um plano semafórico seguro. Alguns pontos são hipotéticos e estão identificados como tal.

### Preparação para a IA (Sprint 2)

O simulador adiciona diferenças entre dias úteis e fins de semana, variação diária, ruído autocorrelacionado e incidentes por corredor. A ocupação é fração 0–1; velocidade em km/h; `intensity` segue a convenção da implementação anterior: quantidade estimada no intervalo de cinco minutos (não veículos/hora). `TimeInstant` em UTC. Nenhuma previsão é treinada nesta sprint. Somente após validar a integridade do histórico, gere períodos mais longos e inéditos com `--dias` (30 dias é a meta da próxima sprint). A velocidade de publicação deve respeitar a capacidade do broker e bancos; não use espaçamento zero sem teste de carga. Não conclua que um modelo treinado nos dados sintéticos prevê o trânsito real de Natal.

## 5. Aceite e versionamento

- [ ] Testes automatizados passam no computador local.
- [ ] Extração real concluída; grafo, GeoJSON e inventário visualmente conferidos.
- [ ] Rota convencional calculada entre dois pontos válidos.
- [ ] Três tipos de entidade criados e relacionamentos conferidos.
- [ ] Sensores do inventário registrados e publicados via MQTT.
- [ ] Semáforos simulados agrupados por corredor.
- [ ] Validação do CrateDB indica todas as amostras do teste curto, sem duplicações; conferência do Draco realizada.
- [ ] Alterações adicionadas à branch de desenvolvimento, mantendo `main` intacta.

```powershell
git status
git add geodata sprint1 tests docs/SPRINT1.md .gitignore
git commit -m "feat: add pilot road graph and FIWARE traffic expansion"
```

O código novo foi compilado e testado com uma malha sintética no ambiente de preparação. OSMnx, Overpass, Docker e os serviços FIWARE reais não foram executados nesse ambiente. Não considere a Sprint 1 concluída antes dos testes de integração no ambiente do projeto.

## Referências técnicas

- OSMnx: https://osmnx.readthedocs.io/en/stable/user-reference.html
- Smart Data Models (Device): https://github.com/smart-data-models/dataModel.Device/tree/master/Device
- Smart Data Models (Transportation): https://github.com/smart-data-models/dataModel.Transportation
- Atribuição OSM: https://www.openstreetmap.org/copyright
