from cryptography.fernet import Fernet
from settings import B_FERNET_KEY


# key = Fernet.generate_key()
# print(key.decode())  # Скопируй это и сохрани в .env

fernet = Fernet(B_FERNET_KEY)

def encrypt_email(email: str) -> str:
    return fernet.encrypt(email.encode()).decode()


def decrypt_email(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()