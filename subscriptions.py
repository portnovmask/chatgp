from fastapi import APIRouter, HTTPException, Depends
from models.users import users_collection
from datetime import datetime, timedelta, timezone
import requests
import random
from auth import get_user

router = APIRouter()



TON_WALLET = "YOUR_TON_WALLET_ADDRESS"


# 🔹 Функция для проверки платежа через TON API, когда он будет
# def get_ton_transactions():
#     url = f"https://tonapi.io/v2/accounts/{TON_WALLET}/transactions"
#     response = requests.get(url)
#     return response.json() if response.status_code == 200 else None

# Функция эмуляции транзакций
def mock_get_ton_transactions():
    return {
        "transactions": [
            {
                "hash": f"tx_{random.randint(1000, 9999)}",
                "in_msg": {
                    "source": "FAKE_WALLET_ADDRESS",
                    "value": str(5 * 1_000_000_000)  # Оплата 5 TON
                }
            }
        ]
    }

# Подменяем функцию
get_ton_transactions = mock_get_ton_transactions


# 🔹 Получение подписки пользователя
@router.get("/subscription/")
async def get_subscription(user: dict = Depends(get_user)):
    # email = user["email"]
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user.get("subscription", {})


# 🔹 Покупка подписки
@router.post("/subscribe/")
async def subscribe(level: str, user: dict = Depends(get_user)):
    email = user["email"]
    current_status = user.get("status", "trial")
    current_expiry = user.get("subscription", {}).get("expires_at")

    levels = ["trial", "basic", "pro", "premium"]
    current_index = levels.index(current_status)
    new_index = levels.index(level)

    # 📌 Повышение подписки – списать оплату сразу
    if new_index > current_index:
        tx_id = "mock_tx_id"  # Здесь должна быть реальная транзакция TON
        new_expiry = datetime.now(timezone.utc) + timedelta(days=30)

        await users_collection.update_one({"email": email}, {
            "$set": {
                "status": level,
                "subscription.level": level,
                "subscription.expires_at": new_expiry.isoformat(),
                "subscription.next_billing_date": new_expiry.isoformat(),
                "subscription.is_active": True,
                "subscription.transaction_id": tx_id,
            },
            "$push": {
                "subscription.payment_history": {
                    "tx_id": tx_id,
                    "amount": 10,  # Реальная сумма
                    "date": datetime.now(timezone.utc).isoformat()
                }
            }
        })
        return {"message": f"Подписка '{level}' активирована сразу!", "redirect": "/success"}

    # 📌 Понижение подписки – активируем позже
    elif new_index < current_index:
        await users_collection.update_one({"email": email}, {
            "$set": {
                "subscription.pending_level": level,
                "subscription.pending_activation_date": current_expiry,
            }
        })
        return {"message": f"Подписка '{level}' вступит в силу после {current_expiry}."}

    return {"message": "Вы уже на этом уровне подписки!"}


# 🔹 Автоматическое продление подписки
@router.post("/renew-subscriptions/")
async def renew_subscriptions():
    now = datetime.now(timezone.utc).isoformat()

    users = await users_collection.find({"subscription.pending_activation_date": {"$lte": now}}).to_list(None)

    for user in users:
        email = user["email"]
        new_level = user["subscription"]["pending_level"]

        tx_id = "mock_tx_id"
        new_expiry = datetime.now(timezone.utc) + timedelta(days=30)

        await users_collection.update_one({"email": email}, {
            "$set": {
                "status": new_level,
                "subscription.level": new_level,
                "subscription.expires_at": new_expiry.isoformat(),
                "subscription.next_billing_date": new_expiry.isoformat(),
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
                    "amount": 10,  # Реальная сумма
                    "date": datetime.now(timezone.utc).isoformat()
                }
            }
        })

    return {"message": "Все отложенные подписки обновлены!"}

