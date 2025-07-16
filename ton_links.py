# ton_links.py
import hmac
import hashlib
import logging
import urllib.parse
#from fastapi import Request
from settings import TON_WALLET, TON_SECRET_KEY # если используешь pydantic.BaseSettings

logger = logging.getLogger("app_logger")

def generate_payment_link(email: str, level: str, amount: float, payment_id: str) -> dict:
    user_amount = amount
    base_url = f"https://app.tonkeeper.com/transfer/{TON_WALLET}"
    #base_url = "https://tonkeeper.app/transfer/TEST_PUBLIC_KEY" # Тестовая ссылка

    # параметры для подписи
    params = {
        "email": email,
        "level": level,
        "payment_id": payment_id,
        "amount": str(amount)
    }

    # сериализация в виде строки запроса
    query_string = urllib.parse.urlencode(params)

    # HMAC-SHA256 подпись
    signature = hmac.new(
       TON_SECRET_KEY.encode(),
        query_string.encode(),
        hashlib.sha256
    ).hexdigest()

    # итоговая ссылка
    full_query = f"{query_string}&sig={signature}"
    full_url = f"{base_url}?{full_query}"
    logger.info(f"Сформирована ссылка на оплату для пользователя {email} на сумму {amount} нанотон, ссылка: {full_url}")
    return {
        "payment_id": payment_id,
        "url": full_url
    }
