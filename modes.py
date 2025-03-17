import json
from models.user_data import users_data_collection
from models.users import users_collection
from datetime import datetime, timezone

async def update_user_mode(user, mode: str):

    await users_data_collection.update_one(
        {"email": user.get("email")},
        {"$set": {"mode.current_mode": mode}}
    )



async def set_chat(user, chat_id: str):
    if user and chat_id != "new":
        await users_data_collection.update_one(
            {"email": user.get("email")},
            {"$set": {"mode.current_chat": chat_id}}
        )
    else:
        print("set_chat - было выбрано создание нового чата, его айди установится после стрима\n")
        return


async def reset_chat(user):
    """Обнуляет текущее значение current_chat для пользователя."""
    await users_data_collection.update_one(
        {"email": user.get("email")},
        {"$set": {"mode.current_chat": "new"}}
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

    if user["mode"]["current_chat"]:
        return user["mode"]["current_chat"]

    # Получаем список чатов и сортируем по времени (если порядок не гарантирован)
    if recent_chat and user["mode"]["current_chat"] != "new":
        last_chat = max(user["chats"], key=lambda chat: chat["chat_time"])  # Берем самый последний
        return last_chat["chat_id"]

    return None


async def get_chat_body_by_id(user, chat_id):
    data = await users_data_collection.find_one(
        {"email": user.get("email")},
        {"chats.chat_body": 1, "chats.chat_id": 1, "_id": 0}  # ✅ Теперь запрашиваем chat_id тоже!
    )

    if not data or "chats" not in data:
        return None  # ✅ Возвращаем None, если чатов нет

    # ✅ Безопасно проверяем наличие chat_id перед сравнением
    chat_body = next((chat.get("chat_body") for chat in data["chats"] if chat.get("chat_id") == chat_id), None)

    return chat_body






class User:


    def __init__(self, user):
        self.user = user
        # self.details = []
    #     self.history = []  # Глобальный список для хранения данных
    #     self.MAX_SIZE = 5  # Ограничение по количеству элементов
    #
    # async def add_to_history(self, prompt, response):
    #     """Добавляет новый элемент в список, удаляя старые по FIFO."""
    #     current_time = datetime.now(timezone.utc).isoformat()
    #     value = f"Пользователь:{prompt} \n Ответ ЛЛМ модели: {response} \n временная метка: {current_time}"
    #     if len(self.history) >= self.MAX_SIZE:
    #         self.history.pop(0)  # Удаляем первый элемент (FIFO)
    #     self.history.append(value)  # Добавляем новый элемент
    #     print (f"Сам текст: {value} \n")
    #
    #     #return "\n".join(reversed(self.history))
    #
    # async def get_formatted_history(self):
    #     """Возвращает элементы в порядке LIFO, разделённые переносами строк."""
    #     print("\n".join(reversed(self.history)) if self.history else 'no history')
    #     print(f"Сам список: {self.history} \n")
    #     return "\n".join(reversed(self.history)) if self.history else ''  # Возвращаем элементы в порядке LIFO
    #


    async def get_current_chat_id(self, chat_id: str):
        data = await users_data_collection.find_one(
            {"email": self.user.get("email")},
            {"chats.chat_id": 1, "_id": 0}  # Запрашиваем только поле chat_id из массива chats
        )

        if not data or "chats" not in data:
            print(f"функция get_current_chat_id не нашла чат в базе\n")
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
            {"mode.current_mode": 1}
        )
        return me_data if me_data else None

    async def add_to_chat_db(self, prompt: str, body: str, chat_id: str = "new", stream_id: str = None,
                             summary: str = "Без названия"):
        chat_update = {"prompt": prompt, "body": body}
        current_time = datetime.now(timezone.utc).isoformat()  # Актуальное время
        print(f"Полный ответ в функции add_to_chat_db: {body[10:20]}...\n")
        print(f"chat_id в функции add_to_chat_db: {chat_id}\n")
        print(f"stream_id в функции add_to_chat_db: {stream_id}\n")
        try:
            result = await users_data_collection.update_one(
                {"email": self.user.get("email"), "chats.chat_id": chat_id},  # Проверяем, есть ли этот чат
                {
                    "$push": {"chats.$.chat_body": chat_update},  # Добавляем сообщение в chat_body
                    "$set": {"chats.$.chat_time": current_time}  # Обновляем chat_time
                }
            )

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
                        "$set": {"mode.current_chat": stream_id},  # Обновляем current_chat
                        "$push": {"chats": chat_entry}  # Добавляем новый чат в массив chats
                    }
                )

                print(f"создан новый чат add_to_chat_db {stream_id}\n")
        except Exception as e:
            print(f"ошибка добавления данных в чат: {e}")
            return





    async def update_token_count_db(self, token_count: int):

        await users_collection.update_one(
            {"email": self.user.get("email")},
            {"$inc": {"tokens": token_count}}
        )

    # async def format_request_str(self, params: dict, user_content: str = "Представься и поздоровайся"):
    #
    #     request_str = f'''model="{params.get("model", "gpt-4o-mini")}",
    # messages={json.dumps([
    #     {"role": "system", "content": params.get("content", "Ты ассистент")},
    #     {"role": "user", "content": user_content}
    # ], ensure_ascii=False)},
    # temperature={params.get("temperature", 0.2)}'''
    #
    #     if params.get("stream", True):  # Если stream=True, добавляем stream и stream_options
    #         request_str += f''',
    # stream=True,
    # stream_options={json.dumps(params.get("stream_options", {"include_usage": True}), ensure_ascii=False)}'''
    #
    #     return request_str

# self.modes = {
#         "basic" : {
#             "model": "gpt-4o-mini",
#             "messages": [
#                 {"role": "system", "content": "Ты ассистент."}
#             ],
#             "temperature": 0.5,
#             "stream": True,
#             "stream_options": {"include_usage": True}
#         },
#         "translator" : {
#             "model": "gpt-4o-mini",
#             "messages": [
#                 {"role": "system", "content": "Ты профессиональный переводчик и знаешь многие популярные языки. Пожалуйста, всегда уточняй задание: язык исходника и язык перевода. Будь в меру точен и креативен, будь внимателен к терминам, именам, датам и прочим важным деталям. Прошу тебя использовать стиль в соответствие с исходным текстом. Для общения с пользователем твой базовый язык - русский, переходи на английский только при необходимости или по запросу пользователя. Если уточнения не требуются, то в ответе пользователю должен быть только текст перевода согласно заданию."}
#             ],
#             "temperature": 0.4,
#             "stream": True,
#             "stream_options": {"include_usage": True}
#         }
# }