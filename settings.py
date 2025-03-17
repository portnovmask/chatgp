import os
import dotenv

dotenv.load_dotenv('.env')


APY_KEY = os.environ['APY_KEY']
APP_SECRET_KEY = os.environ['APP_SECRET_KEY']
MAIL_USERNAME = os.environ['MAIL_USERNAME']
MAIL_PASSWORD = os.environ['MAIL_PASSWORD']
SQL_USERNAME = os.environ['SQL_USERNAME']
SQL_PASSWORD = os.environ['SQL_PASSWORD']
DB_NAME = os.environ['DB_NAME']
DB_HOST = os.environ['DB_HOST']
GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']

def pri():

    print(os.environ)
    pass
