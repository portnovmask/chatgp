from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
import logging
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import uuid
import httpx
from pymongo import UpdateOne
import re
from models.users import users_collection
from datetime import datetime, timedelta, timezone
import random
from auth import get_user
import locale
from settings import TON_WALLET, TON_API_KEY, LEVELS, PRETTY_NAMES, PRICES, LOGO_URL, BASE_URL
from mail import EmailTemplate, send_email, generate_confirmation_token
router = APIRouter(prefix="/api")
templates = Jinja2Templates(directory="templates")

locale.setlocale(locale.LC_TIME, '')

logger = logging.getLogger("app_logger")



async def get_ton_usdt_price():
    url = "https://api.coinlore.net/api/ticker/?id=54683"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=3)

        logger.info(f"Ответ от апи курса Тон: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            price = data[0].get("price_usd")
            logger.info(f"Текущий курс Тон: {price}")
            return float(price)
    except Exception as e:
        logger.warning(f"Ошибка при получении курса Тон: {e}")

    logger.info("Не удалось получить курс Тон, возвращаем дефолтный курс")
    return 2.70

# 🔹 Функция для проверки платежа через TON API, когда он будет

import requests

async def get_ton_transaction(min_amount_ton: float = 1.0):
    url = f"https://tonapi.io/v2/blockchain/accounts/{TON_WALLET}/transactions"
    headers = {
        "Authorization": f"Bearer {TON_API_KEY}"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.info(f"get_ton_transaction - Ошибка {exc.response.status_code}: {exc.response.text}")
            return None
        except httpx.RequestError as exc:
            logger.info(f"get_ton_transaction - Ошибка запроса: {exc}")
            return None

    data = response.json()
    for tx in data.get("transactions", []):
        in_msg = tx.get("in_msg")
        if not in_msg:
            continue

        try:
            value_nano = int(in_msg.get("value", "0"))
            value_ton = value_nano / 1_000_000_000
            if value_ton >= min_amount_ton:
                return {
                    "hash": tx["hash"],
                    "value_nano": value_nano,
                    "value_ton": value_ton,
                    "source": in_msg.get("source"),
                }
        except (TypeError, ValueError):
            logger.info("get_ton_transaction - Ошибка при обработке транзакции")
            continue

    return None


# Функция отображения человеческого времени
def format_datetime_pretty(dt: datetime) -> str:
    return dt.strftime("%-d %B %Yг в %H:%M")


# # Функция эмуляции транзакций
# def mock_get_ton_transactions(expected_amount_ton: float):
#     # Преобразуем TON в нанотоны, умножая на 1_000_000_000
#     nano_ton = int(expected_amount_ton * 1_000_000_000)
#
#     if nano_ton > 0:
#         return {
#             "transactions": [
#                 {
#                     "hash": f"tx_{random.randint(1000, 9999)}",
#                     "in_msg": {
#                         "source": "FAKE_WALLET_ADDRESS",
#                         "value": nano_ton  # Используем целое число
#                     }
#                 }
#             ]
#         }
#     else:
#         return {}
#
#
# # Подменяем функцию
# get_ton_transactions = mock_get_ton_transactions


# 🔹 Получение подписки пользователя
@router.get("/subscription/")
async def get_subscription(user: dict = Depends(get_user)):
    # email = user["email"]
    if not user:
        logger.info(f"get_subscription - пользователь не найден, email: {user.get("email")}")
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
# #     current_index = LEVELS.index(current_status)
# #     new_index = LEVELS.index(level)
# #     new_price = PRICES[new_index]
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
# #         return {"message": f"Поздравляем! План '{PRETTY_NAMES[level]}' будет активирован сразу после подтверждения оплаты!", "status": "success"}
#
#     #  Понижение подписки – активируем позже
#     elif new_index < current_index:
#         await users_collection.update_one({"email": email}, {
#             "$set": {
#                 "subscription.pending_level": level,
#                 "subscription.pending_activation_date": current_expiry,
#             }
#         })
#         return {"message": f"Вы успешно сменили подписку! План '{PRETTY_NAMES[level]}' будет активирован после подтверждения оплаты и вступит в силу после истечения текущей подписки:\n {format_datetime_pretty(current_expiry)}." , "status": "success"}
#
#     return {"message": "Вы уже на этом уровне подписки!", "status": "info"}

@router.post("/subscribe/")
async def subscribe(level: str, user: dict = Depends(get_user)):
    if not user:
        return RedirectResponse(url="/")
    email = user["email"]

    if level not in LEVELS:
        return {"message": "Подписка на этот уровень невозможна на данный момент!", "status": "error"}
    if level == "trial":
        return {"message": "Для отмены текущей подписки просто не оплачивайте следующий период или отмените подписку на Бусти!", "status": "info"}

    payment_id = str(uuid.uuid4())

    # Можно временно сохранить payment_id в БД пользователя, если нужно
    await users_collection.update_one({"email": email}, {
        "$set": {"subscription.pending_payment_id": payment_id}
    })

    # Вставка URL параметров в редирект
    return {"redirect": f"/api/payment/{payment_id}?level={level}"}


# routes/ton.py
from ton_links import generate_payment_link
from qr_utils import generate_qr_base64


@router.get("/payment/{payment_id}")
async def payment_page(request: Request, background_tasks: BackgroundTasks, payment_id: str, level: str, user: dict = Depends(get_user)):
    if not user:
        return RedirectResponse(url="/")
    if not user.get("contact"):
        return templates.TemplateResponse("feedback.html", {
            "request": request,
            "message": "Для покупки уровней вам необходимо указать контактный email!",
            "status": "warning",
            "action": {
                "label": "Добавить email",
                "url": "/dash",
                "method": "get"
            }
        })
    email = user.get("email")
    boosty = user.get("boosty_code", False)
    usdt_price = await get_ton_usdt_price()
    price = (PRICES[LEVELS.index(level)]/usdt_price)*1000000000
    payment = generate_payment_link(email, level, price, payment_id)
    qr = generate_qr_base64(payment["url"])

    email_template = EmailTemplate(
        logo_url=LOGO_URL,
        header_link=BASE_URL,
        header_text="Вы выбрали подписку!!!",
        description=f"Уровеень подписки: {level}.",
        recipient_name=email,
        body_text=f"Спасибо за выбор подписки {level} на ChatGP по цене {round(price / 1_000_000_000, 2)} Ton!"
                  "Если вы еще не оплатили по ссылке или qr коду на сайте вы можете провести оплату по ссылке ниже с ценой подписки."
                  "Для оплаты по ссылке убедитесь, что у вас есть аккаунт в TonKeeper или другом криптовалютном кошельке.",
        action_label="ссылка на оплату",
        action_url=payment,
        footer_text="Если вы считаете, что письмо пришло вам по ошибке — просто проигнорируйте его."
    )
    html = email_template.render()
    background_tasks.add_task(send_email, user, "Выбор подписки", html)

    return templates.TemplateResponse("payment.html", {
        "request": request,
        "payment_url": payment["url"],
        "qr_base64": qr,
        "level": level,
        "payment_id": payment_id,
        "pretty_name": PRETTY_NAMES[level],
        "boosty": boosty,
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
async def verify_ton_payment(request: Request, background_tasks: BackgroundTasks, level: str, user: dict = Depends(get_user)):
    if not user:
        return RedirectResponse(url="/")
    if level not in LEVELS:
        logger.info(f"verify_ton_payment - Некорректный уровень подписки, email: {user.get("email")}, level: {level}")
        raise HTTPException(status_code=405, detail="Некорректный уровень подписки")

    email = user["email"]
    current_status = user.get("status", "trial")
    current_expiry = user.get("subscription", {}).get("expires_at")
    current_index = LEVELS.index(current_status)
    new_index = LEVELS.index(level)
    if new_index == current_index:
        return templates.TemplateResponse("feedback.html", {
            "request": request,
            "message": "Вы уже на этом уровне подписки",
            "status": "warning",
            "action": {
                "label": "Выбрать другой уровень",
                "url": "/price",
                "method": "get"
            }
        })

    price = PRICES[new_index]
    transactions = await get_ton_transaction(price)

    if not transactions:
        logger.info(
            f"verify_ton_payment - Платеж не найден или не подтверждён, email: {user.get("email")}, level: {level}")
        return templates.TemplateResponse("feedback.html", {
            "request": request,
            "message": "Платёж не найден или не подтверждён. Проверьте позже в личном кабинете",
            "status": "warning",
            "action": {
                "label": "Проверить",
                "url": "/dash",
                "method": "get"
            }
        })

    data = transactions.get("transactions", [])



    tx = data[0]
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
        return templates.TemplateResponse("feedback.html", {
            "request": request,
            "message": "Эта транзакция уже была использована.",
            "status": "warning",
            "action": {
                "label": "Попробовать еще раз",
                "url": "/price",
                "method": "get"
            }
        })

    now = datetime.now(timezone.utc)
    new_expiry = now + timedelta(days=30)

    # 🔼 Повышение — активируем сразу
    if new_index > current_index:
        await users_collection.update_one({"email": email}, {
            "$set": {
                "status": level,
                "original_status": level,
                "tokens": 0,
                "attempts": 0,
                "subscription.level": level,
                "subscription.expires_at": new_expiry,
                "subscription.next_billing_date": new_expiry,
                "subscription.is_active": True,
                "subscription.transaction_id": tx_id
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
        logger.info(f"verify_ton_payment - Подписка активирована, email: {user.get("email")}, level: {level}")

        email_template = EmailTemplate(
            logo_url=LOGO_URL,
            header_link=BASE_URL,
            header_text="Вы активировали подписку!!!",
            description=f"Уровень подписки: {level}.",
            recipient_name=email,
            body_text=f"Спасибо за оплату подписки уровня {level} на ChatGP по цене {round(price / 1_000_000_000, 2)} Ton!"
                      "Срок подписки - 30 дней."
                      "Желаем вам продуктивной работы и приятного времяпрепровождения с ChatGP."
                      "Если вы оплатили подписку по ошибке, вы можете написать в поддержку для отмены и возврата средств.",
            action_label="Личный кабинет",
            action_url=f"{BASE_URL}/dash",
            footer_text="Если вы считаете, что письмо пришло вам по ошибке — просто проигнорируйте его."
        )
        html = email_template.render()
        background_tasks.add_task(send_email, user, "Выбор подписки", html)

        return templates.TemplateResponse("feedback.html", {
            "request": request,
            "message": f"Подписка '{PRETTY_NAMES[level]}' активирована!",
            "status": "success",
            "action": {
                "label": "Начать чат",
                "url": "/",
                "method": "get"
            }

        })

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
        logger.info(
            f"verify_ton_payment - Подписка будет активирована по истечение текущей подписки: {format_datetime_pretty(current_expiry)}, email: {user.get("email")}, level: {level}")

        email_template = EmailTemplate(
            logo_url=LOGO_URL,
            header_link=BASE_URL,
            header_text="Подписка будет позже!!!",
            description=f"Уровень подписки: {level}.",
            recipient_name=email,
            body_text=f"Спасибо за оплату новой подписки уровня {level} на ChatGP по цене {round(price / 1_000_000_000, 2)} Ton!"
                      f"Ваша текущая подписка истекает: {format_datetime_pretty(current_expiry)}."
                      f"Новая подписка вступит в силу сразу по истечение текущей."
                      "Желаем вам продуктивной работы и приятного времяпрепровождения с ChatGP."
                      "Если вы оплатили подписку по ошибке, вы можете написать в поддержку для отмены и возврата средств.",
            action_label="Личный кабинет",
            action_url=f"{BASE_URL}/dash",
            footer_text="Если вы считаете, что письмо пришло вам по ошибке — просто проигнорируйте его."
        )
        html = email_template.render()
        background_tasks.add_task(send_email, user, "Выбор подписки", html)
        return templates.TemplateResponse("feedback.html", {
            "request": request,
            "message": f"Оплата принята! Новый уровень подписки '{PRETTY_NAMES[level]}' будет активирован после окончания текущего периода: {format_datetime_pretty(current_expiry)}.",
            "status": "success",
            "action": {
                "label": "Начать чат",
                "url": "/",
                "method": "get"
            }

        })
    logger.info(
        f"verify_ton_payment - Оплата подписки не подтверждена, email: {user.get("email")}, level: {level}")
    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "message": "Оплата не подтверждена, обычно это занимает не более 15 минут, но иногда может потребоваться до 2 часов. Проверьте email.",
        "status": "warning",
        "action": {
            "label": "Проверить статус",
            "url": "/dash",
            "method": "get"
        }
    })


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
        new_index = LEVELS.index(new_level)
        new_price = PRICES[new_index]
        transactions = await get_ton_transaction(new_price)
        data = transactions.get("transactions", [])
        if transactions:
            for tx in data:
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
                "attempts": 0,
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
    logger.info(f"renew_subscriptions - все отложенные подписки обновлены, на: {datetime.now(timezone.utc)}")
    return {"message": "Все отложенные подписки обновлены!"}



async def notify_expiring_subscriptions(background_tasks: BackgroundTasks = None):
    now = datetime.now(timezone.utc)
    targets = []

    for days_before in (3, 1):
        target_date = now + timedelta(days=days_before)
        users = await users_collection.find({
            "subscription.expires_at": {
                "$gte": target_date.replace(hour=0, minute=0, second=0),
                "$lte": target_date.replace(hour=23, minute=59, second=59)
            },
            "$or": [
                {"subscription.notified_days_before": {"$ne": days_before}},
                {"subscription.notified_days_before": {"$exists": False}}
            ]
        }).to_list(None)

        for user in users:
            email = user["email"]
            level = user["subscription"]["level"]
            expires_at = user["subscription"]["expires_at"]
            username = user.get("name") or email.split("@")[0]

            subject = f"Ваша подписка истекает через {days_before} день(дня)"
            desc = f"Уровень подписки: {level}. Истекает: {format_datetime_pretty(expires_at)}"

            body_text = (
                f"Ваша подписка уровня {level} истекает {format_datetime_pretty(expires_at)}.\n"
                f"Продлите её, чтобы не потерять доступ к функциям ChatGP.\n"
                "Если вы не планируете продлевать, доступ будет ограничен автоматически."
            )

            email_template = EmailTemplate(
                logo_url=LOGO_URL,
                header_link=BASE_URL,
                header_text="Подписка скоро истекает",
                description=desc,
                recipient_name=username,
                body_text=body_text,
                action_label="Продлить подписку",
                action_url=f"{BASE_URL}/subscribe",
                footer_text="Если вы считаете, что письмо пришло по ошибке — просто проигнорируйте его."
            )
            html = email_template.render()

            # Отправка письма в фоне
            background_tasks.add_task(send_email, user, subject, html)

            targets.append(UpdateOne(
                {"email": email},
                {
                    "$addToSet": {"subscription.notified_days_before": days_before},
                    "$set": {"subscription.last_notified": now}
                }
            ))

    if targets:
        await users_collection.bulk_write(targets)
        logger.info(f"notify_expiring_subscriptions - отправлено уведомлений: {len(targets)}")
    else:
        logger.info("notify_expiring_subscriptions - уведомлений не требовалось")

    return {"message": "Уведомления о подписках обработаны"}
