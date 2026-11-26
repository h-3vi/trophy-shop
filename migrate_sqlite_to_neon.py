"""Безопасный перенос SQLite -> PostgreSQL (Neon) для Trophy Shop.

Запуск из корня проекта: python migrate_sqlite_to_neon.py

Переносит поля текущих SQLAlchemy-моделей. Старые дополнительные
столбцы SQLite (например, categories.image) пропускает. Полная
копия SQLite остаётся в backups/, поэтому исходные данные не теряются.
Не перезаписывает непустые таблицы Neon.
"""

import os
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Date, DateTime, Numeric, Boolean, MetaData, Table
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.engine import URL

from app.extensions import db
import app.models  # noqa: F401 - импорт регистрирует модели SQLAlchemy


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def fail(message):
    raise SystemExit("ОШИБКА: " + message)


def sqlite_path():
    explicit = os.getenv("SQLITE_SOURCE", "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        path = path if path.is_absolute() else ROOT / path
        if not path.is_file():
            fail(f"Файл SQLite не найден: {path}")
        return path.resolve()

    candidates = (
        ROOT / "shop.db",
        ROOT / "instance" / "shop.db",
        ROOT / "app" / "instance" / "shop.db",
    )
    found = [path.resolve() for path in candidates if path.is_file()]
    if not found:
        fail("Файл shop.db не найден. Укажи SQLITE_SOURCE в .env")
    if len(found) > 1:
        fail("Найдено несколько shop.db. Укажи SQLITE_SOURCE в .env: "
             + ", ".join(map(str, found)))
    return found[0]


def neon_url():
    raw = os.getenv("DIRECT_DATABASE_URL", "").strip()
    if not raw:
        fail("В .env отсутствует DIRECT_DATABASE_URL (прямое соединение Neon)")
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw[len("postgres://"):]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://"):]
    if not raw.startswith("postgresql+psycopg://"):
        fail("Нужен URL postgresql://... или postgresql+psycopg://...")
    return raw


def make_backup(original):
    folder = ROOT / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = folder / f"shop-before-neon-{stamp}.db"
    source_db = sqlite3.connect(original.as_uri() + "?mode=ro", uri=True)
    backup_db = sqlite3.connect(str(backup_path))
    try:
        source_db.backup(backup_db)
    finally:
        backup_db.close()
        source_db.close()
    return backup_path


def convert_value(value, column):
    """Привести значения SQLite к типам, принимаемым psycopg/PostgreSQL."""
    if value is None:
        return None
    if isinstance(column.type, Boolean):
        return bool(value)
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date) and isinstance(value, str):
        return date.fromisoformat(value)
    if isinstance(column.type, Numeric) and not isinstance(value, Decimal):
        return Decimal(str(value))
    return value


def main():
    original = sqlite_path()
    model_tables = list(db.Model.metadata.sorted_tables)
    if not model_tables:
        fail("Модели SQLAlchemy не найдены")

    backup_file = make_backup(original)
    print(f"Исходная SQLite: {original}")
    print(f"Резервная копия: {backup_file}")

    # Читаем из неподвижной резервной копии, а не из файла работающего сайта.
    sqlite_engine = create_engine("sqlite:///" + backup_file.as_posix())
    pg_engine = create_engine(neon_url(), pool_pre_ping=True)
    legacy_tables = {}
    counts = {}
    try:
        source_names = set(inspect(sqlite_engine).get_table_names())
        for model in model_tables:
            if model.name not in source_names:
                fail(f"В SQLite отсутствует таблица {model.name}")

            legacy = Table(model.name, MetaData(), autoload_with=sqlite_engine)
            old_fields = set(legacy.c.keys())
            new_fields = set(model.c.keys())
            missing = sorted(new_fields - old_fields)
            extra = sorted(old_fields - new_fields)

            if missing:
                fail(f"В SQLite для {model.name} отсутствуют поля модели: "
                     + ", ".join(missing)
                     + ". Нужна отдельная миграция схемы")
            if extra:
                print(f"ВНИМАНИЕ: {model.name}: лишние старые поля "
                      + ", ".join(extra) + "; они останутся в резервной SQLite")

            legacy_tables[model.name] = legacy
            with sqlite_engine.connect() as connection:
                counts[model.name] = connection.scalar(
                    select(func.count()).select_from(legacy)
                )

        if not counts.get("categories") or not counts.get("products"):
            fail("В исходной SQLite нет категорий или товаров. Проверь SQLITE_SOURCE")

        print("В SQLite:", ", ".join(f"{name}={count}" for name, count in counts.items()))

        pg_inspector = inspect(pg_engine)
        pg_names = set(pg_inspector.get_table_names())
        with pg_engine.connect() as connection:
            for model in model_tables:
                if model.name not in pg_names:
                    continue
                pg_fields = {col["name"] for col in pg_inspector.get_columns(model.name)}
                missing_pg = set(model.c.keys()) - pg_fields
                if missing_pg:
                    fail(f"В Neon таблица {model.name} имеет старую схему. "
                         f"Не хватает: {sorted(missing_pg)}")
                rows_count = connection.scalar(select(func.count()).select_from(model))
                if rows_count:
                    fail(f"Neon уже содержит записи в {model.name}: {rows_count}. "
                         "Перезапись запрещена")

        # Создание отсутствующих таблиц и весь перенос идут одной транзакцией.
        with sqlite_engine.connect() as old, pg_engine.begin() as new:
            db.Model.metadata.create_all(bind=new)

            for model in model_tables:
                legacy = legacy_tables[model.name]
                columns = [legacy.c[col.name] for col in model.columns]
                rows = []
                for row in old.execute(select(*columns)).mappings():
                    rows.append({
                        col.name: convert_value(row[col.name], col)
                        for col in model.columns
                    })

                if rows:
                    new.execute(model.insert(), rows)

                inserted = new.scalar(select(func.count()).select_from(model))
                if inserted != counts[model.name]:
                    fail(f"Проверка {model.name}: ожидалось "
                         f"{counts[model.name]}, перенесено {inserted}")

                if rows and "id" in model.c:
                    seq = new.scalar(
                        text("SELECT pg_get_serial_sequence(:t, 'id')"),
                        {"t": model.name},
                    )
                    if seq:
                        new.execute(
                            text("SELECT setval(CAST(:seq AS regclass), :id, true)"),
                            {"seq": seq, "id": max(row["id"] for row in rows)},
                        )
                print(f"Перенесено {model.name}: {inserted}")

        print("\nУСПЕШНО: перенос завершён. SQLite и резервная копия сохранены.")
        print("Можно проверить магазин, затем заменить DATABASE_URL на Neon.")
    finally:
        sqlite_engine.dispose()
        pg_engine.dispose()


if __name__ == "__main__":
    main()
