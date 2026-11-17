"""Витрина магазина: каталог, товар, корзина, оформление и оплата заказа."""
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (Blueprint, current_app, flash, redirect,
                   render_template, request, url_for)

from ..extensions import csrf, db
from ..models import Category, Order, OrderItem, Product
from ..payments import PaymentError, create_payment
from ..utils import (add_to_cart, cart_items, clear_cart, mark_order_paid,
                     remove_from_cart, set_quantity)

shop_bp = Blueprint("shop", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[\d\s()\-]{10,20}$")


def _safe_back(default_endpoint="shop.catalog"):
    """Возврат на предыдущую страницу с защитой от open redirect."""
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        return referrer
    return url_for(default_endpoint)


@shop_bp.route("/")
def index():
    """Главная страница: новинки и акции."""
    novelties = Product.query.filter_by(is_active=True) \
        .order_by(Product.created_at.desc()).limit(8).all()
    deals = Product.query.filter(Product.is_active.is_(True),
                                 Product.old_price.isnot(None)).limit(4).all()
    return render_template("index.html", novelties=novelties, deals=deals,
                           title="Трофей — товары для охоты и рыбалки")


@shop_bp.route("/catalog")
def catalog():
    """Каталог с фильтрацией: категория, поиск, цена, наличие, сортировка."""
    page = request.args.get("page", 1, type=int)
    query_text = request.args.get("q", "").strip()
    category_slug = request.args.get("category", "")
    sort = request.args.get("sort", "new")
    price_min = request.args.get("price_min", "")
    price_max = request.args.get("price_max", "")
    in_stock = request.args.get("in_stock") == "1"

    query = Product.query.filter(Product.is_active.is_(True))
    selected_category = None
    if category_slug:
        selected_category = Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.filter(Product.category_id == selected_category.id)
    if query_text:
        query = query.filter(Product.search_index.contains(query_text.lower(),
                                                           autoescape=True))
    for raw, mode in ((price_min, "min"), (price_max, "max")):
        try:
            value = Decimal(raw.replace(",", "."))
        except (InvalidOperation, AttributeError):
            continue
        query = query.filter(Product.price >= value if mode == "min"
                             else Product.price <= value)
    if in_stock:
        query = query.filter(Product.stock > 0)

    sorting = {
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "name": Product.name.asc(),
        "new": Product.created_at.desc(),
    }
    query = query.order_by(sorting.get(sort, Product.created_at.desc()))
    pagination = query.paginate(page=page,
                                per_page=current_app.config["PRODUCTS_PER_PAGE"],
                                error_out=False)
    return render_template("catalog.html", pagination=pagination,
                           products=pagination.items, q=query_text, sort=sort,
                           selected_category=selected_category,
                           price_min=price_min, price_max=price_max,
                           in_stock=in_stock, title="Каталог товаров")


@shop_bp.route("/product/<slug>")
def product(slug):
    """Страница товара с похожими позициями из той же категории."""
    item = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    related = Product.query.filter(Product.category_id == item.category_id,
                                   Product.id != item.id,
                                   Product.is_active.is_(True)).limit(4).all()
    return render_template("product.html", product=item, related=related,
                           title=item.name)


@shop_bp.route("/cart")
def cart():
    """Страница корзины."""
    items, total, count = cart_items()
    return render_template("cart.html", items=items, total=total, count=count,
                           title="Корзина")


@shop_bp.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    """Добавление товара в корзину с возвратом на предыдущую страницу."""
    quantity = request.form.get("quantity", 1, type=int)
    added = add_to_cart(product_id, quantity)
    if added:
        flash("Товар добавлен в корзину", "success")
    else:
        flash("Товара нет в наличии", "warning")
    return redirect(_safe_back())


@shop_bp.route("/cart/update/<int:product_id>", methods=["POST"])
def cart_update(product_id):
    """Обновление количества позиции в корзине."""
    set_quantity(product_id, request.form.get("quantity", 1, type=int))
    flash("Корзина обновлена", "success")
    return redirect(url_for("shop.cart"))


@shop_bp.route("/cart/remove/<int:product_id>", methods=["POST"])
def cart_remove(product_id):
    """Удаление позиции из корзины."""
    remove_from_cart(product_id)
    flash("Товар удалён из корзины", "success")
    return redirect(url_for("shop.cart"))


def _validate_checkout(form):
    """Серверная валидация формы оформления заказа."""
    errors = {}
    if len(form.get("name", "").strip()) < 2:
        errors["name"] = "Укажите имя и фамилию (не менее 2 символов)"
    if not EMAIL_RE.match(form.get("email", "").strip()):
        errors["email"] = "Некорректный адрес электронной почты"
    if not PHONE_RE.match(form.get("phone", "").strip()):
        errors["phone"] = "Телефон должен содержать не менее 10 цифр"
    if len(form.get("address", "").strip()) < 10:
        errors["address"] = "Укажите полный адрес доставки (от 10 символов)"
    if not form.get("agree"):
        errors["agree"] = "Необходимо согласие на обработку персональных данных"
    return errors


@shop_bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    """Оформление заказа: форма, валидация, создание заказа и редирект на оплату."""
    items, total, count = cart_items()
    if not items:
        flash("Корзина пуста — добавьте товары перед оформлением заказа", "warning")
        return redirect(url_for("shop.catalog"))

    errors = {}
    if request.method == "POST":
        errors = _validate_checkout(request.form)
        if not errors:
            order = Order(
                customer_name=request.form["name"].strip(),
                email=request.form["email"].strip(),
                phone=request.form["phone"].strip(),
                address=request.form["address"].strip(),
                comment=request.form.get("comment", "").strip(),
                total=total,
                status="new",
            )
            db.session.add(order)
            db.session.flush()  # получаем id для номера заказа
            order.number = f"HF{datetime.now():%y%m%d}-{order.id:04d}"
            for item in items:
                db.session.add(OrderItem(
                    order_id=order.id, product_id=item["product"].id,
                    title=item["product"].name, price=item["product"].price,
                    quantity=item["quantity"]))
            db.session.commit()
            clear_cart()

            return_url = url_for("shop.payment_return", number=order.number,
                                 _external=True)
            try:
                payment = create_payment(order, return_url)
            except PaymentError:
                flash("Платёжный шлюз недоступен. Заказ сохранён — оплатите его позже.",
                      "warning")
                return redirect(url_for("shop.order_view", number=order.number))

            order.payment_id = payment.payment_id
            order.payment_provider = payment.provider
            db.session.commit()
            return redirect(payment.confirmation_url)

    return render_template("checkout.html", items=items, total=total,
                           count=count, errors=errors, form=request.form,
                           title="Оформление заказа")


@shop_bp.route("/payment/demo/<number>", methods=["GET", "POST"])
def demo_payment(number):
    """Эмулятор страницы банка: тестовый режим без реальных списаний."""
    order = Order.query.filter_by(number=number).first_or_404()
    if order.status != "new":
        return redirect(url_for("shop.order_view", number=order.number))

    if request.method == "POST":
        if request.form.get("result") == "success":
            mark_order_paid(order)
            flash("Оплата прошла успешно", "success")
            return redirect(url_for("shop.order_view", number=order.number))
        flash("Платёж отклонён эмулятором банка. Попробуйте ещё раз.", "danger")
        return redirect(url_for("shop.demo_payment", number=order.number))

    return render_template("payment_demo.html", order=order,
                           title="Оплата заказа")


@shop_bp.route("/payment/return/<number>")
def payment_return(number):
    """Возврат покупателя из ЮKassa: статус уточняем запросом к шлюзу."""
    order = Order.query.filter_by(number=number).first_or_404()
    if order.payment_provider == "yookassa" and order.payment_id:
        try:
            from ..payments import fetch_payment_status
            if fetch_payment_status(order.payment_id) == "succeeded":
                mark_order_paid(order)
        except PaymentError:
            flash("Не удалось уточнить статус платежа, обновите страницу позже.",
                  "warning")
    return redirect(url_for("shop.order_view", number=order.number))


@shop_bp.route("/payment/webhook", methods=["POST"])
@csrf.exempt
def payment_webhook():
    """Уведомления от ЮKassa. CSRF не применяется: запрос приходит извне."""
    payload = request.get_json(silent=True) or {}
    payment_object = payload.get("object", {})
    payment_id = payment_object.get("id")
    if not payment_id:
        return "", 400
    order = Order.query.filter_by(payment_id=payment_id).first()
    if order is None:
        return "", 200
    try:
        from ..payments import fetch_payment_status
        status = fetch_payment_status(payment_id)
    except PaymentError:
        return "", 500
    if status == "succeeded":
        mark_order_paid(order)
    elif status == "canceled":
        order.status = "cancelled"
        db.session.commit()
    return "", 200


@shop_bp.route("/order/<number>")
def order_view(number):
    """Страница заказа: статус, состав, сумма."""
    order = Order.query.filter_by(number=number).first_or_404()
    return render_template("order_success.html", order=order,
                           title=f"Заказ {order.number}")


@shop_bp.route("/info/<slug>")
def info(slug):
    """Информационные страницы магазина."""
    pages = {"delivery": "Доставка и оплата", "about": "О магазине",
             "contacts": "Контакты"}
    if slug not in pages:
        from flask import abort
        abort(404)
    return render_template(f"pages/{slug}.html", title=pages[slug])