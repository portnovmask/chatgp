from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
import logging
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import uuid
import httpx
import re
from models.users import users_collection
from datetime import datetime, timedelta, timezone
import random
from auth import get_user
import locale
from settings import TON_WALLET, LEVELS, PRETTY_NAMES, PRICES, LOGO_URL, BASE_URL
from mail import EmailTemplate, send_email, generate_confirmation_token
router = APIRouter()
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


# def get_ton_transaction(min_amount_ton: float = 1.0):
#     url = f"https://tonapi.io/v2/accounts/{TON_WALLET}/transactions"
#     response = requests.get(url)
#
#     if response.status_code != 200:
#         logger.info(f"get_ton_transaction - Не удалось подключиться к tonapi.io, ошибка: {response.status_code}")
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
#             logger.info(f"get_ton_transaction - Не удалось проверить транзакцию")
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
async def payment_page(request: Request, background_tasks: BackgroundTasks, payment_id: str, level: str, user: dict = Depends(get_user)):
    if not user:
        return RedirectResponse(url="/")
    email = user.get("email")

    price = PRICES[LEVELS.index(level)]
    payment = generate_payment_link(email, level, price, payment_id)
    qr = generate_qr_base64(payment["url"])

    email_template = EmailTemplate(
        logo_url=LOGO_URL,
        header_link=BASE_URL,
        header_text="Вы купили подписку!",
        description="Это письмо содержит важную информацию.",
        recipient_name=email,
        body_text="Спасибо за выбор подписки на ChatGP. "
                  "Если вы еще не оплатили по ссылке или qr коду на сайте вы можете провести оплату по ссылке ниже с ценой подписки."
                  "Для оплаты по ссылке убедитесь, что у вас есть аккаунт в",
        action_label=price,
        action_url=payment,
        footer_text="Если вы считаете, что письмо пришло вам по ошибке — просто проигнорируйте его."
    )
    html = email_template.render()
    background_tasks.add_task(send_email, email, "Подтверждение регистрации", html)

    return templates.TemplateResponse("payment.html", {
        "request": request,
        "payment_url": payment["url"],
        "qr_base64": qr,
        "level": level,
        "payment_id": payment_id,
        "pretty_name": PRETTY_NAMES[level]
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
async def verify_ton_payment(request: Request, level: str, user: dict = Depends(get_user)):
    if not user:
        return RedirectResponse(url="/")
    if level not in LEVELS:
        logger.info(f"verify_ton_payment - Некорректный уровень подписки, email: {user.get("email")}, level: {level}")
        raise HTTPException(status_code=400, detail="Некорректный уровень подписки")

    email = user["email"]
    current_status = user.get("status", "trial")
    current_expiry = user.get("subscription", {}).get("expires_at")
    current_index = LEVELS.index(current_status)
    new_index = LEVELS.index(level)

    if new_index == current_index:
        return {"message": "Вы уже на этом уровне подписки!", "status": "info"}

    price = PRICES[new_index]
    transactions = get_ton_transactions(price).get("transactions", [])

    if not transactions:
        logger.info(
            f"verify_ton_payment - Платеж не найден или не подтверждён, email: {user.get("email")}, level: {level}")
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
    new_expiry = now + timedelta(days=7)

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



# # Отправка почты
#
# # Шаблон блоков универсального html письма
# class EmailTemplate:
#     def __init__(self, **kwargs):
#         self.data = {
#             "logo_url": kwargs.get("logo_url"),
#             "header_link": kwargs.get("header_link"),
#             "header_text": kwargs.get("header_text"),
#             "description": kwargs.get("description"),
#             "recipient_name": kwargs.get("recipient_name"),
#             "body_text": kwargs.get("body_text"),
#             "action_label": kwargs.get("action_label"),
#             "action_url": kwargs.get("action_url"),
#             "footer_text": kwargs.get("footer_text"),
#             "date": kwargs.get("date") or datetime.now(timezone.utc).strftime("%B %d, %Y")
#         }
#
#     def render(self) -> str:
#         template = templates.get_template("email_template.html")
#         return template.render(**self.data)
#
#
#
# # SMTP клиент
# async def send_email(to_email: str, subject: str, html_content: str):
#     message = EmailMessage()
#     message["From"] = "noreply@example.com"
#     message["To"] = to_email
#     message["Subject"] = subject
#     message.set_content("HTML only email", subtype="plain")
#     message.add_alternative(html_content, subtype="html")
#
#     # await aiosmtplib.send(
#     #     message,
#     #     hostname="smtp.example.com",
#     #     port=587,
#     #     start_tls=True,
#     #     username="your_username",
#     #     password="your_password",
#     # )
#
#     await aiosmtplib.send(
#         message,
#         hostname="localhost",
#         port=1025,  # порт MailHog
#     )
#
#
# # Универсальный маршрут для отправки писем
# @router.post("/send-email/")
# async def send_email_route(background_tasks: BackgroundTasks):
#     email = EmailTemplate(
#         logo_url="https://ketome.ru/wp-content/uploads/2025/04/black-white-minimalist-signature-personal-brand-logo.png",
#         header_link="https://example.com",
#         header_text="Добро пожаловать!",
#         description="Это письмо содержит важную информацию.",
#         recipient_name="Иван Иванов",
#         body_text="Спасибо за регистрацию на нашем сервисе. Пожалуйста, подтвердите вашу почту.",
#         action_label="Подтвердить Email",
#         action_url="https://example.com/confirm?token=abc123",
#         footer_text="Если вы не регистрировались — просто проигнорируйте это письмо."
#     )
#
#     html = email.render()
#     background_tasks.add_task(send_email, "ivan@example.com", "Добро пожаловать!", html)
#     return {"message": "Письмо отправлено"}
#
#
#

# Контактная форма

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


# Дефолтный маршрут контактной формы
# @router.get("/contact", response_class=HTMLResponse)
# async def contact_form(request: Request):
#     return templates.TemplateResponse("contact.html", {
#         "request": request,
#         "form_time": datetime.now(timezone.utc).isoformat()
#     })
#
#
# # Маршрут после отправки контактной формы с проверкой каптчи, пустого поля, времени заполнения, длины строки
# @router.post("/contact/submit", response_class=HTMLResponse)
# async def submit_contact_form(
#         request: Request,
#         name: str = Form(...),
#         email: str = Form(...),
#         message: str = Form(...),
#         form_time: str = Form(...),
#         honeypot: str = Form(""),
#         recaptcha_token: str = Form(...),
#         background_tasks: BackgroundTasks = None
# ):
#     error = None
#     success_message = None
#
#     # 🐜 Anti-bot (honeypot, timing)
#     if honeypot:
#         error = "Обнаружен бот."
#     else:
#         try:
#             form_dt = datetime.fromisoformat(form_time)
#             if (datetime.now(timezone.utc) - form_dt).total_seconds() < 5:
#                 error = "Форма отправлена слишком быстро."
#         except Exception:
#             error = "Ошибка времени отправки формы."
#
#     # 📧 Email format
#     if not error and not EMAIL_REGEX.match(email):
#         error = "Некорректный email."
#
#     # ✏️ Message length
#     if not error and len(message.strip()) < 50:
#         error = "Сообщение должно содержать не менее 50 символов."
#
#     # 🔐 reCAPTCHA
#     if not error:
#         async with httpx.AsyncClient() as client:
#             r = await client.post(
#                 "https://www.google.com/recaptcha/api/siteverify",
#                 data={"secret": RECAPTCHA_SECRET, "response": recaptcha_token}
#             )
#             result = r.json()
#             if not result.get("success") or result.get("score", 0) < 0.5:
#                 error = "Проверка reCAPTCHA не пройдена."
#
#     if not error:
#         email_template = EmailTemplate(
#             logo_url="https://ketome.ru/wp-content/uploads/2025/04/black-white-minimalist-signature-personal-brand-logo.png",
#             header_link="https://example.com",
#             header_text=f"Новое сообщение от {name}",
#             description=message,
#             recipient_name="Администратор",
#             body_text=f"Письмо от {name} ({email}):\n\n{message}",
#             action_label="Ответить",
#             action_url=f"mailto:{email}",
#             footer_text="Контактная форма сайта"
#         )
#         html = email_template.render()
#         background_tasks.add_task(send_email, "admin@example.com", f"Новое сообщение от {name}", html)
#         success_message = "Сообщение отправлено. Спасибо!"
#         # очищаем поля формы
#         name = ""
#         email = ""
#         message = ""
#
#     return templates.TemplateResponse("contact.html", {
#         "request": request,
#         "form_time": datetime.now(timezone.utc).isoformat(),
#         "message": success_message,
#         "error": error,
#         "name": name,
#         "email": email,
#         "message_text": message
#     })
#
#
#
# # Подтверждение email
#
# @router.get("/confirm-notice", response_class=HTMLResponse)
# async def confirm_notice(request: Request):
#     return templates.TemplateResponse("confirm_notice.html", {"request": request})
#
# @router.get("/confirm-email")
# async def confirm_email(token: str):
#     email = confirm_token(token)
#     if not email:
#         return HTMLResponse("<h2>Срок действия ссылки истёк или она недействительна.</h2>", status_code=400)
#
#     result = await users_collection.update_one(
#         {"email": email, "contact": "not_confirmed"},
#         {"$set": {"contact": email}}
#     )
#
#     if result.modified_count == 1:
#         return HTMLResponse("<h2>Email подтверждён! Теперь вы можете войти в систему.</h2>")
#     else:
#         return HTMLResponse("<h2>Email уже был подтверждён или не найден.</h2>")
