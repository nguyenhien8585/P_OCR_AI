import streamlit as st
import requests
import base64
import os
import tempfile
from PIL import Image
from io import BytesIO
from docx import Document
from app_config import OCR_API_URL, OCR_API_KEY, GPT4O_API_URL, GPT4O_API_KEY

from pdf2image import convert_from_bytes
from extract_figures_from_image_pillow import extract_figures_from_image

st.set_page_config(page_title="OCR PDF/Ảnh ➔ LaTeX + Word minh hoạ", layout="centered")

# ==== Hàm gọi OCR SmartOCR chuẩn ====
def ocr_api(file_name, mime_type, base64_str):
    payload = {
        "endpoint": "convert",    # BẮT BUỘC
        "apiKey": OCR_API_KEY,
        "file_name": file_name,
        "file_data": f"data:{mime_type};base64,{base64_str}"  # BẮT BUỘC
    }
    try:
        resp = requests.post(OCR_API_URL, json=payload, timeout=120)
        st.write(f"OCR status: {resp.status_code} - {resp.text[:300]}")
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"❌ OCR API lỗi: {e}\n{resp.text if 'resp' in locals() else ''}")
        return {"success": False, "error": str(e), "data": {}}

# ==== Hàm gọi GPT-4o chuyển sang LaTeX ====
def call_gpt4o_latex(text):
    headers = {
        "Authorization": f"Bearer {GPT4O_API_KEY}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "Bạn là AI chuyên chuyển đề Toán tiếng Việt sang LaTeX. "
        "Chỉ trả về mã LaTeX thuần túy, không giải thích, không chú thích."
    )
    payload = {
        "model": "openai:gpt-4o",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        "temperature": 0.2
    }
    resp = requests.post(GPT4O_API_URL, headers=headers, json=payload, timeout=120)
    if resp.status_code != 200:
        st.error(f"❌ GPT-4o lỗi HTTP {resp.status_code}: {resp.text}")
        return ""
    try:
        data = resp.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        st.error("❌ GPT-4o trả về JSON nhưng không có trường 'choices'.")
        return ""
    except Exception as e:
        st.error(f"❌ Lỗi khi parse JSON GPT-4o: {resp.text}")
        return ""

# ==== Tách ảnh minh hoạ ====
def extract_figures_from_pdf(pdf_bytes):
    figures = []
    pdf_pages = convert_from_bytes(pdf_bytes)
    for i, im in enumerate(pdf_pages):
        buf = BytesIO()
        im.save(buf, format="JPEG")
        page_bytes = buf.getvalue()
        figs = extract_figures_from_image(page_bytes, min_area=1200, max_figures=8)
        for idx, fig in enumerate(figs):
            fig['name'] = f"IMAGE-{len(figures)+1}"
            fig['page'] = i+1
            figures.append(fig)
    return figures

def extract_figures_from_uploaded_image(img_file):
    img = Image.open(img_file)
    buf = BytesIO()
    img.save(buf, format=img.format if img.format else "PNG")
    img_bytes = buf.getvalue()
    figs = extract_figures_from_image(img_bytes, min_area=1200, max_figures=8)
    for idx, fig in enumerate(figs):
        fig['name'] = f"IMAGE-{idx+1}"
        fig['page'] = 1
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

# ==== Xuất Word, chèn ảnh vào vị trí placeholder ====
def save_to_word(text, figures):
    doc = Document()
    for line in text.splitlines():
        img_placeholder = None
        for fig in figures:
            if f"[{fig['name']}]" in line:
                img_placeholder = fig
                break
        if img_placeholder:
            p = doc.add_paragraph(line.replace(f"[{img_placeholder['name']}]", ""))
            img_bytes = base64.b64decode(img_placeholder["base64"])
            img_stream = BytesIO(img_bytes)
            doc.add_picture(img_stream, width=None)
            doc.add_paragraph(img_placeholder["name"])
        else:
            doc.add_paragraph(line)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        doc.save(tmp.name)
        tmp.seek(0)
        data = tmp.read()
    os.remove(tmp.name)
    return data

def save_to_latex(latex_content, figures):
    for fig in figures:
        img_bytes = base64.b64decode(fig["base64"])
        fname = f"{fig['name']}.png"
        img_path = os.path.join(tempfile.gettempdir(), fname)
        with open(img_path, "wb") as f:
            f.write(img_bytes)
    content = []
    content.append("\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}")
    content.append(latex_content)
    content.append("\\end{document}")
    latex_code = "\n\n".join(content)
    return latex_code

tab1, tab2 = st.tabs(["📄 PDF sang LaTeX+Word", "🖼️ Ảnh sang LaTeX+Word"])

with tab1:
    st.header("📄 Chuyển PDF Toán → LaTeX & Word")
    uploaded_pdf = st.file_uploader("Chọn file PDF để xử lý", type=["pdf"])
    if uploaded_pdf:
        file_bytes = uploaded_pdf.read()
        st.info(f"**Tên file:** {uploaded_pdf.name}")
        st.info(f"**Kích thước:** {round(len(file_bytes)/1024,1)} KB")
        if st.button("🚀 OCR & tách minh hoạ PDF", use_container_width=True):
            with st.spinner("Đang OCR và tách minh hoạ..."):
                base64_str = base64.b64encode(file_bytes).decode()
                result = ocr_api(uploaded_pdf.name, "application/pdf", base64_str)
            if result.get("success"):
                st.success("✅ Đã nhận diện văn bản!")
                text_content = result["data"].get("text_content", "")
                figures = extract_figures_from_pdf(file_bytes)
                for idx, fig in enumerate(figures):
                    text_content += f"\n[{fig['name']}]"
                st.text_area("Văn bản đã OCR (có chèn placeholder minh hoạ):", text_content, height=300)
                if st.button("✨ Chuyển sang LaTeX bằng GPT-4o", use_container_width=True):
                    with st.spinner("Đang chuyển sang LaTeX bằng GPT-4o..."):
                        latex = call_gpt4o_latex(text_content)
                        st.text_area("Kết quả LaTeX (GPT-4o):", latex, height=300)
                        st.download_button("Tải file LaTeX", latex, file_name="output_gpt4o.tex", mime="text/plain", use_container_width=True)
                        if st.button("⬇️ Xuất file Word (minh hoạ đúng vị trí)", use_container_width=True):
                            word_bytes = save_to_word(text_content, figures)
                            st.download_button("Tải file Word", word_bytes, file_name="output.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

with tab2:
    st.header("🖼️ Ảnh Toán (PNG/JPG) sang LaTeX+Word")
    uploaded_img = st.file_uploader("Chọn ảnh để xử lý", type=["png", "jpg", "jpeg"])
    if uploaded_img:
        st.image(uploaded_img, caption="Ảnh đã chọn", use_column_width=True)
        if st.button("🚀 OCR & tách minh hoạ ảnh", use_container_width=True):
            with st.spinner("Đang OCR và tách minh hoạ..."):
                base64_str, img_bytes = convert_file_to_base64(uploaded_img, "image/png")
                result = ocr_api(uploaded_img.name, "image/png", base64_str)
            if result.get("success"):
                st.success("✅ Đã nhận diện văn bản!")
                text_content = result["data"].get("text_content", "")
                figures = extract_figures_from_uploaded_image(uploaded_img)
                for idx, fig in enumerate(figures):
                    text_content += f"\n[{fig['name']}]"
                st.text_area("Văn bản đã OCR (có chèn placeholder minh hoạ):", text_content, height=300)
                if st.button("✨ Chuyển sang LaTeX bằng GPT-4o", key="gpt4o_img", use_container_width=True):
                    with st.spinner("Đang chuyển sang LaTeX bằng GPT-4o..."):
                        latex = call_gpt4o_latex(text_content)
                        st.text_area("Kết quả LaTeX (GPT-4o):", latex, height=300)
                        st.download_button("Tải file LaTeX", latex, file_name="output_gpt4o.tex", mime="text/plain", use_container_width=True)
                        if st.button("⬇️ Xuất file Word (minh hoạ đúng vị trí)", use_container_width=True):
                            word_bytes = save_to_word(text_content, figures)
                            st.download_button("Tải file Word", word_bytes, file_name="output.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            else:
                st.error("❌ Lỗi: " + result.get("error", "Không rõ nguyên nhân"))

st.caption("© 2025 - OCR đề Toán, tách minh hoạ, xuất Word và LaTeX tự động với GPT-4o")
