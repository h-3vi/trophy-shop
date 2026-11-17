"""Вспомогательные функции: слаги, корзина, форматирование, доступ."""
import re
import uuid
from decimal import Decimal
from functools import wraps
from pathlib import Path

from flask import abort, current_app, session
from flask_login import current_user
from werkzeug.utils import secure_filename

from .extensions import db
from .models import Product

CART_SESSION_KEY = "cart"

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(value: str) -> str:
    """ЧПУ-ссылка: 'Спиннинг 2.4 м' -> 'spinning-2-4-m'."""
    value = (value or "").strip().lower()
    value = "".join(_TRANSLIT.get(ch, ch) for ch in value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:150] or "item"


def unique_slug(model, value: str, exclude_id=None) -> str:
    """Подбирает свободный slug, при совпадении добавляет номер."""
    base = slugify(value)
    slug, index = base, 2
    while True:
        query = model.query.filter_by(slug=slug)
        if exclude_id:
            query = query.filter(model.id != exclude_id)
        if not db.session.query(query.exists()).scalar():
            return slug
        slug, index = f"{base}-{index}", index + 1


def money(value) -> str:
    """Фильтр Jinja2: 4990.00 -> '4 990 ₽'."""
    if value is None:
        return "0 ₽"
    text = f"{Decimal(value):,.2f}".replace(",", "\u00a0").replace(".", ",")
    if text.endswith(",00"):
        text = text[:-3]
    return f"{text}\u00a0₽"


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def save_uploaded_image(file):
    """Сохраняет картинку товара, возвращает (имя_файла, ошибка)."""
    if not file or not file.filename:
        return None, None
    extension = Path(file.filename).suffix.lower().lstrip(".")
    if extension not in current_app.config["ALLOWED_EXTENSIONS"]:
        return None, "Допустимые форматы изображения: PNG, JPG, WEBP"
    safe_name = secure_filename(file.filename) or f"image.{extension}"
    filename = f"{uuid.uuid4().hex[:10]}_{safe_name}"
    file.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)
    return filename, None


# --- Корзина хранится в сессии: покупателю не нужна регистрация ---

def get_cart() -> dict:
    cart = session.get(CART_SESSION_KEY)
    return cart if isinstance(cart, dict) else {}


def save_cart(cart: dict):
    session[CART_SESSION_KEY] = {str(k): int(v) for k, v in cart.items() if int(v) > 0}
    session.modified = True


def add_to_cart(product_id: int, quantity: int = 1) -> int:
    product = db.session.get(Product, product_id)
    if product is None or not product.is_active:
        return 0
    cart = get_cart()
    key = str(product_id)
    wanted = cart.get(key, 0) + max(1, int(quantity))
    cart[key] = max(0, min(wanted, product.stock))
    save_cart(cart)
    return cart[key]


def set_quantity(product_id: int, quantity: int):
    cart = get_cart()
    key = str(product_id)
    product = db.session.get(Product, product_id)
    if product is None:
        cart.pop(key, None)
    else:
        cart[key] = max(0, min(int(quantity), product.stock))
    save_cart(cart)


def remove_from_cart(product_id: int):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)


def clear_cart():
    session[CART_SESSION_KEY] = {}
    session.modified = True


def cart_items():
    """Возвращает (позиции, сумма, количество товаров)."""
    cart = get_cart()
    if not cart:
        return [], Decimal("0.00"), 0
    ids = [int(key) for key in cart]
    products = Product.query.filter(Product.id.in_(ids),
                                    Product.is_active.is_(True)).all()
    items, total, count = [], Decimal("0.00"), 0
    for product in products:
        quantity = min(cart.get(str(product.id), 0), product.stock)
        if quantity <= 0:
            continue
        subtotal = Decimal(product.price) * quantity
        items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
        total += subtotal
        count += quantity
    items.sort(key=lambda item: item["product"].name)
    return items, total, count


def cart_count() -> int:
    return sum(int(value) for value in get_cart().values())


def mark_order_paid(order, payment_id=None):
    """Идемпотентно: повторный вызов не спишет остатки дважды."""
    if order.status == "paid":
        return
    order.status = "paid"
    if payment_id:
        order.payment_id = payment_id
    for item in order.items:
        if item.product:
            item.product.stock = max(0, item.product.stock - item.quantity)
    db.session.commit()