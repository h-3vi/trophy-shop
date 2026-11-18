
"""Фабрика Flask-приложения интернет-магазина Трофей."""

from datetime import datetime
from pathlib import Path

from flask import Flask, render_template

from .config import BASE_DIR, Config
from .extensions import csrf, db, login_manager
from .models import ORDER_STATUSES, Category
from .seed import register_commands
from .user_setup import register_user_commands
from .utils import cart_count, money
from .views import admin_bp, auth_bp, shop_bp


def create_app(config_class=Config):

    app = Flask(__name__)

    app.config.from_object(config_class)

    app.json.ensure_ascii = False

    # Создание необходимых папок
    (BASE_DIR / "logs").mkdir(
        parents=True,
        exist_ok=True
    )

    uploads_dir = Path(
        app.config["UPLOAD_FOLDER"]
    )

    if not uploads_dir.is_absolute():
        uploads_dir = BASE_DIR / uploads_dir

    uploads_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Подключение расширений
    db.init_app(app)

    login_manager.init_app(app)

    csrf.init_app(app)

    # Регистрация маршрутов
    app.register_blueprint(shop_bp)

    app.register_blueprint(auth_bp)

    app.register_blueprint(admin_bp)

    # Команды Flask
    register_commands(app)

    register_user_commands(app)

    # Фильтры шаблонов
    app.jinja_env.filters["money"] = money

    app.jinja_env.filters["dt"] = (
        lambda value:
        value.strftime("%d.%m.%Y %H:%M")
        if value else ""
    )

    # Общие данные для шаблонов
    @app.context_processor
    def inject_globals():

        return {
            "cart_count": cart_count(),

            "nav_categories": (
                Category.query
                .order_by(Category.name)
                .all()
            ),

            "order_statuses": ORDER_STATUSES,

            "site_name": "Трофей",

            "current_year": datetime.now().year,
        }

    # Ошибка 403
    @app.errorhandler(403)
    def forbidden(error):

        return render_template(
            "errors/403.html",
            title="Доступ запрещён"
        ), 403

    # Ошибка 404
    @app.errorhandler(404)
    def not_found(error):

        return render_template(
            "errors/404.html",
            title="Страница не найдена"
        ), 404

    # Ошибка 500
    @app.errorhandler(500)
    def server_error(error):

        db.session.rollback()

        app.logger.exception(
            "Внутренняя ошибка сервера"
        )

        return render_template(
            "errors/500.html",
            title="Ошибка сервера"
        ), 500

    # Инициализация таблиц
    with app.app_context():

        db.create_all()

    # Объекты для flask shell
    @app.shell_context_processor
    def shell_context():

        from .models import (
            Order,
            OrderItem,
            Product,
            User,
        )

        return {
            "db": db,
            "Category": Category,
            "Product": Product,
            "User": User,
            "Order": Order,
            "OrderItem": OrderItem,
        }

    # Проверка работоспособности
    @app.route("/health")
    def health():

        return {
            "status": "ok",
            "project": "Трофей",
        }

    return app
