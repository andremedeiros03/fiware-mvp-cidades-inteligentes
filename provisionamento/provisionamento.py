import json
import os
import sys
import time
import urllib.error
import urllib.request

ORION = os.environ.get("ORION_URL", "http://orion-ld:1026")
IOTA = os.environ.get("IOTA_URL", "http://iot-agent:4041")
QUANTUMLEAP = os.environ.get("QUANTUMLEAP_URL", "http://quantumleap:8668")
CRATE = os.environ.get("CRATE_URL", "http://cratedb:4200")
NIFI = os.environ.get("NIFI_URL", "http://draco:9090")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "draco_user")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "draco_password")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "fiware_data")

TENANT = "transito"
API_KEY = "chave-trafego"
ENTITY_TYPE = "TrafficFlowObserved"
CONTEXT = "https://smart-data-models.github.io/dataModel.Transportation/context.jsonld"
LINK = f'<{CONTEXT}>; rel="http://www.w3.org/ns/json-ld#context"; type="application/ld+json"'
ORION_HEADERS = {"NGSILD-Tenant": TENANT, "Link": LINK}
IOTA_HEADERS = {"fiware-service": TENANT, "fiware-servicepath": "/"}
QL_HEADERS = {"Fiware-Service": TENANT, "Fiware-ServicePath": "/"}
WATCHED_ATTRIBUTES = ["averageVehicleSpeed", "intensity", "occupancy", "congested"]
QL_TABLE = ("mt" + TENANT, "et" + ENTITY_TYPE.lower())
PRIMING_ID = f"urn:ngsi-ld:{ENTITY_TYPE}:preparo"
NIFI_TEMPLATE = "ORION-TO-POSTGRESQL"
WAIT_SECONDS = 180


class HttpError(Exception):
    pass


def request(method, url, body=None, headers=None, accept=(200, 201, 204)):
    data = json.dumps(body).encode() if body is not None else None
    all_headers = {"Content-Type": "application/json"} if data else {}
    all_headers.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status, text = response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        status, text = error.code, error.read().decode()
    if status not in accept:
        raise HttpError(f"{method} {url} -> {status}: {text[:300]}")
    return status, json.loads(text) if text.strip() else None


def log(state, message):
    print(f"[{state}] {message}", flush=True)


def wait_for(name, url):
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            request("GET", url)
            log("ok", f"{name} disponível")
            return
        except (HttpError, OSError):
            if time.monotonic() > deadline:
                sys.exit(f"[erro] {name} não respondeu em {WAIT_SECONDS} s ({url})")
            time.sleep(3)


def crate_sql(statement):
    _, result = request("POST", f"{CRATE}/_sql", {"stmt": statement})
    return result["rows"]


def road_segment(letter, name, lanes, speed, length, start, end):
    return {
        "id": f"urn:ngsi-ld:RoadSegment:avenida-principal-{letter}",
        "type": "RoadSegment",
        "name": {"type": "Property", "value": name},
        "refRoad": {"type": "Relationship", "object": "urn:ngsi-ld:Road:avenida-principal"},
        "startPoint": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": start}},
        "endPoint": {"type": "GeoProperty", "value": {"type": "Point", "coordinates": end}},
        "location": {"type": "GeoProperty", "value": {"type": "LineString", "coordinates": [start, end]}},
        "allowedVehicleType": {"type": "Property", "value": ["car", "bus", "motorcycle", "lorry"]},
        "totalLaneNumber": {"type": "Property", "value": lanes},
        "maximumAllowedSpeed": {"type": "Property", "value": speed, "unitCode": "KMH"},
        "length": {"type": "Property", "value": length, "unitCode": "KMT"},
    }


def device(letter, point):
    return {
        "device_id": f"sensor-trafego-{letter}",
        "entity_name": f"urn:ngsi-ld:{ENTITY_TYPE}:sensor-trafego-{letter}",
        "entity_type": ENTITY_TYPE,
        "apikey": API_KEY,
        "transport": "MQTT",
        "attributes": [
            {"object_id": "v", "name": "averageVehicleSpeed", "type": "Number"},
            {"object_id": "q", "name": "intensity", "type": "Number"},
            {"object_id": "o", "name": "occupancy", "type": "Number"},
            {"name": "congested", "type": "Boolean", "expression": "o > 0.25"},
            {"name": "dateObserved", "type": "DateTime", "expression": "TimeInstant"},
        ],
        "static_attributes": [
            {"name": "refRoadSegment", "type": "Relationship", "value": f"urn:ngsi-ld:RoadSegment:avenida-principal-{letter}"},
            {"name": "laneId", "type": "Number", "value": 1},
            {"name": "laneDirection", "type": "Text", "value": "forward"},
            {"name": "location", "type": "geo:json", "value": {"type": "Point", "coordinates": point}},
            {"name": "dataProvider", "type": "Text", "value": "simulador-mvp"},
        ],
    }


def subscription(name, description, uri):
    return {
        "id": f"urn:ngsi-ld:Subscription:{name}",
        "type": "Subscription",
        "description": description,
        "entities": [{"type": ENTITY_TYPE}],
        "watchedAttributes": WATCHED_ATTRIBUTES,
        "notification": {"endpoint": {"uri": uri, "accept": "application/json"}},
    }


def provision_road_segments():
    segments = [
        road_segment("a", "Avenida Principal - Trecho A (Norte)", 3, 60, 1.0, [-46.6500, -10.1000], [-46.6500, -10.1090]),
        road_segment("b", "Avenida Principal - Trecho B (Sul)", 2, 50, 0.9, [-46.6500, -10.1090], [-46.6500, -10.1170]),
    ]
    request("POST", f"{ORION}/ngsi-ld/v1/entityOperations/upsert", segments, ORION_HEADERS)
    log("ok", "RoadSegment avenida-principal-a e avenida-principal-b")


def provision_service_group():
    _, result = request("GET", f"{IOTA}/iot/services", headers=IOTA_HEADERS)
    if any(group["apikey"] == API_KEY for group in result["services"]):
        log("já existe", f"service group {API_KEY}")
        return
    group = {"apikey": API_KEY, "cbroker": "http://orion-ld:1026", "entity_type": ENTITY_TYPE, "resource": "/iot/json"}
    request("POST", f"{IOTA}/iot/services", {"services": [group]}, IOTA_HEADERS)
    log("criado", f"service group {API_KEY}")


def provision_devices():
    for letter, point in (("a", [-46.6500, -10.1045]), ("b", [-46.6500, -10.1130])):
        device_id = f"sensor-trafego-{letter}"
        status, _ = request("GET", f"{IOTA}/iot/devices/{device_id}", headers=IOTA_HEADERS, accept=(200, 404))
        if status == 200:
            log("já existe", f"device {device_id}")
            continue
        request("POST", f"{IOTA}/iot/devices", {"devices": [device(letter, point)]}, IOTA_HEADERS)
        log("criado", f"device {device_id}")


def provision_subscription(body):
    url = f"{ORION}/ngsi-ld/v1/subscriptions"
    request("DELETE", f"{url}/{body['id']}", headers=ORION_HEADERS, accept=(204, 404))
    request("POST", url, body, ORION_HEADERS)
    log("criado", f"subscription {body['id']}")


def table_exists():
    schema, table = QL_TABLE
    rows = crate_sql(
        f"SELECT count(*) FROM information_schema.tables WHERE table_schema = '{schema}' AND table_name = '{table}'"
    )
    return rows[0][0] > 0


def prime_quantumleap_table():
    if table_exists():
        log("já existe", f"tabela {'.'.join(QL_TABLE)}")
        return
    moment = "2000-01-01T00:00:00Z"
    entity = {
        "id": PRIMING_ID,
        "type": ENTITY_TYPE,
        "averageVehicleSpeed": {"type": "Property", "value": 0.5, "observedAt": moment},
        "occupancy": {"type": "Property", "value": 0.5, "observedAt": moment},
        "intensity": {"type": "Property", "value": 1, "observedAt": moment},
    }
    request("POST", f"{ORION}/ngsi-ld/v1/entities", entity, ORION_HEADERS)
    deadline = time.monotonic() + 60
    while not table_exists():
        if time.monotonic() > deadline:
            sys.exit("[erro] o QuantumLeap não criou a tabela em 60 s; verifique o espaço em disco do CrateDB")
        time.sleep(2)
    request("DELETE", f"{QUANTUMLEAP}/v2/types/{ENTITY_TYPE}", headers=QL_HEADERS)
    request("DELETE", f"{ORION}/ngsi-ld/v1/entities/{PRIMING_ID}", headers={"NGSILD-Tenant": TENANT})
    log("criado", f"tabela {'.'.join(QL_TABLE)} com colunas decimais")


def nifi(method, path, body=None):
    return request(method, f"{NIFI}/nifi-api{path}", body)[1]


def nifi_update_processor(processor, properties, auto_terminated):
    nifi("PUT", f"/processors/{processor['id']}", {
        "revision": processor["revision"],
        "component": {
            "id": processor["id"],
            "config": {"properties": properties, "autoTerminatedRelationships": auto_terminated},
        },
    })


def provision_draco_flow():
    root = nifi("GET", "/flow/process-groups/root")["processGroupFlow"]
    group_id = root["id"]
    if root["flow"]["processors"]:
        log("já existe", "fluxo NiFi do Draco")
        return
    templates = nifi("GET", "/flow/templates")["templates"]
    template_id = next(t["id"] for t in templates if t["template"]["name"] == NIFI_TEMPLATE)
    nifi("POST", f"/process-groups/{group_id}/template-instance", {"templateId": template_id, "originX": 0, "originY": 0})

    service = nifi("GET", f"/flow/process-groups/{group_id}/controller-services")["controllerServices"][0]
    service = nifi("PUT", f"/controller-services/{service['id']}", {
        "revision": service["revision"],
        "component": {"id": service["id"], "properties": {
            "Database Connection URL": f"jdbc:postgresql://postgres-db:5432/{POSTGRES_DB}",
            "Database User": POSTGRES_USER,
            "Password": POSTGRES_PASSWORD,
            "database-driver-locations": "/opt/nifi/nifi-current/drivers/postgresql.jar",
        }},
    })
    nifi("PUT", f"/controller-services/{service['id']}/run-status", {"revision": service["revision"], "state": "ENABLED"})
    deadline = time.monotonic() + 60
    while nifi("GET", f"/controller-services/{service['id']}")["component"]["state"] != "ENABLED":
        if time.monotonic() > deadline:
            sys.exit("[erro] o pool JDBC do Draco não foi habilitado em 60 s")
        time.sleep(1)

    processors = {p["component"]["name"]: p for p in nifi("GET", f"/process-groups/{group_id}/processors")["processors"]}
    nifi_update_processor(processors["NGSIToPostgreSQL"], {
        "ngsi-version": "ld",
        "data-model": "db-by-entity-type",
        "default-service": TENANT,
        "default-service-path": "/",
        "Batch Size": "1",
    }, ["retry"])
    nifi_update_processor(processors["LogAttribute"], {"Log Payload": "true"}, ["success"])

    connections = nifi("GET", f"/process-groups/{group_id}/connections")["connections"]
    to_log = next(c for c in connections if c["component"]["destination"]["name"] == "LogAttribute")
    nifi("PUT", f"/connections/{to_log['id']}", {
        "revision": to_log["revision"],
        "component": {"id": to_log["id"], "selectedRelationships": ["success", "failure"]},
    })

    nifi("PUT", f"/flow/process-groups/{group_id}", {"id": group_id, "state": "RUNNING"})
    log("criado", "fluxo NiFi ListenHTTP -> NGSIToPostgreSQL -> LogAttribute")


def main():
    wait_for("Orion-LD", f"{ORION}/version")
    wait_for("IoT Agent JSON", f"{IOTA}/iot/about")
    wait_for("QuantumLeap", f"{QUANTUMLEAP}/version")
    wait_for("CrateDB", f"{CRATE}/")
    wait_for("Draco (NiFi)", f"{NIFI}/nifi-api/flow/templates")

    provision_road_segments()
    provision_service_group()
    provision_devices()
    provision_subscription(subscription(
        "quantumleap-trafficflowobserved",
        "Histórico de TrafficFlowObserved no QuantumLeap",
        "http://fiware-quantumleap:8668/v2/notify",
    ))
    prime_quantumleap_table()
    provision_draco_flow()
    provision_subscription(subscription(
        "draco-trafficflowobserved",
        "Persistência de TrafficFlowObserved no Draco",
        "http://fiware-draco:5050/v2/notify",
    ))
    log("ok", "provisionamento concluído")


if __name__ == "__main__":
    try:
        main()
    except HttpError as error:
        sys.exit(f"[erro] {error}")
