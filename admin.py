from fastapi import APIRouter, Request, Response, Depends, HTTPException, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pymongo import UpdateOne
import logging
from pydantic import BaseModel

from models.chats import chats_collection
from models.user_data import users_data_collection
from models.users import users_collection
from models.tokens import tokens_collection
from models.blog import blog_posts_collection
from datetime import datetime, timezone, timedelta
from auth import get_user, verify_csrf_token as verify_csrf
from settings import *
from fernet_utils import encrypt_email, decrypt_email
from mail import send_email_internal

admin_router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger("app_logger")

templates = Jinja2Templates(directory="templates")

# Настроить поведение сериализации JSON в фильтре tojson
templates.env.policies['json.dumps_kwargs'] = {"default": str}

DEFAULT_CHAT_BODY = [
    {"prompt": "Добро пожаловать", "body": "ваши предыдущие чаты были удалены по вашему запросу или за несоблюдение правил сервиса."}
]

# Создаём chat_id и chat_time на основе текущего времени
DEFAULT_CHAT_ID = "default_id_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

# Дефолтный чат
DEFAULT_CHAT = {
    "chat_id": DEFAULT_CHAT_ID,
    "chat_time": datetime.now(timezone.utc).isoformat(),
    "chat_summary": "Это пример чата",
}

class UserDataRequest(BaseModel):
    user_id: str
    csrf_token: str
    data: dict | None = None

class PostDataRequest(BaseModel):
    slug: str
    csrf_token: str



async  def get_user_updates(email):
    if not email:
        return {}
    user = await users_collection.find_one({"email": email})
    if not user:
        return {}
    cursor = await users_data_collection.aggregate([
        {"$match": {"email": email}},
        {"$project": {
            "_id": 1,
            "email": 1,
            "status": 1,
            "mode": 1,
            "chats": {
                "$map": {
                    "input": "$chats",
                    "as": "chat",
                    "in": {
                        "chat_id": "$$chat.chat_id",
                        "chat_time": "$$chat.chat_time",
                        "chat_summary": "$$chat.chat_summary",
                        "chat_body": {"$size": {"$ifNull": ["$$chat.chat_body", []]}}
                    }
                }
            }
        }}
    ])
    user_data_list = await cursor.to_list(length=1)
    user_data = user_data_list[0] if user_data_list else None

    if not user_data:
        return {}
    logger.info(
        f"admin  - данные пользователя: {email} - обновлены\n")
    return {"user": user, "user_data": user_data}




@admin_router.api_route("/admin-dashboard", methods=["GET", "POST"], response_class=HTMLResponse)
async def admin_dashboard(request: Request, user: dict = Depends(get_user)):
   csrf_token = request.cookies.get("csrf_token")

   if not user or user.get("email") != ADMIN:
      logger.info(f"Несанкционированная попытка входа: {user.get('email') if user else 'аноним'}")
      raise HTTPException(status_code=403, detail="Access_denied")

   if not csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
      logger.info(f"Неверный или отсутствующий CSRF токен от {user['email']}")
      return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
         "message": {"status": "fail", "detail": "CSRF токен недействителен"}
      })

   context = {"request": request, "csrf_token": csrf_token}

   if request.method == "POST":
      form = await request.form()
      email = form.get("user_id")
      if email:
         current_user = await users_collection.find_one({"email": email})
         if current_user:
            context["user_info"] = await get_user_updates(email)
            context["message"] = {"status": "success", "detail": f"Найден пользователь {email}"}
         else:
            context["message"] = {"status": "fail", "detail": f"Пользователь {email} не найден"}
   logger.info(
       f"admin  - вход в админ панель\n")
   return templates.TemplateResponse("admin-dashboard.html", context)


@admin_router.post("/get-user-info")
async def get_user_info(
    request: Request,
    user_id: str = Form(...),
    csrf_token: str = Form(...)):
    email = user_id
    cookie_csrf_token = request.cookies.get("csrf_token")
    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    user_info = await get_user_updates(email)
    logger.info(
        f"admin  - Запрос данных пользователя: {email}\n")
    return templates.TemplateResponse("admin-dashboard.html", {
       "request": request,
       "user_info": user_info,
       "csrf_token": csrf_token,
       "message": {"status": "success", "detail": "Информация получена"}
    })


@admin_router.post("/update-user-data")
async def update_user_data(
    request: Request,
    user_id: str = Form(...),
    status: str = Form(...),
    tokens: int = Form(...),
    contact: str = Form(...),
    attempts: int = Form(...),
    csrf_token: str = Form(...)
        ):

    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    edit_user = await users_collection.find_one({"email": user_id})
    updates = []

    if edit_user:
        new_status = status if status else edit_user["status"]
        new_tokens = tokens if tokens else edit_user["tokens"]
        new_contact = contact if contact else edit_user["contact"]
        new_attempts = attempts if attempts else edit_user["attempts"]
        updates.append(UpdateOne(
           {"email": edit_user["email"]},
           {"$set": {
              "status": new_status,
              "tokens": new_tokens,
              "contact": new_contact,
              "attempts": new_attempts,
              "updated_at": datetime.now(timezone.utc)
           }}
        ))

    if updates:
        await users_collection.bulk_write(updates)
        user_info = await get_user_updates(user_id)
        logger.info(
            f"admin  - def update_user_data - информация о пользователе: {user_id} - обновлена\n")
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "user_info": user_info,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail": "Информация обновлена"}
        })
    if contact:
        boosty = encrypt_email(contact)
        await users_collection.update_one(
            {"email": user_id},
            {"$set": {"boosty_code": boosty}
             }
        )
    logger.info(
        f"admin  - def update_user_data - ошибка обновления информации о пользователе: {user_id}\n")
    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Обновление не удалось"}
    })

@admin_router.post("/update-user-subscription")
async def add_user_payment(
    request: Request,
        background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    level: str = Form(...),
    tx_id: str = Form(...),
    amount: int = Form(...),
    sender: str = Form(...),
    csrf_token: str = Form(...)):
    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    edit_user = await users_collection.find_one({"email": user_id})

    if edit_user:
        new_level = level if level else edit_user["level"]
        new_tx_id = tx_id if tx_id else edit_user["tx_id"]
        new_amount = amount if amount else edit_user["amount"]
        new_sender = sender if sender else edit_user["sender"]
        time_now = datetime.now(timezone.utc)
        new_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        await users_collection.update_one({"email": user_id}, {
            "$set": {
                "status": new_level,
                "original_status": new_level,
                "tokens": 0,
                "attempts": 0,
                "updated_at": datetime.now(timezone.utc),
                "subscription.level": new_level,
                "subscription.expires_at": new_expiry,
                "subscription.next_billing_date": new_expiry,
                "subscription.is_active": True,
                "subscription.transaction_id": new_tx_id
            },
            "$push": {
                "subscription.payment_history": {
                    "tx_id": new_tx_id,
                    "amount": new_amount,
                    "source": new_sender,
                    "date": time_now
                }
            }
        })
        user_info = await get_user_updates(user_id)
        await send_email_internal(background_tasks, user_id,
                                  "Подписка ChatGP",
                                  " Поздравляем! Вы теперь подписаны на ChatGP!",
                                  f"Уважаемый{user_id}",
                                  f"Это письмо подтверждает, что вы подписаны на план {new_level} на сайте ChatGP.Ru.\n Вы можете повысить или изменить текущий план в вашем дашборде на ChatGP.Ru.",
                                  "Перейти в дашборд",
                                  f"{BASE_URL}/dash",
                                  "Если это письмо пришло вам по ошибке, проигнорируйте его")
        logger.info(
            f"admin  - def  add_user_payment - подписка пользователя: {user_id} - обновлена\n")
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "user_info": user_info,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail": "Подписка оформлена/обновлена"}
        })
    logger.info(
        f"admin  - def  add_user_payment - ошибка обновления подписки пользователя: {user_id}\n")
    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Обновление не удалось"}
    })


@admin_router.post("/update-boosty-subscription")
async def add_boosty_payment(
    request: Request, background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    boosty_level: str = Form(...),
    boosty_id: str = Form(...),
    boosty_amount: int = Form(...),
    boosty_sender: str = Form(...),
    expire_days: int = Form(...),
    csrf_token: str = Form(...)):

    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })

    boosty_user = await users_collection.find_one({"email": user_id})

    if (not boosty_id or boosty_id != boosty_user["boosty_code"]) and decrypt_email(boosty_id) != user_id:

       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "Индивидуальный бусти код не совпадает или подделан"}
       })


    if boosty_user:
        new_level = boosty_level if boosty_level else "trial"
        new_boosty_id = boosty_id if boosty_id else None
        new_amount = boosty_amount if boosty_amount else 0
        new_sender = boosty_sender if boosty_sender else "boosty"
        time_now = datetime.now(timezone.utc)
        new_expiry = datetime.now(timezone.utc) + timedelta(days=expire_days)
        await users_collection.update_one({"email": user_id}, {
            "$set": {
                "status": new_level,
                "original_status": new_level,
                "tokens": 0,
                "attempts": 0,
                "updated_at": datetime.now(timezone.utc),
                "subscription.level": new_level,
                "subscription.expires_at": new_expiry,
                "subscription.next_billing_date": new_expiry,
                "subscription.is_active": True,
                "subscription.transaction_id": new_boosty_id
            },
            "$push": {
                "subscription.payment_history": {
                    "boosty_id": new_boosty_id,
                    "amount": new_amount,
                    "source": new_sender,
                    "date": time_now
                }
            }
        })
        user_info = await get_user_updates(user_id)
        await send_email_internal(background_tasks, user_id,
                                  "Подписка ChatGP",
                                  "Поздравляем! Вы подписаны на ChatGP через Boosty!",
                                  f"Уважаемый{user_id}",
                                  f"Это письмо подтверждает, что вы подписались на план {new_level} на сайте ChatGP.Ru.\n Вы можете повысить или изменить текущий план в вашем дашборде на ChatGP.Ru. Так же вы можете отменить вашу подписку на boosty.to",
                                  "Перейти в дашборд",
        f"{BASE_URL}/dash",
              "Если это письмо пришло вам по ошибке, проигнорируйте его"                    )
        logger.info(
            f"admin  - def  add_boosty_payment - подписка бусти пользователя: {user_id} - обновлена\n")
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "user_info": user_info,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail": "Бусти информация обновлена"}
        })
    logger.info(
        f"admin  - def  add_boosty_payment - ошибка бусти подписки пользователя: {user_id}\n")
    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Бусти обновление не удалось"}
    })



@admin_router.post("/send-angry-email")
async def send_angry_email(
    request: Request,
        background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    subject: str = Form(...),
    descr: str = Form(...),
    name_to: str = Form(...),
    body: str = Form(...),
    csrf_token: str = Form(...)):

    cookie_csrf_token = request.cookies.get("csrf_token")


    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    mail_to_user = await users_collection.find_one({"email": user_id})

    if mail_to_user:
        user_info = await get_user_updates(user_id)
        await send_email_internal(background_tasks, user_id,
                                  subject,
                                  descr,
                                  name_to,
                                  body,
                                  "Ответить на сайте",
                                  f"{BASE_URL}/conact",
                                  "Если это письмо пришло вам по ошибке, проигнорируйте его")
        logger.info(
            f"admin  - def  send_angry_email - Письмо от администратора пользователю: {user_id} - отправлено\n")
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "user_info": user_info,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail":  f"Письмо для: {user_id} - отправлено"}
        })
    logger.info(
        f"admin  - def  send_angry_email - ошибка отправки письма пользователю: {user_id}\n")
    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Отправка письма не удалась"}
    })


@admin_router.post("/drop-post")
async def drop_post(
    request: Request,
    slug: str = Form(...),
    csrf_token: str = Form(...)):

    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })

    existing = await blog_posts_collection.find_one({"slug": slug})
    if existing:
        post_id = existing.get("_id")
        await blog_posts_collection.delete_one({"_id": post_id})
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail": "Пост успешно удалён, убедитесь, что пост отсутствует по слагу"},
            "slug": slug
        })

    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Не удалось найти и удалить пост, проверьте слаг ниже"},
        "slug": slug
            })



@admin_router.post("/drop-user")
async def drop_user(
    request: Request,
    user_id: str = Form(...),
    user_id_repeat: str = Form(...),
    psw: str = Form(...),
    csrf_token: str = Form(...)):
    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "CSRF токен недействителен"},
         "user_delete_message": {"status": "fail", "detail": "CSRF токен недействителен"}
        })
    delete_user = await users_collection.find_one({"email": user_id})

    if delete_user:
       if user_id != user_id_repeat:
           return templates.TemplateResponse("admin-dashboard.html", {
               "request": request,
               "csrf_token": csrf_token,
               "message": {"status": "fail", "detail": "Повторный ввод email не совпадает, проверьте ввод"},
               "user_delete_message": {"status": "fail", "detail": "Повторный ввод email не совпадает, проверьте ввод"}
           })
       if not psw or psw != ADMIN_PIN:
           return templates.TemplateResponse("admin-dashboard.html", {
               "request": request,
               "csrf_token": csrf_token,
               "message": {"status": "fail", "detail": "Неверный пин-код"},
               "user_delete_message": {"status": "fail", "detail": "Неверный пин-код"}
           })
       await users_collection.delete_one({"email": user_id})
       await tokens_collection.delete_one({"email": user_id})
       logger.info(
           f"admin  - def  drop_user - пользователь: {user_id} - удалён\n")
       return templates.TemplateResponse("admin-dashboard.html", {
       "request": request,
       "csrf_token": csrf_token,
       "message": {"status": "success", "detail": "Пользователь удалён"},
       "user_delete_message": {"status": "success", "detail": "Пользователь удалён"}
   })
    logger.info(
        f"admin  - def  drop_user - Ошибка! - пользователь: {user_id} - не найден и удаление не удалось\n")
    return templates.TemplateResponse("admin-dashboard.html", {
       "request": request,
       "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Пользователь не найден или не все поля заполнены верно"},
       "user_delete_message": {"status": "fail", "detail": "Пользователь не найден или не все поля заполнены верно"}
   })

@admin_router.post("/drop-user-collections")
async def drop_user_collections(
    request: Request,
    user_id: str = Form(...),
    data_user_id_repeat: str = Form(...),
    data_psw: str = Form(...),
    csrf_token: str = Form(...)):

    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
           "message": {"status": "fail", "detail": "CSRF токен недействителен"},
         "data_delete_message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    current_user_data = await users_data_collection.find_one({"email": user_id})

    if current_user_data:
       if user_id != data_user_id_repeat:
           return templates.TemplateResponse("admin-dashboard.html", {
               "request": request,
               "csrf_token": csrf_token,
               "message": {"status": "fail", "detail": "Повторный ввод email не совпадает, проверьте ввод"},
               "data_delete_message": {"status": "fail", "detail": "Повторный ввод email не совпадает, проверьте ввод"}
           })
       if not data_psw or data_psw != ADMIN_PIN:
           return templates.TemplateResponse("admin-dashboard.html", {
               "request": request,
               "csrf_token": csrf_token,
               "message": {"status": "fail", "detail": "Неверный пин-код"},
               "data_delete_message": {"status": "fail", "detail": "Неверный пин-код"}
           })
       await users_data_collection.update_one(
           {"email": user_id},
           {"$set": {"chats": [DEFAULT_CHAT]}}
       )
       default_chat = {
           "chat_id": DEFAULT_CHAT_ID,
           "chat_time": datetime.now(timezone.utc).isoformat(),
           "chat_summary": "Это пример чата",
           "chat_body": DEFAULT_CHAT_BODY,
           "user_email": user_id
       }
       # Сначала удалим все чаты пользователя
       await chats_collection.delete_many({"user_email": user_id})

       # Затем добавим один дефолтный чат
       await chats_collection.insert_one(default_chat)
       logger.info(
           f"admin  - def  drop_user_collection - чаты пользователя: {user_id} - удалёны\n")
       return templates.TemplateResponse("admin-dashboard.html", {
           "request": request,
           "csrf_token": csrf_token,
           "message": {"status": "success", "detail": "Данные пользователя удалены"},
           "data_delete_message": {"status": "success", "detail": "Данные пользователя удалены"}
       })
    logger.info(
        f"admin  - def  drop_user_collection - Ошибка удаления чатов пользователя: {user_id} - пользователь не найден\n")
    return templates.TemplateResponse("admin-dashboard.html", {
       "request": request,
       "csrf_token": csrf_token,
       "message": {"status": "fail", "detail": "Пользователь не найден или не все поля заполнены верно"},
        "data_delete_message": {"status": "fail", "detail": "Пользователь не найден или не все поля заполнены верно"}
   })



@admin_router.post("/assign-user-collections")
async def assign_user_collections(
    request: Request,
    user_id: str = Form(...),
    csrf_token: str = Form(...)):

    cookie_csrf_token = request.cookies.get("csrf_token")

    if not cookie_csrf_token or cookie_csrf_token != csrf_token or not verify_csrf(csrf_token, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
         "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    current_user = await users_collection.find_one({"email": user_id})
    if current_user:
      pass


@admin_router.post("/add-admin")
async def add_admin(request_data: UserDataRequest, response: Response):
    pass


@admin_router.post("/update-admin-password")
async def update_admin_password(request_data: UserDataRequest, response: Response):
    pass
