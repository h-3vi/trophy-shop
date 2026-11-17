"""Точка входа для WSGI-сервера (хостинг)."""
from app import create_app

application = create_app()
app = application