import logging
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from models.users import users_collection
from models.tokens import tokens_collection
from models.user_data import users_data_collection
from settings import *

router = APIRouter()
logger = logging.getLogger("app_logger")

SECRET_KEY = APP_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

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
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM), expire



def create_refresh_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM), expire



async def get_user(request: Request):
    """Проверяет access-токен в куках и валидирует его"""
    token = request.cookies.get("access_token")
    logger.info(f"def get_user - Токен в куках: {token}")  # Логируем токен из кук
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"def get_user - Payload токена: {payload}")  # Посмотрим, что в токене
        email = payload.get("sub")
        if not email:
            logger.info("def get_user - Нет email в payload")
            return None

        # Проверяем, есть ли access-токен в БД
        token_in_db = await tokens_collection.find_one({"email": email, "access_token": token})
        if not token_in_db:
            logger.info(f"def get_user - Токен не найден в БД: {token}")
            return None

        user = await users_collection.find_one({"email": email})
        logger.info(f"def get_user - Пользователь {user['email']} авторизован: {token}")
        return {"email": user["email"], "id": str(user["_id"]), "status": str(user["status"]), "tokens": int(user["tokens"])} if user else None
    except JWTError:
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

        # Проверяем, есть ли refresh-токен в БД
        token_in_db = await tokens_collection.find_one({"email": email, "refresh_token": refresh_token})
        if not token_in_db:
            logger.info(f"/refresh  - def refresh_token - refresh token не найден в бд\n")
            raise HTTPException(status_code=401, detail="Недействительный токен  - время истекло")

        # Генерируем новый access-токен
        new_access_token, access_expires = create_access_token(email)

        # Обновляем токен в БД
        await tokens_collection.update_one(
            {"email": email, "refresh_token": refresh_token},
            {"$set": {"access_token": new_access_token}}
        )
        logger.info(f"/refresh  - def refresh_token - токены в бд обновлены\n")
        response = JSONResponse({"message": "Токен обновлен"})
        response.set_cookie("access_token", new_access_token, httponly=True)
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
                "password": hashed_password,
                "registered_at": register_time,
                "auth_provider": "local",
                "oauth_id": None,
                "status": status,
                "tokens": tokens}
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
    access_token, access_expires = create_access_token(email)
    refresh_token, refresh_expires = create_refresh_token(email)
    await tokens_collection.insert_one({
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": refresh_expires
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
    access_token, access_expires = create_access_token(str(user["email"]))
    refresh_token, refresh_expires = create_refresh_token(str(user["email"]))

    # Удаляем старые токены пользователя
    await tokens_collection.delete_many({"email": str(user["email"])})

    # Записываем новые токены в БД
    await tokens_collection.insert_one({
        "user_id": str(user["_id"]),
        "email": str(user["email"]),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": refresh_expires
    })
    logger.info(f"/login  - def login - Для пользователя: {email} - созданы новые токены\n")

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(f"/login  - def login - Для пользователя: {email} - в куки добавлены новые токены\n")
    return response

@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_user)):
    logger.info(f"/dashboard  - def dashboard - Пользователь: {user['email']} - зашел в свою панель управления\n")
    """Защищенный роут для авторизованных пользователей"""
    return {"message": f"Привет, {user['email']}! Это твоя панель управления."}

@router.get("/logout")
async def logout():
    """Выход и удаление токенов из БД"""
    response = RedirectResponse(url="/authorize")

    # Получаем токен из куки
    refresh_token = response.delete_cookie("refresh_token")

    # Удаляем токены из БД
    await tokens_collection.delete_many({"refresh_token": refresh_token})

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    logger.info(f"/logout  - def logout - Пользователь вышел, токены удалены в бд и куках\n")
    return response


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
        access_token, _ = create_access_token(email)
        refresh_token, _ = create_refresh_token(email)

        response = RedirectResponse(url="/")
        response.set_cookie("access_token", access_token, httponly=True)
        response.set_cookie("refresh_token", refresh_token, httponly=True)
        logger.info(
            f"/auth/google/callback  - Пользователь: {email} - выполнен вход через Гугл, обновляем токены в куках и в бд\n")
        return response

    # Регистрируем нового пользователя
    new_user = {
        "email": email,
        "password": None,  # Пароль не нужен для OAuth
        "registered_at": datetime.now(timezone.utc),
        "auth_provider": "google",
        "oauth_id": google_id,
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
    access_token, _ = create_access_token(email)
    refresh_token, _ = create_refresh_token(email)

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

    if existing_user and existing_user["auth_provider"] == "local":
        logger.info(
            f"/auth/yandex/callback  - Этот email: {email} - уже зарегистрирован через пароль.\n")
        raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")

    if not existing_user:
        result = await users_collection.insert_one({
            "email": email,
            "password": None,
            "registered_at": datetime.now(timezone.utc),
            "auth_provider": "yandex",
            "oauth_id": yandex_id
        })

    existing_user_data = await users_data_collection.find_one({"email": email})
    if not existing_user_data:
        user_id = str(result.inserted_id)  # Теперь _id точно есть
        logger.info(
            f"/auth/yandex/callback  - Новый пользователь: {email} - вошёл через Яндекс, создаём чат по умолчанию.\n")
        # Данные для нового пользователя
        user_data = {
            "user_id": user_id,
            "email": email,
            "status": "trial",
            "mode": [MODE],
            "chats": [DEFAULT_CHAT]  # Добавляем дефолтный чат в массив chats
        }
        await users_data_collection.insert_one(user_data)

    access_token, _ = create_access_token(email)
    refresh_token, _ = create_refresh_token(email)

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

    if existing_user and existing_user["auth_provider"] == "local":
        logger.info(f"/auth/telegram/callback  - Этот email уже зарегистрирован через пароль для входа через Телеграм\n")
        raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")

    if not existing_user:
        result = await users_collection.insert_one({
            "email": email,
            "password": None,
            "registered_at": datetime.now(timezone.utc),
            "auth_provider": "telegram",
            "oauth_id": telegram_id
        })
    existing_user_data = await users_data_collection.find_one({"email": email})
    if not existing_user_data:
        user_id = str(result.inserted_id)  # Теперь _id точно есть
        logger.info(
            f"/auth/telegram/callback  - Новый пользователь: {username} - выполнен вход через Телеграм\n")
        # Данные для нового пользователя
        user_data = {
            "user_id": user_id,
            "email": email,
            "status": "trial",
            "mode": [MODE],
            "chats": [DEFAULT_CHAT]  # Добавляем дефолтный чат в массив chats
        }
        await users_data_collection.insert_one(user_data)

    access_token, _ = create_access_token(email)
    refresh_token, _ = create_refresh_token(email)
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

    if existing_user and existing_user["auth_provider"] == "local":
        logger.info(
            f"/auth/vk/callback  - Этот email: {email} -  уже зарегистрирован через пароль.\n")
        raise HTTPException(status_code=400, detail="Этот email уже зарегистрирован через пароль.")

    if not existing_user:
        result = await users_collection.insert_one({
            "email": email,
            "password": None,
            "registered_at": datetime.now(timezone.utc),
            "auth_provider": "vk",
            "oauth_id": str(user_id),
            "full_name": full_name
        })

    existing_user_data = await users_data_collection.find_one({"email": email})
    if not existing_user_data:
        user_id = str(result.inserted_id)  # Теперь _id точно есть
        logger.info(
            f"/auth/vk/callback  - Новый пользователь: {email} - авторизовался через Вконтакте, создаём чат по умолчанию.\n")
        # Данные для нового пользователя
        user_data = {
            "user_id": user_id,
            "email": email,
            "status": "trial",
            "mode": [MODE],
            "chats": [DEFAULT_CHAT]  # Добавляем дефолтный чат в массив chats
        }
        await users_data_collection.insert_one(user_data)

    access_token, _ = create_access_token(email)
    refresh_token, _ = create_refresh_token(email)

    response = RedirectResponse(url="/")
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    logger.info(
        f"/auth/vk/callback  - Пользователь: {email} - успешно авторизовался через Вконтакте, созданы токены в бд и куках.\n")
    return response