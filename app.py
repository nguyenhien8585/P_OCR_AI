import streamlit as st
from PIL import Image
from utils import call_gpt4o_ai_vn, pdf_to_images
import io

st.set_page_config(page_title="📄 PDF/Ảnh ➜ Word/LaTeX", layout="wide")
st.title("📄 Chuyển PDF hoặc ảnh sang Word/LaTeX bằng GPT-4o (không cần OCR)")

uploaded_file = st.file_uploader("📤 Tải lên PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])

if uploaded_file:
    bytes_data = uploaded_file.read()
    images = []

    if uploaded_file.name.endswith(".pdf"):
        images = pdf_to_images(bytes_data)
    else:
        image = Image.open(io.BytesIO(bytes_data)).convert("RGB")
        images = [image]

    st.success(f"✅ Đã xử lý {len(images)} trang")

    for idx, img in enumerate(images):
        st.image(img, caption=f"Trang {idx+1}", use_container_width=True)

        if st.button(f"🚀 GPT-4o xử lý Trang {idx+1}", key=idx):
            with st.spinner("🔍 Đang gửi ảnh lên GPT-4o..."):
                result = call_gpt4o_ai_vn(img)

            st.subheader("📄 Kết quả LaTeX / Word:")
            st.code(result, language="latex")
