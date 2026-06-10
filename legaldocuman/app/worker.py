"""RQ worker entrypoint for document processing.

Run locally with:
  python -m legaldocuman.app.worker
"""
import os

from redis import Redis
from rq import Worker, Queue

from legaldocuman.app import create_app


def main():
    app = create_app()
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    queue_name = os.environ.get("RQ_QUEUE", "documents")
    with app.app_context():
        worker = Worker([Queue(queue_name, connection=Redis.from_url(redis_url))])
        worker.work()


if __name__ == "__main__":
    main()
