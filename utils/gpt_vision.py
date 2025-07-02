import requests
import base64
from PIL import Image
import io

def get_prompt(mode):
    if mode == "latex":
        return "Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau: (rút gọn...)"
    else:
        return "Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này. KHÔNG bịa thêm."

def ask_gpt_vision(image_path, mode, api_key):
    img = Image.open(image_path)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode()

    url = "https://api.sv2.llm.ai.vn/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "openai:gpt-4o",
        "messages": [
            {"role": "system", "content": "Bạn là OCR AI."},
            {"role": "user", "content": [
                {"type": "text", "text": get_prompt(mode)},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]}
        ],
        "temperature": 0.2,
        "max_tokens": 4096
    }

    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        return res.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"GPT API lỗi: {res.status_code} {res.text}")
