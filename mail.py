from email.message import EmailMessage
import aiosmtplib
import httpx
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Request, BackgroundTasks, Form
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from models.users import users_collection
from settings import EMAIL_CONFIRM_KEY, CONFIRM_SALT, RECAPTCHA_SECRET, LOGO_URL, BASE_URL
import logging
from fastapi.responses import HTMLResponse, RedirectResponse
from fernet_utils import encrypt_email

router = APIRouter(prefix="/api")

templates = Jinja2Templates(directory="templates")

logger = logging.getLogger("app_logger")


# Отправка почты

# Шаблон блоков универсального html письма
class EmailTemplate:
    def __init__(self, **kwargs):
        self.data = {
            "logo_url": kwargs.get("logo_url"),
            "header_link": kwargs.get("header_link"),
            "header_text": kwargs.get("header_text"),
            "description": kwargs.get("description"),
            "recipient_name": kwargs.get("recipient_name"),
            "body_text": kwargs.get("body_text"),
            "action_label": kwargs.get("action_label"),
            "action_url": kwargs.get("action_url"),
            "footer_text": kwargs.get("footer_text"),
            "date": kwargs.get("date") or datetime.now(timezone.utc).strftime("%B %d, %Y")
        }

    def render(self) -> str:
        template = templates.get_template("email_template.html")
        return template.render(**self.data)



def generate_confirmation_token(email: str):
    serializer = URLSafeTimedSerializer(EMAIL_CONFIRM_KEY)
    return serializer.dumps(email, salt=CONFIRM_SALT)




def confirm_token(token: str, expiration=45000):
    serializer = URLSafeTimedSerializer(EMAIL_CONFIRM_KEY)
    try:
        email = serializer.loads(token, salt=CONFIRM_SALT, max_age=expiration)
    except Exception:
        return None
    return email


# SMTP клиент
async def send_email(user: dict, subject: str, html_content: str):
    if not user.get("contact") or user.get("contact") == "not_confirmed":
        to_email = user.get("email")
    else:
        to_email = user.get("contact")
    message = EmailMessage()
    message["From"] = "noreply@example.com"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content("HTML only email", subtype="plain")
    message.add_alternative(html_content, subtype="html")


    # await aiosmtplib.send(
    #     message,
    #     hostname="smtp.example.com",
    #     port=587,
    #     start_tls=True,
    #     username="your_username",
    #     password="your_password",
    # )

    await aiosmtplib.send(
        message,
        hostname="mailhog",
        port=1025,  # порт MailHog
    )


# Универсальный маршрут для отправки писем
@router.post("/send-email/")
async def send_email_route(background_tasks: BackgroundTasks, email_to: str = Form(...)):
    email = EmailTemplate(
        logo_url=LOGO_URL,
        header_link=BASE_URL,
        header_text="Добро пожаловать!",
        description="Это письмо содержит важную информацию.",
        recipient_name="Иван Иванов",
        body_text="Спасибо за регистрацию на нашем сервисе. Пожалуйста, подтвердите вашу почту.",
        action_label="Подтвердить Email",
        action_url="https://example.com/confirm?token=abc123",
        footer_text="Если вы не регистрировались — просто проигнорируйте это письмо."
    )
    user = {"email": email_to or "ivan@example.com"}
    html = email.render()
    background_tasks.add_task(send_email, user, "Добро пожаловать!", html)
    return {"message": "Письмо отправлено"}

# Контактная форма

EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")


# Дефолтный маршрут контактной формы
@router.get("/contact", response_class=HTMLResponse)
async def contact_form(request: Request):
    return templates.TemplateResponse("contact.html", {
        "request": request,
        "form_time": datetime.now(timezone.utc).isoformat()
    })


# Маршрут после отправки контактной формы с проверкой каптчи, пустого поля, времени заполнения, длины строки
@router.post("/contact/submit", response_class=HTMLResponse)
async def submit_contact_form(
        request: Request,
        name: str = Form(...),
        email: str = Form(...),
        message: str = Form(...),
        form_time: str = Form(...),
        honeypot: str = Form(""),
        recaptcha_token: str = Form(...),
        background_tasks: BackgroundTasks = None
):
    error = None
    success_message = None

    # 🐜 Anti-bot (honeypot, timing)
    if honeypot:
        error = "Обнаружен бот."
    else:
        try:
            form_dt = datetime.fromisoformat(form_time)
            if (datetime.now(timezone.utc) - form_dt).total_seconds() < 5:
                error = "Форма отправлена слишком быстро."
        except Exception:
            error = "Ошибка времени отправки формы."

    # 📧 Email format
    if not error and not EMAIL_REGEX.match(email):
        error = "Некорректный email."

    # ✏️ Message length
    if not error and len(message.strip()) < 50:
        error = "Сообщение должно содержать не менее 50 символов."

    # 🔐 reCAPTCHA
    if not error:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": RECAPTCHA_SECRET, "response": recaptcha_token}
            )
            result = r.json()
            if not result.get("success") or result.get("score", 0) < 0.5:
                error = "Проверка reCAPTCHA не пройдена."

    if not error:
        email_template = EmailTemplate(
            logo_url=LOGO_URL,
            header_link=BASE_URL,
            header_text=f"Новое сообщение от {name}",
            description="Сообщение из контактной формы",
            recipient_name="Администратор",
            body_text=f"Письмо от {name} ({email}):\n\n{message}",
            action_label="Ответить",
            action_url=f"mailto:{email}",
            footer_text="Контактная форма сайта"
        )
        user = {"email": "support@chatgp.ru", "contact": "support@chatgp.ru"}
        html = email_template.render()
        background_tasks.add_task(send_email, user, f"Новое сообщение от {name}", html)
        success_message = "Сообщение отправлено. Спасибо!"
        # очищаем поля формы
        name = ""
        email = ""
        message = ""

    return templates.TemplateResponse("contact.html", {
        "request": request,
        "form_time": datetime.now(timezone.utc).isoformat(),
        "message": success_message,
        "error": error,
        "name": name,
        "email": email,
        "message_text": message
    })



# Подтверждение email

@router.get("/confirm-notice", response_class=HTMLResponse)
async def confirm_notice(request: Request):

    title = "Подтвердите почту"
    header = "Подтвердите электронную почту"
    subheader = "На указанный вами email отправлена ссылка для подтверждения."
    message = "Для пользования сервисом необходимо подтвердить email."
    action = "Я указал неверный email"

    return templates.TemplateResponse("confirm-notice.html", {"request": request,
                                                              "title": title,
                                                              "header": header,
                                                              "subheader": subheader,
                                                              "message": message, "action": action}
                                      )

@router.get("/confirm-email")
async def confirm_email(request: Request, token: str):
    email = confirm_token(token)
    if not email:
        title = "Подтверждение почты - ошибка"
        header = "Ошибка подтверждения электронной почты"
        subheader = "Срок действия ссылки истёк или она недействительна."
        message = "Вернитесь на главную страницу, выполните вход еще раз, вам будет отправлен повторный email с ссылкой."
        action = "Вернуться на главную"

        return templates.TemplateResponse("confirm-notice.html", {"request": request,
                                                                  "title": title,
                                                                  "header": header,
                                                                  "subheader": subheader,
                                                                  "message": message, "action": action}, status_code=400
                                          )
    boosty = encrypt_email(email)
    result = await users_collection.update_one(
        {"email": email, "contact": "not_confirmed"},
        {"$set": {"contact": email,
         "boosty_code": boosty}
        }
    )

    if result.modified_count == 1:
        title = "Подтверждение почты"
        header = "Ваш email подтверждён!"
        subheader = "Поздравляем! Вы успешно подтвердили электронную почту!"
        message = "Всё готово, теперь вы можете начать пользоваться сервисом полноценно."
        action = "Вернуться на главную"

        return templates.TemplateResponse("confirm-notice.html", {"request": request,
                                                                  "title": title,
                                                                  "header": header,
                                                                  "subheader": subheader,
                                                                  "message": message, "action": action}
                                          )
    else:
        title = "Ошибка подтверждения почты"
        header = "Ваш email уже был подтверждён или не найден"
        subheader = "Это происходит, еслиЖ"
        message = "Вы уже подтверждали вашу электронную почту или указали неверный email."
        action = "Попробовать еще раз"

        return templates.TemplateResponse("confirm-notice.html", {"request": request,
                                                                  "title": title,
                                                                  "header": header,
                                                                  "subheader": subheader,
                                                                  "message": message, "action": action}, status_code=400
                                          )
