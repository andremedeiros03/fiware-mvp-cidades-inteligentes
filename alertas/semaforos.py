"""Seleção do plano do próximo ciclo dos semáforos simulados."""

DEVICE_CONTEXT = "https://smart-data-models.github.io/dataModel.Device/context.jsonld"
TRANSPORT_CONTEXT = "https://smart-data-models.github.io/dataModel.Transportation/context.jsonld"
VOCAB = "https://github.com/andremedeiros03/fiware-mvp-cidades-inteligentes#"
CONTEXT = [TRANSPORT_CONTEXT, DEVICE_CONTEXT, {
    "signalPlan": VOCAB + "signalPlan", "greenDuration": VOCAB + "greenDuration",
}]
SEGMENTS = {f"urn:ngsi-ld:RoadSegment:salgado-filho-{letter}":
            f"urn:ngsi-ld:Device:semaforo-salgado-filho-{letter}" for letter in "ab"}


def device(segment, peak=False):
    return {
        "@context": CONTEXT,
        "id": SEGMENTS[segment], "type": "Device",
        "controlledProperty": {"type": "Property", "value": ["greenDuration"]},
        "refRoadSegment": {"type": "Relationship", "object": segment},
        "signalPlan": {"type": "Property", "value": "pico" if peak else "normal"},
        "greenDuration": {"type": "Property", "value": 45 if peak else 30, "unitCode": "SEC"},
    }


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS signal_alert (
        id TEXT PRIMARY KEY, segment TEXT NOT NULL, closed INTEGER NOT NULL)""")


def on_alert(db, event, publish):
    segment = event.get("alertSource", {}).get("object")
    if segment not in SEGMENTS or event.get("subCategory", {}).get("value") != "trafficJam":
        return
    ended = bool(event.get("validTo", {}).get("value"))
    with db:
        params = (segment,)
        query = "SELECT EXISTS(SELECT 1 FROM signal_alert WHERE segment=? AND closed=0)"
        before = db.execute(query, params).fetchone()[0]
        # Um encerramento é definitivo mesmo se a abertura chegar atrasada.
        db.execute("""INSERT INTO signal_alert VALUES (?, ?, ?)
                      ON CONFLICT(id) DO UPDATE SET closed=max(closed, excluded.closed)""",
                   (event["id"], segment, ended))
        after = db.execute(query, params).fetchone()[0]
        if before != after:
            publish(device(segment, bool(after)))
