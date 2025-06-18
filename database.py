#import certifi
#import asyncio
from pymongo import AsyncMongoClient
from settings import DB_NAME, MONGO_URL

#MONGO_URL = DB_HOST
#email = 'sophie_turner@gameofthron.es'
#client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL,tlsCAFile=certifi.where())
client = AsyncMongoClient(MONGO_URL) # ,tlsCAFile=certifi.where())
db = client.get_database(DB_NAME)


# Коллекции
tokens = db.get_collection("tokens")
blog_posts = db.get_collection("blog_posts")
users = db.get_collection("users")
user_data = db.get_collection("user_data")
chats = db.get_collection("chats")



# Создание индексов
async def create_indexes():
    await tokens.create_index("email", unique=True)
    await users.create_index("email", unique=True)
    await users.create_index("subscription.pending_activation_date")
    await user_data.create_index("email", unique=True)
    await chats.create_index([("user_email", 1), ("created_at", -1)])

# Инициализация базы данных
async def init_db():
    await create_indexes()
# test = db.get_collection("tokens")
#
# async def create_indexes():
#     await test.create_index("email", unique=True)
#
# # Вызывать при старте приложения
# async def init_db():
#     await create_indexes()
# Асинхронная функция для получения данных
# async def get_users():
#     try:
#         dbtest = await test.find_one({"email": email})
#         if dbtest is None:
#             print("User not found")
#         else:
#             print(dbtest["name"])
#     except Exception as e:
#         print(f"Error occurred: {e}")
#
# # Запуск асинхронной функции
#asyncio.run(init_db())

