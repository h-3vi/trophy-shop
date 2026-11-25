"""Общие фикстуры для 20 Selenium-сценариев. Без time.sleep."""
import os
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser):
    parser.addoption("--base-url", action="store", default=os.getenv("TROPHY_BASE_URL", "http://127.0.0.1:5000"))
    parser.addoption("--headed", action="store_true", help="Показывать Chrome")


@pytest.fixture(scope="session")
def base_url(pytestconfig):
    return pytestconfig.getoption("--base-url").rstrip("/")


@pytest.fixture
def driver(request):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--window-size=1440,1000")
    if not request.config.getoption("--headed"):
        options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    browser = webdriver.Chrome(options=options)
    browser.set_page_load_timeout(25)
    yield browser
    if getattr(request.node, "rep_call", None) and request.node.rep_call.failed:
        dest = ROOT / "test-results"
        dest.mkdir(exist_ok=True)
        name = re.sub(r"[^\w.-]+", "_", request.node.nodeid)[:140]
        try:
            browser.save_screenshot(str(dest / f"{name}.png"))
        except Exception:
            pass
    browser.quit()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, "rep_" + report.when, report)
