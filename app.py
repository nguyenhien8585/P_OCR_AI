import streamlit as st
from config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_images import extract_images_from_pdf
from word_export import insert_images_to_word_from_markdown
import os
import base64
import re
from PyPDF2 import PdfReader
import tempfile
import io
import zipfile

st.set_page_config(page_title="OCR cho file PDF", layout="centered")
st.markdown(
    """
    <h2>📝 OCR cho file PDF</h2>
    <small>📁 <b>Chọn file PDF để xử lý OCR</b></small>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Chọn file PDF để xử lý OCR", type=["pdf"], label_visibility="collapsed"
)

# ---------- Thông tin file ----------
num_pages = None
if uploaded_file:
    pdf_bytes = uploaded_file.read()
    file_name = uploaded_file.name
    mime_type = "application/pdf"
    size_mb = len(pdf_bytes) / (1024 * 1024)

    try:
        uploaded_file.seek(0)
        reader = PdfReader(uploaded_file)
        num_pages = len(reader.pages)
        uploaded_file.seek(0)
    except:
        num_pages = "?"

    with st.expander("ℹ️ Thông tin file", expanded=True):
        st.write(f"**Tên file:** {file_name}")
        st.write(f"**Loại file:** {mime_type}")
        st.write(f"**Kích thước:** {size_mb:.1f} MB")
        st.write(f"**Số trang:** {num_pages}")

# ---------- Nút xử lý OCR ----------
if uploaded_file:
    if st.button("🚀 Xử lý OCR PDF", type="primary", use_container_width=True):
        st.info("⏳ Đang xử lý OCR PDF... (quá trình này có thể mất vài phút)")
        with st.spinner("Đang nhận diện văn bản và trích xuất hình ảnh..."):
            client = EnhancedSmartOCRClient(API_URL, API_KEY)
            uploaded_file.seek(0)
            pdf_bytes = uploaded_file.read()
            result = client.convert(pdf_bytes, file_name, mime_type)
            images = extract_images_from_pdf(pdf_bytes)
        if not result.get("success"):
            st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
            st.stop()

        st.session_state["ocr_text_raw"] = result["data"].get("text_content", "")
        st.session_state["ocr_images"] = images
        st.session_state["ocr_done"] = True
        st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

# --------- HÀM TIỆN ÍCH ---------
def to_mathptn_latex(s):
    def replacer(match):
        expr = match.group(1)
        if expr.startswith("{") and expr.endswith("}"):
            return f"${expr}$"
        return f"${{{expr}}}$"
    return re.sub(r'\$(.+?)\$', replacer, s)

def merge_text_and_images_by_page(text_content, images):
    if '\f' in text_content:
        pages = text_content.split('\f')
    else:
        pages = [text_content]
    page_images = {}
    for img in images:
        page_images.setdefault(img.get("page", 0), []).append(img)
    result = ""
    for idx, page_text in enumerate(pages):
        result += page_text.strip() + "\n"
        if idx in page_images:
            for img in page_images[idx]:
                result += f'![]({img["name"]})\n'
        result += "\n\\pagebreak\n"
    return result.strip()

def markdown_to_latex(text):
    text = to_mathptn_latex(text)
    def repl(match):
        caption, img_name = match.groups()
        return (
            "\\begin{figure}[H]\n"
            "  \\centering\n"
            f"  \\includegraphics[width=0.6\\textwidth]{{{img_name}}}\n"
            f"  \\caption{{{caption}}}\n"
            "\\end{figure}\n"
        )
    latex_body = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, text)
    latex_body = re.sub(r'!\[\]\(([^)]+)\)', lambda m: (
        "\\begin{figure}[H]\n"
        "  \\centering\n"
        f"  \\includegraphics[width=0.6\\textwidth]{{{m.group(1)}}}\n"
        "\\end{figure}\n"
    ), latex_body)
    latex_full = (
        "\\documentclass{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{graphicx}\n"
        "\\usepackage{float}\n"
        "\\begin{document}\n"
        + latex_body +
        "\n\\end{document}"
    )
    return latex_full

def export_latex_with_images(text, image_list):
    latex_code = markdown_to_latex(text)
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w") as zf:
        zf.writestr("ket_qua_ocr.tex", latex_code)
        for img in image_list:
            img_bytes = base64.b64decode(img["base64"])
            zf.writestr(img["name"], img_bytes)
    mem_zip.seek(0)
    return mem_zip.getvalue()

# ---------- Hiển thị kết quả nếu đã OCR ----------
if st.session_state.get("ocr_done"):
    raw_text = st.session_state.get("ocr_text_raw", "")
    images = st.session_state.get("ocr_images", [])
    text_content = merge_text_and_images_by_page(raw_text, images)

    tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
    with tab1:
        st.markdown("#### 📋 Kết quả OCR PDF (ảnh tự động chèn vào đúng trang):")
        st.text_area("Kết quả OCR PDF:", text_content, height=350, label_visibility="collapsed")
        st.markdown(
            """
            <small>
            Ảnh minh hoạ được tự động chèn vào đúng vị trí sau mỗi trang.<br>
            Công thức được chuyển về dạng <b>${...}$</b> trong LaTeX.
            </small>
            """,
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True, key="word")
            if word_btn:
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, images, tmp_word.name)
                    with open(tmp_word.name, "rb") as f:
                        word_data = f.read()
                    st.success("✅ Đã tạo file Word thành công!")
                    st.download_button(
                        "⬇️ Tải về file Word",
                        word_data,
                        file_name="ket_qua_ocr.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                    os.remove(tmp_word.name)
        with col3:
            latex_btn = st.button("📝 Tạo và tải file LaTeX", use_container_width=True, key="latex")
            if latex_btn:
                with st.spinner("Đang tạo file LaTeX..."):
                    tex_bytes = export_latex_with_images(text_content, images)
                    st.success("✅ Đã tạo file LaTeX thành công!")
                    st.download_button(
                        "⬇️ Tải về file LaTeX (.zip)",
                        tex_bytes,
                        file_name="ket_qua_ocr_latex.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

    with tab2:
        if images:
            st.success(f"🖼️ Đã tìm thấy {len(images)} hình ảnh:")
            for img in images:
                try:
                    img_bytes = base64.b64decode(img["base64"])
                    st.image(img_bytes, caption=f'{img["name"]} (trang {img["page"]+1})', use_container_width=True)
                except Exception as e:
                    st.error(f"Không đọc được ảnh {img['name']}: {e}")
        else:
            st.warning("Không tìm thấy ảnh minh hoạ thực sự trong PDF!")

st.markdown("---")
st.caption("🔖 <b>OCR PDF: tự động tách ảnh, gắn ảnh đúng vị trí trang, xuất Word/LaTeX/TXT.</b>", unsafe_allow_html=True)
