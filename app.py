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
from PIL import Image
import io

st.set_page_config(page_title="OCR PDF/Ảnh ➔ LaTeX + Word", layout="centered")
st.markdown(
    "<h2>📝 OCR PDF/Ảnh ➔ LaTeX + Word</h2>", unsafe_allow_html=True
)

tab_pdf, tab_img = st.tabs(["📄 PDF", "🖼️ Ảnh (PNG/JPG)"])

# --- TAB PDF ---
with tab_pdf:
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
        if st.button("🚀 Xử lý OCR PDF", type="primary", use_container_width=True, key="btn_ocr_pdf"):
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
            st.session_state["ocr_text_pdf"] = result["data"].get("text_content", "")
            st.session_state["ocr_images_pdf"] = images
            st.session_state["ocr_done_pdf"] = True
            st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

    if st.session_state.get("ocr_done_pdf"):
        raw_text = st.session_state.get("ocr_text_pdf", "")
        images = st.session_state.get("ocr_images_pdf", [])

        # Thêm markdown image vào văn bản để export LaTeX/Word đúng vị trí ảnh
        markdown_with_images = raw_text
        for img in images:
            markdown_with_images += f'\n\n![minh hoạ]({img["name"]})'

        tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
        with tab1:
            st.markdown("#### 📋 Kết quả OCR PDF:")
            st.text_area("Kết quả OCR PDF:", markdown_with_images, height=350, label_visibility="collapsed")

            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📄 Tải văn bản (TXT)",
                    markdown_with_images,
                    file_name="ket_qua_ocr.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with col2:
                word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True, key="word_pdf")
                if word_btn:
                    with st.spinner("Đang tạo file Word..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                            insert_images_to_word_from_markdown(markdown_with_images, images, tmp_word.name)
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
            # Cho phép tải về dạng LaTeX đơn giản:
            st.download_button(
                "📄 Tải về LaTeX (markdown img)",
                markdown_with_images,
                file_name="output_latex_input.txt",
                mime="text/plain",
                use_container_width=True,
            )

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

# --- TAB ẢNH ---
with tab_img:
    uploaded_img = st.file_uploader("Chọn ảnh PNG/JPG để xử lý OCR", type=["png", "jpg", "jpeg"])
    if uploaded_img:
        img_bytes = uploaded_img.read()
        file_name = uploaded_img.name
        mime_type = "image/png"
        size_mb = len(img_bytes) / (1024 * 1024)
        with st.expander("ℹ️ Thông tin ảnh", expanded=True):
            st.write(f"**Tên file:** {file_name}")
            st.write(f"**Loại file:** {mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")

        if st.button("🚀 Xử lý OCR ẢNH", type="primary", use_container_width=True, key="btn_ocr_img"):
            st.info("⏳ Đang xử lý OCR ẢNH...")
            with st.spinner("Đang nhận diện văn bản và tách hình ảnh..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                result = client.convert(img_bytes, file_name, mime_type)
                # Tách từng vùng ảnh nhỏ nếu muốn (hoặc lấy chính ảnh gốc)
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG")
                b64_img = base64.b64encode(buf.getvalue()).decode()
                images = [{"name": "img-0.jpeg", "base64": b64_img}]
            if not result.get("success"):
                st.error("❌ Xử lý OCR ảnh thất bại: " + str(result.get("error")))
                st.stop()
            st.session_state["ocr_text_img"] = result["data"].get("text_content", "")
            st.session_state["ocr_images_img"] = images
            st.session_state["ocr_done_img"] = True
            st.success("✅ Xử lý OCR ảnh thành công!")

    if st.session_state.get("ocr_done_img"):
        raw_text = st.session_state.get("ocr_text_img", "")
        images = st.session_state.get("ocr_images_img", [])
        markdown_with_images = raw_text
        for img in images:
            markdown_with_images += f'\n\n![minh hoạ]({img["name"]})'

        tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Ảnh"])
        with tab1:
            st.markdown("#### 📋 Kết quả OCR ảnh:")
            st.text_area("Kết quả OCR ẢNH:", markdown_with_images, height=350, label_visibility="collapsed")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📄 Tải văn bản (TXT)",
                    markdown_with_images,
                    file_name="ket_qua_ocr_anh.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with col2:
                word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True, key="word_img")
                if word_btn:
                    with st.spinner("Đang tạo file Word..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                            insert_images_to_word_from_markdown(markdown_with_images, images, tmp_word.name)
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
            st.download_button(
                "📄 Tải về LaTeX (markdown img)",
                markdown_with_images,
                file_name="output_latex_input.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with tab2:
            if images:
                st.success(f"🖼️ Ảnh OCR hoặc đã tách:")
                for img in images:
                    try:
                        img_bytes = base64.b64decode(img["base64"])
                        st.image(img_bytes, caption=img["name"], use_container_width=True)
                    except Exception as e:
                        st.error(f"Không đọc được ảnh {img['name']}: {e}")
            else:
                st.warning("Không tìm thấy vùng ảnh!")

st.markdown("---")
st.caption("🔖 <b>OCR PDF/Ảnh: hỗ trợ MathType, ảnh minh hoạ, xuất Word, LaTeX. Giao diện thân thiện.</b>", unsafe_allow_html=True)
