from pymongo import UpdateOne
import logging
from models.user_data import users_data_collection
from models.users import users_collection
from datetime import datetime, timezone


logger = logging.getLogger("app_logger")

async def update_user_mode(user, mode: str):

    await users_data_collection.update_one(
        {"email": user.get("email")},
        {"$set": {"mode.$[].current_mode": mode}}
    )



async def set_chat(user, chat_id: str):
    if user and chat_id != "new":
        await users_data_collection.update_one(
            {"email": user.get("email"), "mode.current_chat": {"$exists": True}},
            {"$set": {"mode.$[].current_chat": chat_id}}  # ✅ Обновляем current_chat во всех объектах массива mode
        )
    else:
        logger.info("set_chat - было выбрано создание нового чата, его айди установится после стрима\n")
        return


async def reset_chat(user):
    """Обнуляет текущее значение current_chat для пользователя."""
    await users_data_collection.update_one(
            {"email": user.get("email"), "mode.current_chat": {"$exists": True}},
            {"$set": {"mode.$[].current_chat": "new"}}  # ✅ Обновляем current_chat во всех объектах массива mode
        )



async def get_user_summaries(user):
    data = await users_data_collection.find_one(
        {"email": user.get("email")},
        {"chats.chat_summary": 1, "chats.chat_id": 1, "chats.chat_time": 1, "_id": 0}  # Запрашиваем нужные поля
    )

    if not data or "chats" not in data:
        return []  # Если у пользователя нет чатов, возвращаем пустой список

    # Извлекаем, сортируем по chat_time в порядке убывания и создаем список summaries
    summaries = sorted(
        [{"summary": chat.get("chat_summary", "Без названия"),  #  Безопасно извлекаем summary
          "chat_id": chat.get("chat_id"),  #  Аналогично для chat_id
          "chat_time": chat.get("chat_time")}  # Аналогично для chat_time
         for chat in data["chats"]],
        key=lambda chat: chat["chat_time"] if chat["chat_time"] else "",  # ✅ Если chat_time = None, сортируем в конец
        reverse=True  # Сортируем от последнего к первому
    )

    return summaries



async def get_last_chat_id(user, recent_chat = False):
    user = await users_data_collection.find_one(
        {"email": user.get("email")},
        {"mode.current_chat": 1, "chats.chat_id": 1, "chats.chat_time": 1, "_id": 0}  # Запрашиваем только нужные поля
    )

    if not user or "chats" not in user or not user["chats"]:
        return None  # Если у пользователя нет чатов, возвращаем None

    if user["mode"][0]["current_chat"]:
        return user["mode"][0]["current_chat"]

    # Получаем список чатов и сортируем по времени (если порядок не гарантирован)
    if recent_chat and user["mode"][0]["current_chat"] != "new":
        last_chat = max(user["chats"], key=lambda chat: chat["chat_time"])  # Берем самый последний
        return last_chat["chat_id"]

    return None


async def get_chat_body_by_id(user, chat_id):
    data = await users_data_collection.find_one(
        {"email": user.get("email")},
        {"chats.chat_body": 1, "chats.chat_id": 1, "_id": 0}  # ✅ Теперь запрашиваем chat_id тоже!
    )

    if not data or "chats" not in data:
        return None  #  Возвращаем None, если чатов нет

    #  Безопасно проверяем наличие chat_id перед сравнением
    chat_body = next((chat.get("chat_body") for chat in data["chats"] if chat.get("chat_id") == chat_id), None)

    return chat_body






class User:


    def __init__(self, user):
        self.user = user
        self.modes = {
            "trial": {
                "model": "gpt-4o-mini",
                "system": "Ты ассистент, но стараешься отвечать кратко и только по делу. Предлагаешь привести примеры или дать дополнительные разъяснения, прежде чем углубляться в подробности.",
                "token_limit": 10000000,
                "temperature": 0.3,
                "4o_usage": 0
            },
            "basic": {
                "model": "gpt-4o-mini",
                "system": "Ты ассистент и всегда рад помочь найти нужную информацию и подсказать возможные решения. Даёшь развёрнутые ответы с примерами.",
                "token_limit": 100000000,
                "temperature": 0.2,
                "4o_usage": 5
            },
            "pro": {
                "model": "gpt-4o",
                "system": "Ты ассистент. Отвечаешь по существу вопроса. Предлагаешь привести примеры или дать дополнительные разъяснения, прежде чем углубляться в подробности.",
                "token_limit": 10000000,
                "temperature": 0.2,
                "4o_usage": 40
            },
            "premium": {
                "model": "gpt-4o",
                "system": "Ты ассистент. Отвечаешь по существу вопроса. Предлагаешь привести примеры или дать дополнительные разъяснения, прежде чем углубляться в подробности.",
                "token_limit": 100000000,
                "temperature": 0.2,
                "4o_usage": 150
            },
            "error_code": {
                "model": "gpt-4o-mini",
                "system": "Ты ассистент",
                "token_limit": 1000000,
                "temperature": 0.2
            },
            "attorney": {
                "model": "gpt-4o-mini",
                "system": "Ты адвокат, опытный советник по вопросам права. Пользователь - твой клиент и ты защищаешь его интересы в правовом поле.",
                "token_limit": 1000000,
                "temperature": 0.4
            },
            "coder": {
                "model": "gpt-4o-mini",
                "system": "Ты практикующий программист с опытом, чётко определяешь задачу, подходящий алгоритм и пишешь код. Ты используешь как проверенные методы, так и новые подходы. А главное - ты можешь доступно объяснить свой код.",
                "token_limit": 1000000,
                "temperature": 0.1
            },
            "translator": {
                "model": "gpt-4o-mini",
                "system": "Ты профессиональный переводчик и знаешь многие популярные языки. Пожалуйста, всегда уточняй задание: язык исходника и язык перевода. Будь в меру точен и креативен, будь внимателен к терминам, именам, датам и прочим важным деталям. Прошу тебя использовать стиль в соответствие с исходным текстом. Для общения с пользователем твой базовый язык - русский, переходи на английский только при необходимости или по запросу пользователя. Если уточнения не требуются, то в ответе пользователю должен быть только текст перевода согласно заданию.",
                "token_limit": 1000000,
                "temperature": 0.5,

             },
            "creator": {
                "model": "gpt-4o-mini",
                "system": "Ты креативщик, редактор, писатель. Ты предлагаешь улучшения текста, исправления синтаксиса, пунктуации и стилистики. Твой язык по умолчанию - русский. Если язык запроса отличается от русского, то ты продолжаешь на языке запроса. Твоя основная задача сделать текст более читаемым, захватывающим внимание и передающим идею.",
                "token_limit": 1000000,
                "temperature": 0.9
            },
        }

    async def refresh(self):
        """синхронизирует изменения в бд с объектами в оперативной памяти"""
        email = self.user.get("email")
        self.user = await users_collection.find_one({"email": email})


    async def get_current_chat_id(self, chat_id: str):
        data = await users_data_collection.find_one(
            {"email": self.user.get("email")},
            {"chats.chat_id": 1, "_id": 0}  # Запрашиваем только поле chat_id из массива chats
        )

        if not data or "chats" not in data:
            logger.info(f"функция get_current_chat_id не нашла чат в базе\n")
            return None  # Если данные отсутствуют или нет поля chats

        # Получаем список всех chat_id у пользователя
        chat_ids = [chat["chat_id"] for chat in data["chats"] if "chat_id" in chat]

        # Проверяем, есть ли переданный chat_id в этом списке
        return chat_id if chat_id in chat_ids else None




    async def get_last_chat_messages(self, chat_id: str, count: int = 10):
        """Возвращает последние count сообщений из chat_body указанного чата."""

        data = await users_data_collection.find_one(
            {"email": self.user.get("email"), "chats.chat_id": chat_id},  # Ищем пользователя с нужным chat_id
            {"chats.$": 1, "_id": 0}  # Берем только соответствующий чат
        )

        if not data or "chats" not in data or not data["chats"]:
            return ""

        chat_body = data["chats"][0].get("chat_body", [])[-count:]  # Берем последние count сообщений

        return "\n".join([f"Пользователь: {msg['prompt']} \nОтвет LLM модели: {msg['body']}" for msg in chat_body])

    async def get_user_mode_from_db(self):
        me_data = await users_data_collection.find_one(
            {"email": self.user.get("email")},
            {"mode": 1, "_id": 0}  #  Запрашиваем весь массив mode
        )

        if not me_data or not me_data.get("mode"):
            return None  # Если mode отсутствует

        return me_data["mode"][0].get("current_mode")  #  Берём current_mode из первого элемента массива

    async def add_to_chat_db(self, prompt: str, body: str, chat_id: str = "new", stream_id: str = None,
                             summary: str = "Без названия"):
        chat_update = {"prompt": prompt, "body": body}
        current_time = datetime.now(timezone.utc).isoformat()  # Актуальное время
        logger.info(f"def add_to_chat_db - Полный ответ в функции add_to_chat_db: {body[0:15]}...\n")
        logger.info(f"def add_to_chat_db - chat_id в функции add_to_chat_db: {chat_id}\n")
        logger.info(f"def add_to_chat_db - stream_id в функции add_to_chat_db: {stream_id}\n")
        try:
            result = await users_data_collection.update_one(
                {"email": self.user.get("email"), "chats.chat_id": chat_id},  # Проверяем, есть ли этот чат
                {
                    "$push": {"chats.$.chat_body": chat_update},  # Добавляем сообщение в chat_body
                    "$set": {"chats.$.chat_time": current_time}  # Обновляем chat_time
                }
            )
            await self.refresh()

            if result.matched_count == 0 and stream_id:  # Если чат не найден, создаем новый
                chat_entry = {
                    "chat_id": stream_id,
                    "chat_time": current_time,  # Устанавливаем текущее время
                    "chat_summary": summary,
                    "chat_body": [chat_update]  # Новый список сообщений
                }
                await users_data_collection.update_one(
                    {"email": self.user.get("email")},
                    {
                        "$set": {"mode.$[].current_chat": stream_id},  # Обновляем current_chat
                        "$push": {"chats": chat_entry}  # Добавляем новый чат в массив chats
                    }
                )
                await self.refresh()

                logger.info(f"def add_to_chat_db - создан новый чат add_to_chat_db {stream_id}\n")
        except Exception as e:
            logger.info(f"def add_to_chat_db - ошибка добавления данных в чат: {e}")
            return





    async def update_token_count_db(self, token_count: int):
        now = datetime.now(timezone.utc)

        if not self.user:
            return
        updates = []
        stat = self.user.get("status")
        token_limit  = self.modes[stat].get("token_limits")
        tokens = self.user.get("tokens", 0)
        email = self.user.get("email")
        original_status = self.user.get("original_status", "trial")
        if stat == "trial" and self.user.get("trial_expires_at"):
            trial_end = self.user["trial_expires_at"]
            if now > trial_end:
                updates.append(UpdateOne(
                    {"email": email},
                    {"$set": {"status": original_status},
                     "$unset": {"original_status": "", "trial_expires_at": ""}}
                ))

        updates.append(UpdateOne(
            {"email": email},
            {"$inc": {"tokens": token_count}}
        ))

        # Проверяем, нужно ли перевести пользователя в trial
        new_token_count = (tokens or 0) + (token_count or 0)
        if new_token_count >= token_limit and stat != "trial":
            end_of_day = now.replace(hour=11, minute=59, second=59, microsecond=0)
            updates.append(UpdateOne(
                {"email": email},
                {"$set": {
                    "tokens": 0,
                    "status": "trial",
                    "original_status": stat,
                    "trial_expires_at": end_of_day
                }}
            ))

        if updates:
            await users_collection.bulk_write(updates)
            await self.refresh()

    async def request_params(self, status):

        params=self.modes.get(status)
        model=params.get("model", "gpt-4o-mini")
        system=params.get("content", "Ты ассистент")
        token_limits=params.get("tokens", 1000000)
        temp=params.get("temperature", 0.2)
        reasoning=params.get("4o_usage", 0)

        request_params = {"model":model, "system":system, "token_limits":token_limits, "temperature":temp, "reasoning":reasoning}


        return request_params

