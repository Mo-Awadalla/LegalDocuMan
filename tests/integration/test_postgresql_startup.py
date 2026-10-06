"""Exercise the app/worker startup path with the packaged PostgreSQL driver."""

import pytest

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db


@pytest.mark.parametrize("database_url", [
    None,
    "postgresql://postgres:postgres@db:5432/legaldocuman",
])
def test_app_initializes_postgresql_without_connecting(monkeypatch, database_url):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("FLASK_ENV", "")
    monkeypatch.setenv("AUTO_CREATE_DB", "0")
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    # Workers and migrations use this same factory. AUTO_CREATE_DB=0 lets us
    # exercise real driver loading without requiring a PostgreSQL service.
    app = create_app()
    with app.app_context():
        try:
            assert db.engine.dialect.driver == "psycopg2"
            assert db.engine.dialect.dbapi.__name__ == "psycopg2"
        finally:
            db.engine.dispose()
