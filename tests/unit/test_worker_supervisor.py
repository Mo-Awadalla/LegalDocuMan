from rq import Worker

from legaldocuman.app.worker import CapableWorker


class RecordingConnection:
    def __init__(self, events):
        self.events = events

    def setex(self, key, ttl, payload):
        self.events.append(("capabilities", key, ttl, payload))


def test_capabilities_are_published_only_after_rq_worker_registration(monkeypatch):
    events = []
    worker = CapableWorker.__new__(CapableWorker)
    worker.connection = RecordingConnection(events)
    worker.capability_key = "legaldocuman:worker:test-worker"
    worker.capability_ttl = 75
    worker.capability_payload = '{"ocr": true, "signature": true}'

    monkeypatch.setattr(Worker, "register_birth", lambda self: events.append(("birth",)))

    worker.register_birth()

    assert events == [
        ("birth",),
        (
            "capabilities",
            "legaldocuman:worker:test-worker",
            75,
            '{"ocr": true, "signature": true}',
        ),
    ]
