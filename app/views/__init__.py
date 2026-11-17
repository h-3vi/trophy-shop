"""Blueprints магазина, аутентификации и админки."""
from .admin import admin_bp
from .auth import auth_bp
from .shop import shop_bp

__all__ = ["shop_bp", "auth_bp", "admin_bp"]