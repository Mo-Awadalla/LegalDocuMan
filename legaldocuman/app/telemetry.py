"""Low-risk structured stdout logging."""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        message = record.getMessage()
        try:
            payload = json.loads(message)
            if not isinstance(payload, dict):
                payload = {"message": message}
        except (TypeError, ValueError):
            payload = {"message": message}
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        payload.setdefault("level", record.levelname.lower())
        payload.setdefault("logger", record.name)
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, sort_keys=True, default=str)


def configure_json_logging():
    root = logging.getLogger()
    formatter = JsonFormatter()
    for handler in root.handlers:
        handler.setFormatter(formatter)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(logging.INFO)
