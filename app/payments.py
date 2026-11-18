
"""Оплата заказов через деморежим или ЮKassa."""

import logging
import uuid
from dataclasses import dataclass

from flask import current_app, url_for

logger = logging.getLogger(__name__)

PAYMENT_METHODS = {
    "bank_card": "Банковская карта",
    "sbp": "Система быстрых платежей",
}


class PaymentError(Exception):
    """Ошибка работы с платёжным провайдером."""


@dataclass
class PaymentSession:
    provider: str
    payment_id: str
    confirmation_url: str


def create_payment(
    order,
    return_url: str,
    payment_method: str = "bank_card",
) -> PaymentSession:
    """Создаёт платёж выбранным способом."""

    if payment_method not in PAYMENT_METHODS:
        raise PaymentError("Неизвестный способ оплаты")

    provider = current_app.config["PAYMENT_PROVIDER"]

    if provider == "yookassa":
        return _create_yookassa_payment(
            order,
            return_url,
            payment_method,
        )

    if provider != "demo":
        raise PaymentError("Неизвестный платёжный провайдер")

    return PaymentSession(
        provider="demo",
        payment_id=f"DEMO-{uuid.uuid4().hex[:12].upper()}",
        confirmation_url=url_for(
            "shop.demo_payment",
            number=order.number,
            method=payment_method,
        ),
    )


def _configure_yookassa():
    """Настраивает официальный SDK ЮKassa."""

    try:
        from yookassa import Configuration
    except ImportError as exc:
        raise PaymentError(
            "Не установлена библиотека yookassa"
        ) from exc

    shop_id = current_app.config["YOOKASSA_SHOP_ID"]
    secret_key = current_app.config["YOOKASSA_SECRET_KEY"]

    if not shop_id or not secret_key:
        raise PaymentError(
            "Не заданы YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY"
        )

    Configuration.account_id = shop_id
    Configuration.secret_key = secret_key


def _create_yookassa_payment(
    order,
    return_url: str,
    payment_method: str,
) -> PaymentSession:
    """Создаёт платёж картой или через СБП."""

    try:
        _configure_yookassa()

        from yookassa import Payment

        payload = {
            "amount": {
                "value": f"{order.total:.2f}",
                "currency": "RUB",
            },
            "capture": True,
            "payment_method_data": {
                "type": payment_method,
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url,
            },
            "description": (
                f"Оплата заказа №{order.number} "
                "в магазине Трофей"
            ),
            "metadata": {
                "order_id": str(order.id),
                "order_number": order.number,
                "payment_method": payment_method,
            },
        }

        # Стабильный ключ для повторной попытки
        # создания одного платежа по заказу.
        idempotency_key = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"trophy:{order.number}:{payment_method}",
            )
        )

        payment = Payment.create(
            payload,
            idempotency_key,
        )

        if (
            not payment.confirmation
            or not payment.confirmation.confirmation_url
        ):
            raise PaymentError(
                "ЮKassa не вернула страницу оплаты"
            )

        return PaymentSession(
            provider="yookassa",
            payment_id=payment.id,
            confirmation_url=payment.confirmation.confirmation_url,
        )

    except PaymentError:
        raise

    except Exception as exc:
        logger.exception(
            "Ошибка создания платежа ЮKassa"
        )

        raise PaymentError(
            "Не удалось создать платёж"
        ) from exc


def fetch_payment_status(payment_id: str) -> str:
    """Получает актуальный статус платежа от ЮKassa."""

    try:
        _configure_yookassa()

        from yookassa import Payment

        payment = Payment.find_one(payment_id)

        return payment.status

    except PaymentError:
        raise

    except Exception as exc:
        logger.exception(
            "Ошибка проверки платежа ЮKassa"
        )

        raise PaymentError(
            "Не удалось проверить статус платежа"
        ) from exc
