"""Модели предметной области: каталог, пользователи, заказы."""
from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import event
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ORDER_STATUSES = {
    "new": "Ожидает оплаты",
    "paid": "Оплачен",
    "shipped": "Отправлен",
    "completed": "Выполнен",
    "cancelled": "Отменён",
}


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    icon = db.Column(db.String(8), default="🎣")
    description = db.Column(db.String(255), default="")

    products = db.relationship("Product", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(160), unique=True, nullable=False, index=True)
    brand = db.Column(db.String(80), default="")
    description = db.Column(db.Text, default="")
    price = db.Column(db.Numeric(10, 2), nullable=False)
    old_price = db.Column(db.Numeric(10, 2))
    stock = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    search_index = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.now)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    category = db.relationship("Category", back_populates="products")

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def discount(self):
        if self.old_price and self.old_price > self.price:
            return int(round((1 - float(self.price) / float(self.old_price)) * 100))
        return 0

    def __repr__(self):
        return f"<Product {self.name} {self.price}>"


@event.listens_for(Product, "before_insert")
@event.listens_for(Product, "before_update")
def _build_search_index(mapper, connection, target):
    """Поисковый индекс в нижнем регистре: SQLite не умеет LOWER() для кириллицы."""
    parts = [target.name or "", target.brand or "", target.description or ""]
    target.search_index = " ".join(parts).lower()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(24), unique=True, index=True)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(32), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    comment = db.Column(db.String(500), default="")
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="new")
    payment_id = db.Column(db.String(64))
    payment_provider = db.Column(db.String(20), default="demo")
    created_at = db.Column(db.DateTime, default=datetime.now)

    items = db.relationship("OrderItem", back_populates="order",
                            cascade="all, delete-orphan", lazy="joined")

    @property
    def status_label(self):
        return ORDER_STATUSES.get(self.status, self.status)

    @property
    def quantity_total(self):
        return sum(item.quantity for item in self.items)


class OrderItem(db.Model):
    """Позиция заказа: название и цена фиксируются на момент покупки."""
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    title = db.Column(db.String(140), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    @property
    def subtotal(self):
        return self.price * self.quantity