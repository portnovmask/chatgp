from jose import jwt

token = jwt.encode({"user": "test"}, "my_secret_key", algorithm="HS256")
decoded = jwt.decode(token, "my_secret_key", algorithms=["HS256"])

print(decoded)  # Должно вывести: {'user': 'test'}
