"""Интеграция с платёжным шлюзом.

Провайдер выбирается переменной PAYMENT_PROVIDER в .env:
  demo     — встроенный эмулятор страницы банка (тестовый режим);
  yookassa — реальный шлюз ЮKassa через официальный SDK.
"""
import logging
import uuid
from dataclasses import dataclass

from flask import current_app, url_for

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Ошибка взаимодействия с платёжным шлюзом."""


@dataclass
class PaymentSession:
    """Результат создания платежа: куда отправить покупателя."""
    provider: str
    payment_id: str
    confirmation_url: str


def create_payment(order, return_url: str) -> PaymentSession:
    """Создаёт платёж и возвращает ссылку для перехода к оплате."""
    provider = current_app.config["PAYMENT_PROVIDER"]
    if provider == "yookassa":
        return _create_yookassa_payment(order, return_url)
    return PaymentSession(
        provider="demo",
        payment_id=f"DEMO-{uuid.uuid4().hex[:12].upper()}",
        confirmation_url=url_for("shop.demo_payment", number=order.number),
    )


def _configure_yookassa():
    from yookassa import Configuration

    shop_id = current_app.config["YOOKASSA_SHOP_ID"]
    secret_key = current_app.config["YOOKASSA_SECRET_KEY"]
    if not shop_id or not secret_key:
        raise PaymentError("Не заданы YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY")
    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key


def _create_yookassa_payment(order, return_url: str) -> PaymentSession:
    from yookassa import Payment

    try:
        _configure_yookassa()
        payload = {
            "amount": {"value": f"{order.total:.2f}", "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": f"Оплата заказа №{order.number} в магазине «Трофей»",
            "metadata": {"order_id": order.id, "order_number": order.number},
        }
        # Ключ идемпотентности: повтор запроса не создаст второй платёж
        payment = Payment.create(payload, uuid.uuid4().hex)
    except PaymentError:
        raise
    except Exception as exc:
        logger.exception("Ошибка создания платежа ЮKassa")
        raise PaymentError(str(exc)) from exc

    return PaymentSession("yookassa", payment.id,
                          payment.confirmation.confirmation_url)


def fetch_payment_status(payment_id: str) -> str:
    """Уточняет статус на стороне шлюза: вебхуку нельзя доверять слепо."""
    from yookassa import Payment

    try:
        _configure_yookassa()
        payment = Payment.find_one(payment_id)
    except Exception as exc:
        logger.exception("Ошибка получения статуса платежа")
        raise PaymentError(str(exc)) from exc
    return payment.status  # pending / waiting_for_capture / succeeded / canceled