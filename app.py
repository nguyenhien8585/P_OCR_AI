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
from extract_figures_from_image_pillow import extract_figures_from_image  # Hàm tách minh hoạ

# =========== GEMINI KEY LIST ===========
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

GEMINI_PROMPT = '''
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh.
2. Nếu phát hiện nhiều hình minh hoạ (hình vẽ, đồ thị, bảng, ...), hãy đánh dấu đúng vị trí từng hình bằng cú pháp markdown: ![Hình minh hoạ](img-x.jpeg) với x là số thứ tự hình đã tách từ trên xuống dưới trong ảnh này (bắt đầu từ 1).
3. Với mỗi hình minh hoạ, hãy chèn markdown ngay sau dòng mô tả có từ “xem hình dưới”, “hình dưới đây”, “bảng biến thiên”, “hình vẽ”, “biểu đồ”, hoặc ngay sau dòng câu hỏi liên quan tới hình/bảng/biểu đồ đó.
4. Giữ nguyên cấu trúc đoạn văn và xuống dòng.
5. Công thức toán học: tất cả ở dạng ${...}$ (inline, hệ, ký hiệu ... như hướng dẫn chi tiết).
6. Bảng biểu: dùng markdown nếu có thể.
7. Dạng bài: Trắc nghiệm, Đúng/Sai, Tự luận: đúng định dạng như ví dụ.
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

# ==== HÀM AUTO CHÈN ĐÚNG VỊ TRÍ NHIỀU HÌNH ====
def auto_insert_figures_multi(text, figures):
    lines = text.split('\n')
    new_lines = []
    fig_idx = 0
    keywords = [
        "xem hình dưới", "hình dưới đây", "hình bên dưới", "hình sau",
        "hình minh hoạ", "hình minh họa", "bảng biến thiên", "hình vẽ", "biểu đồ"
    ]
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Nếu còn hình và dòng chứa từ khoá, hoặc "Câu" và "hình"/"bảng"/"biểu đồ", chèn hình tiếp theo
        if (fig_idx < len(figures)) and (
            any(kw in line.lower() for kw in keywords) or
            ("câu" in line.lower() and ("hình" in line.lower() or "bảng" in line.lower() or "biểu đồ" in line.lower()))
        ):
            new_lines.append(f"![Hình minh hoạ]({figures[fig_idx]['name']})")
            fig_idx += 1
    # Nếu còn hình mà chưa chèn hết, cứ chèn sau cuối cùng
    while fig_idx < len(figures):
        new_lines.append(f"![Hình minh hoạ]({figures[fig_idx]['name']})")
        fig_idx += 1
    return '\n'.join(new_lines)

st.set_page_config(page_title="OCR PDF & Ảnh Toán – Gemini", layout="centered")
st.title("✨ Chuyển PDF & Ảnh Toán sang Word, giữ công thức & minh hoạ ✨")

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
    st.markdown("#### 🖼️ Ảnh (tách minh hoạ tự động) → Word, LaTeX dạng code copy, minh hoạ đúng vị trí")
    uploaded_images = st.file_uploader(
        "Chọn nhiều ảnh (mỗi ảnh là một trang):",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Mỗi ảnh là 1 trang, hệ thống sẽ tự động tách các hình minh hoạ lớn bên trong."
    )
    if uploaded_images:
        latex_results = []
        all_figures = []
        for i, img_file in enumerate(uploaded_images):
            img_bytes = img_file.read()
            figures = extract_figures_from_image(img_bytes)
            all_figures.extend(figures)
            api_key = get_next_api_key()
            with st.spinner(f"Đang nhận diện trang {i+1}..."):
                try:
                    text = gemini_generate_text(img_bytes, api_key)
                except Exception as e:
                    text = f"[Lỗi Gemini: {e}]"
            # Nếu số hình tách ra nhiều hơn số markdown chèn trong text, auto chèn đúng vị trí theo thứ tự
            if figures and sum([fig["name"] in text for fig in figures]) < len(figures):
                text = auto_insert_figures_multi(text, figures)
            latex_results.append((img_file.name, text, figures))

        tab1, tab2 = st.tabs(["📋 Văn bản (copy LaTeX)", "🖼️ Ảnh minh hoạ đã tách"])
        with tab1:
            st.markdown("### 📋 Kết quả từng trang:")
            for idx, (img_name, latex, figures) in enumerate(latex_results):
                st.markdown(f"#### Trang {idx+1}: {img_name}")
                parts = re.split(r"(!\[Hình minh hoạ\]\(img-\d+\.jpeg\))", latex)
                for part in parts:
                    img_match = re.match(r"!\[Hình minh hoạ\]\((img-(\d+)\.jpeg)\)", part)
                    if img_match:
                        findname = img_match.group(1)
                        found = next((img for img in figures if img["name"] == findname), None)
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
            st.markdown("### 🖼️ Tất cả minh hoạ đã tách:")
            for fig in all_figures:
                st.image(base64.b64decode(fig["base64"]), caption=fig["name"], width=200)

        markdown_out = ""
        for idx, (img_name, latex, figures) in enumerate(latex_results):
            markdown_out += f"{latex}\n\n"
        if st.button("📝 Tạo và tải file Word giữ ảnh minh hoạ đã tách", use_container_width=True):
            with st.spinner("Đang tạo file Word..."):
                with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                    insert_images_to_word_from_markdown(markdown_out, all_figures, tmp_word.name)
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

st.caption("✨ Ảnh minh hoạ tự tách, mỗi hình sẽ được chèn sát đúng câu hỏi/bảng mô tả liên quan, LaTeX luôn code dễ copy, xuất Word giữ minh hoạ CHUẨN.")
