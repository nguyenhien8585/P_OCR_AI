def get_prompt(mode):
    if mode == "latex":
        return "Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX. Nếu có hình minh hoạ, đánh dấu tại vị trí bằng dạng: <<image_pageX_Y.png>>. KHÔNG giải thích. KHÔNG bịa thêm."
    else:
        return "Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này. Nếu có hình minh hoạ, đánh dấu tại vị trí bằng dạng: <<image_pageX_Y.png>>. KHÔNG giải thích. KHÔNG bịa thêm."

def ask_gpt_vision(image, mode, api_key):
    import base64, io, requests
    from PIL import Image
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode()

    url = "https://api.sv2.llm.ai.vn/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    payload = {
        "model": "openai:gpt-4o",
        "messages": [
            {"role": "system", "content": "Bạn là AI chuyên OCR học thuật."},
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
        raise Exception(f"Lỗi GPT-4o AI.VN: {res.status_code} {res.text}")
