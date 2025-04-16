# qr_utils.py
import qrcode
from io import BytesIO
import base64

def generate_qr_base64(url: str) -> str:
    qr = qrcode.make(url)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


qr = generate_qr_base64("https://example.com")
with open("test_qr.html", "w") as f:
    f.write(f'<img src="{qr}">')
