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

# ==== Prompt Gemini ====
GEMINI_PROMPT = '''
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh
2. Giữ nguyên cấu trúc đoạn văn và xuống dòng
3. Với công thức toán học: gõ lại chính xác, tất cả công thức Toán dưới dạng ${...}$
   - Inline: ${x^2 + 2x + 1}$
   - Hệ: $\begin{cases} ... \end{cases}$
   - Ký hiệu: các từ đặt tên cho tên bằng chữ A,B,C... hoặc các cụm từ AB, CD, Oxyz,... hoặc các số 1,2,3,..., tỉ lệ phần trăm 1%,0.1% , 0,1%,.... ví dụ ${Oxyz}$, ${A}$, ${AB}$, ${0{,}1\%}$, ${CD}$, ${1}$,${Oxyz}$, ${S.ABCD}$.....
4. Với bảng biểu: dùng markdown nếu có thể
5. Dạng bài:
   - Trắc nghiệm:
     Câu X: Nội dung
     A. Đáp án A
     B. Đáp án B
     C. Đáp án C
     D. Đáp án D
   - Đúng/Sai: a), b), c)...
   - Tự luận: Câu X: ... (Lời giải...)

✅ Gợi ý thêm:
- Nếu ảnh dài hoặc nhiều trang, chia nhỏ xử lý từng ảnh để tránh thiếu trang.
- Khi lưu kết quả, nên xuất file Word định dạng .docx để hiển thị tiếng Việt chuẩn và hỗ trợ tốt Unicode.
'''

# ======== NHẬP NHIỀU KEY TRONG CODE ========
GEMINI_API_KEYS = [
  "AIzaSyCVUtoKWzyw27LvVbQPxs5D4n48eZWNw9k",
  "AIzaSyD6uAzLz6y2CwgEHg-1XVPM11iAPoEoc3E",
  "AIzaSyDCrzo3_3hKMF3jr114J7pb_wAAd2LesjI",
  "AIzaSyDbU_e892synpWo3uV8HLM2gj6CK0mC7eQ",
  "AIzaSyC_LxT0Xa1X5E03-FKPPri8okx6RwwZEd0",
  "AIzaSyCvNhReepkQxOJbJN1RX_n14wXYrZbAK5I"
]
api_key_cycle = itertools.cycle(GEMINI_API_KEYS)

def get_next_api_key():
    return next(api_key_cycle)

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

# ============= GIAO DIỆN APP =============
st.set_page_config(page_title="OCR PDF & Ảnh Toán – Gemini", layout="centered")
st.title("✨ Chuyển PDF & Ảnh Toán sang Word, giữ công thức và minh hoạ ✨")
st.caption("👨‍💻 by CGPT – OCR PDF, sinh tài liệu toán chuẩn từ ảnh, xuất Word Unicode.")

tab_pdf, tab_img = st.tabs(["📄 PDF Toán", "🖼️ Ảnh → Word + LaTeX"])

# =========== TAB PDF ===========
with tab_pdf:
    st.markdown("#### 📝 OCR cho file PDF, giữ công thức và ảnh minh hoạ")
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
    st.markdown("#### 🖼️ Chuyển ảnh Toán sang Word, giữ LaTeX và ảnh minh hoạ")
    uploaded_images = st.file_uploader("Chọn ảnh (PNG/JPEG)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if uploaded_images:
        latex_results = []
        images_data = []
        st.info("⏳ Đang sinh văn bản từng ảnh bằng Gemini...")
        for i, img_file in enumerate(uploaded_images):
            img_bytes = img_file.read()
            try:
                api_key = get_next_api_key()
                text = gemini_generate_text(img_bytes, api_key)
            except Exception as e:
                text = f"[Lỗi khi sinh văn bản: {e}]"
            latex_results.append((img_file.name, text))
            pil_img = Image.open(BytesIO(img_bytes)).convert("RGB")
            buf = BytesIO()
            pil_img.save(buf, format="JPEG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()
            images_data.append({"name": f"img-{i}.jpeg", "base64": img_b64})
        for idx, (img_name, latex) in enumerate(latex_results):
            st.image(uploaded_images[idx], caption=img_name, width=220)
            st.markdown("**Kết quả văn bản:**")
            st.code(latex)
            try:
                st.latex(latex.replace("$", ""))  # thử hiển thị nếu chỉ là công thức
            except:
                pass
        markdown_out = ""
        for idx, (img_name, latex) in enumerate(latex_results):
            markdown_out += f"{latex}\n\n![Hình minh hoạ](img-{idx}.jpeg)\n\n"
        if st.button("📝 Tạo và tải file Word từ ảnh + văn bản", use_container_width=True):
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
    st.caption("📷 Chuyển nhiều ảnh Toán thành tài liệu Word: giữ ảnh, giữ công thức, bảng, câu trắc nghiệm, tự luận, tiếng Việt chuẩn Unicode.")
