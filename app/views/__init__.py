"""Blueprints магазина, аутентификации и админки."""
from .auth import auth_bp
from .shop import shop_bp

__all__ = ["shop_bp", "auth_bp"]