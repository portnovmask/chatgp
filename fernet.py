from cryptography.fernet import Fernet

key = Fernet.generate_key()
print(key.decode())  # Скопируй это и сохрани в .env
