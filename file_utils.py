import uuid
import base64
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from fastapi import UploadFile, HTTPException
from io import BytesIO
import pytesseract
import logging


logger = logging.getLogger("app_logger")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = 10
MAX_WIDTH, MAX_HEIGHT = 768, 2000
DEFAULT_RESOLUTION = (512, 512)
ALLOWED_FORMATS = {"PNG", "JPEG", "JPG", "WEBP", "GIF"}  # только неанимированные
FORBIDDEN_TEXT_KEYWORDS = {"sample", "preview",
                           "demo", "nsfw", "company",
                           "logo", "Stockphoto", "Shutterstock",
                           "iStock", "Depositphotos",
                           "Pixels", "Freepik", "Pixabay"}


async def save_uploaded_image(file: UploadFile, status: int) -> str:
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        logger.info("Файл слишком большой")
        return "Файл слишком большой"

    try:
        img = Image.open(BytesIO(contents))
        format_upper = img.format.upper()

        if format_upper not in ALLOWED_FORMATS:
            logger.info("Недопустимый формат изображения")
            return "Недопустимый формат изображения"


        width, height = img.size
        if width > MAX_WIDTH or height > MAX_HEIGHT or status < 1:
            img = img.resize(DEFAULT_RESOLUTION)
            logger.info(f"При загрузке файла превышено максимальное разрешение")

        # OCR-проверка на запрещённые ключевые слова
        extracted_text = pytesseract.image_to_string(img)
        for word in FORBIDDEN_TEXT_KEYWORDS:
            if word.lower() in extracted_text.lower():
                logger.info("Изображение содержит запрещённый текст")
                return "Изображение содержит запрещённый текст"



        # Генерация безопасного имени
        extension = format_upper.lower()
        if extension == "jpeg":
            extension = "jpg"
        filename = f"{uuid.uuid4().hex}.{extension}"
        save_path = UPLOAD_DIR / filename

        img.save(save_path)
        return str(save_path)

    except UnidentifiedImageError:
        logger.info("Файл не является изображением")
        return "Файл не является изображением"




def image_to_base64(path: str) -> str:
    file_path = Path(path)
    if not file_path.is_file():
        logger.info("Файл не найден")
        raise FileNotFoundError("Файл не найден")

    try:
        with Image.open(file_path) as img:
            detected_format = img.format.lower()
            extension = file_path.suffix.lower().lstrip(".")

            if extension == "jpg":
                extension = "jpeg"
            if detected_format == "jpg":
                detected_format = "jpeg"

            if extension != detected_format:
                file_path.unlink(missing_ok=True)
                logger.info("Формат изображения не соответствует расширению, файл удалён")
                raise ValueError("Формат изображения не соответствует расширению, файл удалён")

        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{extension};base64,{encoded}"

    except UnidentifiedImageError:
        file_path.unlink(missing_ok=True)
        logger.info("Файл повреждён и удалён")
        raise ValueError("Файл повреждён и удалён")
