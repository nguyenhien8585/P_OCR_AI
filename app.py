import os
import io
import tempfile
import streamlit as st
from pdf2image import convert_from_bytes
from utils.gpt_vision import ask_gpt_vision
from utils.doc_writer import build_docx, build_latex

st.set_page_config(page_title="PDF to LaTeX/Word", layout="centered")
st.title("📄 Chuyển PDF sang LaTeX hoặc Word bằng GPT-4o")

api_key = st.text_input("🔐 Nhập API Key từ AI.VN:", type="password")

mode = st.selectbox("🎯 Chế độ chuyển đổi:", ["latex", "word"], format_func=lambda m: "LaTeX (soạn đề)" if m == "latex" else "Word (giữ nguyên văn bản)")

uploaded_file = st.file_uploader("📎 Tải lên file PDF", type=["pdf"])

if uploaded_file and api_key:
    with st.spinner("🔍 Đang chuyển đổi PDF sang ảnh..."):
        images = convert_from_bytes(uploaded_file.read(), dpi=300)

    st.success(f"✅ Đã tách {len(images)} trang từ PDF.")

    output_text = ""
    for i, img in enumerate(images):
        st.image(img, caption=f"Trang {i+1}", use_column_width=True)
        st.info(f"⏳ Đang xử lý trang {i+1}...")
        result = ask_gpt_vision(img, mode, api_key)
        output_text += result + "\n"

    st.success("✅ Xử lý hoàn tất!")

    if mode == "latex":
        st.code(output_text, language="latex")
        st.download_button("📥 Tải LaTeX", data=output_text, file_name="output.tex", mime="text/plain")
    else:
        # Xuất ra file Word
        docx_path = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
        build_docx(output_text, docx_path)
        with open(docx_path, "rb") as f:
            st.download_button("📥 Tải Word", data=f, file_name="output.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
