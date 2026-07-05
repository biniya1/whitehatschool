import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # SECRET_KEY must be set via environment in any real deployment; a random
    # key is generated as a dev-only fallback so the app doesn't ship with a
    # hardcoded secret.
    SECRET_KEY = os.environ.get("SECRET_KEY") or os.urandom(32).hex()

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "market.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB upload cap

    # Session / cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Only force Secure cookies when explicitly running behind HTTPS/ngrok;
    # keep default False so local plain-http dev still works.
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

    # Business thresholds
    PRODUCT_REPORT_THRESHOLD = 3
    USER_REPORT_THRESHOLD = 5
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
    DEFAULT_BALANCE = 1_000_000
    CHAT_RATE_LIMIT_COUNT = 5
    CHAT_RATE_LIMIT_WINDOW_SECONDS = 10
    CHAT_MESSAGE_MAX_LENGTH = 500
    REPORT_REASON_MAX_LENGTH = 500

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

    DEBUG = _env_bool("FLASK_DEBUG", False)
