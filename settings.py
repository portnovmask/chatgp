import os
import dotenv
from pathlib import Path

dotenv.load_dotenv('.env')

ADMIN = os.getenv('ADMIN')
ADMIN_PIN = os.getenv('ADMIN_PIN')
APY_KEY = os.environ['APY_KEY']
APP_SECRET_KEY = os.environ['APP_SECRET_KEY']
CSRF_SECRET_KEY = os.environ['CSRF_SECRET_KEY']
EMAIL_CONFIRM_KEY = os.environ['EMAIL_CONFIRM_KEY']
CONFIRM_SALT = os.environ['CONFIRM_SALT']
FERNET_KEY = os.environ['FERNET_KEY']
MAIL_USERNAME = os.environ['MAIL_USERNAME']
MAIL_PASSWORD = os.environ['MAIL_PASSWORD']
SQL_USERNAME = os.environ['SQL_USERNAME']
SQL_PASSWORD = os.environ['SQL_PASSWORD']
#DB_NAME = os.environ['DB_NAME']
DB_NAME = os.environ['MONGO_INITDB_DATABASE']
# DB_HOST = os.environ['DB_HOST']


DB_USER = os.getenv("MONGO_INITDB_ROOT_USERNAME")
DB_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "mongo")  # имя сервиса в docker-compose

MONGO_URL = f"mongodb://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:27017"

GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
GOOGLE_CLIENT_SECRET = os.environ['GOOGLE_CLIENT_SECRET']
GOOGLE_REDIRECT_URI = os.environ['GOOGLE_REDIRECT_URI']
GOOGLE_AUTH_URL = os.environ['GOOGLE_AUTH_URL']
GOOGLE_TOKEN_URL = os.environ['GOOGLE_TOKEN_URL']
GOOGLE_USERINFO_URL = os.environ['GOOGLE_USERINFO_URL']

YANDEX_CLIENT_ID = os.environ['YANDEX_CLIENT_ID']
YANDEX_CLIENT_SECRET = os.environ['YANDEX_CLIENT_SECRET']
YANDEX_REDIRECT_URI = os.environ['YANDEX_REDIRECT_URI']
YANDEX_AUTH_URL = os.environ['YANDEX_AUTH_URL']
YANDEX_TOKEN_URL = os.environ['YANDEX_TOKEN_URL']
YANDEX_USERINFO_URL = os.environ['YANDEX_USERINFO_URL']

TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_BOT_USERNAME = os.environ['TELEGRAM_BOT_USERNAME']

VK_CLIENT_ID = os.environ['VK_CLIENT_ID']
VK_CLIENT_SECRET = os.environ['VK_CLIENT_SECRET']
VK_REDIRECT_URI = os.environ['VK_REDIRECT_URI']
VK_AUTH_URL = os.environ['VK_AUTH_URL']
VK_TOKEN_URL = os.environ['VK_TOKEN_URL']
VK_USERINFO_URL = os.environ['VK_USERINFO_URL']
TON_SECRET_KEY = os.environ['TON_SECRET_KEY']
TON_WALLET = os.environ['TON_WALLET']
TON_API_KEY = os.environ['TON_API_KEY']
RECAPTCHA_SECRET = os.environ['RECAPTCHA_SECRET']
LOGO_URL = "https://ketome.ru/wp-content/uploads/2025/04/black-white-minimalist-signature-personal-brand-logo.png"
BASE_URL = "https://chatgp.ru"
LEVELS = ["trial", "basic", "advanced", "business", "pro", "premium"]
ATTEMPT_LIMITS = [5, 30, 100, 500, 300, 500]
PRETTY_NAMES = {
    "trial": "Базовый",
    "basic": "Оптимум",
    "advanced": "Фрилансер",
    "business": "Бизнес",
    "pro": "Мыслитель",
    "premium": "Премиум"
}
PRICES = [0, 18, 50, 140, 160, 500]
UPLOAD_DIR = Path("tmp/uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def pri():

    print(os.environ)
    pass
