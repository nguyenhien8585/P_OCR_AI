import streamlit as st
from config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_images import extract_images_from_pdf
from word_export import insert_images_to_word_from_markdown
import os
import base64
import re

st.set_page_config(page_title="Smart OCR - API + Python Image Extract", layout="centered")
st.title("📄 Smart OCR (API + Python image extract) – Xuất Word, ảnh minh hoạ đúng vị trí")
st.write(
    "- Nhận diện text bằng API (dùng key)\n"
    "- Trích xuất ảnh minh hoạ thực sự từ PDF bằng Python\n"
    "- Khi xuất Word: ảnh sẽ được chèn đúng vị trí tên ảnh trong text"
)

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])
if uploaded_file:
    pdf_bytes = uploaded_file.read()
    file_name = uploaded_file.name
    mime_type = "application/pdf"

    with st.spinner("Đang nhận diện văn bản (OCR API)..."):
        client = EnhancedSmartOCRClient(API_URL, API_KEY)
        result = client.convert(pdf_bytes, file_name, mime_type)

    if not result.get("success"):
        st.error("OCR thất bại: " + str(result.get("error")))
    else:
        # --- Chuyển đổi toàn bộ $...$ thành ${...}$ ---
        def dollar_to_mathptn(s):
            # Regex tìm các cụm $...$
            # Không match với $$...$$ hoặc $ $ rỗng
            return re.sub(r'\$(.+?)\$', r'${\1}$', s)

        raw_text = result["data"].get("text_content", "")
        text_content = dollar_to_mathptn(raw_text)
        st.subheader("Văn bản nhận diện (có tên ảnh):")
        st.text_area("Text OCR", text_content, height=350)

        # Tách mọi ảnh thực sự từ PDF
        with st.spinner("Đang trích xuất ảnh minh hoạ từ PDF..."):
            images = extract_images_from_pdf(pdf_bytes)

        if images:
            st.success(f"Trích xuất được {len(images)} ảnh minh hoạ!")
            for img in images:
                try:
                    img_bytes = base64.b64decode(img["base64"])
                    st.image(img_bytes, caption=img["name"], use_container_width=True)
                except Exception as e:
                    st.error(f"Không đọc được ảnh {img['name']}: {e}")
        else:
            st.warning("Không tìm thấy ảnh minh hoạ thực sự trong PDF!")

        # Export Word ONLY (không còn LaTeX)
        if st.button("📥 Xuất file Word (.docx)"):
            word_file = "ket_qua_ocr.docx"
            insert_images_to_word_from_markdown(text_content, images, word_file)
            with open(word_file, "rb") as f:
                st.download_button("Tải về file Word", f, file_name=word_file)
            os.remove(word_file)

st.markdown("---")
st.caption("Code Python: API key nhận diện text, trích xuất ảnh trực tiếp, chuyển $...$ sang ${...}$, mapping đúng tên ảnh khi xuất Word.")
