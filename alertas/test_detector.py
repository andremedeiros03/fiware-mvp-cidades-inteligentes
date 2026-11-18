import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from detector import connect, process


class DetectorTest(unittest.TestCase):
    def test_episode(self):
        sent = []
        start = datetime(2026, 10, 6, tzinfo=timezone.utc)
        def reading(segment, step, value):
            return {"refRoadSegment": {"object": "urn:ngsi-ld:RoadSegment:" + segment},
                    "dateObserved": {"value": (start + step * timedelta(minutes=5)).isoformat()},
                    "occupancy": {"value": value}}

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            db = connect(path)
            for step, value in enumerate([.28, .30, .32, .35, .23, .20]):
                event = reading("b", step, value)
                if step == 2:
                    def unavailable(entity):
                        raise OSError("Orion indisponível")
                    with self.assertRaises(OSError):
                        process(db, event, unavailable)
                process(db, event, sent.append)
                process(db, event, sent.append)
                process(db, reading("a", step, .15), sent.append)
                self.assertEqual(len(sent), [0, 0, 1, 1, 1, 2][step])
                if step == 3:
                    db.close()
                    db = connect(path)
            self.assertEqual(sent[0]["id"], sent[1]["id"])
            self.assertEqual(sent[0]["alertSource"]["object"], "urn:ngsi-ld:RoadSegment:b")
            self.assertEqual(sent[1]["validTo"]["value"]["@value"], "2026-10-06T00:25:00Z")
            for step in [6, 8, 9]:
                process(db, reading("b", step, .30), sent.append)
            self.assertEqual(len(sent), 2)
            process(db, reading("b", 10, .30), sent.append)
            self.assertNotEqual(sent[0]["id"], sent[2]["id"])
            db.close()
