import streamlit as st
import requests
import base64
import tempfile
import re
import itertools
import os
from PIL import Image
from io import BytesIO
from config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_images import extract_images_from_pdf
from word_export import insert_images_to_word_from_markdown
from PyPDF2 import PdfReader

# =========== GEMINI KEY LIST ===========
GEMINI_API_KEYS = [
   "AIzaSyCVUtoKWzyw27LvVbQPxs5D4n48eZWNw9k",
  "AIzaSyD6uAzLz6y2CwgEHg-1XVPM11iAPoEoc3E",
  "AIzaSyDCrzo3_3hKMF3jr114J7pb_wAAd2LesjI",
  "AIzaSyDbU_e892synpWo3uV8HLM2gj6CK0mC7eQ",
  "AIzaSyC_LxT0Xa1X5E03-FKPPri8okx6RwwZEd0",
  "AIzaSyCvNhReepkQxOJbJN1RX_n14wXYrZbAK5I",
]
api_key_cycle = itertools.cycle(GEMINI_API_KEYS)
def get_next_api_key():
    return next(api_key_cycle)

GEMINI_PROMPT = '''
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh.
2. Nếu phát hiện hình minh hoạ (hình vẽ, đồ thị, bảng, ...), đánh dấu đúng vị trí bằng cú pháp markdown: ![Hình minh hoạ](img-x.jpeg) với x là số thứ tự ảnh minh hoạ bạn upload (bắt đầu từ 0).
3. Giữ nguyên cấu trúc đoạn văn và xuống dòng.
4. Công thức toán học: tất cả ở dạng ${...}$ (inline, hệ, ký hiệu ... như hướng dẫn chi tiết).
5. Bảng biểu: dùng markdown nếu có thể.
6. Dạng bài: Trắc nghiệm, Đúng/Sai, Tự luận: đúng định dạng như ví dụ.
'''

def gemini_generate_text(image_bytes, api_key):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    b64_img = base64.b64encode(image_bytes).decode()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": GEMINI_PROMPT},
                {"inlineData": {
                    "mimeType": "image/png",
                    "data": b64_img
                }}
            ]
        }]
    }
    headers = {"Content-Type": "application/json"}
    r = requests.post(f"{api_url}?key={api_key}", json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    res = r.json()
    text = res["candidates"][0]["content"]["parts"][0]["text"]
    return text

st.set_page_config(page_title="OCR PDF & Ảnh Toán – Gemini", layout="centered")
st.title("✨ Chuyển PDF & Ảnh Toán sang Word, giữ công thức, ảnh minh hoạ ✨")

tab_pdf, tab_img = st.tabs(["📄 PDF Toán", "🖼️ Ảnh → Word + Minh hoạ"])

# =========== TAB PDF ===========
with tab_pdf:
    st.markdown("#### 📝 OCR PDF Toán, giữ công thức, ảnh minh hoạ")
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

    if uploaded_file:
        if st.button("🚀 Xử lý OCR PDF", type="primary", use_container_width=True):
            st.info("⏳ Đang xử lý OCR PDF... (vui lòng chờ)")
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
            st.success("✅ Đã nhận diện PDF thành công!")
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
    st.caption("🔖 OCR PDF hỗ trợ MathType, ảnh minh hoạ, xuất Word/TXT. Chuẩn Unicode.")

# =========== TAB ẢNH ===========
with tab_img:
    st.markdown("#### 🖼️ Ảnh (văn bản + ảnh minh hoạ) → Word, giữ vị trí ảnh minh hoạ, LaTeX dạng copy")
    uploaded_images = st.file_uploader(
        "Chọn ảnh gốc (ảnh đề hoặc các ảnh minh hoạ rời, đặt tên img-0.jpeg, img-1.jpeg...)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Chọn nhiều ảnh. Nếu là ảnh minh hoạ rời, đặt tên img-0.jpeg, img-1.jpeg..."
    )
    if uploaded_images:
        images_data = []
        latex_results = []
        # Chuẩn hóa ảnh để chèn Word (JPEG, base64), lấy tên đúng để markdown
        for i, img_file in enumerate(uploaded_images):
            img_bytes = img_file.read()
            pil_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            buf = BytesIO()
            pil_img.save(buf, format="JPEG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            name = img_file.name if img_file.name.endswith('.jpeg') else f"img-{i}.jpeg"
            images_data.append({"name": name, "base64": img_b64})
            api_key = get_next_api_key()
            with st.spinner(f"Đang nhận diện ảnh {i+1}..."):
                try:
                    text = gemini_generate_text(img_bytes, api_key)
                except Exception as e:
                    text = f"[Lỗi Gemini: {e}]"
            latex_results.append((name, text))

        tab1, tab2 = st.tabs(["📋 Văn bản (copy LaTeX)", "🖼️ Hình ảnh minh hoạ"])
        with tab1:
            st.markdown("### 📋 Kết quả từng ảnh (LaTeX dạng code):")
            for idx, (img_name, latex) in enumerate(latex_results):
                st.markdown(f"#### Ảnh {idx+1}: {img_name}")
                # Hiển thị markdown, LaTeX để code, ảnh đúng vị trí
                parts = re.split(r"(!\[Hình minh hoạ\]\(img-\d+\.jpeg\))", latex)
                for part in parts:
                    img_match = re.match(r"!\[Hình minh hoạ\]\((img-\d+\.jpeg)\)", part)
                    if img_match:
                        findname = img_match.group(1)
                        found = next((img for img in images_data if img["name"] == findname), None)
                        if found:
                            st.image(base64.b64decode(found["base64"]), caption=findname, width=340)
                        else:
                            st.warning(f"Không tìm thấy ảnh {findname}")
                    else:
                        lines = part.split("\n")
                        for line in lines:
                            if re.fullmatch(r"\$\{?.+\}?\$", line.strip()):
                                st.code(line.strip())
                            else:
                                st.markdown(line)

        with tab2:
            st.markdown("### 🖼️ Danh sách ảnh đã upload:")
            for img in images_data:
                st.image(base64.b64decode(img["base64"]), caption=img["name"], width=260)

        # Xuất Word
        markdown_out = ""
        for idx, (img_name, latex) in enumerate(latex_results):
            markdown_out += f"{latex}\n\n"
        if st.button("📝 Tạo và tải file Word giữ ảnh minh hoạ", use_container_width=True):
            with st.spinner("Đang tạo file Word..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    insert_images_to_word_from_markdown(markdown_out, images_data, tmp_word.name)
                with open(tmp_word.name, "rb") as f:
                    word_data = f.read()
                st.success("✅ Đã tạo file Word thành công!")
                st.download_button(
                    "⬇️ Tải về file Word",
                    word_data,
                    file_name="ket_qua_anh_toan.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                os.remove(tmp_word.name)
    else:
        st.info("Vui lòng tải lên ít nhất 1 ảnh để bắt đầu.")

st.caption("✨ Ảnh minh hoạ upload dạng base64, LaTeX luôn ở chế độ code dễ copy, chèn đúng vị trí khi xuất Word.")
