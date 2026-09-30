# Relatório Prático do MVP e Deploy de GEs FIWARE

## 1. Concepção da solução

O projeto implementa um MVP de monitoramento de contexto para Cidades Inteligentes utilizando FIWARE. Os dados são enviados por MQTT, processados pelo IoT Agent JSON, gerenciados pelo Orion-LD e persistidos em dois caminhos: QuantumLeap/CrateDB e Draco/PostgreSQL.

Entidade utilizada nos testes:

```text
urn:ngsi-ld:Device:sensor-temperatura-001
```

Atributos principais:

- `temperature`
- `humidity`

## 2. Arquitetura

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
```

## 3. Componentes

- Orion-LD: gerenciamento de contexto NGSI-LD.
- IoT Agent JSON: integração entre MQTT e Orion-LD.
- Mosquitto: broker MQTT.
- QuantumLeap + CrateDB: histórico temporal.
- Draco + PostgreSQL: persistência relacional.

## 4. Validação realizada

O fluxo completo foi validado com sucesso:

```text
MQTT -> IoT Agent -> Orion-LD -> QuantumLeap -> CrateDB
                           \
                            -> Draco -> PostgreSQL
```

No PostgreSQL foi criado o schema `treinamento_fiware` e a tabela `x002f`, contendo registros dos atributos `temperature` e `humidity`.

No QuantumLeap foi validada a consulta do histórico temporal de `temperature` com múltiplas medições.

## 5. Próximas etapas

- adicionar a camada de dashboard prevista na atividade;
- incluir evidências dos testes;
- detalhar variáveis, portas e configuração do Draco;
- gerar a versão final do relatório em PDF.
