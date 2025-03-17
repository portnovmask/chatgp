from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from models.users import users_collection
from models.tokens import tokens_collection
from models.user_data import users_data_collection
from settings import APP_SECRET_KEY

router = APIRouter()

SECRET_KEY = APP_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Настройка для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM), expire



def create_refresh_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM), expire



async def get_user(request: Request):
    #print("z pltcm")
    """Проверяет access-токен в куках и валидирует его"""
    token = request.cookies.get("access_token")
    print(f"Токен в куках: {token}")  # Логируем токен из кук
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Payload токена: {payload}")  # Посмотрим, что в токене
        email = payload.get("sub")
        if not email:
            print("Нет email в payload")
            return None

        # Проверяем, есть ли access-токен в БД
        token_in_db = await tokens_collection.find_one({"email": email, "access_token": token})
        if not token_in_db:
            print(f"Токен не найден в БД: {token}")
            return None

        user = await users_collection.find_one({"email": email})
        print(f"Пользователь авторизован: {token}")
        return {"email": user["email"], "id": str(user["_id"]), "status": str(user["status"]), "tokens": int(user["tokens"])} if user else None
    except JWTError:
        return None



@router.get("/me")
async def get_current_user(request: Request):
    """Получение данных о текущем пользователе по access-токену"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Требуется аутентификация куки")
        #return RedirectResponse(url="/logout", status_code=303)

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        # Получаем пользователя из БД
        user = await users_collection.find_one({"email": email}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
            #return RedirectResponse(url="/logout", status_code=303)
            #return None
        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен необходима авторизация")
        #return RedirectResponse(url="/logout", status_code=303)

@router.post("/refresh")
async def refresh_token(request: Request):
    """Обновление access-токена по refresh-токену"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Требуется аутентификация рефреш")

    try:
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")

        # Проверяем, есть ли refresh-токен в БД
        token_in_db = await tokens_collection.find_one({"email": email, "refresh_token": refresh_token})
        if not token_in_db:
            raise HTTPException(status_code=401, detail="Недействительный токен  - время истекло")

        # Генерируем новый access-токен
        new_access_token, access_expires = create_access_token(email)

        # Обновляем токен в БД
        await tokens_collection.update_one(
            {"email": email, "refresh_token": refresh_token},
            {"$set": {"access_token": new_access_token}}
        )

        response = JSONResponse({"message": "Токен обновлен"})
        response.set_cookie("access_token", new_access_token, httponly=True)
        return response

    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен устарел или удалены куки")

@router.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    """Регистрация нового пользователя"""
    register_time = datetime.now(timezone.utc)
    status = "trial"
    tokens = 0
    existing_user = await users_collection.find_one({"email": email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = pwd_context.hash(password)
    new_user = {"email": email,
                "password": hashed_password,
                "registered_at": register_time,
                "status": status,
                "tokens": tokens}
    result = await users_collection.insert_one(new_user)
    user_id = str(result.inserted_id)  # ✅ Теперь _id точно есть
    # Дефолтные сообщения для chat_body
    default_chat_body = [
        {"prompt": "Добро пожаловать", "body": "У вас пока нет чатов, но вы можете создать новый автоматически."}
    ]

    # Дефолтный чат
    default_chat = {
        "chat_id": "default_id",
        "chat_time": datetime.now(timezone.utc).isoformat(),
        "chat_summary": "Здесь будут ваши чаты",
        "chat_body": default_chat_body  # Добавляем список сообщений в chat_body
    }
    mode = {"current_mode": "basic", "current_chat": None}
    # Данные для нового пользователя
    user_data = {
        "user_id": user_id,
        "email": email,
        "status": status,
        "mode": [mode],
        "chats": [default_chat]  # Добавляем дефолтный чат в массив chats
    }
    await users_data_collection.insert_one(user_data)

    access_token, access_expires = create_access_token(email)
    refresh_token, refresh_expires = create_refresh_token(email)
    await tokens_collection.insert_one({
        "user_id": user_id,
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": refresh_expires
    })

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    return response


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Авторизация с проверкой пароля"""
    user = await users_collection.find_one({"email": email})
    if not user or not pwd_context.verify(password, user["password"]):
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

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", access_token, httponly=True)
    response.set_cookie("refresh_token", refresh_token, httponly=True)
    return response

@router.get("/dashboard")
async def dashboard(user: dict = Depends(get_user)):
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
    return response

