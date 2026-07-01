import os

from legaldocuman.config import Config


def _truthy(value):
    return str(value).lower() in {"1", "true", "yes"}


def validate_runtime_config(app):
    """Fail fast on unsafe production-like runtime configuration."""
    app_env = (app.config.get("APP_ENV") or "").lower()
    flask_env = (app.config.get("FLASK_ENV") or "").lower()
    if app_env != "production" and flask_env != "production":
        return

    errors = []
    unsafe_secret_values = {"", "dev-key-change-in-production", "change-me", "change-me-in-production", "secret"}
    if app.config.get("SECRET_KEY") in unsafe_secret_values:
        errors.append("SECRET_KEY must be set to a non-default value")
    if app.config.get("BOOTSTRAP_ADMIN_PASSWORD") == "change-me-in-production":
        errors.append("BOOTSTRAP_ADMIN_PASSWORD must be changed")
    db_url = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if db_url.startswith("sqlite:"):
        errors.append("SQLite DATABASE_URL is not allowed in production")
    if app.config.get("AUTO_CREATE_DB"):
        errors.append("AUTO_CREATE_DB must be disabled in production")
    if not (app.config.get("CORS_ORIGINS") or "").strip():
        errors.append("CORS_ORIGINS must be configured in production")
    api_key = (app.config.get("API_KEY") or "").strip()
    has_api_key = bool(api_key and api_key not in unsafe_secret_values)
    has_bootstrap = bool((app.config.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip() and (app.config.get("BOOTSTRAP_ADMIN_PASSWORD") or "").strip())
    if not has_api_key and not has_bootstrap:
        errors.append("API_KEY or bootstrap admin credentials are required in production")
    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


def init_app_config(app):
    cfg = Config.get()
    app.config["APP_ENV"] = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development"))
    app.config["FLASK_ENV"] = os.environ.get("FLASK_ENV", "")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    app.config["UPLOAD_FOLDER"] = os.environ.get(
        "UPLOAD_FOLDER",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads"),
    )
    app.config["MAX_UPLOAD_MB"] = int(os.environ.get("MAX_UPLOAD_MB", "20"))
    app.config["MAX_CONTENT_LENGTH"] = app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    app.config["ALLOWED_EXTENSIONS"] = set(cfg.SUPPORTED_EXTENSIONS)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:***@localhost:5432/legaldocuman",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["API_KEY"] = os.environ.get("API_KEY", "")
    app.config["AUTH_TOKEN_TTL_SECONDS"] = int(os.environ.get("AUTH_TOKEN_TTL_SECONDS", "86400"))
    app.config["DOWNLOAD_TOKEN_TTL_SECONDS"] = int(os.environ.get("DOWNLOAD_TOKEN_TTL_SECONDS", "300"))
    app.config["RATE_LIMIT_ENABLED"] = _truthy(os.environ.get("RATE_LIMIT_ENABLED", "1"))
    app.config["RATE_LIMIT_WINDOW_SECONDS"] = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    app.config["RATE_LIMIT_AUTH_PER_MINUTE"] = int(os.environ.get("RATE_LIMIT_AUTH_PER_MINUTE", "10"))
    app.config["RATE_LIMIT_UPLOAD_PER_MINUTE"] = int(os.environ.get("RATE_LIMIT_UPLOAD_PER_MINUTE", "30"))
    app.config["BOOTSTRAP_ADMIN_EMAIL"] = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "")
    app.config["BOOTSTRAP_ADMIN_PASSWORD"] = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
    app.config["BOOTSTRAP_ADMIN_NAME"] = os.environ.get("BOOTSTRAP_ADMIN_NAME", "Admin")
    app.config["BOOTSTRAP_TENANT_NAME"] = os.environ.get("BOOTSTRAP_TENANT_NAME", "Default Tenant")
    app.config["CORS_ORIGINS"] = os.environ.get("CORS_ORIGINS", "")
    app.config["AUTO_CREATE_DB"] = _truthy(os.environ.get("AUTO_CREATE_DB", "1"))
    app.config["ALLOW_OPEN_DEV_MODE"] = _truthy(os.environ.get("ALLOW_OPEN_DEV_MODE", "0"))
    app.config["JOB_BACKEND"] = os.environ.get("JOB_BACKEND", "thread").lower()
    app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "")
    app.config["MALWARE_SCANNER"] = os.environ.get("MALWARE_SCANNER", "builtin").lower()
    app.config["CLAMSCAN_PATH"] = os.environ.get("CLAMSCAN_PATH", "clamscan")
    app.config["STORAGE_BACKEND"] = os.environ.get("STORAGE_BACKEND", "local").lower()
    app.config["S3_BUCKET"] = os.environ.get("S3_BUCKET", "")
    app.config["S3_PREFIX"] = os.environ.get("S3_PREFIX", "uploads")
    app.config["S3_REGION"] = os.environ.get("S3_REGION", "")
    validate_runtime_config(app)
