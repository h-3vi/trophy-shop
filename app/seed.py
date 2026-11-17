"""Наполнение БД демонстрационными данными: flask --app run.py seed."""
import click
from flask import current_app
from flask.cli import with_appcontext

from .extensions import db
from .models import Category, Product, User
from .utils import unique_slug

CATEGORIES = [
    ("Удочки и спиннинги", "🎣", "Спиннинговые, маховые и фидерные удилища"),
    ("Катушки и лески", "🧵", "Безынерционные катушки, шнуры и лески"),
    ("Приманки", "🐟", "Воблеры, блёсны и силикон"),
    ("Охота", "🦌", "Оптика, манки, ягдташи и снаряжение"),
    ("Одежда и обувь", "🥾", "Костюмы, сапоги и термобельё"),
    ("Кемпинг", "🏕️", "Палатки, термосы и походная утварь"),
]

PRODUCTS = [
    ("Спиннинг Волжанка Optima 2.4 м", "Волжанка", "Удочки и спиннинги", 4990, 6490, 12,
     "Универсальный спиннинг среднего строя, тест 5–25 г, карбоновый бланк."),
    ("Удилище маховое Salmo Sniper 5 м", "Salmo", "Удочки и спиннинги", 2350, None, 8,
     "Лёгкое маховое удилище для поплавочной ловли накоротке."),
    ("Фидер Kaida NeoXen 3.6 м", "Kaida", "Удочки и спиннинги", 5780, 6900, 5,
     "Фидерное удилище с тремя квивертипами, тест до 90 г."),
    ("Катушка Shimano Nexave 4000", "Shimano", "Катушки и лески", 6890, None, 10,
     "Безынерционная катушка, 3 подшипника, передний фрикцион."),
    ("Катушка Kaida Spin 3000", "Kaida", "Катушки и лески", 2190, 2790, 15,
     "Бюджетная катушка для спиннинга и лёгкого фидера."),
    ("Плетёный шнур Power Pro 135 м", "Power Pro", "Катушки и лески", 1890, None, 20,
     "Восьмижильный шнур, разрывная нагрузка 12 кг, цвет — зелёный."),
    ("Воблер Rapala Original Floater 90", "Rapala", "Приманки", 1250, None, 25,
     "Классический плавающий воблер из бальсы, заглубление 0,9 м."),
    ("Набор силикона Keitech Easy Shiner 10 шт", "Keitech", "Приманки", 890, 1150, 30,
     "Съедобная резина 3 дюйма, 10 штук в упаковке."),
    ("Блесна Kuusamo Rasanen 70", "Kuusamo", "Приманки", 1490, None, 14,
     "Колеблющаяся блесна для троллинга и ловли щуки на мелководье."),
    ("Прицел оптический Veber 3-9x40", "Veber", "Охота", 8900, 10500, 4,
     "Переменная кратность 3–9x, объектив 40 мм, сетка Duplex."),
    ("Ягдташ кожаный «Следопыт»", "Следопыт", "Охота", 3400, None, 7,
     "Натуральная кожа, сетка для дичи, регулируемый ремень."),
    ("Манок на тетерева Primos", "Primos", "Охота", 1120, None, 9,
     "Духовой манок, воспроизводит ток тетерева и глухаря."),
    ("Костюм зимний «Тайга» -30 °C", "Тайга", "Одежда и обувь", 12500, 15900, 6,
     "Утеплённый костюм с мембраной, куртка и полукомбинезон."),
    ("Сапоги ЭВА Nordman -45 °C", "Nordman", "Одежда и обувь", 4250, None, 11,
     "Сапоги из ЭВА со съёмным чулком, вес пары — 1,2 кг."),
    ("Палатка Trek Planet Sierra 3", "Trek Planet", "Кемпинг", 9990, 12400, 5,
     "Трёхместная двухслойная палатка, водостойкость 3000 мм."),
    ("Термос Stanley Classic 1.0 л", "Stanley", "Кемпинг", 5600, None, 13,
     "Стальной вакуумный термос, держит тепло до 24 часов."),
    ("Нож складной Kizlyar Supreme Bloke", "Kizlyar Supreme", "Кемпинг", 4700, None, 8,
     "Хозяйственно-бытовой складной нож, сталь AUS-8, рукоять G10."),
]


def ensure_admin():
    """Создаёт учётную запись администратора из переменных окружения."""
    username = current_app.config["ADMIN_USERNAME"]
    if User.query.filter_by(username=username).first():
        return
    admin = User(username=username, email="admin@trophy-shop.ru", is_admin=True)
    admin.set_password(current_app.config["ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()
    click.echo(f"Создан администратор: {username}")


@click.command("seed")
@with_appcontext
def seed_command():
    """Создать администратора и наполнить каталог тестовыми товарами."""
    db.create_all()
    ensure_admin()

    for name, icon, description in CATEGORIES:
        if Category.query.filter_by(name=name).first() is None:
            db.session.add(Category(name=name, slug=unique_slug(Category, name),
                                    icon=icon, description=description))
    db.session.commit()

    categories = {category.name: category for category in Category.query.all()}
    added = 0
    for name, brand, category_name, price, old_price, stock, description in PRODUCTS:
        if Product.query.filter_by(name=name).first():
            continue
        db.session.add(Product(
            name=name, slug=unique_slug(Product, name), brand=brand,
            description=description, price=price, old_price=old_price,
            stock=stock, is_active=True,
            category_id=categories[category_name].id))
        added += 1
    db.session.commit()
    click.echo(f"Категорий: {len(CATEGORIES)}, добавлено товаров: {added}")


def register_commands(app):
    app.cli.add_command(seed_command)