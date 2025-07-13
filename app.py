import streamlit as st
import requests
import base64
import os
import tempfile
from PIL import Image
from io import BytesIO
from docx import Document
from app_config import API_URL, API_KEY

from pdf2image import convert_from_bytes
from extract_figures_from_image_pillow import extract_figures_from_image
import regex as re

st.set_page_config(page_title="Smart OCR PDF & Image", layout="centered")

# Từ điển từ tiếng Việt loại trừ
VIET_WORDS = set([
    "trong", "cạnh", "của", "hình", "vuông", "nhật", "các", "tính", "đúng", "sai", "đều", "bằng", "cho",
    "thoi", "tâm", "đáy", "trung", "điểm", "khẳng", "định", "xét", "mặt", "là", "và", "có", "giá", "trị",
    "chóp", "tổng", "hiệu", "trừ", "chia", "nhân", "phần", "diện", "tích", "chu", "vi", "số", "góc", "song",
    "song", "vuông", "với", "bán", "kính", "lượt", "phải", "trái", "thẳng", "đúng", "sai", "theo", "phép",
    "toạ", "độ", "thẳng", "giả", "thiết", "ngược", "hướng", "cạnh", "bởi", "lấy", "lúc", "dài", "ngắn"
])

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

def extract_figures_from_pdf(pdf_bytes):
    images = []
    pdf_pages = convert_from_bytes(pdf_bytes)
    for i, im in enumerate(pdf_pages):
        buf = BytesIO()
        im.save(buf, format="JPEG")
        page_bytes = buf.getvalue()
        figs = extract_figures_from_image(page_bytes, min_area=1200, max_figures=8)
        for fig in figs:
            fig['name'] = f"page-{i+1}-{fig['name']}"
        images.extend(figs)
    return images

def extract_figures_from_uploaded_image(img_file):
    img = Image.open(img_file)
    buf = BytesIO()
    img.save(buf, format=img.format if img.format else "PNG")
    img_bytes = buf.getvalue()
    figs = extract_figures_from_image(img_bytes, min_area=1200, max_figures=8)
    for fig in figs:
        fig['name'] = f"img-{fig['name']}"
    return figs

def save_to_word(text, figures, file_name):
    doc = Document()
    doc.add_paragraph(text)
    for fig in figures:
        img_bytes = base64.b64decode(fig["base64"])
        img_stream = BytesIO(img_bytes)
        doc.add_picture(img_stream, width=None)
        doc.add_paragraph(fig["name"])
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        doc.save(tmp.name)
        tmp.seek(0)
        data = tmp.read()
    os.remove(tmp.name)
    return data

def save_to_latex(text, figures, file_name):
    content = []
    content.append("\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}")
    content.append(text)
    for fig in figures:
        fname = fig["name"] + ".png"
        img_bytes = base64.b64decode(fig["base64"])
        img_path = os.path.join(tempfile.gettempdir(), fname)
        with open(img_path, "wb") as f:
            f.write(img_bytes)
        content.append(f"\\begin{{figure}}[h]\n\\centering\n\\includegraphics[width=0.8\\textwidth]{{{fname}}}\n\\caption{{{fig['name']}}}\n\\end{{figure}}")
    content.append("\\end{document}")
    latex_code = "\n\n".join(content)
    return latex_code

def clean_latex(text):
    text = re.sub(r'//', r'\\parallel ', text)
    text = re.sub(r"\^'|'\^", r'^{\\prime}', text)
    text = re.sub(r"\^\\prime|\^{\\prime}", r'^{\\prime}', text)
    text = re.sub(r'90\^(\{?circ\}?)', r'90^{\\circ}', text)
    text = re.sub(r"\$(\s*)\$", '', text)
    text = re.sub(r'\{(\${.*?}\$)\}', r'\1', text)
    return text

def format_math_expr(text):
    lines = text.split('\n')
    out_lines = []
    for line in lines:
        # Nếu là dòng ý trắc nghiệm: "A. ..." hoặc "B) ..." hoặc "C. ..."
        m = re.match(r'^([ABCD])[\.\)]\s*(.*)', line.strip())
        if m:
            prefix, content = m.groups()
            content = wrap_math_in_line(content)
            out_lines.append(f"{prefix}. {content}")
        else:
            out_lines.append(wrap_math_in_line(line))
    return "\n".join(out_lines)

def wrap_math_in_line(line):
    # Chỉ bọc biến/công thức, không bọc từ tiếng Việt
    def wrap(match):
        expr = match.group(0)
        # Không bọc từ tiếng Việt nhiều hơn 1 ký tự, hoặc chữ thường >=2
        if expr.lower() in VIET_WORDS or re.match(r"^[a-zA-ZÀ-ỹà-ỹ]{2,}$", expr):
            return expr
        return f"${expr}$"
    # Nhận diện biến toán, số, công thức (không bọc từ/cụm tiếng Việt)
    pattern = r'\b(?:[A-Z]{1,3}|[A-Z][A-Z0-9]{1,3}|a|b|c|d|x|y|z|n|m|i|j|k|l|A|B|C|D|O|M|N|S|a|b|c|d)(?:_{[0-9]+}|\^{\\prime})?([ ]*[=+\-*/^][ ]*[0-9A-Za-z]+)?\b'
    return re.sub(pattern, wrap, line)

tab1, tab2 = st.tabs(["📄 OCR PDF", "🖼️ OCR Image"])

with tab1:
    st.header("📄 OCR cho file PDF")
    uploaded_pdf = st.file_uploader("Chọn file PDF để OCR", type=["pdf"])
    if uploaded_pdf:
        file_bytes = uploaded_pdf.read()
        st.info(f"**Tên file:** {uploaded_pdf.name}")
        st.info(f"**Loại file:** application/pdf")
        st.info(f"**Kích thước:** {round(len(file_bytes)/1024,1)} KB")
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(file_bytes))
            st.info(f"**Số trang:** {len(reader.pages)}")
        except:
            st.info("**Số trang:** ?")

        if st.button("🚀 Xử lý OCR PDF", use_container_width=True):
            with st.spinner("Đang gửi file lên Smart OCR..."):
                base64_str = base64.b64encode(file_bytes).decode()
                result = ocr_api(uploaded_pdf.name, "application/pdf", base64_str)
            if result.get("success"):
                st.success("✅ Xử lý thành công!")
                text_content = result["data"].get("text_content", "")
                st.subheader("📝 Văn bản OCR:")
                clean_text = clean_latex(text_content)
                math_text = format_math_expr(clean_text)
                st.text_area("Kết quả OCR:", math_text, height=300)

                st.subheader("🖼️ Hình minh họa từ PDF (tách tự động):")
                figures = extract_figures_from_pdf(file_bytes)
                if figures:
                    cols = st.columns(2)
                    selected_names = []
                    for i, fig in enumerate(figures):
                        with cols[i % 2]:
                            checked = st.checkbox(f"{fig['name']}", value=True, key=f"fig_check_pdf_{i}")
                            st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                            if checked:
                                selected_names.append(fig["name"])
                    export_figures = [fig for fig in figures if fig["name"] in selected_names]
                else:
                    st.info("Không phát hiện hình minh họa.")
                    export_figures = []

                if st.button("⬇️ Xuất file Word", use_container_width=True):
                    word_bytes = save_to_word(math_text, export_figures, "ket_qua_ocr.docx")
                    st.download_button("Tải file Word", word_bytes, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                if st.button("⬇️ Xuất file LaTeX", use_container_width=True):
                    latex_code = save_to_latex(math_text, export_figures, "ket_qua_ocr.tex")
                    st.download_button("Tải file LaTeX", latex_code, file_name="ket_qua_ocr.tex", mime="text/plain", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

with tab2:
    st.header("🖼️ OCR cho ảnh (PNG/JPG)")
    uploaded_img = st.file_uploader("Chọn ảnh để OCR", type=["png", "jpg", "jpeg"])
    if uploaded_img:
        st.image(uploaded_img, caption="Ảnh đã chọn", use_column_width=True)
        if st.button("🚀 Xử lý OCR ảnh", use_container_width=True):
            with st.spinner("Đang gửi ảnh lên Smart OCR..."):
                base64_str, img_bytes = convert_file_to_base64(uploaded_img, "image/png")
                result = ocr_api(uploaded_img.name, "image/png", base64_str)
            if result.get("success"):
                st.success("✅ Xử lý thành công!")
                text_content = result["data"].get("text_content", "")
                st.subheader("📝 Văn bản OCR:")
                clean_text = clean_latex(text_content)
                math_text = format_math_expr(clean_text)
                st.text_area("Kết quả OCR:", math_text, height=300)

                st.subheader("🖼️ Các vùng ảnh tách được (tách tự động):")
                figures = extract_figures_from_uploaded_image(uploaded_img)
                if figures:
                    cols = st.columns(2)
                    selected_names = []
                    for i, fig in enumerate(figures):
                        with cols[i % 2]:
                            checked = st.checkbox(f"{fig['name']}", value=True, key=f"fig_check_img_{i}")
                            st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                            if checked:
                                selected_names.append(fig["name"])
                    export_figures = [fig for fig in figures if fig["name"] in selected_names]
                else:
                    st.info("Không phát hiện vùng ảnh minh họa.")
                    export_figures = []

                if st.button("⬇️ Xuất file Word", key="word_img", use_container_width=True):
                    word_bytes = save_to_word(math_text, export_figures, "ket_qua_ocr.docx")
                    st.download_button("Tải file Word", word_bytes, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                if st.button("⬇️ Xuất file LaTeX", key="latex_img", use_container_width=True):
                    latex_code = save_to_latex(math_text, export_figures, "ket_qua_ocr.tex")
                    st.download_button("Tải file LaTeX", latex_code, file_name="ket_qua_ocr.tex", mime="text/plain", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

st.caption("© 2025 - Smart OCR Math, xuất chuẩn Word/LaTeX, tách ảnh minh họa tự động cho PDF và ảnh")
