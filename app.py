import streamlit as st
from PIL import Image
from pdf2image import convert_from_bytes
from utils import extract_text_ocr, call_gpt4o_ai_vn
import io

st.set_page_config(page_title="📄 PDF/Ảnh ➜ Word/LaTeX", layout="wide")
st.title("📄 Chuyển PDF hoặc ảnh sang Word/LaTeX kèm ảnh minh hoạ (GPT-4o)")

uploaded_file = st.file_uploader("Tải lên PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    bytes_data = uploaded_file.read()
    images = []
    if uploaded_file.name.endswith(".pdf"):
        images = convert_from_bytes(bytes_data)
    else:
        image = Image.open(io.BytesIO(bytes_data)).convert("RGB")
        images = [image]

    st.success(f"📑 Đã nhận {len(images)} trang ảnh")

    for idx, img in enumerate(images):
        st.image(img, caption=f"Trang {idx+1}", use_column_width=True)

        if st.button(f"📤 Phân tích với GPT-4o - Trang {idx+1}", key=idx):
            with st.spinner("🔍 Đang nhận dạng văn bản..."):
                ocr_text = extract_text_ocr(img)

            st.subheader("📜 Văn bản OCR:")
            st.code(ocr_text)

            with st.spinner("🤖 Đang xử lý với GPT-4o..."):
                result = call_gpt4o_ai_vn(img, ocr_text)

            st.subheader("📄 Kết quả định dạng (LaTeX/Word):")
            st.code(result, language="latex")
