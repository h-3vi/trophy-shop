
"""
Trophy Shop — привязка фотографий к товарам.

Поддерживаемые форматы:
.jpg, .jpeg, .png, .webp

Фотографии:
app/static/uploads/

Список товаров:
photo_list.csv

Запуск:
python sync_photos.py

Скрипт:
- Находит фотографии независимо от расширения.
- Проверяет, что файл является изображением.
- Привязывает фотографии к товарам по ID.
- Не удаляет товары и существующие фотографии.
- Не изменяет цены, описания и остатки.
- Пропускает HTML-файлы.
"""

import csv
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import Product


# ==========================================
# ПУТИ
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = (
    BASE_DIR
    / "app"
    / "static"
    / "uploads"
)

CSV_FILE = BASE_DIR / "photo_list.csv"

SUPPORTED_FORMATS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


# ==========================================
# ПРОВЕРКА ФОРМАТА ФАЙЛА
# ==========================================

def detect_image_format(path):
    """
    Проверяет настоящий формат изображения
    по содержимому файла, а не только по имени.
    """

    try:
        with path.open("rb") as file:
            header = file.read(16)

        # JPEG
        if header.startswith(b"\xff\xd8\xff"):
            return "jpeg"

        # PNG
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"

        # WEBP
        if (
            header.startswith(b"RIFF")
            and header[8:12] == b"WEBP"
        ):
            return "webp"

    except OSError:
        return None

    return None


def image_is_valid(path):
    """
    Проверяет, соответствует ли содержимое
    расширению изображения.
    """

    actual_format = detect_image_format(path)

    if actual_format is None:
        return False

    extension = path.suffix.lower()

    if actual_format == "jpeg":
        return extension in {".jpg", ".jpeg"}

    return extension == f".{actual_format}"


# ==========================================
# ПОИСК ФОТОГРАФИИ
# ==========================================

def find_photo(expected_filename):
    """
    Ищет файл с нужной основой имени.

    Например:
    fishing-012.jpg

    Найдёт:
    fishing-012.jpeg
    fishing-012.png
    fishing-012.webp
    fishing-012.jpg
    """

    expected_stem = Path(expected_filename).stem.lower()

    matches = []

    for file in UPLOAD_DIR.iterdir():

        if not file.is_file():
            continue

        if file.suffix.lower() not in SUPPORTED_FORMATS:
            continue

        if file.stem.lower() != expected_stem:
            continue

        matches.append(file)

    if not matches:
        return None, "not_found"

    valid_matches = [
        file
        for file in matches
        if image_is_valid(file)
    ]

    if not valid_matches:
        return None, "invalid"

    # Если несколько файлов имеют одно имя
    # с разными расширениями, не выбираем
    # случайно неправильную фотографию.
    if len(valid_matches) > 1:
        return None, "duplicate"

    return valid_matches[0], "ok"


# ==========================================
# ПРИВЯЗКА ФОТОГРАФИЙ
# ==========================================

def sync_photos():

    print()
    print("=" * 55)
    print("TROPHY SHOP — ПРИВЯЗКА ФОТОГРАФИЙ")
    print("=" * 55)

    if not CSV_FILE.exists():
        print()
        print("ОШИБКА: photo_list.csv не найден.")
        print("Сначала создайте список через fill_catalog.py")
        return

    if not UPLOAD_DIR.exists():
        print()
        print("ОШИБКА: папка uploads не найдена.")
        print(UPLOAD_DIR)
        return

    updated = 0
    already_linked = 0
    not_found = 0
    invalid = 0
    duplicates = 0
    skipped = 0

    missing_products = []

    with CSV_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file,
            delimiter=";",
        )

        required_columns = {
            "product_id",
            "product_name",
            "filename",
        }

        if not required_columns.issubset(
            set(reader.fieldnames or [])
        ):
            print(
                "ОШИБКА: неправильная структура photo_list.csv"
            )
            return

        rows = list(reader)

    print(f"\nВсего товаров в списке: {len(rows)}")
    print()

    # Проверяем, что одному товару не назначены
    # противоречащие друг другу имена фотографий.
    seen_ids = set()
    seen_filenames = set()

    for row in rows:

        try:
            product_id = int(row["product_id"])
        except (TypeError, ValueError):
            print("Некорректный ID в CSV.")
            return

        filename = row["filename"].strip()
        stem = Path(filename).stem.lower()

        if (
            Path(filename).name != filename
            or not stem
            or not filename.lower().endswith(".jpg")
        ):
            print(f"Некорректное имя файла: {filename}")
            return

        if product_id in seen_ids or stem in seen_filenames:
            print(
                "ОШИБКА: повторяющийся ID или имя фотографии "
                f"в CSV: {filename}"
            )
            return

        seen_ids.add(product_id)
        seen_filenames.add(stem)

    # ======================================
    # ОБХОД ТОВАРОВ
    # ======================================

    for row in rows:

        product_id = int(row["product_id"])
        product_name = row["product_name"].strip()
        expected_filename = row["filename"].strip()

        product = db.session.get(Product, product_id)

        if product is None:
            skipped += 1
            print(
                f"[ПРОПУСК] Товар ID {product_id} "
                "отсутствует в базе."
            )
            continue

        # Защита от несовпадения CSV и базы.
        if product.name != product_name:
            skipped += 1
            print(
                f"[ПРОПУСК] Название не совпадает: "
                f"ID {product_id}"
            )
            continue

        photo, status = find_photo(expected_filename)

        if status == "not_found":
            not_found += 1
            missing_products.append(
                (product_name, expected_filename)
            )
            print(
                f"[НЕТ ФОТО] {product_name}"
            )
            continue

        if status == "invalid":
            invalid += 1
            print(
                f"[ОШИБКА ФАЙЛА] {expected_filename}"
            )
            continue

        if status == "duplicate":
            duplicates += 1
            print(
                f"[ДУБЛИКАТ] {expected_filename} — "
                "найдено несколько форматов."
            )
            continue

        # В БД хранится только имя файла.
        # Шаблон формирует путь static/uploads/.
        new_image = photo.name

        if product.image == new_image:
            already_linked += 1
            print(
                f"[УЖЕ ГОТОВО] {product_name}"
            )
            continue

        product.image = new_image

        updated += 1

        print(
            f"[OK] {product_name}"
        )
        print(
            f"     -> {new_image}"
        )

    # ======================================
    # СОХРАНЕНИЕ
    # ======================================

    try:
        db.session.commit()

    except Exception as error:
        db.session.rollback()

        print()
        print("Ошибка сохранения в базу данных:")
        print(error)
        return

    # ======================================
    # ОТЧЁТ
    # ======================================

    print()
    print("=" * 55)
    print("РЕЗУЛЬТАТ")
    print("=" * 55)

    print(f"Товаров в списке:       {len(rows)}")
    print(f"Фотографий привязано:   {updated}")
    print(f"Уже были привязаны:     {already_linked}")
    print(f"Фотографии не найдены:  {not_found}")
    print(f"Неверные файлы:         {invalid}")
    print(f"Дублирующиеся файлы:    {duplicates}")
    print(f"Пропущено товаров:      {skipped}")

    if missing_products:

        print()
        print("СПИСОК НЕДОСТАЮЩИХ ФОТОГРАФИЙ:")

        for name, filename in missing_products:
            print(f" - {filename} : {name}")

    print()
    print("Готово!")
    print()


# ==========================================
# ЗАПУСК
# ==========================================

if __name__ == "__main__":

    app = create_app()

    with app.app_context():
        sync_photos()
