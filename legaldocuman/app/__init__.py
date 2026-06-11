from flask import Flask
from flask_cors import CORS

from .config_loader import init_app_config
from .extensions import db, migrate
from .security import init_security


def create_app():
    app = Flask(__name__)
    init_app_config(app)
    db.init_app(app)
    migrate.init_app(app, db)
    init_security(app)

    cors_origins = app.config.get("CORS_ORIGINS") or ""
    origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
    CORS(app, resources={r"/api/*": {"origins": origins or []}})

    from .main.routes import main_bp
    from .api.routes import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    if app.config.get("AUTO_CREATE_DB"):
        with app.app_context():
            from . import models  # noqa: F401
            from .auth import bootstrap_default_identity
            db.create_all()
            bootstrap_default_identity()

    return app
