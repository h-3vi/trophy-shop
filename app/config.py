"""Конфигурация приложения. Секреты читаются из переменных окружения."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _database_uri() -> str:
    uri = os.getenv("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'shop.db').as_posix()}")
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = str(BASE_DIR / "app" / "static" / "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    PRODUCTS_PER_PAGE = 9
    ADMIN_PER_PAGE = 10

    PAYMENT_PROVIDER = os.getenv("PAYMENT_PROVIDER", "demo").lower()
    YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
    SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:5000")

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestConfig(Config):
    """Отдельная БД для автотестов."""
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{(BASE_DIR / 'test_shop.db').as_posix()}"
    WTF_CSRF_ENABLED = False
    TESTING = True