import os

from legaldocuman.config import Config


def init_app_config(app):
    cfg = Config.get()
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    app.config["UPLOAD_FOLDER"] = os.environ.get(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads"),
    )
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("MAX_UPLOAD_MB", "20")
    ) * 1024 * 1024
    app.config["ALLOWED_EXTENSIONS"] = set(cfg.SUPPORTED_EXTENSIONS)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/legaldocuman",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
