import streamlit as st
from app_config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_figures_from_image_pillow import extract_figures_from_image
from word_export import insert_images_to_word_from_markdown
from pix2tex_wrapper import recognize_latex_from_images  # MỚI
import os
import base64
import re
from PyPDF2 import PdfReader
import tempfile
from PIL import Image
import io
from pdf2image import convert_from_bytes

st.set_page_config(page_title="OCR PDF & Image", layout="centered")

# -------------------- FILTER TOÁN HỌC ----------------------
def format_math_ocr(text):
    excluded_keywords = [
        "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "KỲ THI", "ĐỀ THI", "Môn thi", "Họ, tên thí sinh",
        "Số báo danh", "Mã đề", "Trang", "Thời gian làm bài", "PHẦN", "Bảng", "BẢNG"
    ]
    def should_exclude(line):
        return any(line.strip().startswith(kw) for kw in excluded_keywords)

    def is_choice_line(line):
        return re.match(r"^\s*[ABCD]\.?\)?", line)

    math_pattern = r'(\d+([.,]\d+)?|[a-zA-Z_][a-zA-Z_\d]*|\\?[a-zA-Z]+|\\?\^\{[^}]+\}|\\?\_[^ ]+)'  # nhận diện biến và hàm

    lines = text.split("\n")
    output = []
    for line in lines:
        l = line.strip()
        if should_exclude(l) or is_choice_line(l) or l == "":
            output.append(l)
        else:
            m = re.match(r'^(Câu\s*\d+[:：]?)\s*(.*)', l)
            if m:
                header, rest = m.groups()
                rest = re.sub(math_pattern, lambda m: f"${{{m.group(0)}}}$", rest)
                output.append(f"{header} {rest}".strip())
            else:
                l = re.sub(math_pattern, lambda m: f"${{{m.group(0)}}}$", l)
                output.append(l)
    return "\n".join(output)

# -------------------- TAB PDF ----------------------------
tab1, tab2 = st.tabs(["📄 OCR PDF", "🖼️ OCR Image"])

with tab1:
    st.header("📄 OCR cho file PDF")
    uploaded_pdf = st.file_uploader("Chọn file PDF để xử lý OCR", type=["pdf"])

    if uploaded_pdf:
        pdf_bytes = uploaded_pdf.read()
        file_name = uploaded_pdf.name
        mime_type = "application/pdf"

        try:
            uploaded_pdf.seek(0)
            reader = PdfReader(uploaded_pdf)
            num_pages = len(reader.pages)
        except:
            num_pages = "?"

        st.info(f"**Tên file:** {file_name} | **Số trang:** {num_pages}")

        if st.button("🚀 Xử lý OCR PDF", use_container_width=True):
            with st.spinner("Đang xử lý OCR và trích xuất hình ảnh..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                uploaded_pdf.seek(0)
                result = client.convert(pdf_bytes, file_name, mime_type)
                pdf_images = convert_from_bytes(pdf_bytes)

                images = []
                for i, im in enumerate(pdf_images):
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG")
                    page_bytes = buf.getvalue()
                    figs = extract_figures_from_image(page_bytes, min_area=1200, max_figures=8)
                    for fig in figs:
                        fig['name'] = f"page-{i+1}-{fig['name']}"
                    images.extend(figs)

                if not result.get("success"):
                    st.error("❌ OCR thất bại: " + str(result.get("error")))
                    st.stop()

                st.session_state["ocr_text"] = result["data"].get("text_content", "")
                st.session_state["ocr_figures"] = images
                st.session_state["ocr_done"] = True
                st.success("✅ Đã xử lý OCR thành công!")

    if st.session_state.get("ocr_done"):
        raw_text = st.session_state["ocr_text"]
        figures = st.session_state["ocr_figures"]

        st.subheader("📝 Văn bản OCR (MathType):")
        filtered_text = format_math_ocr(raw_text)
        st.text_area("Kết quả OCR:", filtered_text, height=300, label_visibility="collapsed")

        st.subheader("🖼️ Hình minh hoạ và ảnh công thức:")
        if figures:
            cols = st.columns(2)
            selected_names = []
            for i, fig in enumerate(figures):
                with cols[i % 2]:
                    checked = st.checkbox(f"{fig['name']}", value=True, key=f"fig_check{i}")
                    st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                    if checked:
                        selected_names.append(fig["name"])

            export_figures = [fig for fig in figures if fig["name"] in selected_names]

            # 📌 Thêm xử lý Pix2Tex tại đây:
            if st.button("✨ Nhận diện công thức từ hình ảnh (pix2tex)", use_container_width=True):
                with st.spinner("Đang nhận diện công thức bằng Pix2Tex..."):
                    latex_results = recognize_latex_from_images(export_figures)
                st.success("✅ Đã nhận diện công thức thành công!")
                for item in latex_results:
                    st.markdown(f"**{item['name']}** ➜ `${item['latex']}$`")

        if st.button("📝 Tạo file Word", use_container_width=True):
            with st.spinner("Đang tạo file Word..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    insert_images_to_word_from_markdown(filtered_text, export_figures, tmp_word.name)
                with open(tmp_word.name, "rb") as f:
                    word_data = f.read()
                st.download_button("⬇️ Tải file Word", word_data, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                os.remove(tmp_word.name)

st.caption("© 2025 - Ứng dụng OCR MathType + Pix2Tex hỗ trợ đề Toán chuẩn LaTeX + Word")
