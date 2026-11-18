
"""Регистрация и авторизация пользователей."""
import re
import secrets
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    current_user,
    login_user,
    logout_user,
)

from ..extensions import db
from ..models import User


auth_bp = Blueprint("auth", __name__)

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)

NAME_PATTERN = re.compile(
    r"^[A-Za-zА-Яа-яЁё-]+"
    r"(?:\s+[A-Za-zА-Яа-яЁё-]+)+$"
)


def normalize_phone(value):
    """Нормализует российские номера к формату 7XXXXXXXXXX."""
    phone = re.sub(r"\D", "", value or "")

    if len(phone) == 11 and phone.startswith("8"):
        phone = "7" + phone[1:]

    if len(phone) != 11 or not phone.startswith("7"):
        return None

    return phone


def safe_next_url(value):
    """Разрешены только внутренние относительные адреса."""
    if not value:
        return None

    parsed = urlsplit(value)

    if (
        not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or parsed.scheme
        or parsed.netloc
    ):
        return None

    return value


def home_for_user(user):
    if user.is_admin:
        return url_for("admin.dashboard")
    return url_for("shop.index")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация обычного покупателя."""
    if current_user.is_authenticated:
        return redirect(home_for_user(current_user))

    errors = {}
    values = {
        "full_name": "",
        "email": "",
        "phone": "",
    }

    if request.method == "POST":
        full_name = " ".join(
            request.form.get("full_name", "").strip().split()
        )
        email = request.form.get("email", "").strip().lower()
        raw_phone = request.form.get("phone", "").strip()
        phone = normalize_phone(raw_phone)
        password = request.form.get("password", "")
        password_confirm = request.form.get(
            "password_confirm", ""
        )

        values = {
            "full_name": full_name,
            "email": email,
            "phone": raw_phone,
        }

        if (
            len(full_name) > 120
            or not NAME_PATTERN.fullmatch(full_name)
        ):
            errors["full_name"] = (
                "Введите фамилию и имя русскими "
                "или латинскими буквами."
            )

        if len(email) > 120 or not EMAIL_PATTERN.fullmatch(email):
            errors["email"] = "Введите корректную почту."
        elif User.query.filter_by(email=email).first():
            errors["email"] = "Эта почта уже зарегистрирована."

        if not phone:
            errors["phone"] = (
                "Укажите российский номер из 11 цифр, "
                "начиная с 7 или 8."
            )
        elif User.query.filter_by(phone=phone).first():
            errors["phone"] = "Этот номер уже зарегистрирован."

        if len(password) < 8:
            errors["password"] = (
                "Пароль должен содержать минимум 8 символов."
            )
        elif (
            not re.search(r"[A-Za-zА-Яа-яЁё]", password)
            or not re.search(r"\d", password)
        ):
            errors["password"] = (
                "Добавьте в пароль хотя бы одну букву и цифру."
            )

        if password != password_confirm:
            errors["password_confirm"] = "Пароли не совпадают."

        if not errors:
            username = "customer_" + secrets.token_hex(12)

            user = User(
                username=username,
                full_name=full_name,
                email=email,
                phone=phone,
                is_admin=False,
            )
            user.set_password(password)

            try:
                db.session.add(user)
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Ошибка регистрации пользователя"
                )
                errors["general"] = (
                    "Не удалось зарегистрироваться. "
                    "Проверьте данные и попробуйте ещё раз."
                )
            else:
                login_user(user)
                flash(
                    "Регистрация успешна! Добро пожаловать.",
                    "success",
                )
                return redirect(url_for("shop.index"))

    return render_template(
        "register.html",
        errors=errors,
        values=values,
        title="Регистрация",
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Вход по email и паролю."""
    if current_user.is_authenticated:
        return redirect(home_for_user(current_user))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)

            flash(
                f"Добро пожаловать, {user.display_name}!",
                "success",
            )

            destination = home_for_user(user)

            # Администратора можно направить на внутреннюю
            # страницу админки, с которой он пришёл.
            if user.is_admin:
                requested = safe_next_url(
                    request.args.get("next", "")
                )
                if requested and requested.startswith("/admin"):
                    destination = requested

            return redirect(destination)

        error = "Неверная почта или пароль."
        current_app.logger.warning(
            "Неудачная попытка входа через email"
        )

    return render_template(
        "login.html",
        error=error,
        title="Вход",
    )


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Безопасный выход через POST-запрос."""
    logout_user()
    flash("Вы вышли из аккаунта.", "success")
    return redirect(url_for("shop.index"))
