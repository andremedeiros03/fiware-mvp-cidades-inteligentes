# Publicações MQTT do MVP

Este documento lista as mensagens MQTT usadas para testar o fluxo dos sensores até o Orion-LD. Cada caso tem o comando, o resultado esperado e um espaço para o resultado observado.

## Estrutura do tópico

```text
/json/<apikey>/<device_id>/attrs
```

| Parte | Valor no MVP | Significado |
|---|---|---|
| `json` | fixo | Protocolo do IoT Agent JSON |
| `<apikey>` | `chave-trafego` | Chave do service group do tenant `transito` |
| `<device_id>` | `sensor-trafego-a` ou `sensor-trafego-b` | Sensor registrado no IoT Agent |
| `attrs` | fixo | Mensagem com medições |

## Estrutura da mensagem

```json
{"v": 44.5, "q": 38, "o": 0.12, "TimeInstant": "2026-10-05T10:00:00Z"}
```

| Chave | Atributo NGSI-LD | Unidade |
|---|---|---|
| `v` | `averageVehicleSpeed` | km/h |
| `q` | `intensity` | veículos em 5 min |
| `o` | `occupancy` | fração de 0 a 1 |
| `TimeInstant` | `observedAt` de cada atributo e valor de `dateObserved` | ISO 8601 UTC |

O IoT Agent calcula `congested` com a expressão `o > 0.25`.

## Acompanhar as mensagens

Em um terminal separado, mostre todas as mensagens que chegam ao broker:

```bash
sudo docker exec mosquitto mosquitto_sub -v -t '/json/#'
```

## Consultar o resultado

Defina o cabeçalho `Link` e um filtro `jq` que resume os atributos medidos e os horários:

```bash
LINK='<https://smart-data-models.github.io/dataModel.Transportation/context.jsonld>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'

RESUMO='{id, averageVehicleSpeed: .averageVehicleSpeed.value, intensity: .intensity.value, occupancy: .occupancy.value, congested: .congested.value, observedAt: .averageVehicleSpeed.observedAt, dateObserved: .dateObserved.value}'
```

Consulte a entidade de um sensor com o resumo:

```bash
curl -s 'localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-b' \
  -H 'NGSILD-Tenant: transito' -H "Link: $LINK" | jq "$RESUMO"
```

Para ver a entidade completa, troque `jq "$RESUMO"` por `jq`.

### Exemplo de entidade completa

Resultado do caso 1. O IoT Agent aplica o `TimeInstant` da mensagem como `observedAt` de todos os atributos, inclusive dos estáticos.

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-a",
  "type": "TrafficFlowObserved",
  "refRoadSegment": {
    "object": "urn:ngsi-ld:RoadSegment:avenida-principal-a",
    "type": "Relationship",
    "observedAt": "2026-10-05T10:00:00.000Z"
  },
  "laneId": {"value": 1, "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "laneDirection": {"value": "forward", "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "location": {
    "value": {"type": "Point", "coordinates": [-46.65, -10.1045]},
    "type": "GeoProperty",
    "observedAt": "2026-10-05T10:00:00.000Z"
  },
  "dataProvider": {"value": "simulador-mvp", "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "averageVehicleSpeed": {"value": 56.2, "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "intensity": {"value": 41, "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "occupancy": {"value": 0.09, "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "congested": {"value": false, "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"},
  "dateObserved": {"value": "2026-10-05T10:00:00.000Z", "type": "Property", "observedAt": "2026-10-05T10:00:00.000Z"}
}
```

## Casos de uso

### Caso 1: fluxo livre no Trecho A

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-trafego/sensor-trafego-a/attrs' \
  -m '{"v":56.2,"q":41,"o":0.09,"TimeInstant":"2026-10-05T10:00:00Z"}'
```

**Esperado:** a entidade `sensor-trafego-a` é criada na primeira medição, com `averageVehicleSpeed` = 56.2, `intensity` = 41, `occupancy` = 0.09 e `congested` = `false`. O `observedAt` de cada atributo é `2026-10-05T10:00:00Z`.

**Observado:** conforme o esperado.

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-a",
  "averageVehicleSpeed": 56.2,
  "intensity": 41,
  "occupancy": 0.09,
  "congested": false,
  "observedAt": "2026-10-05T10:00:00.000Z",
  "dateObserved": "2026-10-05T10:00:00.000Z"
}
```

### Caso 2: fluxo livre no Trecho B

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-trafego/sensor-trafego-b/attrs' \
  -m '{"v":44.5,"q":38,"o":0.12,"TimeInstant":"2026-10-05T10:00:00Z"}'
```

**Esperado:** a entidade `sensor-trafego-b` tem `averageVehicleSpeed` = 44.5 e `congested` = `false`. A entidade `sensor-trafego-a` não muda.

**Observado:** conforme o esperado. A entidade `sensor-trafego-a` manteve os valores do caso 1.

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-b",
  "averageVehicleSpeed": 44.5,
  "intensity": 38,
  "occupancy": 0.12,
  "congested": false,
  "observedAt": "2026-10-05T10:00:00.000Z",
  "dateObserved": "2026-10-05T10:00:00.000Z"
}
```

### Caso 3: congestionamento no Trecho B

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-trafego/sensor-trafego-b/attrs' \
  -m '{"v":17.8,"q":22,"o":0.34,"TimeInstant":"2026-10-05T10:05:00Z"}'
```

**Esperado:** a ocupação passa de 0.25, então `congested` = `true`. A velocidade e o fluxo caem ao mesmo tempo: a via tem mais veículos, mas escoa menos. O `observedAt` e o `dateObserved` passam para `2026-10-05T10:05:00Z`.

**Observado:** conforme o esperado.

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-b",
  "averageVehicleSpeed": 17.8,
  "intensity": 22,
  "occupancy": 0.34,
  "congested": true,
  "observedAt": "2026-10-05T10:05:00.000Z",
  "dateObserved": "2026-10-05T10:05:00.000Z"
}
```

### Caso 4: limite do congestionamento

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-trafego/sensor-trafego-b/attrs' \
  -m '{"v":30.1,"q":35,"o":0.25,"TimeInstant":"2026-10-05T10:10:00Z"}'
```

**Esperado:** a expressão usa `>` e não `>=`, então ocupação igual a 0.25 dá `congested` = `false`.

**Observado:** conforme o esperado.

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-b",
  "averageVehicleSpeed": 30.1,
  "intensity": 35,
  "occupancy": 0.25,
  "congested": false,
  "observedAt": "2026-10-05T10:10:00.000Z",
  "dateObserved": "2026-10-05T10:10:00.000Z"
}
```

### Caso 5: medição sem `TimeInstant`

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-trafego/sensor-trafego-a/attrs' \
  -m '{"v":52.0,"q":40,"o":0.11}'
```

**Esperado:** o `observedAt` recebe a hora de chegada ao IoT Agent, e não a hora da observação. A expressão do `dateObserved` não tem valor para copiar, então o IoT Agent não envia esse atributo, e o Orion-LD mantém o valor anterior.

**Observado:** as medições receberam a hora de chegada (`22:30:33`), mas o `dateObserved` ficou com o valor do caso 1 (`10:00:00`). A entidade passa a ter duas datas que não concordam.

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-a",
  "averageVehicleSpeed": 52,
  "intensity": 40,
  "occupancy": 0.11,
  "congested": false,
  "observedAt": "2026-10-05T22:30:33.629Z",
  "dateObserved": "2026-10-05T10:00:00.000Z"
}
```

**Conclusão:** o sensor deve sempre enviar o `TimeInstant`. Sem ele, o horário registrado depende de atrasos na rede, e o `dateObserved` fica desatualizado.

### Caso 6: chave de API errada

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-invalida/sensor-trafego-a/attrs' \
  -m '{"v":10.0,"q":5,"o":0.50,"TimeInstant":"2026-10-05T10:15:00Z"}'
```

**Esperado:** o IoT Agent ignora a mensagem, porque não existe service group com essa chave. A entidade `sensor-trafego-a` não muda. O log do IoT Agent registra o erro:

```bash
docker logs fiware-iot-agent 2>&1 | grep MEASURES-004 | tail -1
```

**Observado:** conforme o esperado. A entidade `sensor-trafego-a` manteve os valores do caso 5, e o log registra:

```text
lvl=DEBUG | msg=Looking for group params ["resource","apikey"] with queryObj {"resource":"/iot/json","apikey":"chave-invalida"}
lvl=DEBUG | msg=Device group for fields [["resource","apikey"]] not found: [{"resource":"/iot/json","apikey":"chave-invalida"}]
lvl=WARN  | msg=MEASURES-004: Device not found for topic /json/chave-invalida/sensor-trafego-a/attrs
```

### Caso 7: sensor não registrado

```bash
sudo docker exec mosquitto mosquitto_pub -t '/json/chave-trafego/sensor-trafego-x/attrs' \
  -m '{"v":40.0,"q":30,"o":0.15,"TimeInstant":"2026-10-05T10:20:00Z"}'
```

**Esperado:** a chave existe, então o IoT Agent registra o sensor automaticamente (autoprovisionamento). O `id` da entidade junta o tipo do service group e o `device_id`. Como o sensor não tem mapeamento de atributos, as chaves `v`, `q` e `o` chegam sem tradução, e faltam os atributos calculados e estáticos.

Liste as entidades para ver o resultado:

```bash
curl -s 'localhost:1026/ngsi-ld/v1/entities?type=TrafficFlowObserved&options=keyValues' \
  -H 'NGSILD-Tenant: transito' -H "Link: $LINK" | jq
```

**Observado:** conforme o esperado. O log registra `Registering autoprovision of Device {"id":"sensor-trafego-x", ...}`, e a entidade criada é:

```json
{
  "id": "urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-x",
  "type": "TrafficFlowObserved",
  "v": {"value": 40, "type": "Property", "observedAt": "2026-10-05T10:20:00.000Z"},
  "q": {"value": 30, "type": "Property", "observedAt": "2026-10-05T10:20:00.000Z"},
  "o": {"value": 0.15, "type": "Property", "observedAt": "2026-10-05T10:20:00.000Z"}
}
```

A entidade tem o tipo `TrafficFlowObserved`, mas não segue o Data Model: não tem `averageVehicleSpeed`, `congested`, `dateObserved`, `refRoadSegment` nem `location`.

**Conclusão:** cada sensor deve ser registrado antes de publicar.

Depois do teste, remova o sensor no IoT Agent e a entidade no Orion-LD. Remover o sensor não apaga a entidade.

```bash
curl -s -X DELETE localhost:4041/iot/devices/sensor-trafego-x \
  -H 'fiware-service: transito' -H 'fiware-servicepath: /' -w '%{http_code}\n'

curl -s -X DELETE 'localhost:1026/ngsi-ld/v1/entities/urn:ngsi-ld:TrafficFlowObserved:sensor-trafego-x' \
  -H 'NGSILD-Tenant: transito' -w '%{http_code}\n'
```

Os dois comandos devem responder `204`.
