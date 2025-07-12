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

st.set_page_config(page_title="OCR PDF & Image", layout="centered")

tab1, tab2 = st.tabs([
    "📄 OCR PDF", 
    "🖼️ OCR Image"
])

# ================= TAB 1: OCR PDF =================
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
            with st.spinner("Đang nhận diện văn bản và trích xuất hình ảnh..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                uploaded_pdf.seek(0)
                pdf_bytes = uploaded_pdf.read()
                result = client.convert(pdf_bytes, file_name, mime_type)
                images = extract_images_from_pdf(pdf_bytes)
            if not result.get("success"):
                st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
                st.stop()

            st.session_state["ocr_pdf_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_pdf_images"] = images
            st.session_state["ocr_pdf_done"] = True
            st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

    if st.session_state.get("ocr_pdf_done"):
        def dollar_to_mathptn(s):
            return re.sub(r'\$(.+?)\$', r'${\1}$', s)
        raw_text = st.session_state.get("ocr_pdf_text_raw", "")
        text_content = dollar_to_mathptn(raw_text)
        images = st.session_state.get("ocr_pdf_images", [])

        tab_pdf_text, tab_pdf_img = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
        with tab_pdf_text:
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
                word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True, key="word_pdf")
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
        with tab_pdf_img:
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

# ================= TAB 2: OCR Image ================
with tab2:
    st.markdown("### 🖼️ OCR cho file Ảnh (PNG, JPG)")
    uploaded_img = st.file_uploader("Chọn file ảnh để xử lý OCR", type=["png", "jpg", "jpeg"])
    img_file_name = None

    if uploaded_img:
        img_bytes = uploaded_img.read()
        img_file_name = uploaded_img.name
        img_mime_type = uploaded_img.type
        size_mb = len(img_bytes) / (1024 * 1024)
        with st.expander("ℹ️ Thông tin file", expanded=True):
            st.write(f"**Tên file:** {img_file_name}")
            st.write(f"**Loại file:** {img_mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")
        st.image(img_bytes, caption=img_file_name, use_container_width=True)

    if uploaded_img:
        if st.button("🚀 Xử lý OCR Ảnh", key="ocr_img_btn", use_container_width=True):
            st.info("⏳ Đang xử lý OCR Ảnh...")
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
        def dollar_to_mathptn(s):
            return re.sub(r'\$(.+?)\$', r'${\1}$', s)
        raw_text = st.session_state.get("ocr_img_text_raw", "")
        text_content = dollar_to_mathptn(raw_text)
        st.markdown("#### 📋 Kết quả OCR Ảnh:")
        st.text_area("Kết quả OCR Ảnh:", text_content, height=350, label_visibility="collapsed")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr_anh.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True, key="word_img")
            if word_btn:
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        # Ảnh upload là ảnh gốc, không tách block ảnh nhỏ như PDF, chỉ chèn cuối cùng
                        images = []
                        # Nếu muốn chèn ảnh gốc vào Word, thêm block:
                        images.append({"name": img_file_name, "base64": base64.b64encode(img_bytes).decode()})
                        insert_images_to_word_from_markdown(text_content, images, tmp_word.name)
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
st.caption("🔖 <b>OCR PDF & Ảnh: hỗ trợ MathType, ảnh minh hoạ, xuất Word/TXT. Giao diện hiện đại.</b>", unsafe_allow_html=True)
