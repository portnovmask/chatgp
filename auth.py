import logging
import uuid
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from starlette.responses import HTMLResponse

from models.users import users_collection
from models.tokens import tokens_collection
from models.user_data import users_data_collection
from settings import *

router = APIRouter()
logger = logging.getLogger("app_logger")

SECRET_KEY = APP_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

# Настройка для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



# Дефолтный чат

# Дефолтные сообщения для chat_body
DEFAULT_CHAT_BODY = [
    {"prompt": "Добро пожаловать", "body": "У вас пока нет чатов, но вы можете создать новый автоматически."}
]


# Дефолтный чат
DEFAULT_CHAT = {
    "chat_id": "default_id",
    "chat_time": datetime.now(timezone.utc).isoformat(),
    "chat_summary": "Здесь будут ваши чаты",
    "chat_body": DEFAULT_CHAT_BODY  # Добавляем список сообщений в chat_body
}


# Дефолтный режим
MODE = {"current_mode": "basic", "current_chat": None}



def create_access_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": email,
        "exp": expire,
        "iat": now,
        "jti": jti
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), expire, jti


def create_refresh_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": email,
        "exp": expire,
        "iat": now,
        "jti": jti
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), expire, jti


from bson import ObjectId

def serialize(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


async def get_user(request: Request):
    """Проверяет access-токен в куках и валидирует его"""
    token = request.cookies.get("access_token")
    logger.info(f"def get_user - Токен в куках: {token}")
    if not token:
        raise HTTPException(status_code=401, detail="Access token is missing")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"def get_user - Payload токена: {payload}")
        email = payload.get("sub")
        if not email:
            logger.info("def get_user - Нет email в payload")
            raise HTTPException(status_code=401, detail="Token payload invalid")

        token_in_db = await tokens_collection.find_one({"email": email, "access_token": token})
        if not token_in_db:
            logger.info(f"def get_user - Токен не найден в БД: {token}")
            raise HTTPException(status_code=401, detail="Access token not found in DB")

        user = await users_collection.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        logger.info(f"def get_user - Пользователь {user['email']} авторизован: {token}")

        return {
            "email": user["email"],
            "id": str(user["_id"]),
            "registered_at": user["registered_at"],
            "contact": user.get("contact"),
            "status": str(user["status"]),
            "tokens": int(user["tokens"]),
            "attempts": int(user.get("attempts", 0)),
            "auth_provider": str(user.get("auth_provider", "email")),
            "oauth_id": str(user.get("oauth_id", "email")),
            "original_status": str(user.get("original_status", user["status"])),
            "trial_expires_at": user.get("trial_expires_at"),
            "trial_expires_blocked": user.get("trial_expires_blocked"),  # если используешь
            "subscription": user.get("subscription", {})
        }

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid access token")


from typing import Optional

async def get_user_optional(request: Request) -> Optional[dict]:
    try:
        return await get_user(request)
    except HTTPException:
        return None

@router.get("/me")
async def get_current_user(request: Request):
    """Получение данных о текущем пользователе по access-токену"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        logger.info(f"/me  - def get_current_user - access token не найден в куках\n")
        raise HTTPException(status_code=401, detail="Требуется аутентификация куки")
        #return RedirectResponse(url="/logout", status_code=303)

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        # Получаем пользователя из БД
        user = await users_collection.find_one({"email": email}, {"_id": 0, "password": 0})
        if not user:
            logger.info(f"/me  - def get_current_user - пользователь не найден в бд")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
            #return RedirectResponse(url="/logout", status_code=303)
            #return None
        logger.info(f"/me  - def get_current_user - email пользователя: {user['email']} - Пользователь найден\n")
        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен необходима авторизация")
        #return RedirectResponse(url="/logout", status_code=303)

@router.post("/refresh")
async def refresh_token(request: Request):
    """Обновление access-токена по refresh-токену"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        logger.info(f"/refresh  - def refresh_token - refresh token не найден в куках\n")
        raise HTTPException(status_code=401, detail="Требуется аутентификация рефреш")

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        jti = payload.get("jti")

        # Проверяем, есть ли refresh-токен в БД
        token_in_db = await tokens_collection.find_one({"email": email,  "refresh_jti": jti})
        if not token_in_db:
            logger.info(f"/refresh  - def refresh_token - refresh token не найден в бд\n")
            raise HTTPException(status_code=401, detail="Недействительный токен  - время истекло")

        new_access_token, _, new_access_jti = create_access_token(email)
        new_refresh_token, _, new_refresh_jti = create_refresh_token(email)
        # Обновляем в БД по refresh_jti
        await tokens_collection.update_one(
            {"email": email, "refresh_jti": jti},
            {"$set": {
                "access_token": new_access_token,
                "access_jti": new_access_jti,
                "refresh_token": new_refresh_token,
                "refresh_jti": new_refresh_jti,
            }},
        )

        # Устанавливаем куки
        response = JSONResponse({"message": "Токены обновлены"})
        response.set_cookie("access_token", new_access_token, httponly=True)
        response.set_cookie("refresh_token", new_refresh_token, httponly=True)
        return response

    except JWTError:
        logger.info(f"/refresh  - def refresh_token - Недействительный токен устарел или удалены куки\n")
        raise HTTPException(status_code=401, detail="Недействительный токен устарел или удалены куки")

@router.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    """Регистрация нового пользователя"""
    register_time = datetime.now(timezone.utc)
    status = "trial"
    tokens = 0
    existing_user = await users_collection.find_one({"email": email})
    if existing_user:
        logger.info(f"/register  - def register - попытка добавить существующего пользователя\n")
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = pwd_context.hash(password)
    new_user = {"email": email,
                "contact": email,
                "password": hashed_password,
                "registered_at": register_time,
                "auth_provider": "local",
                "oauth_id": None,
                "status": status,
                "tokens": tokens,
                "original_status": status,
                "trial_expires_at": None}
    result = await users_collection.insert_one(new_user)
    logger.info(f"/register  - def register - пользователь: {new_user['email']} создан\n")
    user_id = str(result.inserted_id)  #  Теперь _id точно есть

    # Данные для нового пользователя
    user_data = {
        "user_id": user_id,
        "email": email,
        "status": status,
        "mode": [MODE],
        "chats": [DEFAULT_CHAT]  # Добавляем дефолтный чат в массив chats
    }
    await users_data_collection.insert_one(user_data)
    logger.info(f"/register  - def register - создан чат по умолчанию для пользователя: {new_user['email']}\n")
    access_token, access_expires, access_jti = create_access_token(email)
    refresh_token, refresh_expires, refresh_jti = create_refresh_token(email)
    await tokens_collection.insert_one({
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "access_jti": access_jti,
        "refresh_token": refresh_token,
        "refresh_jti": refresh_jti,
        "created_at": datetime.now(timezone.utc)
    })
    logger.info(f"/register  - def register - пользователь успешно зарегистрирован, токены добавлены в бд\n")
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    return response


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Авторизация с проверкой пароля"""
    user = await users_collection.find_one({"email": email})
    if not user or not pwd_context.verify(password, user["password"]):
        logger.info(f"/login  - def login - Для ввода: {email} - пароль или email не верны\n")
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    access_token, access_expires, access_jti = create_access_token(str(user["email"]))
    refresh_token, refresh_expires, refresh_jti = create_refresh_token(str(user["email"]))

    # Удаляем старые токены пользователя
    await tokens_collection.delete_many({"email": str(user["email"])})

    # Записываем новые токены в БД
    await tokens_collection.insert_one({
        "user_id": str(user["_id"]),
        "email": email,
        "access_token": access_token,
        "access_jti": access_jti,
        "refresh_token": refresh_token,
        "refresh_jti": refresh_jti,
        "created_at": datetime.now(timezone.utc)
        })
    logger.info(f"/login  - def login - Для пользователя: {email} - созданы новые токены\n")

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(f"/login  - def login - Для пользователя: {email} - в куки добавлены новые токены\n")
    return response

@router.post("/add_email")
async def add_email(request: Request, email: str = Form(...), user: dict = Depends(get_user)):
    """Добавление контактного email"""
    if user:
        user_email = user["email"]
        await users_collection.update_one(
            {"email": user_email},
            {"$set": {"contact": email}},
        )
        logger.info(f"/add_email  - def add email - пользователь: {user_email}добавил email для связи: {email}\n")
        return {"message": "email для связи успешно добавлен", "status": "success"}
    else:
        logger.info(f"/add_email  - def add email - пользователь не авторизован, не удалось отправить email для связи: {email}\n")
        return {"message": "пользователь не авторизован", "status": "error"}
@router.get("/logout")
async def logout(request: Request):
    """Выход и удаление токенов из БД"""
    refresh_token = request.cookies.get("refresh_token")
    response = RedirectResponse(url="/authorize")

    if not refresh_token:
        logger.info(f"/logout - refresh_token не найден в куках")
        return response

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")

        if jti:
            # Удаляем конкретную сессию по refresh_jti
            await tokens_collection.delete_one({"refresh_jti": jti})
            logger.info(f"/logout - удалён токен с jti={jti}")
        else:
            logger.warning(f"/logout - jti не найден в payload")

    except JWTError:
        logger.warning(f"/logout - недействительный или просроченный refresh_token")

    # Удаляем куки на клиенте
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.post("/logout_all")
async def logout_all(request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Вы не авторизованы")

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        # Удаляем все токены этого пользователя
        await tokens_collection.delete_many({"email": email})
        logger.info(f" Пользователь {email} вышел со всех устройств")

        response = JSONResponse({"message": "Вышли со всех устройств"})
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response

    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный или просроченный токен")

async def vendor_user_login(user, vendor):
    # Авторизуем пользователя, выдаём токены

    access_token, access_expires, access_jti = create_access_token(str(user["email"]))
    refresh_token, refresh_expires, refresh_jti = create_refresh_token(str(user["email"]))

    # Удаляем старые токены пользователя
    await tokens_collection.delete_many({"email": str(user["email"])})

    # Записываем новые токены в БД
    await tokens_collection.insert_one({
        "user_id": str(user["_id"]),
        "email": str(user["email"]),
        "access_token": access_token,
        "access_jti": access_jti,
        "refresh_token": refresh_token,
        "refresh_jti": refresh_jti,
        "created_at": datetime.now(timezone.utc)
    })
    logger.info(f"/{vendor}_callback  - def {vendor}_callback - Для пользователя: {user["email"]} - созданы новые токены\n")
    return access_token, refresh_token

async def vendor_user_register(email, vendor, vendor_id):
    # Регистрируем нового пользователя
    if vendor == "Google" or vendor == "yandex":
        contact = email
    else:
        contact = None
    new_user = {
        "email": email,
        "contact": contact,
        "password": None,  # Пароль не нужен для OAuth
        "registered_at": datetime.now(timezone.utc),
        "auth_provider": vendor,
        "oauth_id": vendor_id,
        "status": "trial",
        "tokens": 0
    }
    result = await users_collection.insert_one(new_user)
    existing_user_data = await users_data_collection.find_one({"email": email})
    if not existing_user_data:
        logger.info(
            f"/auth/google/callback  - Новый пользователь: {email} - выполнил вход через Гугл, создаём чат по умолчанию\n")
        user_id = str(result.inserted_id)  # Теперь _id точно есть

        # Данные для нового пользователя
        user_data = {
            "user_id": user_id,
            "email": email,
            "status": "trial",
            "mode": [MODE],
            "chats": [DEFAULT_CHAT]  # Добавляем дефолтный чат в массив chats
        }
        await users_data_collection.insert_one(user_data)

    # Выдаём токены
    access_token, access_expires, access_jti = create_access_token(str(email))
    refresh_token, refresh_expires, refresh_jti = create_refresh_token(str(email))
    user_id = str(result.inserted_id)
    await tokens_collection.insert_one({
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "access_jti": access_jti,
        "refresh_token": refresh_token,
        "refresh_jti": refresh_jti,
        "created_at": datetime.now(timezone.utc)
    })
    logger.info(f"/{vendor}_callback  - def {vendor}_callback - Для пользователя: {email} - созданы новые токены в бд\n")
    return access_token, refresh_token


@router.get("/auth/google")
def google_login():
    """Редирект на авторизацию Google"""
    google_auth_url = (
        f"{GOOGLE_AUTH_URL}?response_type=code&client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}&scope=openid%20email%20profile"
    )
    logger.info(f"/auth/google  - Выбран вход через Гугл\n")
    return RedirectResponse(google_auth_url)




import requests

@router.get("/auth/google/callback")
async def google_callback(request: Request, code: str):
    """Получаем токен и данные пользователя из Google"""
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    token_response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    token_json = token_response.json()

    if "access_token" not in token_json:
        logger.info(
            f"/auth/google/callback  - Ошибка авторизации Google\n")
        raise HTTPException(status_code=400, detail="Ошибка авторизации Google")

    # Получаем данные пользователя
    user_info_response = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {token_json['access_token']}"})
    user_info = user_info_response.json()

    email = user_info["email"]
    google_id = user_info["sub"]
    if not email and google_id:
        logger.info(
            f"/auth/google/callback  - Ошибка авторизации Google нет email или айди\n")
        raise HTTPException(status_code=400, detail="Ошибка авторизации Google, no email or id")

    logger.info(
        f"/auth/google/callback  - Получены данные пользователя Google: {email}\n")
    # Проверяем пользователя в MongoDB
    existing_user = await users_collection.find_one({"email": email})

    if existing_user:
        if existing_user["auth_provider"] == "local":
            logger.info(
                f"/auth/google/callback  - Этот email: {email} - уже зарегистрирован через пароль\n")
            raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")

        # Авторизуем пользователя, выдаём токены
        access_token, refresh_token = await vendor_user_login(existing_user, "google")

        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True)
        response.set_cookie("refresh_token", refresh_token, httponly=True)
        logger.info(
            f"/auth/google/callback  - Пользователь: {email} - выполнен вход через Гугл, обновляем токены в куках и в бд\n")
        return response

    # Регистрируем нового пользователя
    access_token, refresh_token = await vendor_user_register(email, "google", google_id)

    response = RedirectResponse(url="/")
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(
        f"/auth/google/callback  - Новый пользователь: {email} - выполнил вход через Гугл, созданы новые токены в куках и в бд\n")
    return response


@router.get("/auth/yandex")
def yandex_login():
    """Редирект на авторизацию Яндекса"""
    logger.info(f"/auth/yandex  - Выбран вход через Yandex\n")
    return RedirectResponse(
        f"{YANDEX_AUTH_URL}?response_type=code&client_id={YANDEX_CLIENT_ID}&redirect_uri={YANDEX_REDIRECT_URI}"
    )

@router.get("/auth/yandex/callback")
async def yandex_callback(request: Request, code: str):
    """Обрабатываем ответ Яндекса"""
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": YANDEX_CLIENT_ID,
        "client_secret": YANDEX_CLIENT_SECRET
    }
    token_response = requests.post(YANDEX_TOKEN_URL, data=token_data)
    token_json = token_response.json()
    result = ''
    if "access_token" not in token_json:
        logger.info(
            f"/auth/yandex/callback  - Ошибка авторизации Yandex\n")
        raise HTTPException(status_code=400, detail="Ошибка авторизации Яндекса")

    # Получаем данные пользователя
    user_info_response = requests.get(YANDEX_USERINFO_URL, headers={"Authorization": f"OAuth {token_json['access_token']}"})
    user_info = user_info_response.json()

    email = user_info.get("default_email")
    yandex_id = str(user_info.get("id"))

    if not email:
        logger.info(
            f"/auth/yandex/callback  - Яндекс не вернул email\n")
        raise HTTPException(status_code=400, detail="Яндекс не вернул email")

    existing_user = await users_collection.find_one({"email": email})

    if existing_user:
        if existing_user["auth_provider"] == "local":
            logger.info(
                f"/auth/yandex/callback  - Этот email: {email} - уже зарегистрирован через пароль.\n")
            raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")
        # Авторизуем пользователя, выдаём токены
        access_token, refresh_token = await vendor_user_login(existing_user, "yandex")

        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True)
        response.set_cookie("refresh_token", refresh_token, httponly=True)
        logger.info(
            f"/auth/yandex/callback  - Пользователь: {email} - выполнен вход через Yandex, обновляем токены в куках и в бд\n")
        return response

    # Регистрируем нового пользователя
    access_token, refresh_token = await vendor_user_register(email, "yandex", yandex_id)

    response = RedirectResponse(url="/")
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(
        f"/auth/yandex/callback  - Пользователь: {email} - успешно авторизован через Яндекс, созданы токены в бд и куках.\n")
    return response



import hashlib
import hmac

@router.get("/auth/telegram/callback")
async def telegram_callback(request: Request):
    """Проверяем данные от Телеграма"""
    logger.info(f"/auth/telegram/callback  - Вызвана коллбэк функция входа через Телеграм\n")
    data = dict(request.query_params)
    auth_data = data.copy()
    result = ''
    # Проверяем подпись
    check_hash = auth_data.pop("hash", None)
    auth_data_str = "\n".join(f"{k}={v}" for k, v in sorted(auth_data.items()))
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    expected_hash = hmac.new(secret_key, auth_data_str.encode(), hashlib.sha256).hexdigest()

    if check_hash != expected_hash:
        logger.info(f"/auth/telegram/callback  - Недействительная подпись данных для входа через Телеграм\n")
        raise HTTPException(status_code=400, detail="Недействительная подпись данных")

    # Проверяем время запроса (не старше 1 мин)
    auth_time = datetime.fromtimestamp(int(auth_data["auth_date"]), tz=timezone.utc)
    current_time = datetime.now(timezone.utc)

    if (current_time - auth_time).total_seconds() > 60:
        logger.info(f"/auth/telegram/callback  - Данные устарели (60 минут) для входа через Телеграм\n")
        raise HTTPException(status_code=400, detail="Данные устарели")

    telegram_id = auth_data["id"]
    username = auth_data["username"]
    email = f"{username}@telegram.com"  # Условный email

    # Проверяем пользователя в БД
    existing_user = await users_collection.find_one({"email": email})

    if existing_user:
        if existing_user["auth_provider"] == "local":
            logger.info(f"/auth/telegram/callback  - Этот email уже зарегистрирован через пароль для входа через Телеграм\n")
            raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")

        # Авторизуем пользователя, выдаём токены
        access_token, refresh_token = await vendor_user_login(existing_user, "telegram")
        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True)
        response.set_cookie("refresh_token", refresh_token, httponly=True)
        logger.info(
            f"/auth/telegram/callback  - Пользователь: {email} - выполнен вход через telegram, обновляем токены в куках и в бд\n")
        return response

    # Регистрируем нового пользователя
    access_token, refresh_token = await vendor_user_register(email, "telegram", telegram_id)
    response = RedirectResponse(url="/")
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(
        f"/auth/telegram/callback  - Пользователь: {username} - выполнил вход через Телеграм, созданы новые токены в куки и в бд\n")
    return response


@router.get("/auth/vk")
def vk_login():
    """Редирект на VK OAuth"""
    logger.info(
        f"/auth/vk  - Выбрана авторизация через VK.\n")
    return RedirectResponse(
        f"{VK_AUTH_URL}?client_id={VK_CLIENT_ID}&display=page"
        f"&redirect_uri={VK_REDIRECT_URI}&scope=email"
        f"&response_type=code&v=5.131"
    )


@router.get("/auth/vk/callback")
async def vk_callback(request: Request, code: str):
    """Обрабатываем ответ VK"""
    token_data = {
        "client_id": VK_CLIENT_ID,
        "client_secret": VK_CLIENT_SECRET,
        "redirect_uri": VK_REDIRECT_URI,
        "code": code
    }
    token_response = requests.post(VK_TOKEN_URL, data=token_data)
    token_json = token_response.json()
    result = ''

    if "access_token" not in token_json:
        logger.info(
            f"/auth/vk/callback  - Ошибка авторизации VK.\n")
        raise HTTPException(status_code=400, detail="Ошибка авторизации VK")

    access_token = token_json["access_token"]
    user_id = token_json["user_id"]
    email = token_json.get("email", f"vk_{user_id}@vk.com")  # Email может отсутствовать

    # Получаем данные пользователя
    user_info_response = requests.get(
        VK_USERINFO_URL,
        params={"user_ids": user_id, "access_token": access_token, "v": "5.131", "fields": "first_name,last_name"}
    )
    user_info = user_info_response.json()

    if "response" not in user_info:
        logger.info(
            f"/auth/vk/callback  - Ошибка получения данных VK.\n")
        raise HTTPException(status_code=400, detail="Ошибка получения данных VK")

    vk_user = user_info["response"][0]
    full_name = f"{vk_user['first_name']} {vk_user['last_name']}"

    # Проверяем пользователя в БД
    existing_user = await users_collection.find_one({"email": email})

    if existing_user:
        if existing_user["auth_provider"] == "local":
            logger.info(
                f"/auth/vk/callback  - Этот email: {email} -  уже зарегистрирован через пароль.\n")
            raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")
        # Авторизуем пользователя, выдаём токены
        access_token, refresh_token = await vendor_user_login(existing_user, "vk")

        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True)
        response.set_cookie("refresh_token", refresh_token, httponly=True)
        logger.info(
            f"/auth/vk/callback  - Пользователь: {email} - выполнен вход через VK, обновляем токены в куках и в бд\n")
        return response
    # Регистрируем нового пользователя
    access_token, refresh_token = await vendor_user_register(email, "vk", user_id)
    response = RedirectResponse(url="/")
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(
        f"/auth/vk/callback  - Пользователь: {email} - успешно авторизовался через Вконтакте, созданы токены в бд и куках.\n")
    return response