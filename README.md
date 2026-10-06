# MVP FIWARE: monitoramento de tráfego urbano

MVP de Cidades Inteligentes que monitora o fluxo de veículos em um corredor viário com Generic Enablers (GEs) FIWARE e NGSI-LD.

Dois sensores de tráfego virtuais, um em cada trecho da **Avenida Principal** (via fictícia), publicam a cada 5 minutos a velocidade média, o número de veículos e a ocupação da faixa. A plataforma mantém o estado atual de cada trecho, marca os períodos de congestionamento, guarda o histórico e mostra os indicadores em um dashboard.

Os dados são **sintéticos**, gerados por um simulador com perfil diário de tráfego e modelo de Greenshields.

## Arquitetura

```text
 Simulador de sensores
        │ MQTT (JSON)
        ▼
    Mosquitto ──────► IoT Agent JSON ──────► Orion-LD ◄──── MongoDB
                                             │      │
                             subscription NGSI-LD   subscription NGSI-LD
                                             ▼      ▼
                                    QuantumLeap    Draco (NiFi)
                                             │      │
                                             ▼      ▼
                                       CrateDB    PostgreSQL
                                             │
                                             ▼
                                          Grafana
```

| Componente | Função | Versão | Porta local |
|---|---|---|---:|
| Orion-LD | Context Broker NGSI-LD | 1.12.0 | 1026 |
| MongoDB | Base do Orion-LD | 4.4 | 27017 |
| IoT Agent JSON | Converte mensagens MQTT em NGSI-LD | 3.14.0 | 4041 |
| MongoDB | Registro do IoT Agent | 6.0 | — |
| Mosquitto | Broker MQTT | 2.0.22 | 1883 |
| QuantumLeap | Histórico temporal (API) | 1.0.0 | 8668 |
| CrateDB | Banco do QuantumLeap | 5.5 | 4200 (HTTP) / 5433 (PostgreSQL) |
| Draco | Persistência de notificações (Apache NiFi) | 2.1.0 | 9090 (interface) / 5050 (notificações) |
| PostgreSQL | Banco do Draco | 15 | 5432 |
| Grafana | Dashboard | 13.2.2 | 3000 |

## Data Model

Smart Data Models, domínio de transporte: <https://github.com/smart-data-models/dataModel.Transportation>

| Entidade | Origem | Identificadores |
|---|---|---|
| `RoadSegment` | Provisionamento | `urn:ngsi-ld:RoadSegment:avenida-principal-a`, `...-b` |
| `TrafficFlowObserved` | Sensores via IoT Agent | `urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-a`, `...-b` |

Todos os dados ficam no tenant `transito`.

## Pré-requisitos

- Docker e Docker Compose
- Cerca de 4 GB de memória livre
- **Disco com menos de 85% de uso.** Acima disso, o CrateDB não cria tabelas, e o histórico não é gravado.
- Acesso à internet (o `@context` do Smart Data Models é baixado em tempo de execução)

Se o seu usuário não estiver no grupo `docker`, coloque `sudo` antes dos comandos `docker`.

## Execução

### 1. Subir os serviços

```bash
docker compose up -d
docker compose ps
```

O `driver-downloader` termina com `Exited (0)` depois de baixar o driver JDBC do Draco.

### 2. Provisionar o ambiente

```bash
docker compose --profile setup run --rm provisionamento
```

O provisionamento espera os serviços responderem e cria, nessa ordem:

1. As entidades `RoadSegment` dos trechos A e B no Orion-LD.
2. O service group `chave-trafego` e os devices `sensor-trafego-a` e `sensor-trafego-b` no IoT Agent.
3. A subscription do Orion-LD para o QuantumLeap.
4. A tabela de histórico no CrateDB, com colunas decimais.
5. O fluxo `ListenHTTP → NGSIToPostgreSQL → LogAttribute` no Draco.
6. A subscription do Orion-LD para o Draco.

Pode ser executado de novo sem duplicar dados.

### 3. Gerar dados

Gera o equivalente a um dia de tráfego simulado em cerca de 5 minutos:

```bash
docker compose --profile simulador run --rm simulador --inicio 2026-10-06T00:00:00
```

| Parâmetro | Padrão | Descrição |
|---|---|---|
| `--inicio` | hoje às 00:00 | Início da simulação (ISO 8601, horário local) |
| `--dias` | 1 | Dias simulados |
| `--intervalo` | 1 | Segundos reais por passo de 5 minutos |
| `--tempo-real` | — | Publica um passo a cada 5 minutos com a hora atual |
| `--fuso` | -3 | Fuso horário local em horas |
| `--semente` | 42 | Semente do ruído aleatório |

O QuantumLeap duplica linhas quando recebe a mesma observação duas vezes. Antes de simular de novo um período já simulado, limpe o histórico:

```bash
curl -s -X DELETE localhost:8668/v2/types/TrafficFlowObserved \
  -H 'Fiware-Service: transito' -H 'Fiware-ServicePath: /'
docker exec postgres-db psql -U draco_user -d fiware_data -c 'TRUNCATE transito.trafficflowobserved;'
```

### 4. Ver o dashboard

Abra <http://localhost:3000> (admin:admin) → **Dashboards → FIWARE → Avenida Principal: monitoramento de tráfego**.

O intervalo padrão é o dia 06/10/2026. No modo `--tempo-real`, troque o intervalo para "Last 6 hours".

## Validação

Defina o cabeçalho de contexto:

```bash
LINK='<https://smart-data-models.github.io/dataModel.Transportation/context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
```

Estado atual no Orion-LD:

```bash
curl -s 'localhost:1026/ngsi-ld/v1/entities?type=TrafficFlowObserved&options=keyValues' \
  -H 'NGSILD-Tenant: transito' -H "Link: $LINK" | jq
```

Histórico pela API do QuantumLeap:

```bash
curl -s 'localhost:8668/v2/entities/urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-b/attrs/averageVehicleSpeed?lastN=5' \
  -H 'Fiware-Service: transito' -H 'Fiware-ServicePath: /' | jq
```

Histórico no CrateDB (ou no console <http://localhost:4200/#!/console>):

```bash
curl -s -X POST localhost:4200/_sql -H 'Content-Type: application/json' \
  -d '{"stmt":"SELECT entity_id, count(*), sum(CASE WHEN congested THEN 1 ELSE 0 END) FROM mttransito.ettrafficflowobserved GROUP BY entity_id"}' | jq .rows
```

Histórico no PostgreSQL (Draco):

```bash
docker exec postgres-db psql -U draco_user -d fiware_data \
  -c 'SELECT entityid, count(*) FROM transito.trafficflowobserved GROUP BY entityid;'
```

Depois de um dia simulado, cada sensor tem 288 linhas nos dois bancos.

## Testes manuais

- [`docs/mqtt.md`](docs/mqtt.md): tópicos, formato das mensagens e casos de teste MQTT com resultados observados.
- [`hoppscotch/mvp-trafego.postman_collection.json`](hoppscotch/mvp-trafego.postman_collection.json): coleção com as requisições HTTP de cada etapa. Importe no Hoppscotch ou no Postman (formato Postman v2.1).

## Limitações conhecidas

| Limitação | Efeito | Tratamento no MVP |
|---|---|---|
| O Orion-LD 1.12.0 usa o protocolo `OP_QUERY`, removido do MongoDB 5.1 | Não inicia com MongoDB 6.0 ou superior | MongoDB 4.4 para o Orion-LD |
| O CrateDB não aloca shards com o disco acima de 85% | O QuantumLeap não grava, e o Orion-LD registra timeout | Pré-requisito de disco |
| O QuantumLeap fixa o tipo da coluna pelo primeiro valor | Um primeiro valor inteiro cria coluna `bigint`, e os decimais seguintes se perdem | O provisionamento cria a tabela com valores decimais |
| A conversão NGSI-LD → NGSI-v2 do Orion-LD deixa o `observedAt` como texto | O Draco em modo `v2` falha | Draco em modo `ld`, com `db-by-entity-type` |
| O Orion-LD pode deixar de notificar um destino lento quando duas entidades mudam ao mesmo tempo | O Draco perdeu 4,5% das notificações, sem registro de falha | O simulador espaça as publicações dos sensores |
| O teste de saúde do Grafana envia um comando vazio, que o CrateDB rejeita | "Save & test" falha no datasource CrateDB | Nenhum: as consultas funcionam |
| O Draco grava todos os valores como texto | Consultas no PostgreSQL exigem conversão de tipo | O dashboard usa o CrateDB |
| Sem `TimeInstant`, o IoT Agent usa a hora de chegada e não atualiza o `dateObserved` | Horários inconsistentes na entidade | O simulador sempre envia `TimeInstant` |

## Estrutura do repositório

```text
.
├── docker-compose.yml
├── README.md
├── docs/
│   └── mqtt.md
├── grafana/
│   ├── dashboards/
│   │   └── avenida-principal.json
│   └── provisioning/
│       ├── dashboards/dashboards.yml
│       └── datasources/
│           ├── cratedb.yml
│           └── postgres.yml
├── hoppscotch/
│   └── mvp-trafego.postman_collection.json
├── provisionamento/
│   ├── Dockerfile
│   └── provisionamento.py
└── simulador/
    ├── Dockerfile
    └── simulador.py
```

## Autores

- André Medeiros
- Ângelo Campelo

Projeto acadêmico desenvolvido no Instituto Metrópole Digital / UFRN.
