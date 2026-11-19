import unittest
from unittest.mock import Mock

from detector import alert, connect
from semaforos import SEGMENTS, on_alert


class SignalTest(unittest.TestCase):
    def test_plans(self):
        db = connect(":memory:")
        self.addCleanup(db.close)
        a, b = SEGMENTS
        opened = alert(b, "2026-11-19T10:00:00Z")
        second = alert(b, "2026-11-19T10:05:00Z")
        closed = dict(opened, validTo={"value": "2026-11-19T10:15:00Z"})
        send = Mock(side_effect=OSError())
        with self.assertRaises(OSError):
            on_alert(db, opened, send)
        output = []
        for event in [opened, opened, second, closed, opened,
                      dict(second, validTo=closed["validTo"]), alert(a, "2026-11-19T11:00:00Z")]:
            on_alert(db, event, output.append)
        self.assertEqual([(v["id"], v["signalPlan"]["value"], v["greenDuration"]["value"]) for v in output],
                         [(SEGMENTS[b], "pico", 45), (SEGMENTS[b], "normal", 30), (SEGMENTS[a], "pico", 45)])
