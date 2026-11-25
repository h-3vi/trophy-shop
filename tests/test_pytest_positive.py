
"""5 позитивных модульных тестов Trophy Shop.

Проверяют модели товаров, расчёт стоимости
и корректность данных оформления заказа.

Selenium и браузер не используются.
"""

from decimal import Decimal

from app.models import OrderItem, Product
from app.views.shop import _validate_checkout


def test_unit_positive_01_product_in_stock():
    """Товар с положительным остатком доступен."""

    product = Product(
        name="Тестовый товар",
        stock=3,
        price=Decimal("100.00"),
    )

    assert product.in_stock is True


def test_unit_positive_02_product_discount():
    """Скидка рассчитывается правильно."""

    product = Product(
        name="Тестовый товар",
        stock=1,
        price=Decimal("80.00"),
        old_price=Decimal("100.00"),
    )

    assert product.discount == 20


def test_unit_positive_03_no_discount_when_equal_price():
    """При одинаковых ценах скидка равна нулю."""

    product = Product(
        name="Тестовый товар",
        stock=1,
        price=Decimal("100.00"),
        old_price=Decimal("100.00"),
    )

    assert product.discount == 0


def test_unit_positive_04_order_item_subtotal():
    """Стоимость позиции равна цене за штуку,
    умноженной на количество.
    """

    item = OrderItem(
        title="Тестовый товар",
        price=Decimal("125.50"),
        quantity=3,
    )

    assert item.subtotal == Decimal("376.50")


def test_unit_positive_05_checkout_valid_data():
    """Правильные данные заказа проходят валидацию."""

    form = {
        "name": "Иван Иванов",
        "email": "ivan@example.com",
        "phone": "+79991234567",
        "address": "Вологда, Первомайская, д. 42",
        "agree": "1",
    }

    errors = _validate_checkout(form)

    assert errors == {}, (
        f"Корректные данные отклонены: {errors}"
    )
