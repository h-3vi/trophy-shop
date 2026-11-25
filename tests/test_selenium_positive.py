
"""10 позитивных Selenium-тестов интернет-магазина Трофей."""

from urllib.parse import parse_qs, urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from .ui_helpers import (
    open_catalog,
    open_home,
    first_product,
)


WAIT = 15


def wait_for_page_reload(driver, old_element):
    """Ожидаем завершения запроса и перезагрузки страницы."""
    WebDriverWait(driver, WAIT).until(
        EC.staleness_of(old_element)
    )

    WebDriverWait(driver, WAIT).until(
        lambda browser:
            browser.execute_script(
                "return document.readyState"
            ) == "complete"
    )


def product_titles(driver):
    """Получаем названия товаров, отображённых в каталоге."""
    return [
        item.text.strip()
        for item in driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="product-title"]'
        )
        if item.text.strip()
    ]


def open_available_product(driver, base_url):
    """
    Находим доступный товар и открываем его карточку.
    Не выбираем товар без остатка на складе.
    """
    open_catalog(driver, base_url)

    wait = WebDriverWait(driver, WAIT)

    cards = wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, '[data-testid="product-card"]')
        )
    )

    product_url = None

    for card in cards:
        buttons = card.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="add-to-cart"]'
        )

        links = card.find_elements(
            By.CSS_SELECTOR,
            "a.card-media"
        )

        if buttons and buttons[0].is_enabled() and links:
            product_url = links[0].get_attribute("href")
            break

    assert product_url, "Не найден товар в наличии"

    driver.get(product_url)

    name = wait.until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="product-name"]')
        )
    ).text.strip()

    assert name

    return name


def add_product_to_cart(driver, base_url):
    """
    Добавляем товар и дожидаемся завершения POST-запроса.
    Затем проверяем содержимое корзины.
    """

    name = open_available_product(driver, base_url)

    wait = WebDriverWait(driver, WAIT)

    button = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="add-to-cart"]')
        )
    )

    assert button.is_enabled(), "Кнопка покупки отключена"

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        button
    )

    # Обычный пользовательский клик.
    wait.until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, '[data-testid="add-to-cart"]')
        )
    ).click()

    # Flask выполняет POST и redirect.
    # Пока старая страница не исчезла,
    # переходить в корзину нельзя.
    wait_for_page_reload(driver, button)

    # Проверяем подтверждение от сервера.
    messages = [
        element.text.strip()
        for element in driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="flash-message"]'
        )
    ]

    assert any(
        "добавлен" in message.casefold()
        for message in messages
    ), (
        "Нет подтверждения добавления товара. "
        f"Сообщения сервера: {messages}. "
        f"URL: {driver.current_url}"
    )

    driver.get(base_url + "/cart")

    wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, '[data-testid="cart-item"]')
        )
    )

    names = [
        item.text.strip()
        for item in driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="cart-item-name"] a'
        )
    ]

    assert name in names, (
        f"Товар '{name}' не появился в корзине. "
        f"Фактическое содержимое: {names}"
    )

    return name


def test_ui_positive_01_home_opens(driver, base_url):
    open_home(driver, base_url)

    assert "Трофей" in driver.title


def test_ui_positive_02_slider_available(driver, base_url):
    open_home(driver, base_url)

    slides = driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="slide"]'
    )

    assert len(slides) >= 2

    assert any(
        "is-active" in slide.get_attribute("class")
        for slide in slides
    )


def test_ui_positive_03_catalog_opens(driver, base_url):
    open_catalog(driver, base_url)

    assert "/catalog" in driver.current_url

    assert driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    ).is_displayed()


def test_ui_positive_04_category_filter(driver, base_url):
    open_catalog(driver, base_url)

    selector = '[data-testid="category-filter"]'

    Select(
        driver.find_element(By.CSS_SELECTOR, selector)
    ).select_by_value("rybalka")

    form = driver.find_element(
        By.ID,
        "catalog-filters"
    )

    form.find_element(
        By.CSS_SELECTOR,
        '[data-testid="filter-apply"]'
    ).click()

    wait_for_page_reload(driver, form)

    params = parse_qs(urlparse(driver.current_url).query)

    assert params.get("category") == ["rybalka"]


def test_ui_positive_05_contacts_page(driver, base_url):
    open_home(driver, base_url)

    driver.get(base_url + "/info/contacts")

    assert "contacts" in driver.current_url

    assert driver.find_element(
        By.TAG_NAME,
        "main"
    ).is_displayed()


def test_ui_positive_06_product_page(driver, base_url):
    first_product(driver, base_url)

    name = driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="product-name"]'
    )

    price = driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="product-price"]'
    )

    assert name.text.strip()
    assert price.text.strip()


def test_ui_positive_07_search_existing_product(driver, base_url):
    """
    Берём название существующего товара.
    Отправляем поисковую форму и ожидаем
    завершения загрузки результатов.
    """

    open_catalog(driver, base_url)

    names = product_titles(driver)

    assert names, "В каталоге отсутствуют товары"

    original_name = names[0]

    # Используем первое слово названия.
    keyword = original_name.split()[0]

    assert keyword, "Не удалось получить поисковое слово"

    search = driver.find_element(
        By.CSS_SELECTOR,
        '[data-testid="search-input"]'
    )

    search.clear()
    search.send_keys(keyword)

    form = driver.find_element(
        By.ID,
        "catalog-filters"
    )

    form.find_element(
        By.CSS_SELECTOR,
        '[data-testid="filter-apply"]'
    ).click()

    wait_for_page_reload(driver, form)

    params = parse_qs(
        urlparse(driver.current_url).query
    )

    assert params.get("q") == [keyword], (
        f"Поисковая форма не отправила запрос '{keyword}'. "
        f"URL: {driver.current_url}"
    )

    results = product_titles(driver)

    assert results, (
        f"Поиск по '{keyword}' не вернул товаров. "
        f"Исходное название: '{original_name}'. "
        f"URL: {driver.current_url}. "
        "Проверь заполнение Product.search_index в базе."
    )

    assert any(
        keyword.casefold() in title.casefold()
        for title in results
    ), (
        f"Не найден ожидаемый товар по '{keyword}'. "
        f"Результаты: {results}"
    )


def test_ui_positive_08_sort_price(driver, base_url):
    open_catalog(driver, base_url)

    Select(
        driver.find_element(
            By.CSS_SELECTOR,
            '[data-testid="sort-select"]'
        )
    ).select_by_value("price_asc")

    form = driver.find_element(
        By.ID,
        "catalog-filters"
    )

    form.find_element(
        By.CSS_SELECTOR,
        '[data-testid="filter-apply"]'
    ).click()

    wait_for_page_reload(driver, form)

    params = parse_qs(
        urlparse(driver.current_url).query
    )

    assert params.get("sort") == ["price_asc"]


def test_ui_positive_09_add_to_cart(driver, base_url):
    name = add_product_to_cart(driver, base_url)

    names = [
        element.text.strip()
        for element in driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="cart-item-name"] a'
        )
    ]

    assert name in names


def test_ui_positive_10_remove_from_cart(driver, base_url):
    name = add_product_to_cart(driver, base_url)

    wait = WebDriverWait(driver, WAIT)

    target = None

    for row in driver.find_elements(
        By.CSS_SELECTOR,
        '[data-testid="cart-item"]'
    ):
        link = row.find_element(
            By.CSS_SELECTOR,
            '[data-testid="cart-item-name"] a'
        )

        if link.text.strip() == name:
            target = row
            break

    assert target is not None, (
        f"Товар '{name}' не найден перед удалением"
    )

    button = target.find_element(
        By.CSS_SELECTOR,
        '[data-testid="remove-item"]'
    )

    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});",
        button
    )

    button.click()

    wait_for_page_reload(driver, button)

    names = [
        element.text.strip()
        for element in driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="cart-item-name"] a'
        )
    ]

    assert name not in names, (
        f"Товар '{name}' остался после удаления"
    )

    # Проверка сохранения состояния корзины.
    driver.refresh()

    names_after_refresh = [
        element.text.strip()
        for element in driver.find_elements(
            By.CSS_SELECTOR,
            '[data-testid="cart-item-name"] a'
        )
    ]

    assert name not in names_after_refresh
