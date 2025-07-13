import streamlit as st
import requests
import base64
import tempfile
import re
import itertools
import os
from PIL import Image
from io import BytesIO
import numpy as np
import cv2
from config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_images import extract_images_from_pdf
from word_export import insert_images_to_word_from_markdown
from PyPDF2 import PdfReader

# =========== GEMINI KEY LIST ===========
GEMINI_API_KEYS = [
    "AIzaSyAAA111111111111111111111111",
    "AIzaSyBBB222222222222222222222222"
]
api_key_cycle = itertools.cycle(GEMINI_API_KEYS)
def get_next_api_key():
    return next(api_key_cycle)

# =========== PROMPT ==============
GEMINI_PROMPT = '''
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh.
2. Nếu phát hiện hình minh hoạ (hình vẽ, đồ thị, bảng, ...), đánh dấu đúng vị trí bằng cú pháp markdown: ![Hình minh hoạ](subimg-x.jpeg) với x là số thứ tự hình minh hoạ bạn phát hiện trên ảnh này (bắt đầu từ 0).
3. Giữ nguyên cấu trúc đoạn văn và xuống dòng.
4. Công thức toán học: tất cả ở dạng ${...}$ (inline, hệ, ký hiệu ... như hướng dẫn chi tiết).
5. Bảng biểu: dùng markdown nếu có thể.
6. Dạng bài: Trắc nghiệm, Đúng/Sai, Tự luận: đúng định dạng như ví dụ.
'''

# =========== HÀM TÁCH ẢNH MINH HOẠ ==========
def extract_sub_images(pil_img, min_area=3000):
    img = np.array(pil_img.convert("L"))
    _, thresh = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sub_images = []
    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h > min_area:
            crop = pil_img.crop((x, y, x + w, y + h))
            buf = BytesIO()
            crop.save(buf, format="JPEG")
            sub_images.append({"name": f"subimg-{i}.jpeg", "base64": base64.b64encode(buf.getvalue()).decode()})
    return sub_images

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

    # --------- Nút OCR ----------
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
    # --------- Hiển thị kết quả ----------
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
    st.markdown("#### 🖼️ Tách minh hoạ từ ảnh, sinh văn bản, xuất Word đúng vị trí ảnh minh hoạ")
    uploaded_images = st.file_uploader(
        "Chọn hình ảnh để xử lý OCR",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Drag & drop hoặc chọn nhiều ảnh. Mỗi ảnh là 1 trang, hệ thống sẽ tách minh hoạ tự động."
    )
    if uploaded_images:
        tab1, tab2 = st.tabs(["📋 Văn bản", "🖼️ Hình minh hoạ"])
        all_subimgs = []
        markdown_results = []
        for idx, img_file in enumerate(uploaded_images):
            img_bytes = img_file.read()
            pil_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            api_key = get_next_api_key()
            with st.spinner(f"Đang nhận diện trang {idx+1}..."):
                subimgs = extract_sub_images(pil_img)
                all_subimgs.extend(subimgs)
                try:
                    text = gemini_generate_text(img_bytes, api_key)
                except Exception as e:
                    text = f"[Lỗi Gemini: {e}]"
                markdown_results.append((text, subimgs))

        # Tab văn bản: preview từng trang (ảnh), có markdown ảnh minh hoạ
        with tab1:
            st.markdown("### 📋 Kết quả OCR Image:")
            for idx, (text, subimgs) in enumerate(markdown_results):
                st.markdown(f"#### Trang {idx+1}:")
                parts = re.split(r"(!\[Hình minh hoạ\]\(subimg-\d+\.jpeg\))", text)
                for part in parts:
                    img_match = re.match(r"!\[Hình minh hoạ\]\((subimg-(\d+)\.jpeg)\)", part)
                    if img_match:
                        imgname = img_match.group(1)
                        found = next((img for img in subimgs if img["name"] == imgname), None)
                        if found:
                            st.image(base64.b64decode(found["base64"]), caption=imgname, width=340)
                        else:
                            st.warning(f"Không tìm thấy ảnh {imgname}")
                    else:
                        st.markdown(part)
        # Tab hình minh hoạ: preview toàn bộ ảnh nhỏ đã tách
        with tab2:
            st.markdown(f"### 🖼️ Đã tách {len(all_subimgs)} hình minh hoạ từ {len(uploaded_images)} ảnh:")
            for img in all_subimgs:
                st.image(base64.b64decode(img["base64"]), caption=img["name"], width=260)

        # Tạo file Word giữ đúng vị trí ảnh minh hoạ
        all_markdown = ""
        all_images = []
        for idx, (text, subimgs) in enumerate(markdown_results):
            all_markdown += f"### Trang {idx+1}\n{text}\n\n"
            all_images.extend(subimgs)
        if st.button("📝 Tạo và tải file Word giữ ảnh minh hoạ", use_container_width=True):
            with st.spinner("Đang tạo file Word..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    insert_images_to_word_from_markdown(all_markdown, all_images, tmp_word.name)
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

st.caption("✨ Kết quả Word luôn giữ vị trí ảnh minh hoạ, công thức toán học chuẩn LaTeX, chuẩn Unicode.")
