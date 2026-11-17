"""Панель управления: CRUD товаров и категорий, обработка заказов."""
from decimal import Decimal, InvalidOperation

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user

from ..extensions import db
from ..models import ORDER_STATUSES, Category, Order, OrderItem, Product
from ..utils import save_uploaded_image, unique_slug

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def restrict_to_admin():
    """Все маршруты админки доступны только авторизованному администратору."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=request.path))
    if not current_user.is_admin:
        abort(403)


@admin_bp.route("/")
def dashboard():
    """Сводка: остатки, заказы, выручка по оплаченным заказам."""
    paid_statuses = ("paid", "shipped", "completed")
    paid_orders = Order.query.filter(Order.status.in_(paid_statuses)).all()
    stats = {
        "products": Product.query.count(),
        "active": Product.query.filter_by(is_active=True).count(),
        "orders": Order.query.count(),
        "new_orders": Order.query.filter_by(status="new").count(),
        "revenue": sum((order.total for order in paid_orders), Decimal("0.00")),
        "low_stock": Product.query.filter(Product.stock < 3).count(),
    }
    latest = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, latest=latest,
                           title="Панель управления")


# ---------- Товары ----------

@admin_bp.route("/products")
def products():
    """Список товаров с поиском и пагинацией."""
    page = request.args.get("page", 1, type=int)
    query_text = request.args.get("q", "").strip()
    query = Product.query
    if query_text:
        query = query.filter(Product.search_index.contains(query_text.lower(),
                                                           autoescape=True))
    pagination = query.order_by(Product.created_at.desc()) \
        .paginate(page=page, per_page=10, error_out=False)
    return render_template("admin/products.html", pagination=pagination,
                           q=query_text, title="Товары")


def _parse_product_form(form, files):
    """Серверная валидация формы товара. Возвращает (данные, ошибки)."""
    data, errors = {}, {}

    name = form.get("name", "").strip()
    if len(name) < 3:
        errors["name"] = "Название должно содержать не менее 3 символов"
    data["name"] = name

    try:
        price = Decimal(form.get("price", "").replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise InvalidOperation
        data["price"] = price.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        errors["price"] = "Цена должна быть положительным числом"

    raw_old = form.get("old_price", "").strip()
    if raw_old:
        try:
            old_price = Decimal(raw_old.replace(",", "."))
            if "price" in data and old_price <= data["price"]:
                errors["old_price"] = "Старая цена должна быть больше текущей"
            data["old_price"] = old_price.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            errors["old_price"] = "Некорректное значение старой цены"
    else:
        data["old_price"] = None

    try:
        stock = int(form.get("stock", ""))
        if stock < 0:
            raise ValueError
        data["stock"] = stock
    except ValueError:
        errors["stock"] = "Остаток должен быть целым числом не меньше нуля"

    try:
        category_id = int(form.get("category_id", ""))
        if db.session.get(Category, category_id) is None:
            raise ValueError
        data["category_id"] = category_id
    except ValueError:
        errors["category_id"] = "Выберите существующую категорию"

    data["brand"] = form.get("brand", "").strip()
    data["description"] = form.get("description", "").strip()
    data["is_active"] = bool(form.get("is_active"))

    filename, image_error = save_uploaded_image(files.get("image"))
    if image_error:
        errors["image"] = image_error
    elif filename:
        data["image"] = filename

    return data, errors


@admin_bp.route("/products/new", methods=["GET", "POST"])
@admin_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
def product_form(product_id=None):
    """Создание и редактирование товара одной формой."""
    product = db.session.get(Product, product_id) if product_id else None
    if product_id and product is None:
        abort(404)
    categories = Category.query.order_by(Category.name).all()
    errors = {}

    if request.method == "POST":
        data, errors = _parse_product_form(request.form, request.files)
        if not errors:
            product = product or Product()
            for key, value in data.items():
                setattr(product, key, value)
            product.slug = unique_slug(Product, data["name"], exclude_id=product.id)
            db.session.add(product)
            db.session.commit()
            flash(f"Товар «{product.name}» сохранён", "success")
            return redirect(url_for("admin.products"))

    return render_template("admin/product_form.html", product=product,
                           categories=categories, errors=errors,
                           form=request.form,
                           title="Редактирование товара" if product_id
                           else "Новый товар")


@admin_bp.route("/products/<int:product_id>/delete", methods=["GET", "POST"])
def product_delete(product_id):
    """Удаление в два шага: страница подтверждения, затем POST."""
    product = db.session.get(Product, product_id)
    if product is None:
        abort(404)
    if request.method == "POST":
        # позиции старых заказов сохраняем, ссылку на товар обнуляем
        OrderItem.query.filter_by(product_id=product.id).update({"product_id": None})
        db.session.delete(product)
        db.session.commit()
        flash(f"Товар «{product.name}» удалён", "success")
        return redirect(url_for("admin.products"))
    return render_template("admin/confirm_delete.html", product=product,
                           title="Удаление товара")


# ---------- Категории ----------

@admin_bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if len(name) < 3:
            flash("Название категории слишком короткое", "danger")
        elif Category.query.filter_by(name=name).first():
            flash("Категория с таким названием уже существует", "danger")
        else:
            db.session.add(Category(
                name=name, slug=unique_slug(Category, name),
                icon=request.form.get("icon", "🎣").strip() or "🎣",
                description=request.form.get("description", "").strip()))
            db.session.commit()
            flash("Категория добавлена", "success")
        return redirect(url_for("admin.categories"))

    rows = Category.query.order_by(Category.name).all()
    return render_template("admin/categories.html", categories=rows,
                           title="Категории")


@admin_bp.route("/categories/<int:category_id>/edit", methods=["POST"])
def category_edit(category_id):
    category = db.session.get(Category, category_id) or abort(404)
    name = request.form.get("name", "").strip()
    if len(name) < 3:
        flash("Название категории слишком короткое", "danger")
    else:
        category.name = name
        category.slug = unique_slug(Category, name, exclude_id=category.id)
        category.icon = request.form.get("icon", "🎣").strip() or "🎣"
        category.description = request.form.get("description", "").strip()
        db.session.commit()
        flash("Категория обновлена", "success")
    return redirect(url_for("admin.categories"))


@admin_bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    """Запрещаем удалять категорию, пока в ней есть товары."""
    category = db.session.get(Category, category_id) or abort(404)
    if category.products:
        flash("Нельзя удалить категорию: в ней есть товары", "danger")
    else:
        db.session.delete(category)
        db.session.commit()
        flash("Категория удалена", "success")
    return redirect(url_for("admin.categories"))


# ---------- Заказы ----------

@admin_bp.route("/orders")
def orders():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    query = Order.query
    if status in ORDER_STATUSES:
        query = query.filter_by(status=status)
    pagination = query.order_by(Order.created_at.desc()) \
        .paginate(page=page, per_page=10, error_out=False)
    return render_template("admin/orders.html", pagination=pagination,
                           status=status, title="Заказы")


@admin_bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    return render_template("admin/order_detail.html", order=order,
                           title=f"Заказ {order.number}")


@admin_bp.route("/orders/<int:order_id>/status", methods=["POST"])
def order_status(order_id):
    order = db.session.get(Order, order_id) or abort(404)
    new_status = request.form.get("status", "")
    if new_status not in ORDER_STATUSES:
        flash("Недопустимый статус заказа", "danger")
    else:
        order.status = new_status
        db.session.commit()
        flash(f"Статус заказа {order.number}: {order.status_label}", "success")
    return redirect(url_for("admin.order_detail", order_id=order.id))