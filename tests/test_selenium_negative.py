
"""10 негативных Selenium-тестов Trophy Shop."""

from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .ui_helpers import (
    add_product,
    apply_catalog,
    open_catalog,
    open_home,
)


def test_ui_negative_01_no_results_search(driver, base_url):
    open_catalog(driver, base_url)

    driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    ).send_keys("zz_no_such_product_490283")

    apply_catalog(driver)

    assert driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="empty-result"]'
    )


def test_ui_negative_02_unknown_category_returns_404(driver, base_url):
    driver.get(
        base_url + "/catalog?category=no-such-category-8295"
    )

    assert not driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="product-card"]'
    )

    assert "500" not in driver.title


def test_ui_negative_03_unknown_product_returns_404(driver, base_url):
    driver.get(
        base_url + "/product/no-such-product-8295"
    )

    assert not driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="product-name"]'
    )

    assert "500" not in driver.title


def test_ui_negative_04_unknown_info_returns_404(driver, base_url):
    driver.get(
        base_url + "/info/no-such-page-8295"
    )

    assert "500" not in driver.title

    assert not driver.find_elements(
        By.CSS_SELECTOR,
        ".t-contact-value"
    )


def test_ui_negative_05_invalid_page_no_crash(driver, base_url):
    driver.get(
        base_url + "/catalog?page=not-a-number"
    )

    assert driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    )


def test_ui_negative_06_invalid_minimum_price_no_crash(driver, base_url):
    driver.get(
        base_url + "/catalog?price_min=wrong"
    )

    assert driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    )


def test_ui_negative_07_invalid_sort_no_crash(driver, base_url):
    driver.get(
        base_url + "/catalog?sort=unknown_sort"
    )

    assert driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    )


def test_ui_negative_08_unknown_search_with_special_chars(driver, base_url):
    driver.get(
        base_url + "/catalog?q=" +
        quote("___@@@###ззз_не_существует")
    )

    assert driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    )

    assert not driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="product-card"]'
    )


def test_ui_negative_09_empty_cart_cannot_checkout(driver, base_url):
    open_home(driver, base_url)

    driver.get(
        base_url + "/checkout"
    )

    assert "/checkout" not in driver.current_url


def test_ui_negative_10_checkout_invalid_email(driver, base_url):
    """
    Проверка:
    заказ нельзя оформить с некорректным email.

    Отправка выполняется через requestSubmit(),
    чтобы проверить настоящую HTML-валидацию,
    не завися от перекрытия кнопки элементами CSS.
    """

    # Добавляем товар в корзину.
    add_product(driver, base_url)

    checkout_link = driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="checkout-button"]'
    )

    checkout_url = checkout_link.get_attribute("href")

    driver.get(checkout_url)

    wait = WebDriverWait(driver, 12)

    email_field = wait.until(
        EC.presence_of_element_located(
            (
                By.CSS_SELECTOR,
                '[data-testid="input-email"]'
            )
        )
    )

    # Заполняем форму.
    fields = {
        "input-name": "Иван Иванов",
        "input-phone": "+79991234567",
        "input-email": "not-an-email",
        "input-address": "Вологда, Первомайская, 42",
    }

    for test_id, value in fields.items():

        element = driver.find_element(
            By.CSS_SELECTOR,
            f'[data-testid="{test_id}"]'
        )

        element.clear()
        element.send_keys(value)

    # Проверяем, что email действительно
    # содержит некорректное значение.
    assert email_field.get_attribute("value") == "not-an-email"

    # Устанавливаем согласие.
    agree = driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="input-agree"]'
    )

    if not agree.is_selected():
        driver.execute_script(
            "arguments[0].click();",
            agree
        )

    assert agree.is_selected(), (
        "Согласие на обработку данных не установлено"
    )

    # Получаем кнопку оформления.
    submit_button = driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="submit-order"]'
    )

    # ВАЖНО:
    # requestSubmit() сохраняет HTML5-валидацию,
    # но не требует физического клика мышью.
    driver.execute_script(
        """
        const button = arguments[0];
        const form = button.closest('form');

        if (!form) {
            throw new Error(
                'Не найдена форма оформления заказа'
            );
        }

        form.requestSubmit(button);
        """,
        submit_button
    )

    # Проверяем отказ в отправке.
    def email_rejected(browser):

        errors = browser.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="error-email"]'
        )

        visible_errors = any(
            element.is_displayed()
            for element in errors
        )

        email_fields = browser.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="input-email"]'
        )

        invalid_html5 = False

        if email_fields:

            invalid_html5 = browser.execute_script(
                """
                return !arguments[0].validity.valid;
                """,
                email_fields[0]
            )

        return visible_errors or invalid_html5

    assert wait.until(email_rejected), (
        "Форма не отклонила некорректный email"
    )

    # Не должно быть перехода к оплате
    # или странице подтверждения заказа.
    assert "/payment/" not in driver.current_url
    assert "/order/success" not in driver.current_url

    # Страница оформления должна остаться открытой.
    assert "/checkout" in driver.current_url
