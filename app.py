import streamlit as st
import fitz  # PyMuPDF
import requests
from PIL import Image
import base64
import io
import json
import uuid

# Cấu hình API
GPT4O_API_URL = "https://api.sv2.llm.ai.vn/v1/chat/completions"
GEMINI_API_URL = "https://api.sv2.llm.ai.vn/v1/models/gemini:gemini-2.5-pro-preview-06-05:generate-content"
API_KEY = "sk-j4DkzI7htsVqEZqC272d3b58B0Fb49A183573dD2Fc04F71d"  # Thay bằng API key thật

# Prompt cho GPT-4o
PROMPT_LATEX = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
... (như bạn đã cung cấp ở trên)"""

PROMPT_WORD = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.
... (như bạn đã cung cấp ở trên)"""

PROMPT_GEMINI = "Trong ảnh sau, hãy tìm ra các vùng ảnh minh họa (biểu đồ, hình vẽ, bảng, sơ đồ,...) và trả về danh sách các tọa độ (x, y, width, height) cho từng vùng ảnh đó. Kết quả phải ở dạng JSON như sau: ..."

# Hàm gửi ảnh tới Gemini để tách vùng hình minh hoạ
def detect_image_regions(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT_GEMINI},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}}
            ]
        }]
    }
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.post(GEMINI_API_URL, json=payload, headers=headers)
    try:
        return json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    except:
        return []

# Hàm gửi ảnh sang GPT-4o để sinh LaTeX hoặc Word

def call_gpt4o(image, mode="latex"):
    prompt = PROMPT_LATEX if mode == "latex" else PROMPT_WORD
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "model": "openai:gpt-4o",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ]
        }],
        "temperature": 0.3
    }
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.post(GPT4O_API_URL, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"]

# Hàm xử lý toàn bộ PDF

def process_pdf(uploaded_file, mode):
    results = []
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # Gọi Gemini để phát hiện vùng hình
        regions = detect_image_regions(img)

        # Cắt ảnh minh hoạ nếu có
        for region in regions:
            x, y, w, h = region["x"], region["y"], region["width"], region["height"]
            cropped = img.crop((x, y, x + w, y + h))
            region["image"] = cropped

        # Gửi ảnh gốc sang GPT-4o
        latex_or_word = call_gpt4o(img, mode=mode)

        results.append({"page": i+1, "text": latex_or_word, "images": regions})

    return results

# Streamlit UI
st.title("Chuyển PDF sang LaTeX hoặc Word kèm hình minh hoạ")
uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])
mode = st.selectbox("Chế độ xuất", ["latex", "word"])

if uploaded_file:
    if st.button("Chuyển đổi"):
        with st.spinner("Đang xử lý..."):
            output = process_pdf(uploaded_file, mode)

        for item in output:
            st.subheader(f"Trang {item['page']}")
            st.code(item['text'], language="latex" if mode == "latex" else "markdown")
            for img_data in item["images"]:
                st.image(img_data["image"], caption=img_data["label"], width=300)

        st.success("Xử lý xong!")
