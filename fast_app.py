import json
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, Response, Query, Depends, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import router as auth_router
from users import router as users_router
from products import router as products_router
from subscriptions import router as subscription_router, renew_subscriptions
from auth import get_user
import openai
from settings import APY_KEY
from modes import User, get_user_summaries, get_chat_body_by_id, get_last_chat_id, set_chat, reset_chat
import asyncio
# from fastapi_utils.tasks import repeat_every

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

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(products_router)

app.include_router(subscription_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# @app.get("/", response_class=HTMLResponse)
# async def read_root(request: Request):
#    return templates.TemplateResponse("index.html", {"request": request})

client = openai.AsyncOpenAI(api_key=APY_KEY)

# TOKEN_LIMIT = True
#client2 = openai.AsyncOpenAI(api_key=APY_KEY)


async def generate_summary(data):
    logger.info(f"Данные пришли в функцию generate_summary: {data}")
    try:
        response = await client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'user',
                 'content': f"Создай ёмкий заголовок из 2-3 слов на языке оригинала для этого диалога: {data}. "
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, response: Response, user: dict = Depends(get_user), chat_id: str = None,
                new_chat: int = Query(None)):
    if not user:
        return RedirectResponse(url="/authorize", status_code=303)

    user_chat = []
    param = request.cookies.get("param", "basic")

    #await update_user_mode(user, param)
    user_summaries = await get_user_summaries(user)

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
                                       "user_chat": user_chat})


@app.get("/stream")
async def stream(prompt: str = Query(...), user: dict = Depends(get_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не авторизован")
    chat = User(user)

    chat_id = await get_last_chat_id(user) or None
    logger.info(f"Выбранный chat_id stream get_last_chat_id: {chat_id}")
    # Достаем последние 5 сообщений для assistant_content

    assistant_content = await chat.get_last_chat_messages(chat_id)
    logger.info(f"assistant_content stream: {assistant_content[0:15]}\n")

    user_tokens = user.get("tokens", 0)  # Предотвращаем ошибку, если у user нет "tokens"
    request_params = await chat.request_params()
    async def generate_stream(context, hit_limits):
        collected_messages = []
        stream_id = None
        system_content = 'Ты консультант-помощник'

        # Проверка лимита токенов
        if (1000000000 - hit_limits) <= 0:
            logger.info(f"Токенов слишком много: {hit_limits}\n")
            #return

        # GPT запрос
        completion = await client.chat.completions.create(
            model=request_params.get("model", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": request_params.get("content", system_content)},
                {"role": "assistant", "content": context},
                {"role": "user", "content": prompt}
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
                hit_limits += int(chunk.usage.total_tokens)
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

        asyncio.create_task(after_stream_processing(chat, prompt, full_reply_content, chat_id, stream_id, hit_limits))
        logger.info(f"Запустили фоновую функцию из стрима с чат айди: {chat_id}\n")

    return StreamingResponse(generate_stream(assistant_content, user_tokens), media_type="text/event-stream")


@app.get("/authorize")
async def authorize(request: Request, mode: str = "login"):
    return templates.TemplateResponse("authorize.html", {"request": request, "mode": mode})

@app.get("/price")
async def price(request: Request, user: dict = Depends(get_user)):
    return templates.TemplateResponse("price.html", {"request": request, "user": user})



@app.get("/change_param")  #Ручка для выбора параметров
async def change_param(request: Request, user: dict = Depends(get_user), param: str = "basic"):
    response = RedirectResponse(url="/")  # Перенаправляем на корень
    #Логика получения параметра и проверки доступа пользователя к нему
    if user:
        status = await user.get("status")

        if status != "advanced" and param != "basic":
            mode = "basic"
        else:
            mode = param
        response.set_cookie(key="param", value=mode, httponly=True, max_age=3600)  # Меняем куки
    else:
        response = RedirectResponse(url="/authorize")
    return response


@app.get("/get_chat_body")
async def get_chat_body(chat_id: str, user: dict = Depends(get_user), response: Response = None):
    chat_body = await get_chat_body_by_id(user, chat_id)
    await set_chat(user, chat_id)

    if chat_body is None:
        return JSONResponse({"error": "Чат не найден"}, status_code=404)

    response = JSONResponse({"chat_body": chat_body})
    response.set_cookie(key="chat_id_cookie", value=chat_id, path="/", httponly=True, max_age=3600)
    return response


@app.get("/reset_chat")
async def reset_chat_route(response: Response, user: dict = Depends(get_user), new_chat: int = Query(None)):
    if new_chat:
        await reset_chat(user)
        response.delete_cookie("chat_id_cookie")
    return RedirectResponse(url="/", status_code=303)


@app.post("/update_summaries")
async def update_summaries(
        request: Request, user: dict = Depends(get_user)
):
    user_summaries = await get_user_summaries(user)

    return {"summaries": user_summaries}


import re
import html
import markdown2

CODE_BLOCK_RE = re.compile(r"```(.*?)```", re.DOTALL)


@app.post("/format-text/")
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
# Регистрируем фильтр
templates.env.filters["format_code_blocks"] = format_code_blocks



# Запуск фонового обновления подписок
# @app.on_event("startup")
# @repeat_every(seconds=86400)  # Раз в сутки
# async def auto_renew_subscriptions():
#     await renew_subscriptions()



if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
