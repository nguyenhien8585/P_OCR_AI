# 📄 OCR PDF/Ảnh bằng GPT-4o (Giống web mẫu)
import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import tempfile
import base64
import requests
import os

# ------------------------------
# 📌 Hàm chuyển PDF thành ảnh
# ------------------------------
def pdf_to_images(pdf_bytes):
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

# ------------------------------
# 📌 Hàm gọi GPT-4o AI.VN
# ------------------------------
def get_prompt(mode):
    if mode == "latex":
        return "Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX. KHÔNG giải thích. KHÔNG bịa thêm."
    else:
        return "Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này. KHÔNG giải thích. KHÔNG bịa thêm."

def ask_gpt_vision(image, mode, api_key):
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

# ------------------------------
# 📌 Hàm tạo file Word
# ------------------------------
def build_docx(text, output_path):
    from docx import Document
    doc = Document()
    for line in text.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    doc.save(output_path)

# ------------------------------
# 🎯 Giao diện Streamlit Web
# ------------------------------
st.set_page_config(page_title="📄 PDF to Word/LaTeX", layout="centered")
st.title("📄 Chuyển PDF hoặc ảnh sang Word/LaTeX bằng GPT-4o")

api_key = st.text_input("🔐 Nhập API Key AI.VN", type="password")
mode = st.radio("Chọn chế độ chuyển đổi:", ["word", "latex"], index=0, format_func=lambda x: "Word (giữ nguyên)" if x == "word" else "LaTeX (soạn đề)")
file = st.file_uploader("📎 Tải lên file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])

if api_key and file:
    with st.spinner("🔄 Đang xử lý ảnh..."):
        if file.type == "application/pdf":
            images = pdf_to_images(file.read())
        else:
            images = [Image.open(file)]

    st.success(f"✅ Đã tải {len(images)} trang ảnh")
    all_text = ""
    for i, img in enumerate(images):
        st.image(img, caption=f"Trang {i+1}", use_column_width=True)
        st.info(f"⏳ GPT-4o đang đọc trang {i+1}...")
        text = ask_gpt_vision(img, mode, api_key)
        all_text += text + "\n"

    st.success("🎉 Đã xử lý xong toàn bộ ảnh!")

    if mode == "latex":
        st.code(all_text, language="latex")
        st.download_button("📥 Tải LaTeX (.tex)", all_text, file_name="output.tex", mime="text/plain")
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            build_docx(all_text, tmp.name)
            st.download_button("📥 Tải Word (.docx)", open(tmp.name, "rb"), file_name="output.docx")
