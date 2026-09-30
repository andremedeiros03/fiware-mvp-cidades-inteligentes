# MVP FIWARE para Cidades Inteligentes

Projeto acadêmico desenvolvido para demonstrar a implantação e integração de Generic Enablers FIWARE em um cenário de Internet das Coisas e Cidades Inteligentes.

A solução implementa o fluxo completo de aquisição, gerenciamento, persistência e visualização de dados de contexto usando MQTT, IoT Agent, Orion-LD, QuantumLeap, Draco, CrateDB, PostgreSQL e Grafana.

## Arquitetura

```text
Sensor / Cliente MQTT
        |
        v
   Mosquitto MQTT
        |
        v
 IoT Agent JSON
        |
        v
    Orion-LD
      /   \
     v     v
 QuantumLeap   Draco
     |          |
     v          v
  CrateDB   PostgreSQL
                |
                v
              Grafana
```

## Componentes utilizados

| Componente | Função | Porta local |
|---|---|---:|
| Orion-LD | Context Broker NGSI-LD | 1026 |
| MongoDB | Persistência do Orion-LD | 27017 |
| IoT Agent JSON | Integração entre dispositivos/MQTT e Orion-LD | 4041 |
| Mosquitto | Broker MQTT | 1883 |
| QuantumLeap | Histórico temporal de contexto | 8668 |
| CrateDB | Banco temporal utilizado pelo QuantumLeap | 4200 / 5433 |
| Draco | Persistência de notificações do Orion | 9090 / 5050 |
| PostgreSQL | Persistência utilizada pelo Draco | 5432 |
| Grafana | Dashboard de visualização | 3000 |

## Pré-requisitos

- Docker
- Docker Compose
- Git
- curl ou Postman para testes HTTP

## Executando o ambiente

Clone o repositório:

```bash
git clone https://github.com/andremedeiros03/fiware-mvp-cidades-inteligentes.git
```

Entre na pasta:

```bash
cd fiware-mvp-cidades-inteligentes
```

Suba os serviços:

```bash
docker compose up -d
```

Confira os containers:

```bash
docker compose ps
```

## Entidade utilizada nos testes

```text
urn:ngsi-ld:Device:sensor-temperatura-001
```

Tipo: `Device`

Atributos principais:

- `temperature`
- `humidity`

## MQTT

Tópico utilizado:

```text
/json/minha-chave-secreta-456/sensor-temperatura-001/attrs
```

Exemplo de publicação:

```bash
docker exec -it mosquitto mosquitto_pub -h localhost -t '/json/minha-chave-secreta-456/sensor-temperatura-001/attrs' -m '{"t":34.2,"h":49.8}'
```

Aliases utilizados pelo IoT Agent:

```text
t -> temperature
h -> humidity
```

## Draco + PostgreSQL

Fluxo configurado no Apache NiFi do Draco:

```text
ListenHTTP -> NGSIToPostgreSQL -> LogAttribute
```

Configuração utilizada no `NGSIToPostgreSQL`:

| Propriedade | Valor |
|---|---|
| JDBC Connection Pool | DBCPConnectionPool |
| NGSI Version | v2 |
| Data Model | db-by-service-path |
| Attribute Persistence | row |
| Default Service | treinamento_fiware |
| Default Service path | / |
| Enable Encoding | true |
| CKAN compatibility | false |
| Enable Lowercase | true |
| Batch Size | 1 durante os testes |
| Rollback On Failure | false |

Pool JDBC:

```text
jdbc:postgresql://postgres-db:5432/fiware_data
```

Driver PostgreSQL no Draco:

```text
/opt/nifi/nifi-current/drivers/postgresql.jar
```

### Validação no PostgreSQL

```bash
docker exec -it postgres-db psql -U draco_user -d fiware_data -c '\dn'
```

```bash
docker exec -it postgres-db psql -U draco_user -d fiware_data -c '\dt treinamento_fiware.*'
```

Tabela criada durante os testes:

```text
treinamento_fiware.x002f
```

Consulta dos registros:

```bash
docker exec -it postgres-db psql -U draco_user -d fiware_data -c 'SELECT * FROM treinamento_fiware.x002f;'
```

## QuantumLeap + CrateDB

Exemplo de consulta temporal:

```http
GET http://localhost:8668/v2/entities/urn:ngsi-ld:Device:sensor-temperatura-001/attrs/temperature?type=Device&lastN=5
```

Foi validado o armazenamento de múltiplas medições históricas da entidade.

## Grafana

O Grafana é provisionado automaticamente pelo Docker Compose.

Acesse:

```text
http://localhost:3000
```

Credenciais padrão do ambiente de laboratório:

```text
usuário: admin
senha: admin
```

O datasource `FIWARE PostgreSQL` é configurado automaticamente apontando para o PostgreSQL utilizado pelo Draco.

O dashboard provisionado é:

```text
FIWARE - Sensor de Temperatura e Umidade
```

Ele contém dois painéis de série temporal:

- Temperatura
- Umidade

Os painéis consultam diretamente:

```text
treinamento_fiware.x002f
```

O dashboard utiliza `recvtimets` como eixo temporal e `attrvalue` como valor da medição.

Arquivos de provisionamento:

```text
grafana/provisioning/datasources/postgres.yml
grafana/provisioning/dashboards/dashboards.yml
grafana/dashboards/fiware-sensor.json
```

## Observação sobre o tipo de `temperature`

Durante os testes, a coluna `temperature` foi inicialmente criada como `BIGINT` no CrateDB. Como consequência, valores decimais posteriores foram armazenados sem as casas decimais.

A integração permanece funcional, mas esse comportamento deve ser considerado caso o projeto exija precisão decimal no histórico temporal.

## Estrutura do repositório

```text
.
├── docker-compose.yml
├── README.md
├── .gitignore
├── grafana/
│   ├── dashboards/
│   │   └── fiware-sensor.json
│   └── provisioning/
│       ├── dashboards/
│       │   └── dashboards.yml
│       └── datasources/
│           └── postgres.yml
└── docs/
    └── relatorio.md
```

## Status da integração

- MQTT -> IoT Agent: funcionando
- IoT Agent -> Orion-LD: funcionando
- Orion-LD -> QuantumLeap -> CrateDB: funcionando
- Orion-LD -> Draco -> PostgreSQL: funcionando
- PostgreSQL -> Grafana: configurado

## Autor

André Fernandes Medeiros

Projeto acadêmico desenvolvido no Instituto Metrópole Digital / UFRN.
