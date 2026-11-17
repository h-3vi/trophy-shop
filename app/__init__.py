"""Фабрика приложения. Дополняется по мере разработки модулей."""
from flask import Flask

from .config import BASE_DIR, Config
from .extensions import csrf, db, login_manager
from .seed import register_commands


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.ensure_ascii = False

    (BASE_DIR / "logs").mkdir(exist_ok=True)
    uploads_dir = app.config["UPLOAD_FOLDER"]
    (BASE_DIR / uploads_dir).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    register_commands(app)

    with app.app_context():
        db.create_all()

    @app.shell_context_processor
    def shell_context():
        """Объекты, доступные в flask shell без импорта."""
        from .models import Category, Order, OrderItem, Product, User
        return {"db": db, "Category": Category, "Product": Product,
                "User": User, "Order": Order, "OrderItem": OrderItem}

    @app.route("/health")
    def health():
        """Служебный эндпоинт проверки работоспособности."""
        return {"status": "ok", "project": "Трофей"}

    return app