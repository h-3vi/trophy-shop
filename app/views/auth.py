"""Аутентификация сотрудников магазина."""
from flask import (Blueprint, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_user, logout_user

from ..models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Вход в панель управления."""
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f"Добро пожаловать, {user.username}!", "success")
            next_url = request.args.get("next", "")
            if not next_url.startswith("/"):
                next_url = url_for("admin.dashboard")
            return redirect(next_url)
        error = "Неверный логин или пароль"
        current_app.logger.warning("Неудачная попытка входа: %s", username)

    return render_template("login.html", error=error, title="Вход в систему")


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for("shop.index"))