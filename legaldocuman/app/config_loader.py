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
        "postgresql://postgres:***@localhost:5432/legaldocuman",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_KEY"] = os.environ.get("API_KEY", "")
    app.config["AUTH_TOKEN_TTL_SECONDS"] = int(os.environ.get("AUTH_TOKEN_TTL_SECONDS", "86400"))
    app.config["DOWNLOAD_TOKEN_TTL_SECONDS"] = int(os.environ.get("DOWNLOAD_TOKEN_TTL_SECONDS", "300"))
    app.config["RATE_LIMIT_ENABLED"] = os.environ.get("RATE_LIMIT_ENABLED", "1").lower() in {"1", "true", "yes"}
    app.config["RATE_LIMIT_WINDOW_SECONDS"] = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    app.config["RATE_LIMIT_AUTH_PER_MINUTE"] = int(os.environ.get("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
    app.config["RATE_LIMIT_UPLOAD_PER_MINUTE"] = int(os.environ.get("RATE_LIMIT_UPLOAD_PER_MINUTE", "30"))
    app.config["BOOTSTRAP_ADMIN_EMAIL"] = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    app.config["BOOTSTRAP_ADMIN_PASSWORD"] = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin")
    app.config["BOOTSTRAP_ADMIN_NAME"] = os.environ.get("BOOTSTRAP_ADMIN_NAME", "Admin")
    app.config["BOOTSTRAP_TENANT_NAME"] = os.environ.get("BOOTSTRAP_TENANT_NAME", "Default Tenant")
    app.config["CORS_ORIGINS"] = os.environ.get("CORS_ORIGINS", "")
    app.config["AUTO_CREATE_DB"] = os.environ.get("AUTO_CREATE_DB", "1").lower() in {"1", "true", "yes"}
    app.config["ALLOW_OPEN_DEV_MODE"] = os.environ.get("ALLOW_OPEN_DEV_MODE", "0").lower() in {"1", "true", "yes"}
    app.config["JOB_BACKEND"] = os.environ.get("JOB_BACKEND", "thread").lower()
    app.config["MALWARE_SCANNER"] = os.environ.get("MALWARE_SCANNER", "builtin").lower()
    app.config["CLAMSCAN_PATH"] = os.environ.get("CLAMSCAN_PATH", "clamscan")
    app.config["STORAGE_BACKEND"] = os.environ.get("STORAGE_BACKEND", "local").lower()
    app.config["S3_BUCKET"] = os.environ.get("S3_BUCKET", "")
    app.config["S3_PREFIX"] = os.environ.get("S3_PREFIX", "uploads")
    app.config["S3_REGION"] = os.environ.get("S3_REGION", "")
