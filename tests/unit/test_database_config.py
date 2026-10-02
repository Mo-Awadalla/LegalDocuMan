"""Database URLs must select the PostgreSQL driver installed in the image."""

import pytest
from flask import Flask

from legaldocuman.app.config_loader import init_app_config
from legaldocuman.app.extensions import db


def _configured_app(monkeypatch, database_url):
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("FLASK_ENV", "")
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)
    app = Flask(__name__)
    init_app_config(app)
    return app


@pytest.mark.parametrize("database_url", [
    None,
    "postgresql://postgres:postgres@db:5432/legaldocuman",
    "postgresql+psycopg2://postgres:postgres@db:5432/legaldocuman",
])
def test_postgresql_engine_loads_installed_driver(monkeypatch, database_url):
    app = _configured_app(monkeypatch, database_url)

    # Initialize the real DBAPI without connecting to a running PostgreSQL server.
    # SQLAlchemy 2.1 defaults bare postgresql:// URLs to the uninstalled psycopg 3.
    db.init_app(app)
    with app.app_context():
        try:
            assert db.engine.dialect.driver == "psycopg2"
            assert db.engine.dialect.dbapi.__name__ == "psycopg2"
        finally:
            db.engine.dispose()


def test_postgresql_url_keeps_credentials_and_query(monkeypatch):
    suffix = "user:p%40ss%2Fword@[::1]:5432/documents?sslmode=require&application_name=worker"
    app = _configured_app(monkeypatch, "postgresql://" + suffix)
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "postgresql+psycopg2://" + suffix


@pytest.mark.parametrize("database_url", [
    "postgresql+psycopg2://user:password@db/documents?sslmode=require",
    "postgresql+psycopg://user:password@db/documents",
    "postgresql+pg8000://user:password@db/documents",
    "sqlite:///legaldocuman.db",
    "sqlite:///:memory:",
])
def test_explicit_drivers_and_other_databases_are_preserved(monkeypatch, database_url):
    app = _configured_app(monkeypatch, database_url)
    assert app.config["SQLALCHEMY_DATABASE_URI"] == database_url
