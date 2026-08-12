import re
import uuid

from flask import Flask, g, request
from flask_cors import CORS

from .config_loader import init_app_config
from .extensions import db, migrate
from .security import init_security
from .telemetry import configure_json_logging


def create_app():
    configure_json_logging()
    app = Flask(__name__)
    init_app_config(app)
    db.init_app(app)
    migrate.init_app(app, db)
    init_security(app)

    cors_origins = app.config.get("CORS_ORIGINS") or ""
    origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins or []}})

    from .api.routes import api_bp
    from .main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    from .jobs import jobs_cli
    app.cli.add_command(jobs_cli)

    @app.before_request
    def assign_correlation_id():
        supplied = (request.headers.get("X-Correlation-ID") or "").strip()
        g.correlation_id = supplied if re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", supplied) else str(uuid.uuid4())

    @app.after_request
    def return_correlation_id(response):
        response.headers["X-Correlation-ID"] = getattr(g, "correlation_id", str(uuid.uuid4()))
        return response

    if app.config.get("AUTO_CREATE_DB"):
        with app.app_context():
            from . import models  # noqa: F401
            from .auth import bootstrap_default_identity
            db.create_all()
            bootstrap_default_identity()

    return app
