import streamlit as st
import requests
import base64
import os
import tempfile
from PIL import Image
from io import BytesIO
from docx import Document

# Lấy cấu hình API từ file app_config.py
from app_config import API_URL, API_KEY

st.set_page_config(page_title="Smart OCR PDF/Image", layout="centered")

def convert_file_to_base64(file, mime_type):
    if mime_type.startswith("image/"):
        image = Image.open(file)
        buf = BytesIO()
        image.save(buf, format=image.format if image.format else "PNG")
        file_bytes = buf.getvalue()
    else:
        file_bytes = file.read()
    return base64.b64encode(file_bytes).decode(), file_bytes

def ocr_api(file_name, mime_type, base64_str):
    payload = {
        "endpoint": "convert",
        "apiKey": API_KEY,
        "file_data": f"data:{mime_type};base64,{base64_str}",
        "file_name": file_name,
        "options": {
            "language": "auto",
            "include_page_numbers": True,
            "output_format": "text"
        }
    }
    try:
        resp = requests.post(API_URL, json=payload, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "data": {}}

def save_to_word(text, file_name):
    doc = Document()
    doc.add_paragraph(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        doc.save(tmp.name)
        tmp.seek(0)
        data = tmp.read()
    os.remove(tmp.name)
    return data

tab1, tab2 = st.tabs(["📄 OCR PDF", "🖼️ OCR Image"])

# --- TAB 1: PDF ---
with tab1:
    st.header("📄 OCR cho file PDF")
    uploaded_pdf = st.file_uploader("Chọn file PDF để OCR", type=["pdf"])
    if uploaded_pdf:
        st.info(f"**Tên file:** {uploaded_pdf.name}")
        if st.button("🚀 Xử lý OCR PDF", use_container_width=True):
            with st.spinner("Đang gửi file lên Smart OCR..."):
                base64_str, _ = convert_file_to_base64(uploaded_pdf, "application/pdf")
                result = ocr_api(uploaded_pdf.name, "application/pdf", base64_str)
            if result.get("success"):
                st.success("✅ Xử lý thành công!")
                text_content = result["data"].get("text_content", "")
                st.text_area("Kết quả OCR:", text_content, height=300)
                if st.button("⬇️ Tải về file Word", use_container_width=True):
                    word_bytes = save_to_word(text_content, "ket_qua_ocr.docx")
                    st.download_button("Tải file Word", word_bytes, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

# --- TAB 2: ẢNH ---
with tab2:
    st.header("🖼️ OCR cho ảnh (PNG/JPG)")
    uploaded_img = st.file_uploader("Chọn ảnh để OCR", type=["png", "jpg", "jpeg"])
    if uploaded_img:
        st.image(uploaded_img, caption="Ảnh đã chọn", use_column_width=True)
        if st.button("🚀 Xử lý OCR ảnh", use_container_width=True):
            with st.spinner("Đang gửi ảnh lên Smart OCR..."):
                base64_str, _ = convert_file_to_base64(uploaded_img, "image/png")
                result = ocr_api(uploaded_img.name, "image/png", base64_str)
            if result.get("success"):
                st.success("✅ Xử lý thành công!")
                text_content = result["data"].get("text_content", "")
                st.text_area("Kết quả OCR:", text_content, height=300)
                if st.button("⬇️ Tải về file Word", key="wordimg", use_container_width=True):
                    word_bytes = save_to_word(text_content, "ket_qua_ocr.docx")
                    st.download_button("Tải file Word", word_bytes, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

st.caption("© 2025 - Smart OCR (Apps Script API) - Python + Streamlit")
