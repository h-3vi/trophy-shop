# Трофей — интернет-магазин товаров для охоты и рыбалки

Курсовой проект: разработка и обеспечение качества модуля электронной коммерции.

## Стек
Python 3.12, Flask 3, Jinja2, SQLAlchemy, SQLite, Selenium + pytest.

## Запуск
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python run.py


## Структура
- `app/` — приложение (модели, представления, шаблоны, статика)
- `tests/` — автотесты Selenium
- `docs/` — документация и материалы к отчёту