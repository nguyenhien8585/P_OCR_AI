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

st.set_page_config(page_title="Smart OCR PDF & Image + GPT-4o LaTeX", layout="centered")

# ==================== GPT-4o LaTeX ====================

def call_gpt4o_latex(text, api_key, api_url):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    prompt = (
        "Bạn là AI chuyên chuyển đề Toán tiếng Việt sang LaTeX. "
        "Hãy chuyển toàn bộ nội dung dưới đây thành mã LaTeX thuần túy, chuẩn chỉnh để chép vào Word hoặc Overleaf. "
        "Không thêm lời giải thích, chỉ trả về mã LaTeX. "
        "Các biểu thức toán, ký hiệu, cụm như AB, AC, BC, S, x^2, a=10,... đều phải được bọc đúng LaTeX ($...$), các ký hiệu hình học như \\perp, \\parallel, \\angle, ... giữ nguyên LaTeX. "
        "Với bảng/phương án trắc nghiệm, trình bày đúng cấu trúc. "
        "Nếu có xuống dòng giữa các ý, giữ nguyên. Không dịch nghĩa."
    )
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.2
    }
    resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Tùy format API, thử 2 kiểu phổ biến
    if "choices" in data and data["choices"]:
        return data["choices"][0]["message"]["content"]
    if "result" in data:
        return data["result"]
    return ""

# ==================== Tách ảnh minh họa ====================

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
                st.text_area("Kết quả OCR:", text_content, height=300)

                # Nút chuyển LaTeX bằng GPT-4o
                if st.button("✨ Chuyển sang LaTeX bằng GPT-4o", use_container_width=True):
                    with st.spinner("Đang chuyển sang LaTeX bằng GPT-4o..."):
                        try:
                            latex = call_gpt4o_latex(text_content, API_KEY, API_URL)
                            st.text_area("Kết quả LaTeX (GPT-4o):", latex, height=300)
                            st.download_button("Tải file LaTeX", latex, file_name="ket_qua_ocr_gpt4o.tex", mime="text/plain", use_container_width=True)
                        except Exception as e:
                            st.error(f"Lỗi khi gọi GPT-4o: {str(e)}")

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
                    word_bytes = save_to_word(text_content, export_figures, "ket_qua_ocr.docx")
                    st.download_button("Tải file Word", word_bytes, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                if st.button("⬇️ Xuất file LaTeX", use_container_width=True):
                    latex_code = save_to_latex(text_content, export_figures, "ket_qua_ocr.tex")
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
                st.text_area("Kết quả OCR:", text_content, height=300)

                if st.button("✨ Chuyển sang LaTeX bằng GPT-4o", key="gpt4o_img", use_container_width=True):
                    with st.spinner("Đang chuyển sang LaTeX bằng GPT-4o..."):
                        try:
                            latex = call_gpt4o_latex(text_content, API_KEY, API_URL)
                            st.text_area("Kết quả LaTeX (GPT-4o):", latex, height=300)
                            st.download_button("Tải file LaTeX", latex, file_name="ket_qua_ocr_gpt4o.tex", mime="text/plain", use_container_width=True)
                        except Exception as e:
                            st.error(f"Lỗi khi gọi GPT-4o: {str(e)}")

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
                    word_bytes = save_to_word(text_content, export_figures, "ket_qua_ocr.docx")
                    st.download_button("Tải file Word", word_bytes, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
                if st.button("⬇️ Xuất file LaTeX", key="latex_img", use_container_width=True):
                    latex_code = save_to_latex(text_content, export_figures, "ket_qua_ocr.tex")
                    st.download_button("Tải file LaTeX", latex_code, file_name="ket_qua_ocr.tex", mime="text/plain", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

st.caption("© 2025 - Smart OCR Math + GPT-4o LaTeX, tách ảnh minh họa tự động cho PDF và ảnh")
