import json
import logging
import os
from database import init_db
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, Response, Query, Depends, HTTPException, UploadFile, File
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from auth import router as auth_router
from blog_post import router as posts_router
from mail import router as mail_router
from subscriptions import router as subscription_router, get_ton_usdt_price, renew_subscriptions
from auth import get_user, get_user_optional, generate_csrf_token, verify_csrf_or_guest, verify_csrf_token
import openai
from settings import APY_KEY, LEVELS, ATTEMPT_LIMITS, CSRF_SECRET_KEY, UPLOAD_DIR
from file_utils import save_uploaded_image, image_to_base64
from modes import (User, get_user_summaries, get_chat_body_by_id, get_last_chat_id,
                   set_chat, reset_chat, delete_chat, get_current_attempts,
                   update_user_image_upload, delete_user_image_upload)
import asyncio
import markdown
from blog_post import get_post_by_slug, get_all_post_titles, get_latest_post
access_logger = logging.getLogger("uvicorn.access")

file_handler = logging.FileHandler("access.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
access_logger.addHandler(file_handler)



# Настраиваем логгер (общий для всего проекта)
logger = logging.getLogger("app_logger")  # Уникальное имя логгера
logger.setLevel(logging.INFO)

# Обработчик для записи логов в файл с ротацией
file_handler = RotatingFileHandler("app.log", maxBytes=5*1024*1024, backupCount=3)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Добавляем обработчик (если он еще не был добавлен)
if not logger.hasHandlers():
    logger.addHandler(file_handler)


MAX_FILE_AGE = timedelta(minutes=15)  # 15 минут
SUBSCRIPTION_RENEW_INTERVAL = 3600  # 1 час



# === Современный lifespan-хендлер ===
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Сначала инициализация БД
    await init_db()

    tasks = [
        asyncio.create_task(cleanup_expired_files()),
        asyncio.create_task(auto_renew_subscriptions()),
    ]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/tmp/uploads", StaticFiles(directory=UPLOAD_DIR.resolve()), name="uploads")
app.include_router(auth_router)
app.include_router(posts_router)
app.include_router(mail_router)

app.include_router(subscription_router)



templates = Jinja2Templates(directory="templates")

# @app.get("/", response_class=HTMLResponse)
# async def read_root(request: Request):
#    return templates.TemplateResponse("index.html", {"request": request})

client = openai.AsyncOpenAI(api_key=APY_KEY)

# TOKEN_LIMIT = True
#client2 = openai.AsyncOpenAI(api_key=APY_KEY)


async def generate_summary(data, words: int = 2):
    logger.info(f"Данные пришли в функцию generate_summary: {data}")
    try:
        response = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'user',
                 'content': f"Создай ёмкий заголовок из {words}-{words+1} слов на языке оригинала для этого диалога: {data}. "
                            "В твоём ответе должен быть только заголовок, без вступлений, пояснений, пожеланий или выводов."}
            ],
            temperature=0,
        )

        if not response.choices or not response.choices[0].message:
            logger.info("Ошибка: Пустой ответ от API OpenAI")
            return "Ошибка генерации заголовка"

        reply_content = response.choices[0].message.content
        logger.info(f"Summary: \n{reply_content}")
        return reply_content

    except Exception as e:
        logger.info(f"Ошибка в generate_summary: {e}")
        return "Ошибка генерации заголовка"


async def after_stream_processing(chat, prompt, full_reply_content, chat_id, stream_id, user_tokens):
    logger.info(f"Полный ответ after_stream_processing обрезанный: {full_reply_content[0:15]}")
    logger.info(f"def after_stream_processing user tokens: {user_tokens}")
    if not chat_id or chat_id == "new":  # Если чат новый, создаем summary
        summary = await generate_summary(full_reply_content)  # ✅ Дожидаемся результата
        logger.info(f"Создан summary after_stream_processing: {summary}")
    else:
        summary = None

    await chat.add_to_chat_db(prompt, full_reply_content, chat_id, stream_id, summary)  # ✅ Теперь summary — строка
    logger.info(f"Данные сохранены в чат after_stream_processing {chat_id}")

    await chat.update_token_count_db(user_tokens)
    logger.info(f"Обновлены токены after_stream_processing: {user_tokens}")


# def get_ton_usdt_price():
#     url = "https://api.coinlore.net/api/ticker/?id=54683"
#
#     response = requests.get(url)
#     logger.info(f"Ответ от апи курса Тон: {response.status_code}")
#     if response.status_code > 200:
#         data = response.json()
#         logger.info(f"Текущий курс Тон: {data[0].get("price_usd")}")
#         return data[0].get("price_usd")
#     logger.info(f"Не удалось получить курс Тон, возвращаем дефолтный курс")
#     return 2.70

# ton_to_usdt = float(await get_ton_usdt_price())




@app.get("/", response_class=HTMLResponse)
async def index(request: Request, response: Response, user: dict | None = Depends(get_user_optional), chat_id: str = None,
                new_chat: int = Query(None)):
    if not user:
        guest_token = generate_csrf_token("guest", CSRF_SECRET_KEY)

        response = templates.TemplateResponse("index.html",
                                          {"request": request, "user": user,
                                           })
        response.set_cookie("csrf_token", guest_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response

    user_chat = []
    param = request.cookies.get("param", "stream")
    csrf_token = request.cookies.get("csrf_token")
    #await update_user_mode(user, param)
    user_summaries = await get_user_summaries(user)
    attempts = await get_current_attempts(user)
    # Если chat_id отсутствует, пробуем взять из куки

    if not chat_id:
        logger.info(f"Чат айди нет, ищем в базе\n")
        chat_id = await get_last_chat_id(user, recent_chat=True) or request.cookies.get("chat_id_cookie")
        logger.info(f"Чат айди есть, в куках: {request.cookies.get("chat_id_cookie")}\n")
        logger.info(f"Чат айди после поиска в базе и в куках: {chat_id}\n")

    if chat_id:
        response.set_cookie(key="chat_id_cookie", value=chat_id, path="/", httponly=False, max_age=3600)
        user_chat = await get_chat_body_by_id(user, chat_id)
        await set_chat(user, chat_id)

    logger.info(f"Определен пользователь на корне: {user}, param: {param}, chat_id: {chat_id}\n")

    # else:
    #     await reset_chat(user)  # Сброс текущего чата
    #     return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("index.html",
                                      {"request": request, "user": user,
                                       "param": param,
                                       "user_summaries": user_summaries,
                                       "user_chat": user_chat,
                                       "csrf_token": csrf_token,
                                       "attempts": attempts})



class PromptRequest(BaseModel):
    prompt: str
    csrf_token: str
    extras: str | None = None

class ImagePromptRequest(PromptRequest):
    image_url: Optional[str] = None

class VoicePromptRequest(PromptRequest):
    voice_clip_id: Optional[str] = None


# @app.get("/stream")
# async def stream(prompt: str = Query(...), user: dict = Depends(get_user)):
#     if not user:
#         logger.info(f" def stream: Пользователь не авторизован")
#         raise HTTPException(status_code=401, detail="Пользователь не авторизован")

@app.post("/api/stream")
async def stream(request_data: PromptRequest, user: dict = Depends(get_user)):
    if not user:
        logger.info(f"def stream: Пользователь не авторизован")
        raise HTTPException(status_code=401, detail="Пользователь не авторизован")
    csrf_token = request_data.csrf_token
    user_email = user["email"]
    if not csrf_token or not verify_csrf_token(csrf_token, user_email, CSRF_SECRET_KEY):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    prompt = request_data.prompt
    extras = request_data.extras
    chat = User(user)
    prompt_pic = await chat.get_user_image_upload_from_db()
    user_message =  {"role": "user", "content": prompt}

    chat_id = await get_last_chat_id(user) or None
    logger.info(f"Выбранный chat_id stream get_last_chat_id: {chat_id}")
    # Достаем последние 5 сообщений для assistant_content

    assistant_content = await chat.get_last_chat_messages(chat_id)
    logger.info(f"assistant_content stream: {assistant_content[0:15]}\n")

    user_tokens = user.get("tokens", 0)  # Предотвращаем ошибку, если у user нет "tokens"
    request_params = await chat.request_params()

    if extras and extras==prompt_pic:
        #file_path = f"http://127.0.0.1:8000/tmp/uploads/{prompt_pic}" ссылка заработает, когда будет сервер
        file_path = "https://ketome.ru/wp-content/uploads/2024/05/pohudenie-s-pomoschyu-ketoza-na-keto.jpg" # заглушка для демонстрации работы распознавания изображений
        user_message = {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{prompt}"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"{file_path}",
                                },
                            },
                        ],
                    }
        await delete_user_image_upload(user)



    async def generate_stream(context, hit_limits):
        token_usage = 0
        collected_messages = []
        stream_id = None
        system_content = 'Ты консультант-помощник'

        # Проверка лимита токенов
        if (100000000 - hit_limits) <= 0:
            logger.info(f"/stream-{user.get("email")} Токенов слишком много: {hit_limits}\n")
            #return

        # GPT запрос
        completion = await client.chat.completions.create(
            model=request_params.get("model", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": request_params.get("content", system_content)},
                {"role": "assistant", "content": context},
                # {"role": "user", "content": prompt}
                user_message
            ],
            temperature=request_params.get("temperature", 0.2),
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content:
                collected_messages.append(chunk.choices[0].delta.content)
                stream_id = chunk.id
                #print(f"Стрим-фрагмент: {chunk.choices[0].delta.content}")  # Логируем потоковые данные

            if chunk.usage:
                token_usage = int(chunk.usage.total_tokens)
                hit_limits += token_usage
                logger.info(f"Обновленный лимит токенов stream: {hit_limits}\n")

            json_data = json.dumps({
                "id": chunk.id,
                "created": chunk.created,
                "user_query": prompt,
                "content": chunk.choices[0].delta.content if chunk.choices else '\n',
                "finish_reason": chunk.choices[0].finish_reason if chunk.choices else 'End',
                "usage": chunk.usage.total_tokens if chunk.usage else 0,
            })
            yield f"data: {json_data}\n\n"

        full_reply_content = ''.join(collected_messages)
        logger.info(f"Полный ответ в стриме: {full_reply_content[0:15]}")
        logger.info(f"Айди стрима: {stream_id}\n")

        asyncio.create_task(after_stream_processing(chat, prompt, full_reply_content, chat_id, stream_id, token_usage))
        logger.info(f"Запустили фоновую функцию из стрима с чат айди: {chat_id}\n")

    return StreamingResponse(generate_stream(assistant_content, user_tokens), media_type="text/event-stream")

@app.post("/api/search")
async def search(request_data: PromptRequest, user: dict = Depends(get_user)):

    if not user:
        logger.info(f"def search: Пользователь не авторизован")
        raise HTTPException(status_code=401, detail="Пользователь не авторизован")
    csrf_token = request_data.csrf_token
    user_email = user["email"]
    if not csrf_token or not verify_csrf_token(csrf_token, user_email, CSRF_SECRET_KEY):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    prompt = request_data.prompt

    search_chat = User(user)
    search_chat_id = await get_last_chat_id(user) or None
    stream_id = None

    status = user.get("status", "trial")
    attempts = user.get("attempts", 0)
    user_tokens = user.get("tokens", 0)
    params = await search_chat.request_params()
    search_model = params.get("search_model")
    level_index = LEVELS.index(status)

    if level_index < 2:
        return {"message": "Поиск недоступен на вашем уровне подписки!", "status": "error"}

    if (params.get("search") - attempts) < 1:
        return {"message": "Вы исчерпали лимиты поиска на сегодня!", "status": "info"}

    # assistant_content = await search_chat.get_last_chat_messages(search_chat_id)
    # logger.info(f"assistant_content search: {assistant_content[0:15]}\n")

    def insert_annotations(text: str, annotations: list[dict]) -> str:
        if not annotations:
            return text

        annotations = sorted(annotations, key=lambda a: a["url_citation"]["start_index"], reverse=True)

        for ann in annotations:
            citation = ann.get("url_citation")
            if not citation:
                continue

            start = citation.get("start_index")
            end = citation.get("end_index")
            url = citation.get("url")
            title = citation.get("title")

            if not (0 <= start < end <= len(text)):
                continue

            cited_text = text[start:end]
            link = f'<a href="{url}" target="_blank" title="{title}">{cited_text}</a>'
            text = text[:start] + link + text[end:]

        return text

    async def generate_search(user_prompt, user_attempts, tokens, user_model):
        token_usage = 1000
        completion = await client.chat.completions.create(
            model=user_model,
            messages=[{
                "role": "user",
                "content": user_prompt,
            }],
        )

        user_attempts += 1
        # Проверка лимита токенов
        if (100000000 - tokens) <= 0 or (params.get("search") - user_attempts) <= 0 :
            logger.info(f"/search-{user.get("email")}: Токенов или попыток поиска слишком много. Токены: {tokens}, Попытки: {user_attempts}\n")
            # return

        await search_chat.update_attempts(1)
        await search_chat.refresh()

        if completion:
            message_obj = completion.choices[0]
            full_reply_content = message_obj.message.content
            annotations = message_obj.annotations if hasattr(message_obj, "annotations") else []

            full_reply_with_links = insert_annotations(full_reply_content, annotations)
            search_id = completion.id

            await after_stream_processing(search_chat, prompt, full_reply_content, search_chat_id, search_id,
                                          token_usage)
            logger.info(f"Запустили фоновую функцию из поиска с чат айди: {search_chat_id}\n")

            return full_reply_with_links
        else:
            return "Ошибка поиска"

    new_attempt_count = await get_current_attempts(user)
    final_response = await generate_search(prompt, attempts, user_tokens, search_model)

    return {
        "response": final_response,
        "attempts": new_attempt_count,
        "id": stream_id
    }



from fastapi import Form

@app.post("/api/upload-image/")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
    user: dict = Depends(get_user)
):
    if not user:
        logger.info(f"def upload_image: Пользователь не авторизован")
        return RedirectResponse('/', status_code=302)

    user_email = user["email"]
    stored_token = request.cookies.get("csrf_token")
    if not stored_token or csrf_token != stored_token or not verify_csrf_token(stored_token, user_email, CSRF_SECRET_KEY):
        return RedirectResponse('/', status_code=302)

    status = user.get("status", "trial")
    level_index = LEVELS.index(status)

    if file:
        file_check = await save_uploaded_image(file, level_index)
        if file_check and "/" in file_check:
            file_name = os.path.basename(file_check)
            await update_user_image_upload(user, file_name)
            return JSONResponse(content={"path": file_name})
        return None
    return None


@app.post("/api/delete-image/")
async def delete_uploaded_image(
    request: Request,
    csrf_token: str = Form(...),
    user: dict = Depends(get_user)
):
    if not user:
        return RedirectResponse("/", status_code=302)

    stored_token = request.cookies.get("csrf_token")
    if not stored_token or csrf_token != stored_token or not verify_csrf_token(stored_token, user["email"], CSRF_SECRET_KEY):
        return RedirectResponse("/", status_code=302)

    await delete_user_image_upload(user)
    return {"status": "deleted"}



@app.get("/authorize")
async def authorize(request: Request, mode: str = "login", user: dict | None = Depends(get_user_optional)):
    if user:
        return RedirectResponse('/api/logout', status_code=302)
    csrf_token = request.cookies.get("csrf_token")
    response = templates.TemplateResponse("authorize.html", {"request": request, "mode": mode, "csrf_token": csrf_token})
    if not csrf_token or not verify_csrf_token(csrf_token, "guest", CSRF_SECRET_KEY, 3600):
        guest_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("authorize.html",
                                              {"request": request, "mode": mode, "csrf_token": guest_token,})
        response.set_cookie("csrf_token", guest_token, httponly=False, samesite="lax")
        return response
    return response

@app.get("/help")
async def get_help(request: Request, user: dict | None = Depends(get_user_optional)):
    if not user:
        csrf_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("help.html", {"request": request})
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response
    return templates.TemplateResponse("help.html", {"request": request})

@app.get("/privacy")
async def privacy(request: Request, user: dict | None = Depends(get_user_optional)):
    if not user:
        csrf_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("privacy.html", {"request": request})
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/about")
async def about(request: Request, user: dict | None = Depends(get_user_optional)):
    if not user:
        csrf_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("about.html", {"request": request})
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response
    return templates.TemplateResponse("about.html", {"request": request})




@app.get("/price")
async def price(request: Request, user: dict | None = Depends(get_user_optional)):
    ton_to_usdt = float(await get_ton_usdt_price())
    if not user:
        csrf_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("price.html", {"request": request, "ton_to_usdt": ton_to_usdt})
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response
    return templates.TemplateResponse("price.html", {"request": request, "user": user, "ton_to_usdt": ton_to_usdt})


@app.get("/dash")
async def dash(request: Request, user: dict = Depends(get_user)):
    if not user:
        return RedirectResponse('/', status_code=302)
    else:
        plans = {
            "trial": "Базовый",
            "basic": "Оптимум",
            "advanced": "Фрилансер",
            "business": "Бизнес",
            "pro": "Мыслитель",
            "premium": "Премиум"
        }
        logger.info(f"/dashboard  - def dashboard - Пользователь: {user['email']} - зашел в свою панель управления\n")

        return templates.TemplateResponse("dash.html",
                                          {"request": request, "user": user, "plans": plans})


@app.get("/post", response_class=HTMLResponse)
async def post_home(request: Request,
    user: dict | None = Depends(get_user_optional)
):

    post = await get_latest_post()
    if post:
        post["content"] = markdown.markdown(
            post["content"], extensions=["extra", "sane_lists", "nl2br"]
        )
    posts = await get_all_post_titles()
    if not user:
        csrf_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("blog.html", {
            "request": request,
            "post": post,
            "posts": posts,
            "user": user,
        })
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response
    return templates.TemplateResponse("blog.html", {
        "request": request,
        "post": post,
        "posts": posts,
        "user": user,
    })

@app.get("/post/{slug}", response_class=HTMLResponse)
async def view_post(request: Request, slug: str,
    user: dict | None = Depends(get_user_optional)
):

    post = await get_post_by_slug(slug)
    if not post:
        return HTMLResponse("Not found", status_code=404)

    post["content"] = markdown.markdown(
        post["content"], extensions=["extra", "sane_lists", "nl2br"]
    )
    posts = await get_all_post_titles()
    if not user:
        csrf_token = generate_csrf_token("guest", CSRF_SECRET_KEY)
        response = templates.TemplateResponse("blog.html", {
        "request": request,
        "post": post,
        "posts": posts,
        "user": user,
    })
        response.set_cookie("csrf_token", csrf_token, httponly=False, samesite="lax", secure=True, max_age=900)
        return response
    return templates.TemplateResponse("blog.html", {
        "request": request,
        "post": post,
        "posts": posts,
        "user": user,
    })

@app.get("/api/change_param")  #Ручка для выбора параметров
async def change_param(request: Request, user: dict = Depends(get_user), param: str = "stream"):
    response = RedirectResponse(url="/")  # Перенаправляем на корень
    #Логика получения параметра и проверки доступа пользователя к нему
    if user:
        status = user.get("status")
        attempts = user.get("attempts")
        level_index = LEVELS.index(status)
        if level_index < 2 and param != "stream":
            mode = "stream"
        elif (ATTEMPT_LIMITS[level_index] - attempts) < 1:
            mode = "stream"
        else:
            mode = param
        response.set_cookie(key="param", value=mode, max_age=3600)  # Меняем куки
    else:
        response = RedirectResponse(url="/")
    return response


@app.get("/api/get_chat_body")
async def get_chat_body(chat_id: str, user: dict = Depends(get_user)):
    if not user:
        logger.info(f" get_chat_body: Пользователь не авторизован")
        raise HTTPException(status_code=401, detail="Пользователь не авторизован")
    chat_body = await get_chat_body_by_id(user, chat_id)
    await set_chat(user, chat_id)

    if chat_body is None:
        return JSONResponse({"error": "Чат не найден"}, status_code=404)

    response = JSONResponse({"chat_body": chat_body})
    response.set_cookie(key="chat_id_cookie", value=chat_id, path="/", httponly=True, max_age=3600)
    return response


@app.get("/api/reset_chat")
async def reset_chat_route(response: Response, user: dict = Depends(get_user), new_chat: int = Query(None)):
    if new_chat:
        await reset_chat(user)
        response.delete_cookie("chat_id_cookie")
    return RedirectResponse(url="/", status_code=303)


@app.post("/api/update_summaries")
async def update_summaries(
        request: Request, user: dict = Depends(get_user)
):
    user_summaries = await get_user_summaries(user)

    return {"summaries": user_summaries}



@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page(
    request: Request,
    message: str = "Что-то произошло.",
    status: str = "info",
    action_label: str = None,
    action_url: str = None,
    action_method: str = "get"
):
    action = None
    if action_label and action_url:
        action = {
            "label": action_label,
            "url": action_url,
            "method": action_method.lower()
        }

    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "message": message,
        "status": status,
        "action": action
    })


import re
import html
import markdown2

CODE_BLOCK_RE = re.compile(r"```(.*?)```", re.DOTALL)


@app.post("/api/format-text/")
async def format_text(request: Request):
    """Получает текст от фронта и оборачивает кодовые блоки"""
    data = await request.json()
    raw_text = data.get("text", "")

    formatted_text = format_code_blocks(raw_text)

    return JSONResponse(content={"formatted_text": formatted_text})


def format_code_blocks(text):
    """Оборачивает кодовые блоки в <pre><code> и сохраняет остальной текст"""

    def replace_code(match):
        # Экранируем возможные HTML-символы в коде для безопасности
        code = match.group(1)
        escaped_code = html.escape(code)
        return (f"<div class='code-snippet'><pre class='language-css'><code>{escaped_code}</code>"
                f"<button class='copy-button'><img src='/static/img/icons/copy.svg' width='20' height='20' alt='copy'></button></pre></div>")

    # Заменяем все кодовые блоки с помощью регулярного выражения
    formatted_text = CODE_BLOCK_RE.sub(replace_code, text)
    # Рендерим оставшийся Markdown в HTML (заголовки, жирный текст, списки)
    formatted_text = markdown2.markdown(formatted_text)

    # Возвращаем HTML, безопасный для вывода
    return formatted_text

def format_datetime(value, fmt='%d.%m.%Y %H:%M'):
    if isinstance(value, datetime):
        return value.strftime(fmt)
    return value

# Регистрируем фильтр форматирования времени
templates.env.filters['datetimeformat'] = format_datetime

# Регистрируем фильтр форматирования блоков кода
templates.env.filters["format_code_blocks"] = format_code_blocks

@app.post("/api/delete-chat/")
async def delete_chat_route(request: Request, user=Depends(get_user)):

    if not user:
        return JSONResponse(status_code=401, content={"error": "Unauthorized"})

    data = await request.json()
    chat_id = data.get("chat_id")
    if not chat_id:
        return {"deletion_status": "missing chat_id"}


    deleted = await delete_chat(user, chat_id)

    if deleted:
        return {"chat_id": chat_id, "deletion_status": "deleted"}
    else:
        return {"chat_id": chat_id, "deletion_status": "not found"}


# === Фоновая задача: удаление устаревших файлов ===
async def cleanup_expired_files():
    while True:
        now = datetime.now(timezone.utc)
        deleted = 0
        for file_path in UPLOAD_DIR.glob("*"):
            if file_path.is_file():
                # Получаем время последней модификации файла как datetime
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                if now - mtime > MAX_FILE_AGE:
                    try:
                        file_path.unlink()
                        deleted += 1
                    except Exception as e:
                        print(f"[CLEANUP] Ошибка удаления {file_path}: {e}")
        if deleted:
            print(f"[CLEANUP] Удалено {deleted} файлов")
        await asyncio.sleep(600)  # каждые 10 минут

# === Фоновая задача: автообновление подписок ===
async def auto_renew_subscriptions():
    while True:
        try:
            await renew_subscriptions()
        except Exception as e:
            print(f"[SUBSCRIPTIONS] Ошибка обновления: {e}")
        await asyncio.sleep(SUBSCRIPTION_RENEW_INTERVAL)



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
