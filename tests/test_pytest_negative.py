"""5 негативных unit-тестов: серверная проверка некорректного оформления."""
from app.views.shop import _validate_checkout


VALID = {
    "name": "Иван Иванов",
    "email": "ivan@example.com",
    "phone": "+79991234567",
    "address": "Вологда, Первомайская, д. 42",
    "agree": "1",
}


def broken_form(field, value):
    result = VALID.copy()
    if value is None:
        result.pop(field)
    else:
        result[field] = value
    return result


def test_unit_negative_01_name_too_short():
    assert "name" in _validate_checkout(broken_form("name", "А"))


def test_unit_negative_02_bad_email():
    assert "email" in _validate_checkout(broken_form("email", "wrong-address"))


def test_unit_negative_03_bad_phone():
    assert "phone" in _validate_checkout(broken_form("phone", "123"))


def test_unit_negative_04_short_address():
    assert "address" in _validate_checkout(broken_form("address", "Вологда"))


def test_unit_negative_05_consent_missing():
    assert "agree" in _validate_checkout(broken_form("agree", None))
