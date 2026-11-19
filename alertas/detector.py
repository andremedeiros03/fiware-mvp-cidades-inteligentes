import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

from semaforos import initialize, on_alert

CONTEXT = "https://smart-data-models.github.io/dataModel.Alert/context.jsonld"
ORION = os.getenv("ORION_URL", "http://orion-ld:1026")
DATABASE = os.getenv("ALERTAS_DB", "/dados/estado.sqlite")
STEP = timedelta(minutes=5)


def prop(value):
    return {"type": "Property", "value": value}


def alert(segment, start, end=None):
    entity = {
        "id": f"urn:ngsi-ld:Alert:{segment.rsplit(':', 1)[-1]}:{start}",
        "type": "Alert",
        "category": prop("traffic"),
        "subCategory": prop("trafficJam"),
        "severity": prop("medium"),
        "description": prop("Congestionamento detectado por ocupação da via."),
        "alertSource": {"type": "Relationship", "object": segment},
        "dateIssued": prop({"@type": "DateTime", "@value": start}),
        "@context": CONTEXT,
    }
    if end:
        entity["validTo"] = prop({"@type": "DateTime", "@value": end})
    return entity


def publish(entity):
    req = Request(ORION + "/ngsi-ld/v1/entityOperations/upsert",
                  data=json.dumps([entity]).encode(),
                  headers={"Content-Type": "application/ld+json", "NGSILD-Tenant": "transito"})
    with urlopen(req, timeout=10) as response:
        if response.status not in (201, 204):
            raise OSError(f"Falha no upsert: {response.status} {response.read()[:300]}")


def process(db, entity, send=publish):
    segment = entity["refRoadSegment"]["object"]
    raw_time = entity["dateObserved"]["value"]
    if isinstance(raw_time, dict):
        raw_time = raw_time["@value"]
    moment = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("dateObserved precisa incluir o fuso")
    stamp = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    occupancy = float(entity["occupancy"]["value"])
    if not 0 <= occupancy <= 1:
        raise ValueError("occupancy fora do intervalo")
    with db:
        previous = db.execute("SELECT last, streak, opened FROM segment WHERE id=?", (segment,)).fetchone()
        streak, opened = 0, None
        if previous:
            last, streak, opened = previous
            gap = moment - datetime.fromisoformat(last.replace("Z", "+00:00"))
            if gap <= timedelta(0):
                return
            if gap != STEP:
                streak = 0
        if occupancy > 0.25:
            streak = min(3, max(0, streak) + 1)
            if streak == 3 and not opened:
                opened = stamp
                send(alert(segment, opened))
        else:
            streak = max(-2, min(0, streak) - 1)
            if streak == -2 and opened:
                send(alert(segment, opened, stamp))
                opened = None
        db.execute("INSERT OR REPLACE INTO segment VALUES (?, ?, ?, ?)", (segment, stamp, streak, opened))


def connect(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS segment (id TEXT PRIMARY KEY, last TEXT, streak INTEGER, opened TEXT)")
    initialize(db)
    return db


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path not in ("/notify", "/semaforos"):
            return self.send_error(404)
        try:
            events = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["data"]
            for entity in events:
                if self.path == "/semaforos":
                    on_alert(self.server.db, entity, publish)
                    continue
                # O cadastro inicial do dispositivo pode chegar sem medição.
                if entity.get("occupancy", {}).get("value") is None or not entity.get("dateObserved", {}).get("value"):
                    continue
                process(self.server.db, entity)
        except (KeyError, ValueError, TypeError) as error:
            return self.send_error(400, str(error))
        except (OSError, sqlite3.Error) as error:
            return self.send_error(503, str(error))
        self.send_response(204)
        self.end_headers()


if __name__ == "__main__":
    with HTTPServer(("", 8080), Handler) as server:
        server.db = connect(DATABASE)
        server.serve_forever()
