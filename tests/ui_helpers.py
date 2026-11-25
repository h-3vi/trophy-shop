"""Общие действия в браузере, использующие устойчивые data-testid."""
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


WAIT_SECONDS = 12


def open_home(driver, base_url):
    driver.get(base_url + "/")
    return WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'header.header'))
    )


def open_catalog(driver, base_url):
    open_home(driver, base_url)
    link = driver.find_element(By.CSS_SELECTOR, '[data-testid="nav-catalog"]')
    driver.get(link.get_attribute("href"))
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'form:has([data-testid="search-input"])'))
    )


def product_links(driver):
    return driver.find_elements(By.CSS_SELECTOR, '[data-testid="product-card"] a.card-media')


def product_titles(driver):
    return [e.text.strip() for e in driver.find_elements(By.CSS_SELECTOR, '[data-testid="product-title"]')]


def first_product(driver, base_url):
    open_catalog(driver, base_url)
    links = product_links(driver)
    assert links, "В каталоге нет товаров — сначала заполни БД"
    driver.get(links[0].get_attribute("href"))
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-testid="product-name"]'))
    )


def add_product(driver, base_url):
    first_product(driver, base_url)
    button = driver.find_element(By.CSS_SELECTOR, '[data-testid="add-to-cart"]')
    assert button.is_enabled(), "Первый товар отсутствует на складе: выбери доступный для теста"
    button.click()
    driver.get(urljoin(base_url + "/", "cart"))
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="cart-item"]'))
    )


def catalog_form(driver):
    return driver.find_element(By.CSS_SELECTOR, 'form:has([data-testid="search-input"])')


def apply_catalog(driver):
    driver.find_element(By.CSS_SELECTOR, '[data-testid="filter-apply"]').click()
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="search-input"]'))
    )
