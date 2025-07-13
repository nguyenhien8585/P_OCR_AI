import streamlit as st
import requests
import base64
import tempfile
import re
import itertools
import os
from PIL import Image
from io import BytesIO
from config import API_URL, API_KEY  # API_URL, API_KEY cho OCR PDF
from ocr_client_api import EnhancedSmartOCRClient
from extract_images import extract_images_from_pdf
from word_export import insert_images_to_word_from_markdown
from PyPDF2 import PdfReader

# ======= Sidebar: Nhập nhiều Gemini API Key =======
st.sidebar.markdown("### 🔑 Nhập các Gemini API Key")
api_keys_input = st.sidebar.text_area(
    "Nhập mỗi key một dòng hoặc phân tách bởi dấu phẩy (,)", 
    value="", 
    height=100,
    help="Có thể nhập nhiều key Gemini để tự động luân phiên sử dụng khi gọi API."
)
def get_api_keys_list(text):
    # Tách key bởi xuống dòng hoặc dấu phẩy
    return [k.strip() for k in text.replace(',', '\n').split('\n') if k.strip()]

GEMINI_API_KEYS = get_api_keys_list(api_keys_input)
if not GEMINI_API_KEYS:
    st.sidebar.warning("⚠️ Vui lòng nhập ít nhất 1 Gemini API Key để sử dụng tab Ảnh.")

api_key_cycle = itertools.cycle(GEMINI_API_KEYS) if GEMINI_API_KEYS else None
def get_next_api_key():
    if not api_key_cycle:
        return None
    return next(api_key_cycle)

# =================== HEADER ===================
st.set_page_config(page_title="OCR PDF/Ảnh Toán & Gemini LaTeX", layout="centered")
st.title("✨ Chuyển PDF & Ảnh Toán sang Word kèm ảnh minh hoạ, LaTeX ✨")
st.caption("👨‍💻 by CGPT – Hỗ trợ OCR PDF, sinh LaTeX từ ảnh qua Gemini, xuất file Word đúng vị trí ảnh.")

tab_pdf, tab_img = st.tabs(["📄 PDF (giữ nguyên)", "🖼️ Ảnh → LaTeX + Word"])

# =========== TAB 1: XỬ LÝ PDF ===========
with tab_pdf:
    st.markdown(
        """
        <h4>📝 OCR cho file PDF</h4>
        <small>📁 <b>Chọn file PDF để nhận diện văn bản, trích xuất ảnh, xuất Word kèm ảnh minh hoạ đúng vị trí.</b></small>
        """,
        unsafe_allow_html=True,
    )
    uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"], label_visibility="collapsed")
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
    # ---------- Hiển thị kết quả nếu đã OCR ----------
    if st.session_state.get("ocr_done"):
        def dollar_to_mathptn(s):
            return re.sub(r'\$(.+?)\$', r'${\1}$', s)
        raw_text = st.session_state.get("ocr_text_raw", "")
        text_content = dollar_to_mathptn(raw_text)
        images = st.session_state.get("ocr_images", [])
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

# =========== TAB 2: ẢNH → LaTeX & WORD ===============
with tab_img:
    st.markdown("#### 🖼️ Chuyển ảnh thành LaTeX, xuất Word đúng vị trí ảnh minh hoạ.")
    uploaded_images = st.file_uploader("Chọn ảnh (PNG/JPEG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploaded_images:
        if not GEMINI_API_KEYS:
            st.error("⚠️ Bạn cần nhập ít nhất 1 Gemini API Key bên sidebar để sử dụng chức năng này.")
            st.stop()
        latex_results = []
        images_data = []
        st.info("⏳ Đang sinh LaTeX từng ảnh bằng Gemini...")
        for i, img_file in enumerate(uploaded_images):
            img_bytes = img_file.read()
            # Gọi Gemini API sinh LaTeX
            try:
                api_key = get_next_api_key()
                api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
                b64_img = base64.b64encode(img_bytes).decode()
                payload = {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {
                                "text": "Chuyển ảnh này thành mã LaTeX dạng ${...}$, giữ nguyên ký hiệu Toán học, không diễn giải, chỉ trả về mã LaTeX."
                            },
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": b64_img
                                }
                            }
                        ]
                    }]
                }
                headers = {"Content-Type": "application/json"}
                r = requests.post(f"{api_url}?key={api_key}", json=payload, headers=headers, timeout=60)
                r.raise_for_status()
                res = r.json()
                text = res["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                text = "[Lỗi khi sinh LaTeX: {}]".format(e)
            # Sửa lại định dạng cho đúng ${...}$ nếu Gemini trả về $...$
            text = re.sub(r"^\$([^\$]*)\$$", r"${\1}$", text.strip())
            latex_results.append((img_file.name, text))
            # Chuẩn hóa ảnh (JPEG, base64) để chèn Word
            pil_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            buf = BytesIO()
            pil_img.save(buf, format="JPEG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            images_data.append({"name": f"img-{i}.jpeg", "base64": img_b64})
        # Hiển thị từng ảnh & LaTeX
        for idx, (img_name, latex) in enumerate(latex_results):
            st.image(uploaded_images[idx], caption=img_name, width=220)
            st.markdown("**LaTeX:**")
            st.code(latex)
            try:
                st.latex(latex.replace("$", ""))
            except:
                pass
        # Tạo markdown tổng hợp để xuất Word
        markdown_out = ""
        for idx, (img_name, latex) in enumerate(latex_results):
            markdown_out += f"{latex}\n\n![Hình minh hoạ](img-{idx}.jpeg)\n\n"
        if st.button("📝 Tạo và tải file Word từ ảnh + LaTeX", use_container_width=True):
            with st.spinner("Đang tạo file Word..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    insert_images_to_word_from_markdown(markdown_out, images_data, tmp_word.name)
                with open(tmp_word.name, "rb") as f:
                    word_data = f.read()
                st.success("✅ Đã tạo file Word thành công!")
                st.download_button(
                    "⬇️ Tải về file Word",
                    word_data,
                    file_name="ket_qua_anh_latex.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                os.remove(tmp_word.name)
    st.markdown("---")
    st.caption("📷 Chuyển nhiều ảnh thành LaTeX, xuất Word chuẩn với ảnh minh hoạ và mã Toán học.")

