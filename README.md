# Protótipo de Infraestrutura FIWARE para Cidades Inteligentes

Este repositório contém um **protótipo técnico e reutilizável** de infraestrutura FIWARE desenvolvido para apoiar a construção de um MVP no contexto de Internet das Coisas e Cidades Inteligentes.

A ideia central do projeto ainda será definida. O cenário atual de **sensor de temperatura e umidade** foi usado apenas para validar o funcionamento da arquitetura completa, desde a publicação via MQTT até a persistência e visualização dos dados.

A infraestrutura já validada poderá ser reaproveitada quando o problema real do projeto for escolhido. Nesse momento, será necessário principalmente adaptar as entidades NGSI-LD, o Data Model, os atributos dos dispositivos, os tópicos MQTT, as subscriptions e o dashboard.

## Objetivo deste protótipo

Validar uma arquitetura FIWARE capaz de:

- receber dados de dispositivos via MQTT;
- integrar dispositivos com o FIWARE por meio do IoT Agent;
- gerenciar contexto com o Orion-LD;
- armazenar histórico com QuantumLeap e CrateDB;
- persistir notificações com Draco e PostgreSQL;
- visualizar dados em dashboards com Grafana.

## Arquitetura validada

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

## Cenário atual de validação

O cenário usado até aqui é apenas um exemplo técnico para comprovar o funcionamento da infraestrutura.

Entidade utilizada:

```text
urn:ngsi-ld:Device:sensor-temperatura-001
```

Tipo:

```text
Device
```

Atributos principais:

- `temperature`
- `humidity`

Quando a ideia central do projeto for definida, essa entidade e seus atributos serão substituídos ou adaptados para o domínio escolhido.

## MQTT

Tópico utilizado no cenário de teste:

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

Exemplo de consulta temporal utilizada na validação:

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

O datasource `FIWARE PostgreSQL` é configurado automaticamente apontando para o PostgreSQL utilizado pelo Draco.

O dashboard de validação é:

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

A visualização no Grafana foi validada com sucesso. Quando o domínio definitivo do projeto for escolhido, o dashboard será adaptado aos indicadores relevantes para a solução.

Arquivos de provisionamento:

```text
grafana/provisioning/datasources/postgres.yml
grafana/provisioning/dashboards/dashboards.yml
grafana/dashboards/fiware-sensor.json
```

## Observações técnicas encontradas durante a validação

Durante a configuração e os testes foram identificados alguns pontos importantes:

- o processor `NGSIToPostgreSQL` do Draco funcionou de forma estável com notificações no formato NGSI-v2 normalizado;
- o modelo `db-by-entity` gerou nomes de tabela grandes demais para o limite de identificadores do PostgreSQL, por isso foi utilizado `db-by-service-path`;
- no CrateDB, a coluna `temperature` foi inicialmente inferida como `BIGINT`, o que removeu casas decimais de valores posteriores;
- no PostgreSQL do Draco, o campo `recvtimets` foi persistido como texto e pode conter timestamp em formato ISO, exigindo tratamento na consulta do Grafana.

Esses pontos fazem parte da validação técnica do protótipo e serão considerados na evolução do MVP.

## O que será reutilizado no projeto final

A maior parte desta infraestrutura poderá ser mantida:

- `docker-compose.yml`;
- Orion-LD;
- MongoDB;
- Mosquitto;
- IoT Agent;
- Draco;
- PostgreSQL;
- QuantumLeap;
- CrateDB;
- Grafana;
- rede Docker;
- fluxo geral de aquisição, gerenciamento, persistência e visualização.

## O que deverá ser adaptado

Após a definição da ideia central do projeto, deverão ser ajustados:

- problema de Cidades Inteligentes a ser resolvido;
- beneficiários da solução;
- entidades e tipos NGSI-LD;
- Data Model utilizado;
- atributos e sensores;
- tópicos MQTT;
- service groups e devices do IoT Agent;
- subscriptions do Orion-LD;
- consultas e painéis do Grafana;
- documentação e relatório final.

## Próxima etapa

A próxima etapa do projeto é definir a **ideia central do MVP**, incluindo:

1. problema dentro do contexto de Cidades Inteligentes;
2. público beneficiado;
3. dados de contexto necessários;
4. Data Model adequado;
5. sensores ou fontes de dados;
6. indicadores que serão exibidos no dashboard.

Depois disso, a infraestrutura deste repositório será adaptada para representar a solução definitiva.

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

## Status atual

- MQTT -> IoT Agent: funcionando
- IoT Agent -> Orion-LD: funcionando
- Orion-LD -> QuantumLeap -> CrateDB: funcionando
- Orion-LD -> Draco -> PostgreSQL: funcionando
- PostgreSQL -> Grafana: funcionando
- Dashboard de validação: funcionando
- Ideia central do MVP: pendente de definição
- Data Model definitivo: pendente de definição
- Dashboard definitivo: pendente de adaptação

## Autor

André Fernandes Medeiros

Projeto acadêmico desenvolvido no Instituto Metrópole Digital / UFRN.
