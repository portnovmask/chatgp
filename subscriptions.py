from fastapi import APIRouter, HTTPException, Depends, Request
#from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import uuid
from models.users import users_collection
from datetime import datetime, timedelta, timezone
import random
from auth import get_user
import locale

router = APIRouter()
templates = Jinja2Templates(directory="templates")
pretty_names = {
    "trial": "Базовый",
    "basic": "Оптимум",
    "advanced": "Фрилансер",
    "business": "Бизнес",
    "pro": "Мыслитель",
    "premium": "Премиум"
}
locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

TON_WALLET = "YOUR_TON_WALLET_ADDRESS"


# 🔹 Функция для проверки платежа через TON API, когда он будет
import requests

TON_WALLET = "YOUR_WALLET_ADDRESS_HERE"  # замени на адрес своего кошелька

# def get_ton_transaction(min_amount_ton: float = 1.0):
#     url = f"https://tonapi.io/v2/accounts/{TON_WALLET}/transactions"
#     response = requests.get(url)
#
#     if response.status_code != 200:
#         return None
#
#     data = response.json()
#     for tx in data.get("transactions", []):
#         in_msg = tx.get("in_msg")
#         if not in_msg:
#             continue
#
#         try:
#             value_nano = int(in_msg.get("value", "0"))
#             value_ton = value_nano / 1_000_000_000
#             if value_ton >= min_amount_ton:
#                 return {
#                     "hash": tx["hash"],
#                     "value_nano": value_nano,
#                     "value_ton": value_ton,
#                     "source": in_msg.get("source"),
#                 }
#         except (TypeError, ValueError):
#             continue
#
#     return None


# Функция отображения человеческого времени
def format_datetime_pretty(dt: datetime) -> str:
    return dt.strftime("%-d %B %Yг в %H:%M")


# Функция эмуляции транзакций
def mock_get_ton_transactions(expected_amount_ton: float):
    # Преобразуем TON в нанотоны, умножая на 1_000_000_000
    nano_ton = int(expected_amount_ton * 1_000_000_000)

    if nano_ton > 0:
        return {
            "transactions": [
                {
                    "hash": f"tx_{random.randint(1000, 9999)}",
                    "in_msg": {
                        "source": "FAKE_WALLET_ADDRESS",
                        "value": nano_ton  # Используем целое число
                    }
                }
            ]
        }
    else:
        return {}


# Подменяем функцию
get_ton_transactions = mock_get_ton_transactions

levels = ["trial", "basic", "advanced", "business", "pro", "premium"]
prices = [0, 1, 4, 8, 12, 32]

# 🔹 Получение подписки пользователя
@router.get("/subscription/")
async def get_subscription(user: dict = Depends(get_user)):
    # email = user["email"]
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user.get("subscription", {})


#  Покупка подписки
# # @router.post("/subscribe/")
# # async def subscribe(level: str, user: dict = Depends(get_user)):
# #     email = user["email"]
# #     current_status = user.get("status", "trial")
# #     current_expiry = user.get("subscription", {}).get("expires_at")
# #     tx_id, sender, amount_ton = None, None, 0
# #
# #     current_index = levels.index(current_status)
# #     new_index = levels.index(level)
# #     new_price = prices[new_index]
# #
# #     transactions = get_ton_transactions(new_price).get("transactions", [])
# #
# #     if transactions:
# #         for tx in transactions:
# #             tx_id = tx.get("hash")
# #             in_msg = tx.get("in_msg", {})
# #
# #             sender = in_msg.get("source") if sender else None
# #             value = in_msg.get("value")  # в наноTON (1 TON = 1_000_000_000)
# #
# #             # Преобразуем значение из строкового в числовой формат (в TON)
# #             amount_ton = int(value) / 1_000_000_000 if value else 0
# #
# #     #  Повышение подписки – списать оплату сразу
# #     if new_index > current_index:
# #        # Здесь должна быть реальная транзакция TON
# #         new_expiry = datetime.now(timezone.utc) + timedelta(days=7)
# #
# #         await users_collection.update_one({"email": email}, {
# #             "$set": {
# #                 "status": level,
# #                 "original_status": level,
# #                 "tokens": 0,
# #                 "subscription.level": level,
# #                 "subscription.expires_at": new_expiry,
# #                 "subscription.next_billing_date": new_expiry,
# #                 "subscription.is_active": True,
# #                 "subscription.transaction_id": tx_id,
# #             },
# #             "$push": {
# #                 "subscription.payment_history": {
# #                     "tx_id": tx_id,
# #                     "amount": amount_ton, # Реальная сумма
# #                     "source": sender, # контрагент
# #                     "date": datetime.now(timezone.utc)
# #                 }
# #             }
# #         })
# #         return {"message": f"Поздравляем! План '{pretty_names[level]}' будет активирован сразу после подтверждения оплаты!", "status": "success"}
#
#     #  Понижение подписки – активируем позже
#     elif new_index < current_index:
#         await users_collection.update_one({"email": email}, {
#             "$set": {
#                 "subscription.pending_level": level,
#                 "subscription.pending_activation_date": current_expiry,
#             }
#         })
#         return {"message": f"Вы успешно сменили подписку! План '{pretty_names[level]}' будет активирован после подтверждения оплаты и вступит в силу после истечения текущей подписки:\n {format_datetime_pretty(current_expiry)}." , "status": "success"}
#
#     return {"message": "Вы уже на этом уровне подписки!", "status": "info"}

@router.post("/subscribe/")
async def subscribe(level: str, user: dict = Depends(get_user)):
    email = user["email"]

    if level not in levels:
        return {"message": "Подписка на этот уровень невозможна на данный момент!", "status": "error"}
    if level == "trial":
        return {"message": "Для отмены текущей подписки...!", "status": "info"}

    payment_id = str(uuid.uuid4())

    # Можно временно сохранить payment_id в БД пользователя, если нужно
    await users_collection.update_one({"email": email}, {
        "$set": {"subscription.pending_payment_id": payment_id}
    })

    # Вставка URL параметров в редирект
    return {"redirect": f"/payment/{payment_id}?level={level}"}



# routes/ton.py
from ton_links import generate_payment_link
from qr_utils import generate_qr_base64

@router.get("/payment/{payment_id}")
async def payment_page(request: Request, payment_id: str, level: str, user: dict = Depends(get_user)):
    email = user["email"]
    price = prices[levels.index(level)]
    payment = generate_payment_link(email, level, price, payment_id)
    qr = generate_qr_base64(payment["url"])

    return templates.TemplateResponse("payment.html", {
        "request": request,
        "payment_url": payment["url"],
        "qr_base64": qr,
        "level": level,
        "payment_id": payment_id,
        "pretty_name": pretty_names[level]
    })

# @router.get("/ton/prepare-payment/")
# async def prepare_payment(level: str, user: dict = Depends(get_user)):
#     email = user["email"]
#     amount_map = {
#         "basic": 1,
#         "advanced": 4,
#         "business": 8,
#         "pro": 12,
#         "premium": 32,
#     }
#
#     if level not in amount_map:
#         return {"error": "Invalid level"}
#
#     amount = amount_map[level]
#     payment = generate_payment_link(email, level, amount)
#     qr = generate_qr_base64(payment["url"])
#
#     return {
#         "payment_url": payment["url"],
#         "payment_id": payment["payment_id"],
#         "qr_base64": qr
#     }



@router.post("/ton/verify-payment/")
async def verify_ton_payment(level: str, user: dict = Depends(get_user)):
    if level not in levels:
        raise HTTPException(status_code=400, detail="Некорректный уровень подписки")

    email = user["email"]
    current_status = user.get("status", "trial")
    current_expiry = user.get("subscription", {}).get("expires_at")
    current_index = levels.index(current_status)
    new_index = levels.index(level)

    if new_index == current_index:
        return {"message": "Вы уже на этом уровне подписки!", "status": "info"}

    price = prices[new_index]
    transactions = get_ton_transactions(price).get("transactions", [])

    if not transactions:
        raise HTTPException(status_code=402, detail="Платеж не найден или не подтверждён")

    tx = transactions[0]
    tx_id = tx.get("hash")
    in_msg = tx.get("in_msg", {})
    sender = in_msg.get("source")
    value = in_msg.get("value")
    amount_ton = int(value) / 1_000_000_000 if value else 0

    # 🔸 Проверка на повтор транзакции
    existing_tx = await users_collection.find_one({
        "subscription.payment_history.tx_id": tx_id
    })
    if existing_tx:
        return {"message": "Эта транзакция уже была использована.", "status": "warning"}

    now = datetime.now(timezone.utc)
    new_expiry = now + timedelta(days=7)

    # 🔼 Повышение — активируем сразу
    if new_index > current_index:
        await users_collection.update_one({"email": email}, {
            "$set": {
                "status": level,
                "original_status": level,
                "tokens": 0,
                "subscription.level": level,
                "subscription.expires_at": new_expiry,
                "subscription.next_billing_date": new_expiry,
                "subscription.is_active": True,
                "subscription.transaction_id": tx_id,
            },
            "$push": {
                "subscription.payment_history": {
                    "tx_id": tx_id,
                    "amount": amount_ton,
                    "source": sender,
                    "date": now
                }
            }
        })
        return {"message": f"Подписка '{pretty_names[level]}' активирована!", "status": "success"}

    # 🔽 Понижение — активируем позже
    elif new_index < current_index:
        await users_collection.update_one({"email": email}, {
            "$set": {
                "subscription.pending_level": level,
                "subscription.pending_activation_date": current_expiry,
            },
            "$push": {
                "subscription.payment_history": {
                    "tx_id": tx_id,
                    "amount": amount_ton,
                    "source": sender,
                    "date": now
                }
            }
        })
        return {
            "message": f"Оплата принята! Новый уровень подписки '{pretty_names[level]}' будет активирован после окончания текущего периода: {format_datetime_pretty(current_expiry)}.",
            "status": "success"
        }




# 🔹 Автоматическое продление подписки
@router.post("/renew-subscriptions/")
async def renew_subscriptions():
    now = datetime.now(timezone.utc)

    users = await users_collection.find({"subscription.pending_activation_date": {"$lte": now}}).to_list(None)
    sender, amount_ton = None, 0
    for user in users:
        email = user["email"]
        new_level = user["subscription"]["pending_level"]

        tx_id = "mock_tx_id"
        new_expiry = datetime.now(timezone.utc) + timedelta(days=7)
        new_index = levels.index(new_level)
        new_price = prices[new_index]
        transactions = get_ton_transactions(new_price).get("transactions", [])

        if transactions:
            for tx in transactions:
                tx_id = tx.get("hash")
                in_msg = tx.get("in_msg", {})

                sender = in_msg.get("source")
                value = in_msg.get("value")  # в наноTON (1 TON = 1_000_000_000)

                # Преобразуем значение из строкового в числовой формат (в TON)
                amount_ton = int(value) / 1_000_000_000 if value else 0
        await users_collection.update_one({"email": email}, {
            "$set": {
                "status": new_level,
                "original_status": new_level,
                "tokens": 0,
                "subscription.level": new_level,
                "subscription.expires_at": new_expiry,
                "subscription.next_billing_date": new_expiry,
                "subscription.is_active": True,
                "subscription.transaction_id": tx_id,
            },
            "$unset": {
                "subscription.pending_level": "",
                "subscription.pending_activation_date": "",
            },
            "$push": {
                "subscription.payment_history": {
                    "tx_id": tx_id,
                    "amount": amount_ton,  # Реальная сумма
                    "source": sender,  # контрагент
                    "date": datetime.now(timezone.utc)
                }
            }
        })

    return {"message": "Все отложенные подписки обновлены!"}
