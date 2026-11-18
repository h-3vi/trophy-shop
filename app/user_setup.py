
"""Команды обновления пользователей и настройки администратора."""

import click

from flask.cli import with_appcontext
from sqlalchemy import inspect, text

from .extensions import db
from .models import User


@click.command("upgrade-users")
@with_appcontext
def upgrade_users():
    """
    Добавляет ФИО и телефон в существующую таблицу users.
    Не удаляет покупателей, товары и заказы.
    """

    db.create_all()

    inspector = inspect(db.engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    with db.engine.begin() as connection:

        if "full_name" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN full_name VARCHAR(120)"
                )
            )
            click.echo("Добавлено поле full_name.")

        if "phone" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN phone VARCHAR(20)"
                )
            )
            click.echo("Добавлено поле phone.")

        connection.execute(
            text(
                "UPDATE users "
                "SET full_name = username "
                "WHERE full_name IS NULL"
            )
        )

        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "ix_users_phone_unique ON users (phone)"
            )
        )

    click.echo("База пользователей обновлена!")


@click.command("setup-admin")
@with_appcontext
def setup_admin():
    """
    Настраивает администратора магазина.

    ФИО: admin
    Email: admin@admin.ru
    Телефон: 77777777777

    Пароль задаётся через терминал.
    """

    inspector = inspect(db.engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    if not {"full_name", "phone"}.issubset(columns):
        raise click.ClickException(
            "Сначала выполните команду upgrade-users."
        )

    click.echo("")
    click.echo("=== Настройка администратора Трофей ===")
    click.echo("")

    password = click.prompt(
        "Пароль администратора",
        hide_input=True,
        confirmation_prompt=True,
    )

    if len(password) < 8:
        raise click.ClickException(
            "Пароль администратора должен содержать "
            "не менее 8 символов."
        )

    admin = User.query.filter_by(
        username="admin"
    ).first()

    # Не повышаем случайного покупателя до администратора.
    if admin is not None and not admin.is_admin:
        raise click.ClickException(
            "Логин admin занят обычным пользователем."
        )

    email_owner = User.query.filter_by(
        email="admin@admin.ru"
    ).first()

    if email_owner is not None and email_owner != admin:
        raise click.ClickException(
            "Почта admin@admin.ru уже занята."
        )

    phone_owner = User.query.filter_by(
        phone="77777777777"
    ).first()

    if phone_owner is not None and phone_owner != admin:
        raise click.ClickException(
            "Телефон 77777777777 уже занят."
        )

    if admin is None:
        admin = User(
            username="admin",
            is_admin=True,
        )
        db.session.add(admin)

    admin.full_name = "admin"
    admin.email = "admin@admin.ru"
    admin.phone = "77777777777"
    admin.is_admin = True

    admin.set_password(password)

    db.session.commit()

    click.echo("")
    click.echo("Администратор успешно настроен!")
    click.echo("")
    click.echo("ФИО: admin")
    click.echo("Почта: admin@admin.ru")
    click.echo("Телефон: 77777777777")
    click.echo("Роль: Администратор")
    click.echo("")


def register_user_commands(app):
    """Подключает команды к Flask."""

    app.cli.add_command(upgrade_users)
    app.cli.add_command(setup_admin)
