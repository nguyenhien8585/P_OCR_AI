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
import zipfile
import io

st.set_page_config(page_title="OCR PDF & Ảnh", layout="centered")
st.markdown(
    """
    <h2>📝 OCR cho PDF và Ảnh (PNG, JPG)</h2>
    <small>📁 <b>Chọn file PDF hoặc ảnh để xử lý OCR</b></small>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Chọn file PDF hoặc ảnh (PNG/JPG) để xử lý OCR", 
    type=["pdf", "png", "jpg", "jpeg"], 
    label_visibility="collapsed"
)

# ---------- Thông tin file ----------
if uploaded_file:
    file_name = uploaded_file.name
    file_type = file_name.split(".")[-1].lower()
    mime_type = uploaded_file.type
    uploaded_file.seek(0)
    file_bytes = uploaded_file.read()
    size_mb = len(file_bytes) / (1024 * 1024)
    num_pages = None
    if file_type == "pdf":
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
        if file_type == "pdf":
            st.write(f"**Số trang:** {num_pages}")

# ---------- Xử lý OCR ----------
if uploaded_file:
    is_pdf = file_type == "pdf"
    if st.button("🚀 Xử lý OCR", type="primary", use_container_width=True):
        st.info("⏳ Đang xử lý OCR... (có thể mất vài phút)")
        with st.spinner("Đang nhận diện văn bản và trích xuất hình ảnh..."):
            client = EnhancedSmartOCRClient(API_URL, API_KEY)
            result = client.convert(file_bytes, file_name, mime_type)
            if is_pdf:
                images = extract_images_from_pdf(file_bytes)
            else:
                img_b64 = base64.b64encode(file_bytes).decode()
                images = [{"name": file_name, "base64": img_b64}]
        if not result.get("success"):
            st.error("❌ Xử lý OCR thất bại: " + str(result.get("error")))
            st.stop()
        st.session_state["ocr_text_raw"] = result["data"].get("text_content", "")
        st.session_state["ocr_images"] = images
        st.session_state["ocr_done"] = True
        st.success("✅ Xử lý OCR hoàn tất!")

# ---------- Hiển thị kết quả nếu đã OCR ----------
def images_to_latex(images, image_dir='images'):
    latex_code = ""
    for img in images:
        img_name = img['name']
        latex_code += (
            "\\begin{figure}[H]\n"
            "    \\centering\n"
            f"    \\includegraphics[width=0.6\\textwidth]{{{image_dir}/{img_name}}}\n"
            "\\end{figure}\n\n"
        )
    return latex_code

if st.session_state.get("ocr_done"):
    def dollar_to_mathptn(s):
        return re.sub(r'\$(.+?)\$', r'${\1}$', s)
    raw_text = st.session_state.get("ocr_text_raw", "")
    text_content = dollar_to_mathptn(raw_text)
    images = st.session_state.get("ocr_images", [])

    tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
    with tab1:
        st.markdown("#### 📋 Kết quả OCR:")
        st.text_area("Kết quả OCR:", text_content, height=350, label_visibility="collapsed")

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

    with tab2:
        if images:
            st.success(f"🖼️ Đã tìm thấy {len(images)} hình ảnh:")
            # Tải tất cả ảnh ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                for img in images:
                    img_bytes = base64.b64decode(img["base64"])
                    zipf.writestr(img["name"], img_bytes)
            st.download_button(
                "⬇️ Tải tất cả ảnh (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="anh_tach.zip",
                mime="application/zip",
                use_container_width=True,
            )
            # Tải mã LaTeX ảnh
            latex_code = images_to_latex(images)
            st.download_button(
                "📝 Tải mã LaTeX cho ảnh",
                data=latex_code,
                file_name="latex_anh.tex",
                mime="text/plain",
                use_container_width=True,
            )
            # Hiển thị từng ảnh + nút tải riêng
            for img in images:
                try:
                    img_bytes = base64.b64decode(img["base64"])
                    st.image(img_bytes, caption=img["name"], use_container_width=True)
                    st.download_button(
                        f"⬇️ Tải {img['name']}",
                        data=img_bytes,
                        file_name=img["name"],
                        mime="image/jpeg",
                        use_container_width=True,
                        key=img["name"]
                    )
                except Exception as e:
                    st.error(f"Không đọc được ảnh {img['name']}: {e}")
        else:
            st.warning("Không tìm thấy ảnh minh hoạ trong file!")

st.markdown("---")
st.caption("🔖 <b>OCR PDF/Ảnh: hỗ trợ MathType, tách ảnh, xuất Word/TXT, sinh mã LaTeX. Giao diện thân thiện.</b>", unsafe_allow_html=True)
