import streamlit as st
from utils.gpt_vision import ask_gpt_vision
from utils.doc_writer import build_docx, build_latex
import fitz  # PyMuPDF
from PIL import Image
import io
import tempfile

# Chuyển PDF thành danh sách ảnh
def pdf_to_images(pdf_bytes):
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    return images

# Giao diện Streamlit
st.set_page_config(page_title="PDF to LaTeX/Word", layout="centered")
st.title("📄 Chuyển PDF sang LaTeX / Word bằng GPT-4o")

api_key = st.text_input("🔐 Nhập API Key AI.VN", type="password")
mode = st.radio("Chế độ:", ["latex", "word"], format_func=lambda x: "LaTeX (soạn đề)" if x == "latex" else "Word (giữ nguyên gốc)")
uploaded_file = st.file_uploader("📎 Tải file PDF", type=["pdf"])

if uploaded_file and api_key:
    with st.spinner("🔄 Đang tách trang PDF..."):
        images = pdf_to_images(uploaded_file.read())
    st.success(f"✅ Đã tách {len(images)} trang!")

    output_text = ""
    for i, img in enumerate(images):
        st.image(img, caption=f"Trang {i+1}", use_column_width=True)
        st.info(f"⏳ Đang xử lý trang {i+1}...")
        result = ask_gpt_vision(img, mode, api_key)
        output_text += result + "\n"

    if mode == "latex":
        st.code(output_text, language="latex")
        st.download_button("📅 Tải LaTeX", output_text, file_name="output.tex", mime="text/plain")
    else:
        temp_docx = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        build_docx(output_text, temp_docx.name)
        with open(temp_docx.name, "rb") as f:
            st.download_button("📅 Tải Word", f, file_name="output.docx")
