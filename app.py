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

# ============ HEADER & GIAO DIỆN ============
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

file_info = None
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

# ----- CHO BẤM NÚT MỚI XỬ LÝ -----
if uploaded_file:
    run_ocr = st.button("🚀 Xử lý OCR PDF", type="primary", use_container_width=True)
else:
    run_ocr = False

# ========== XỬ LÝ KHI BẤM NÚT ==========
if uploaded_file and run_ocr:
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

    # Chuyển đổi $...$ thành ${...}$ tự động cho MathType
    def dollar_to_mathptn(s):
        return re.sub(r'\$(.+?)\$', r'${\1}$', s)
    raw_text = result["data"].get("text_content", "")
    text_content = dollar_to_mathptn(raw_text)

    st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

    # ==== GIAO DIỆN TABS ====
    tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
    with tab1:
        st.markdown("#### 📋 Kết quả OCR PDF:")
        st.text_area("Kết quả OCR PDF:", text_content, height=350, label_visibility="collapsed")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            # Chỉ tạo/tải file Word sau khi bấm nút
            word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True)
            if word_btn:
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, images, tmp_word.name)
                        tmp_word.seek(0)
                        st.success("✅ Đã tạo file Word thành công!")
                        st.download_button(
                            "⬇️ Tải về file Word",
                            tmp_word,
                            file_name="ket_qua_ocr.docx",
                            use_container_width=True
                        )
                    os.remove(tmp_word.name)

    with tab2:
        if images:
            st.success(f"🖼️ Đã tìm thấy {len(images)} hình ảnh:")
            for img in images:
                try:
                    img_bytes = base64.b64decode(img["base64"])
                    st.image(img_bytes, caption=img["name"], use_container_width=True)
                except Exception as e:
                    st.error(f"Không đọc được ảnh {img['name']}: {e}")
        else:
            st.warning("Không tìm thấy ảnh minh hoạ thực sự trong PDF!")

st.markdown("---")
st.caption("🔖 <b>OCR PDF: hỗ trợ MathType, ảnh minh hoạ, xuất Word/TXT. Giao diện thân thiện.</b>", unsafe_allow_html=True)
