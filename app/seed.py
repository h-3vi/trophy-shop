"""Наполнение БД демонстрационными данными: flask --app run.py seed."""
import click
from flask import current_app
from flask.cli import with_appcontext

from .extensions import db
from .models import Category, Product, User
from .utils import unique_slug

CATEGORIES = [
    ("Рыбалка", "🎣", "Удилища, катушки, шнуры и приманки", "img/categories/fishing.png"),
    ("Охота", "🦌", "Оптика, манки, чучела и снаряжение", "img/categories/hunting.png"),
    ("Одежда и обувь", "🥾", "Костюмы, сапоги и термобельё", "img/categories/clothes.png"),
    ("Туризм", "🏕️", "Палатки, термосы и походная утварь", "img/categories/tourism.png"),
    ("Ножи", "🔪", "Складные и туристические ножи", "img/categories/knives.png"),
]

PRODUCTS = [
    ("Спиннинг Volzhanka Optima 2.4 м", "Volzhanka", "Рыбалка", 4990, 6490, 12,
     "img/products/rod-hand.png",
     "Тест 5–25 г, строй средне-быстрый, бланк карбон IM7. Универсал для джига и воблеров."),
    ("Спиннинг Major Craft Crozzera 2.13 м", "Major Craft", "Рыбалка", 7450, None, 9,
     "img/products/rod-camo.png",
     "Тест 7–28 г, быстрый строй, рукоять EVA. Заточен под джиговую ловлю судака и щуки."),
    ("Удилище маховое Salmo Sniper 5 м", "Salmo", "Рыбалка", 2350, None, 8,
     "img/products/rods-lake.png",
     "Лёгкое маховое удилище из композита, вес 180 г. Для поплавочной ловли накоротке."),
    ("Катушка Shimano Nexave 4000", "Shimano", "Рыбалка", 6890, None, 10,
     "img/products/reel-black.png",
     "3 подшипника, передний фрикцион, передатка 5.0:1. Надёжна в фидере и среднем джиге."),
    ("Катушка Okuma Trio Rex 3000", "Okuma", "Рыбалка", 5290, 6100, 7,
     "img/products/reel-talica.png",
     "Алюминиевая шпуля, 4 подшипника, вес 262 г. Плавный ход и точная укладка шнура."),
    ("Катушка Kaida Spin 3000", "Kaida", "Рыбалка", 2190, 2790, 15,
     "img/products/reel-spool.png",
     "Бюджетная безынерционка для спиннинга и лёгкого фидера, передатка 5.2:1."),
    ("Плетёный шнур Power Pro 135 м 0.15 мм", "Power Pro", "Рыбалка", 1890, None, 20,
     "img/products/braid-pack.png",
     "Четырёхпрядный PE-шнур, разрывная нагрузка 9 кг. Нулевая растяжимость для джига."),
    ("Леска Owner Nylon 100 м 0.25 мм", "Owner", "Рыбалка", 490, None, 35,
     "img/products/line-spool.png",
     "Прозрачная нейлоновая леска для поплавка и фидера, разрывная нагрузка 4.6 кг."),
    ("Воблер Rapala Original Floater 90", "Rapala", "Рыбалка", 1250, None, 25,
     "img/products/lure-pack.png",
     "Плавающий воблер из бальсы, заглубление 0.9 м, длина 9 см. Классика по щуке и окуню."),
    ("Воблер-раттлин Hengjia VIB 70 мм 18 г", "Hengjia", "Рыбалка", 690, 890, 30,
     "img/products/lure-vib.png",
     "Тонущий раттлин с шумовыми шариками, стабильная игра на любой проводке до 3 м."),
    ("Блесна Acme Kastmaster 14 г", "Acme", "Рыбалка", 1490, None, 14,
     "img/products/lure-spoon.png",
     "Легендарный срез для дальнего заброса, работает по жереху, судаку и щуке."),
    ("Набор кренков Tsuribito 14 шт", "Tsuribito", "Рыбалка", 1590, 2100, 18,
     "img/products/lure-crank.png",
     "Комплект из 14 кренков 3–6 см с тройниками №8–12: подбор цвета под любую воду."),
    ("Набор крючков Owner Iseama №8 (10 шт)", "Owner", "Рыбалка", 320, None, 50,
     "",
     "Японские крючки из закалённой стали с химической заточкой жала. Для поплавочной оснастки."),
    ("Прицел оптический Veber 3-9x40", "Veber", "Охота", 8900, 10500, 4,
     "img/products/scope-side.png",
     "Переменная кратность 3–9x, сетка Duplex с подсветкой, корпус заполнен азотом."),
    ("Прицел Tract Toric 3-15x50", "Tract", "Охота", 32500, None, 2,
     "img/products/scope-long.png",
     "Сетка BDC, барабаны с ценой клика 0.1 мрад, линзы с ED-стеклом и просветлением."),
    ("Чучело утки-кряквы вращающееся", "Avery", "Охота", 1150, None, 12,
     "img/products/decoy-duck.png",
     "Вращающееся чучело для посадки кряквы, устойчиво к ветру и выцветанию на солнце."),
    ("Ягдташ кожаный «Следопыт»", "Следопыт", "Охота", 3400, None, 7,
     "img/products/game-bag.png",
     "Натуральная кожа и вощёная канва, сетка для дичи, ремень через плечо с регулировкой."),
    ("Манок на тетерева Primos", "Primos", "Охота", 1120, None, 9,
     "",
     "Духовой манок, воспроизводит ток тетерева и глухаря на дистанции до 300 м."),
    ("Патронташ на 24 патрона 12 к", "Huntpro", "Охота", 1780, 2150, 11,
     "",
     "Неопреновый патронташ на 24 гнезда, крепится на ремень, бесшумные застёжки."),
    ("Костюм зимний «Тайга» -30 °C", "Тайга", "Одежда и обувь", 12500, 15900, 6,
     "img/products/jacket-winter.png",
     "Мембрана 5000 мм, утеплитель Hollowsoft, проклеенные швы. Куртка и полукомбинезон."),
    ("Куртка демисезонная Huntec Softshell", "Huntec", "Одежда и обувь", 8900, None, 8,
     "img/products/jacket-camo.png",
     "Софтшелл с флисовой подкладкой, камуфляж под лес, капюшон и манжеты с регулировкой."),
    ("Сапоги ЭВА Nordman -45 °C", "Nordman", "Одежда и обувь", 4250, None, 11,
     "img/products/boots-black.png",
     "Сапоги из ЭВА со съёмным фольгированным чулком, вес пары 1.2 кг, противоскользящий протектор."),
    ("Сапоги резиновые Muck Arctic Sport", "Muck Boot", "Одежда и обувь", 9800, 11400, 6,
     "img/products/boots-pair.png",
     "Неопрен 5 мм плюс резина, комфорт до -30 °C, усиленные носок и пятка."),
    ("Термобельё Norveg Hunter Wool", "Norveg", "Одежда и обувь", 5400, None, 10,
     "",
     "Двухслойное бельё из мериносовой шерсти: отвод влаги и тепло на ходовой охоте."),
    ("Палатка Trek Planet Sierra 3", "Trek Planet", "Туризм", 9990, 12400, 5,
     "img/products/tent-forest.png",
     "Трёхместная двухслойная палатка, водостойкость тента 3000 мм, тамбур для снаряжения."),
    ("Палатка кемпинговая GreenCamp 2", "GreenCamp", "Туризм", 6400, None, 7,
     "img/products/tent-camp.png",
     "Двухместная палатка с тамбуром, дуги фибергласс, вес 3.4 кг, сборка за 10 минут."),
    ("Термос Stanley Classic 1.0 л", "Stanley", "Туризм", 5600, None, 13,
     "img/products/thermos-steel.png",
     "Вакуумная колба из нержавейки, держит тепло 24 часа, пожизненная гарантия производителя."),
    ("Термос Arctica 1.6 л с ручкой", "Arctica", "Туризм", 3900, 4600, 9,
     "img/products/thermos-set.png",
     "Стальной термос 1.6 л с дополнительной ручкой и двумя чашками в комплекте."),
    ("Нож складной Kizlyar Supreme Bloke", "Kizlyar Supreme", "Ножи", 4700, None, 8,
     "img/products/knife-black.png",
     "Сталь AUS-8, рукоять G10, замок liner-lock. Хозяйственно-бытовой, разрешения не требует."),
    ("Нож туристический Fällkniven F1x", "Fällkniven", "Ножи", 16900, None, 3,
     "img/products/knife-wood.png",
     "Клинок из ламинированной стали Elmax, влагостойкая рукоять, ножны в комплекте."),
]


def ensure_admin():
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
    db.create_all()
    ensure_admin()

    for name, icon, description, image in CATEGORIES:
        if Category.query.filter_by(name=name).first() is None:
            db.session.add(Category(name=name, slug=unique_slug(Category, name),
                                    icon=icon, description=description, image=image))
    db.session.commit()

    categories = {c.name: c for c in Category.query.all()}
    added = 0
    for (name, brand, cat_name, price, old_price, stock, image, desc) in PRODUCTS:
        if Product.query.filter_by(name=name).first():
            continue
        db.session.add(Product(
            name=name, slug=unique_slug(Product, name), brand=brand,
            description=desc, price=price, old_price=old_price,
            stock=stock, image=image, is_active=True,
            category_id=categories[cat_name].id))
        added += 1
    db.session.commit()
    click.echo(f"Категорий: {len(CATEGORIES)}, добавлено товаров: {added}")


def register_commands(app):
    app.cli.add_command(seed_command)