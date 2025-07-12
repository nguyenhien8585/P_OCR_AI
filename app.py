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

st.set_page_config(page_title="OCR PDF & Image", layout="centered")

tab1, tab2 = st.tabs([
    "📄 OCR PDF",
    "🖼️ OCR Image"
])

def format_math_ocr(text):
    """
    - Chỉ bọc ${...}$ cho ký hiệu, số, mặt phẳng, cụm đặc biệt toán học
    - Không bọc đáp án trắc nghiệm (A., B., C., D.)
    - Không bọc các heading/trang/mã đề/Thời gian làm bài
    - Loại bỏ #
    - Ảnh lên đầu (nếu muốn), hoặc để đúng vị trí marker
    """
    # 1. Xoá dấu #, heading, trang, mã đề, tiêu đề
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'=== Page.*?===', '', text)
    text = re.sub(r'^Trang\s+\$\{\d+/\d+\}\s*-\s*Mã\s+đề\s+thi\s+\$\{\d+\}\$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(^|\n)(KỲ\s*\$\{?THI\}?\$?\s*TỐT\s*NGHIỆP.*\n|ĐỀ\s*\$\{?THI\}?\$?\s*CHÍNH\s*THỨC.*\n|Môn\s*thi:.*\n|\(Đề thi.*\n|Thời gian làm bài.*\n|Mã đề:.*\n|Họ, tên thí sinh:.*\n|PHẦN\s*\$\{?I\}?\$?.*\n|Trang.*|^\s*#.*$)', '', text, flags=re.IGNORECASE)
    text = text.replace('\n# ', '\n')
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)

    # Đưa ảnh lên trên nếu muốn (hoặc để nguyên đúng vị trí marker)
    img_pattern = r'!\[([^\]]*)\]\((img-\d+\.jpeg)\)'
    img_lines = re.findall(img_pattern, text)
    img_block = ""
    if img_lines:
        for _, img in img_lines:
            img_block += f'![{img}]({img})\n'
        text = re.sub(img_pattern, '', text)
        text = img_block + "\n" + text

    # Không bọc dòng đáp án A. ... (bắt đầu bằng A., B., C., D.)
    # Chỉ bọc các cụm toán đặc biệt
    math_patterns = [
        r'\bO\.?A?B?C?\b',
        r'\bOxyz\b',
        r'\bOA\b', r'\bOB\b', r'\bOC\b', r'\bAB\b', r'\bAC\b', r'\bBC\b', r"\bA'\b", r"\bB'\b", r"\bC'\b",
        r'\b[Pp]\b', r'\bn̄\b', r'\b[a-zA-Z]\d+\b',           # Cụm kiểu n̄, P, n1...
        r'\b\d{1,3}(?:/\d{1,3})?\b',                         # số hoặc phân số
        r'\([A-Z\' ]+\)',                                    # mặt phẳng (ABC)
        r'[-+]?\d+'                                          # số nguyên
    ]
    def wrap_math(match):
        s = match.group(0)
        # Không bọc nếu là đáp án trắc nghiệm
        if re.match(r'^\s*[A-D]\.', s.strip()):
            return s
        if re.match(r'^\$\{.*\}\$$', s):
            return s
        return f"${{{s}}}$"
    # Bọc math nhưng không bọc câu hỏi/câu số
    for pat in math_patterns:
        text = re.sub(pat, wrap_math, text)
    # Không bọc cho Câu ${1}$: -> Câu 1:
    text = re.sub(r'Câu\s*\$\{(\d+)\}\$', r'Câu \1', text)
    # Đáp án dạng ${A}$., ... về A., B., ...
    text = re.sub(r'\$\{([A-D])\}\$\.', r'\1.', text)
    # Loại trùng lặp liên tiếp
    text = re.sub(r'(\$\{[^}]+\}\$)(\s*\1)+', r'\1', text)
    # Dọn dòng trống
    text = re.sub(r'\n\s*\n', '\n', text)
    # Dọn extra spaces trước marker ảnh
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip()

# ================ TAB 1: OCR PDF ==================
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
            if not result.get("success"):
                st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
                st.stop()

            st.session_state["ocr_pdf_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_pdf_images"] = images
            st.session_state["ocr_pdf_done"] = True
            st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

    if st.session_state.get("ocr_pdf_done"):
        raw_text = st.session_state.get("ocr_pdf_text_raw", "")
        text_content = format_math_ocr(raw_text)
        images = st.session_state.get("ocr_pdf_images", [])

        tab_pdf_text, tab_pdf_img = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
        with tab_pdf_img:
            # Ảnh lên trên
            if images:
                st.success(f"🖼️ Đã tách {len(images)} vùng nghi là hình minh hoạ. Tick chọn đúng hình bên dưới trước khi xuất Word:")
                cols = st.columns(2)
                selected_fig_names = []
                for i, fig in enumerate(images):
                    with cols[i % 2]:
                        checked = st.checkbox(f"Chọn {fig['name']}", value=True, key=f"pdf_figcheck{i}")
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                        if checked:
                            selected_fig_names.append(fig["name"])
            else:
                st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")
            export_figures = [fig for fig in images if fig["name"] in selected_fig_names] if images else []

        with tab_pdf_text:
            st.markdown("#### 📋 Kết quả OCR PDF:")
            st.text_area("Kết quả OCR PDF:", text_content, height=400, label_visibility="collapsed")
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr.txt",
                mime="text/plain",
                use_container_width=True,
            )
            if st.button("📝 Tạo và tải file Word", key="word_pdf_create", use_container_width=True):
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, export_figures, tmp_word.name)
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

# ================ TAB 2: OCR IMAGE ==================
with tab2:
    st.markdown("### 🖼️ OCR cho hình ảnh")
    uploaded_img = st.file_uploader("Chọn hình ảnh để xử lý OCR", type=["png", "jpg", "jpeg", "webp"])
    img_file_name = None

    if uploaded_img:
        img_bytes_orig = uploaded_img.read()
        try:
            img = Image.open(io.BytesIO(img_bytes_orig))
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()
            img_file_name = uploaded_img.name if uploaded_img.name.endswith(".jpg") or uploaded_img.name.endswith(".jpeg") else uploaded_img.name.split(".")[0]+".jpg"
        except Exception as e:
            st.error(f"Ảnh upload không hợp lệ hoặc không đọc được: {e}")
            st.stop()

        img_mime_type = "image/jpeg"
        size_mb = len(img_bytes) / (1024 * 1024)
        with st.expander("ℹ️ Thông tin file", expanded=True):
            st.write(f"**Tên file:** {img_file_name}")
            st.write(f"**Loại file:** {img_mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")
        st.image(img_bytes, caption="Ảnh đã upload", use_container_width=True)

        with st.spinner("Đang tách các hình minh hoạ..."):
            figures = extract_figures_from_image(img_bytes, min_area=1200, max_figures=10)
        st.session_state["ocr_img_figures"] = figures

        if st.button("🚀 Xử lý OCR Image", key="ocr_img_btn", use_container_width=True):
            st.info("⏳ Đang nhận diện văn bản từ ảnh...")
            with st.spinner("Đang nhận diện văn bản từ ảnh..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                result = client.convert(img_bytes, img_file_name, img_mime_type)
            if not result.get("success"):
                st.error("❌ Xử lý OCR ảnh thất bại: " + str(result.get("error")))
                st.stop()
            st.session_state["ocr_img_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_img_done"] = True
            st.success("✅ Xử lý OCR Ảnh hoàn tất thành công!")

    if st.session_state.get("ocr_img_done"):
        raw_text = st.session_state.get("ocr_img_text_raw", "")
        text_content = format_math_ocr(raw_text)
        figures = st.session_state.get("ocr_img_figures", [])

        tab_img_text, tab_img_fig = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
        with tab_img_fig:
            if figures:
                st.success(f"🖼️ Đã tách {len(figures)} vùng nghi là hình minh hoạ. Tick chọn đúng hình bên dưới trước khi xuất Word:")
                cols = st.columns(2)
                selected_fig_names = []
                for i, fig in enumerate(figures):
                    with cols[i % 2]:
                        checked = st.checkbox(f"Chọn {fig['name']}", value=True, key=f"img_figcheck{i}")
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                        if checked:
                            selected_fig_names.append(fig["name"])
            else:
                st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")
            export_figures = [fig for fig in figures if fig["name"] in selected_fig_names] if figures else []

        with tab_img_text:
            st.markdown("#### 📋 Kết quả OCR Ảnh:")
            st.text_area("Kết quả OCR Ảnh:", text_content, height=400, label_visibility="collapsed")
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr_anh.txt",
                mime="text/plain",
                use_container_width=True,
            )
            if st.button("📝 Tạo và tải file Word", key="word_img_create", use_container_width=True):
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, export_figures, tmp_word.name)
                    with open(tmp_word.name, "rb") as f:
                        word_data = f.read()
                    st.success("✅ Đã tạo file Word thành công!")
                    st.download_button(
                        "⬇️ Tải về file Word",
                        word_data,
                        file_name="ket_qua_ocr_anh.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                    os.remove(tmp_word.name)

st.markdown("---")
st.caption(
    "<b>OCR PDF & Ảnh: hỗ trợ MathType, ảnh minh hoạ, xuất Word/TXT. Giao diện hiện đại.</b>",
    unsafe_allow_html=True
)
