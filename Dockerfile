# Используем официальный Python
FROM python:3.12-slim

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    libpq-dev \
    tesseract-ocr \
    libtesseract-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .


# Устанавливаем Python-зависимости
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Открываем порт
EXPOSE 8000

# Запуск uvicorn
CMD ["uvicorn", "fast_app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
