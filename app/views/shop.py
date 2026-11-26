
"""Витрина, корзина, оформление и оплата заказов."""

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from ..extensions import csrf, db
from ..models import Category, Order, OrderItem, Product
from ..payments import (
    PAYMENT_METHODS,
    PaymentError,
    create_payment,
    fetch_payment_status,
)
from ..utils import (
    add_to_cart,
    cart_items,
    clear_cart,
    mark_order_paid,
    remove_from_cart,
    set_quantity,
)

shop_bp = Blueprint("shop", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s()\-]{10,20}$")


def _safe_back(default_endpoint="shop.catalog"):
    """Безопасный возврат на предыдущую страницу."""
    referrer = request.referrer

    if referrer and referrer.startswith(request.host_url):
        return referrer

    return url_for(default_endpoint)


@shop_bp.route("/")
def index():
    """Главная страница."""

    novelties = (
        Product.query
        .filter_by(is_active=True)
        .order_by(Product.created_at.desc())
        .limit(8)
        .all()
    )

    deals = (
        Product.query
        .filter(
            Product.is_active.is_(True),
            Product.old_price.isnot(None),
        )
        .limit(4)
        .all()
    )

    return render_template(
        "index.html",
        novelties=novelties,
        deals=deals,
        title="Трофей — товары для охоты и рыбалки",
    )


@shop_bp.route("/catalog")
def catalog():

    page = request.args.get("page", 1, type=int)
    query_text = request.args.get("q", "").strip()
    category_slug = request.args.get("category", "")
    sort = request.args.get("sort", "new")
    price_min = request.args.get("price_min", "")
    price_max = request.args.get("price_max", "")
    in_stock = request.args.get("in_stock") == "1"

    query = Product.query.filter(
        Product.is_active.is_(True)
    )

    selected_category = None

    if category_slug:
        selected_category = (
            Category.query
            .filter_by(slug=category_slug)
            .first_or_404()
        )

        query = query.filter(
            Product.category_id == selected_category.id
        )

    if query_text:
        query = query.filter(
            Product.search_index.contains(
                query_text.lower(),
                autoescape=True,
            )
        )

    for raw, mode in (
        (price_min, "min"),
        (price_max, "max"),
    ):
        try:
            value = Decimal(raw.replace(",", "."))
        except (InvalidOperation, AttributeError):
            continue

        if mode == "min":
            query = query.filter(Product.price >= value)
        else:
            query = query.filter(Product.price <= value)

    if in_stock:
        query = query.filter(Product.stock > 0)

    sorting = {
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "name": Product.name.asc(),
        "new": Product.created_at.desc(),
    }

    query = query.order_by(
        sorting.get(
            sort,
            Product.created_at.desc(),
        )
    )

    pagination = query.paginate(
        page=page,
        per_page=current_app.config["PRODUCTS_PER_PAGE"],
        error_out=False,
    )

    return render_template(
        "catalog.html",
        pagination=pagination,
        products=pagination.items,
        q=query_text,
        sort=sort,
        selected_category=selected_category,
        price_min=price_min,
        price_max=price_max,
        in_stock=in_stock,
        title="Каталог товаров",
    )


@shop_bp.route("/product/<slug>")
def product(slug):
    """Страница товара."""

    item = (
        Product.query
        .filter_by(slug=slug, is_active=True)
        .first_or_404()
    )

    related = (
        Product.query
        .filter(
            Product.category_id == item.category_id,
            Product.id != item.id,
            Product.is_active.is_(True),
        )
        .limit(4)
        .all()
    )

    return render_template(
        "product.html",
        product=item,
        related=related,
        title=item.name,
    )


@shop_bp.route("/cart")
def cart():
    """Корзина."""

    items, total, count = cart_items()

    return render_template(
        "cart.html",
        items=items,
        total=total,
        count=count,
        title="Корзина",
    )


@shop_bp.route(
    "/cart/add/<int:product_id>",
    methods=["POST"],
)
def cart_add(product_id):
    """Добавление товара в корзину."""

    quantity = request.form.get(
        "quantity",
        1,
        type=int,
    )

    added = add_to_cart(product_id, quantity)

    if added:
        flash("Товар добавлен в корзину", "success")
    else:
        flash("Товара нет в наличии", "warning")

    return redirect(_safe_back())


@shop_bp.route(
    "/cart/update/<int:product_id>",
    methods=["POST"],
)
def cart_update(product_id):
    """Изменение количества товара."""

    quantity = request.form.get(
        "quantity",
        1,
        type=int,
    )

    set_quantity(product_id, quantity)

    flash("Корзина обновлена", "success")

    return redirect(url_for("shop.cart"))


@shop_bp.route(
    "/cart/remove/<int:product_id>",
    methods=["POST"],
)
def cart_remove(product_id):
    """Удаление товара."""

    remove_from_cart(product_id)

    flash("Товар удалён из корзины", "success")

    return redirect(url_for("shop.cart"))


def _validate_checkout(form):
    """Серверная проверка оформления заказа."""

    errors = {}

    name = form.get("name", "").strip()
    email = form.get("email", "").strip()
    phone = form.get("phone", "").strip()
    address = form.get("address", "").strip()
    comment = form.get("comment", "").strip()

    if len(name) < 2 or len(name) > 120:
        errors["name"] = "Введите имя и фамилию."

    if (
        len(email) > 120
        or not EMAIL_RE.fullmatch(email)
    ):
        errors["email"] = (
            "Введите корректную электронную почту."
        )

    digits = re.sub(r"\D", "", phone)

    if (
        not PHONE_RE.fullmatch(phone)
        or len(digits) < 10
        or len(digits) > 15
    ):
        errors["phone"] = (
            "Введите корректный номер телефона."
        )

    if len(address) < 10 or len(address) > 255:
        errors["address"] = (
            "Введите полный адрес доставки."
        )

    if len(comment) > 500:
        errors["comment"] = (
            "Комментарий слишком длинный."
        )

    if form.get("agree") != "1":
        errors["agree"] = (
            "Необходимо согласие на обработку данных."
        )

    payment_method = form.get(
        "payment_method",
        "bank_card",
    )

    if payment_method not in PAYMENT_METHODS:
        errors["payment_method"] = (
            "Выберите способ оплаты."
        )

    return errors


@shop_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    """Оформление заказа и создание платежа."""

    items, total, count = cart_items()

    if not items:
        flash(
            "Корзина пуста. Добавьте товары.",
            "warning",
        )
        return redirect(url_for("shop.catalog"))

    errors = {}

    if request.method == "POST":

        errors = _validate_checkout(request.form)

        if not errors:

            payment_method = request.form.get(
                "payment_method",
                "bank_card",
            )

            order = Order(
                customer_name=request.form["name"].strip(),
                email=request.form["email"].strip(),
                phone=request.form["phone"].strip(),
                address=request.form["address"].strip(),
                comment=request.form.get(
                    "comment",
                    "",
                ).strip(),
                total=total,
                status="new",
            )

            db.session.add(order)
            db.session.flush()

            order.number = (
                f"HF{datetime.now():%y%m%d}-{order.id:04d}"
            )

            for item in items:
                db.session.add(
                    OrderItem(
                        order_id=order.id,
                        product_id=item["product"].id,
                        title=item["product"].name,
                        price=item["product"].price,
                        quantity=item["quantity"],
                    )
                )

            db.session.commit()

            return_url = url_for(
                "shop.payment_return",
                number=order.number,
                _external=True,
            )

            try:
                payment = create_payment(
                    order,
                    return_url,
                    payment_method=payment_method,
                )

            except PaymentError:
                current_app.logger.exception(
                    "Ошибка создания платежа"
                )

                # Заказ уже сохранён.
                # Корзину оставляем до успешного
                # создания платёжной сессии.
                flash(
                    "Заказ создан, но платёжный сервис "
                    "временно недоступен.",
                    "warning",
                )

                return redirect(
                    url_for(
                        "shop.order_view",
                        number=order.number,
                    )
                )

            order.payment_id = payment.payment_id
            order.payment_provider = payment.provider

            db.session.commit()
            clear_cart()

            return redirect(payment.confirmation_url)

    saved_name = ""
    saved_phone = ""
    saved_email = ""

    if current_user.is_authenticated:
        saved_name = current_user.full_name or ""
        saved_phone = current_user.phone or ""
        saved_email = current_user.email or ""

    return render_template(
        "checkout.html",
        items=items,
        total=total,
        count=count,
        errors=errors,
        form=request.form,
        saved_name=saved_name,
        saved_phone=saved_phone,
        saved_email=saved_email,
        payment_methods=PAYMENT_METHODS,
        title="Оформление заказа",
    )


@shop_bp.route(
    "/payment/demo/<number>",
    methods=["GET", "POST"],
)
def demo_payment(number):
    """Демонстрационная оплата без реальных денег."""

    order = Order.query.filter_by(
        number=number
    ).first_or_404()

    if order.status != "new":
        return redirect(
            url_for(
                "shop.order_view",
                number=order.number,
            )
        )

    method = request.args.get(
        "method",
        "bank_card",
    )

    if method not in PAYMENT_METHODS:
        method = "bank_card"

    if request.method == "POST":

        if request.form.get("result") == "success":

            mark_order_paid(order)

            flash(
                "Демонстрационная оплата прошла успешно.",
                "success",
            )

            return redirect(
                url_for(
                    "shop.order_view",
                    number=order.number,
                )
            )

        flash(
            "Демонстрационный платёж отклонён.",
            "danger",
        )

        return redirect(
            url_for(
                "shop.demo_payment",
                number=order.number,
                method=method,
            )
        )

    return render_template(
        "payment_demo.html",
        order=order,
        payment_method=method,
        payment_method_label=PAYMENT_METHODS[method],
        title="Демонстрационная оплата",
    )


@shop_bp.route("/payment/return/<number>")
def payment_return(number):
    """Проверка оплаты после возвращения с ЮKassa."""

    order = Order.query.filter_by(
        number=number
    ).first_or_404()

    if (
        order.payment_provider == "yookassa"
        and order.payment_id
    ):
        try:
            status = fetch_payment_status(
                order.payment_id
            )

            if status == "succeeded":
                mark_order_paid(order)

        except PaymentError:
            flash(
                "Не удалось проверить платёж. "
                "Попробуйте позже.",
                "warning",
            )

    return redirect(
        url_for(
            "shop.order_view",
            number=order.number,
        )
    )


@shop_bp.route(
    "/payment/webhook",
    methods=["POST"],
)
@csrf.exempt
def payment_webhook():
    """Обработка уведомления от ЮKassa."""

    payload = request.get_json(silent=True) or {}

    payment_object = payload.get("object", {})
    payment_id = payment_object.get("id")

    if not payment_id:
        return "", 400

    order = Order.query.filter_by(
        payment_id=payment_id
    ).first()

    if order is None:
        return "", 200

    try:
        status = fetch_payment_status(payment_id)

    except PaymentError:
        return "", 500

    if status == "succeeded":
        mark_order_paid(order)

    elif status == "canceled" and order.status == "new":
        order.status = "cancelled"
        db.session.commit()

    return "", 200


@shop_bp.route("/order/<number>")
def order_view(number):
    """Страница результата заказа."""

    order = Order.query.filter_by(
        number=number
    ).first_or_404()

    return render_template(
        "order_success.html",
        order=order,
        title=f"Заказ {order.number}",
    )


@shop_bp.route("/info/<slug>")
def info(slug):
    """Информационные страницы."""

    pages = {
        "delivery": "Доставка и оплата",
        "about": "О магазине",
        "contacts": "Контакты",
    }

    if slug not in pages:
        abort(404)

    return render_template(
        f"pages/{slug}.html",
        title=pages[slug],
    )
