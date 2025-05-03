# qr_utils.py
import qrcode
from io import BytesIO
import base64

import re
import unidecode

def slugify(text: str) -> str:
    text = unidecode.unidecode(text).lower()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def generate_qr_base64(url: str) -> str:
    qr = qrcode.make(url)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

# проверка создания qr кода
# qr = generate_qr_base64("https://example.com")
# with open("test_qr.html", "w") as f:
#     f.write(f'<img src="{qr}">')
