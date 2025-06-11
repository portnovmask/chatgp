from fastapi import APIRouter, Request, Response, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pymongo import UpdateOne
import logging
from pydantic import BaseModel
from models.user_data import users_data_collection
from models.users import users_collection
from models.tokens import tokens_collection
from models.blog import blog_posts_collection
from datetime import datetime, timezone, timedelta
from auth import get_user, verify_csrf_token
from settings import *
import json
admin_router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger("app_logger")

templates = Jinja2Templates(directory="templates")

# Настроить поведение сериализации JSON в фильтре tojson
templates.env.policies['json.dumps_kwargs'] = {"default": str}

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
    return {"user": user, "user_data": user_data}




@admin_router.api_route("/admin-dashboard", methods=["GET", "POST"], response_class=HTMLResponse)
async def admin_dashboard(request: Request, response: Response, user: dict = Depends(get_user)):
   csrf_token = request.cookies.get("csrf_token")

   if not user or user.get("email") != ADMIN:
      logger.info(f"Несанкционированная попытка входа: {user.get('email') if user else 'аноним'}")
      raise HTTPException(status_code=401, detail="Not authorized")

   if not csrf_token or not verify_csrf_token(csrf_token, ADMIN, CSRF_SECRET_KEY):
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

   return templates.TemplateResponse("admin-dashboard.html", context)


@admin_router.post("/get-user-info")
async def get_user_info(request_data: UserDataRequest, request=Request):
    email = request_data.user_id
    csrf_token = request.get("csrf_token")
    form_csrf = request_data.csrf_token
    if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    user_info = await get_user_updates(email)
    return templates.TemplateResponse("admin-dashboard.html", {
       "request": request,
       "user_info": user_info,
       "csrf_token": csrf_token,
       "message": {"status": "success", "detail": "Информация получена"}
    })


@admin_router.post("/update-user-data")
async def update_user_data(request_data: UserDataRequest, request=Request):
    email = request_data.user_id
    csrf_token = request.get("csrf_token")
    form_csrf = request_data.csrf_token
    if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    current_user = await users_collection.find_one({"email": email})
    updates = []
    data = request_data.data

    if current_user and data:
        status = data.get("status") if data.get("status") else current_user["status"]
        tokens = data.get("tokens") if data.get("tokens") else current_user["tokens"]
        contact = data.get("contact") if data.get("contact") else current_user["contact"]
        attempts = data.get("attempts") if data.get("attempts") else current_user["attempts"]
        updates.append(UpdateOne(
           {"email": current_user["email"]},
           {"$set": {
              "status": status,
              "tokens": tokens,
              "contact": contact,
              "attempts": attempts,
              "updated_at": datetime.now(timezone.utc)
           }}
        ))

    if updates:
        await users_collection.bulk_write(updates)
        user_info = await get_user_updates(email)
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "user_info": user_info,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail": "Информация обновлена"}
        })
    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Обновление не удалось"}
    })

@admin_router.post("/update-user-subscription")
async def add_user_payment(request_data: UserDataRequest, request: Request):
    email = request_data.user_id
    csrf_token = request.get("csrf_token")
    form_csrf = request_data.csrf_token
    if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })
    current_user = await users_collection.find_one({"email": email})
    data = request_data.data
    if current_user and data:
        level = data.get("level") if data.get("level") else current_user["level"]
        tx_id = data.get("tx_id") if data.get("tx_id") else current_user["tx_id"]
        amount = data.get("amount") if data.get("amount") else current_user["amount"]
        sender = data.get("sender") if data.get("sender") else current_user["sender"]
        time_now = datetime.now(timezone.utc)
        new_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        await users_collection.update_one({"email": email}, {
            "$set": {
                "status": level,
                "original_status": level,
                "tokens": 0,
                "attempts": 0,
                "updated_at": datetime.now(timezone.utc),
                "subscription.level": level,
                "subscription.expires_at": new_expiry,
                "subscription.next_billing_date": new_expiry,
                "subscription.is_active": True,
                "subscription.transaction_id": tx_id
            },
            "$push": {
                "subscription.payment_history": {
                    "tx_id": tx_id,
                    "amount": amount,
                    "source": sender,
                    "date": time_now
                }
            }
        })
        user_info = await get_user_updates(email)
        return templates.TemplateResponse("admin-dashboard.html", {
            "request": request,
            "user_info": user_info,
            "csrf_token": csrf_token,
            "message": {"status": "success", "detail": "Информация обновлена"}
        })
    return templates.TemplateResponse("admin-dashboard.html", {
        "request": request,
        "csrf_token": csrf_token,
        "message": {"status": "fail", "detail": "Обновление не удалось"}
    })


@admin_router.post("/assign-user-collections")
async def assign_user_collections(request_data: UserDataRequest, request: Request):
   email = request_data.user_id
   csrf_token = request.get("csrf_token")
   form_csrf = request_data.csrf_token
   if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
      return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
         "message": {"status": "fail", "detail": "CSRF токен недействителен"}
      })
   current_user = await users_collection.find_one({"email": email})
   data = request_data.data
   if current_user and data:
      pass


@admin_router.post("/drop-user")
async def drop_user(request_data: UserDataRequest, request: Request):
   email = request_data.user_id
   csrf_token = request.get("csrf_token")
   form_csrf = request_data.csrf_token
   if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
      return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
         "message": {"status": "fail", "detail": "CSRF токен недействителен"}
      })
   current_user = await users_collection.find_one({"email": email})
   data = request_data.data
   if current_user and data:
      pass


@admin_router.post("/drop-user-collections")
async def drop_user_collections(request_data: UserDataRequest, request: Request):
   email = request_data.user_id
   csrf_token = request.get("csrf_token")
   form_csrf = request_data.csrf_token
   if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
      return templates.TemplateResponse("admin-dashboard.html", {
         "request": request,
         "csrf_token": csrf_token,
         "message": {"status": "fail", "detail": "CSRF токен недействителен"}
      })
   current_user = await users_collection.find_one({"email": email})
   data = request_data.data
   if current_user and data:
      pass


@admin_router.post("/drop-post")
async def drop_post(request_data: PostDataRequest, request: Request):
    post_slug = request_data.slug
    csrf_token = request.get("csrf_token")
    form_csrf = request_data.csrf_token
    if not csrf_token or csrf_token != form_csrf or not verify_csrf_token(form_csrf, ADMIN, CSRF_SECRET_KEY):
       return templates.TemplateResponse("admin-dashboard.html", {
          "request": request,
          "csrf_token": csrf_token,
          "message": {"status": "fail", "detail": "CSRF токен недействителен"}
       })

    existing = await blog_posts_collection.find_one({"slug": post_slug})
    if existing:
        post_id = existing.get("_id")
        await blog_posts_collection.delete_one({"_id": post_id})
        return {"slug": post_slug, "status": "dropped"}

    return {"slug": post_slug, "status": "fail"}


@admin_router.post("/add-admin")
async def add_admin(request_data: UserDataRequest, response: Response):
    pass


@admin_router.post("/update-admin-password")
async def update_admin_password(request_data: UserDataRequest, response: Response):
    pass
