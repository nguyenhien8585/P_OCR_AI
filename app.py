import streamlit as st
from app_config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_figures_from_image_pillow import extract_figures_from_image
from word_export import insert_images_to_word_from_markdown
import os
import base64
import re
from PyPDF2 import PdfReader
import tempfile
from PIL import Image
import io
from pix2tex.cli import LatexOCR

pix2tex_model = LatexOCR()

def pix2tex_from_base64(base64_img: str) -> str:
    try:
        image = Image.open(io.BytesIO(base64.b64decode(base64_img)))
        return pix2tex_model(image)
    except Exception as e:
        return f"% Error recognizing formula: {e}"

def format_math_ocr(text):
    text = text.replace("*", "").replace("#", "")
    excluded_keywords = [
        "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "KỲ THI", "ĐỀ THI", "Môn thi", "Họ, tên thí sinh",
        "Sổ báo danh", "Mã đề", "Trang", "Thời gian làm bài", "PHẦN", "Bảng", "BẢNG"
    ]
    def should_exclude(line):
        for kw in excluded_keywords:
            if line.strip().startswith(kw): return True
        if re.match(r'^\s*Trang\\b', line): return True
        if re.match(r'^\s*Mã đề\\b', line): return True
        return False
    def is_choice_line(line):
        return re.match(r"^\s*[ABCD]\.", line) or re.match(r"^\s*[ABCD]\s*[).]", line)
    math_pattern = r'(?<![\\w\\$])([A-Z][\\.A-Z\\'\d]*|Oxyz|\\vec{[a-zA-Z]+}|n̄|[0-9]+(?:/[0-9]+)?|f\\(x\\)|P|OA|OB|OC|AB|AC|BC|A\'|B\'|C\'|x|y|z|t|n|C|ad|bc|ac|(-?\\d+))(?![\\w\\$])'
    lines = text.split("\n")
    output = []
    for line in lines:
        l = line.strip()
        if should_exclude(l) or is_choice_line(l) or l == "":
            output.append(l)
        else:
            m = re.match(r'^(Câu\s*\\d+[:：])\s*(.*)', l)
            if m:
                header, rest = m.groups()
                formatted = re.sub(math_pattern, lambda m: "${}$".format(m.group(0)), rest)
                output.append(f"{header} {formatted}".strip())
            else:
                formatted = re.sub(math_pattern, lambda m: "${}$".format(m.group(0)), l)
                output.append(formatted)
    return "\n".join(output)

st.set_page_config(page_title="OCR PDF & Image", layout="centered")
tab1, tab2 = st.tabs(["📄 OCR PDF", "🖼️ OCR Image"])

# ===== TAB 1: PDF =====
with tab1:
    st.markdown("### 📄 OCR cho file PDF")
    uploaded_pdf = st.file_uploader("Chọn file PDF để xử lý OCR", type=["pdf"])
    num_pages = None

    if uploaded_pdf:
        pdf_bytes = uploaded_pdf.read()
        file_name = uploaded_pdf.name
        mime_type = "application/pdf"
        size_mb = len(pdf_bytes) / (1024 * 1024)

        try:
            uploaded_pdf.seek(0)
            reader = PdfReader(uploaded_pdf)
            num_pages = len(reader.pages)
            uploaded_pdf.seek(0)
        except:
            num_pages = "?"

        with st.expander("ℹ️ Thông tin file", expanded=True):
            st.write(f"**Tên file:** {file_name}")
            st.write(f"**Loại file:** {mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")
            st.write(f"**Số trang:** {num_pages}")

    if uploaded_pdf:
        if st.button("🚀 Xử lý OCR PDF", key="ocr_pdf_btn", use_container_width=True):
            st.info("⏳ Đang xử lý OCR PDF... (quá trình này có thể mất vài phút)")
            with st.spinner("Đang nhận diện văn bản và tách ảnh minh hoạ..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                uploaded_pdf.seek(0)
                pdf_bytes = uploaded_pdf.read()
                result = client.convert(pdf_bytes, file_name, mime_type)
                from pdf2image import convert_from_bytes
                pdf_images = convert_from_bytes(pdf_bytes)
                images = []
                for i, im in enumerate(pdf_images):
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG")
                    page_bytes = buf.getvalue()
                    page_figs = extract_figures_from_image(page_bytes, min_area=1200, max_figures=7)
                    for fig in page_figs:
                        fig['name'] = f"page-{i+1}-{fig['name']}"
                    images.extend(page_figs)

                latex_map = {}
                for fig in images:
                    if "math" in fig["name"].lower() or "formula" in fig["name"].lower():
                        latex = pix2tex_from_base64(fig["base64"])
                        latex_map[fig["name"]] = f"${latex}$"
                    else:
                        latex_map[fig["name"]] = None

            if not result.get("success"):
                st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
                st.stop()

            st.session_state["ocr_pdf_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_pdf_images"] = images
            st.session_state["ocr_pdf_latex"] = latex_map
            st.session_state["ocr_pdf_done"] = True
            st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

    if st.session_state.get("ocr_pdf_done"):
        raw_text = st.session_state.get("ocr_pdf_text_raw", "")
        text_content = format_math_ocr(raw_text)
        images = st.session_state.get("ocr_pdf_images", [])
        latex_map = st.session_state.get("ocr_pdf_latex", {})

        for name, latex in latex_map.items():
            if latex:
                text_content += f"\n{name}: {latex}"

        tab_pdf_img, tab_pdf_text = st.tabs(["🖼️ Hình ảnh", "📝 Văn bản"])
        with tab_pdf_img:
            st.markdown("#### 🖼️ Hình minh hoạ trích xuất:")
            if images:
                st.success(f"🖼️ Đã tách {len(images)} vùng nghi là hình minh hoạ.")
                cols = st.columns(2)
                for i, fig in enumerate(images):
                    with cols[i % 2]:
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
            else:
                st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")

        with tab_pdf_text:
            st.markdown("#### 📋 Kết quả OCR PDF (MathType):")
            st.text_area("Kết quả OCR PDF:", text_content, height=350, label_visibility="collapsed")
            st.download_button("📄 Tải văn bản (TXT)", text_content, file_name="ket_qua_ocr.txt", mime="text/plain", use_container_width=True)

# ===== TAB 2 (image) giữ nguyên =====
# Bạn có thể sao chép lại toàn bộ xử lý ảnh như trong bản cũ và thêm pix2tex y hệt như trên nếu muốn xử lý ảnh thành công thức luôn

st.markdown("---")
st.caption("<b>OCR PDF & Ảnh: hỗ trợ MathType, ảnh minh hoạ, xuất Word/TXT. Giao diện hiện đại.</b>", unsafe_allow_html=True)
