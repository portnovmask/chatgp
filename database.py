import certifi
#import asyncio
import motor.motor_asyncio
from settings import DB_HOST

MONGO_URL = DB_HOST
#email = 'sophie_turner@gameofthron.es'
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL,tlsCAFile=certifi.where())
db = client.get_database("chatgp_base")
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

