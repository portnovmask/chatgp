import json
with open("clean_for_mongo.json", "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as e:
            print(f"Ошибка в строке {i}: {e}")
