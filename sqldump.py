import json
from datetime import datetime, UTC

def transform_row(row):
    # Конвертация UNIX timestamp → ISO 8601
    registered_at = None
    if row.get("nowtime"):
        registered_at = datetime.fromtimestamp(int(row["nowtime"]), UTC).isoformat()

    # Собираем документ под Mongo
    return {
        "email": row.get("username"),
        "password": row.get("passw"),
        "registered_at": registered_at,
        "status": row.get("status", "trial"),
        "tokens": 0,
        "original_status": row.get("status", "trial"),
        "auth_provider": "local",
        "oauth_id": None,
        "contact": row.get("username"),  # дублируем email в contact
        "phone": row.get("phone") if row.get("phone") else None
    }

# Загружаем MySQL JSON (экспортирован как массив объектов)
with open("user.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Трансформация
transformed = [transform_row(row) for row in data]

# Сохраняем в newline-delimited JSON для Compass
with open("clean_for_mongo.json", "w", encoding="utf-8") as f:
    for doc in transformed:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")

print(f"✅ Готово! Сконвертировано {len(transformed)} записей.")
