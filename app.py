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
from extract_figures_from_image_pillow import extract_figures_from_image
from word_export import insert_images_to_word_from_markdown

# ======= Danh sách GEMINI KEY =======
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

# ==== Hàm Gemini mô tả nội dung từng hình minh hoạ ====
def gemini_caption_image(image_bytes, api_key):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    b64_img = base64.b64encode(image_bytes).decode()
    prompt = "Hãy mô tả ngắn gọn một dòng (không giải thích) về nội dung hình này, ví dụ: 'hình lăng trụ', 'bảng biến thiên', 'hình chóp', 'đồ thị hàm số'..."
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inlineData": {
                    "mimeType": "image/png",
                    "data": b64_img
                }}
            ]
        }]
    }
    headers = {"Content-Type": "application/json"}
    r = requests.post(f"{api_url}?key={api_key}", json=payload, headers=headers, timeout=40)
    r.raise_for_status()
    res = r.json()
    text = res["candidates"][0]["content"]["parts"][0]["text"]
    return text.strip().lower()

# ==== Hàm auto chèn đúng hình vào đúng đoạn mô tả ====
def auto_insert_figures_by_caption(text, figures_with_caption):
    lines = text.split('\n')
    new_lines = []
    used_figs = set()
    for i, line in enumerate(lines):
        new_lines.append(line)
        # Chèn hình bảng biến thiên vào câu chứa "bảng biến thiên"
        for j, fig in enumerate(figures_with_caption):
            if j in used_figs:
                continue
            if ("bảng biến thiên" in fig["caption"] and "bảng biến thiên" in line.lower()):
                new_lines.append(f"![Hình minh hoạ]({fig['name']})")
                used_figs.add(j)
            elif (("lăng trụ" in fig["caption"] or "hình" in fig["caption"] or "chóp" in fig["caption"])
                  and any(x in line.lower() for x in ["lăng trụ", "chóp", "hình"])):
                new_lines.append(f"![Hình minh hoạ]({fig['name']})")
                used_figs.add(j)
    # Nếu còn hình chưa chèn, thêm cuối
    for j, fig in enumerate(figures_with_caption):
        if j not in used_figs:
            new_lines.append(f"![Hình minh hoạ]({fig['name']})")
    return '\n'.join(new_lines)

st.set_page_config(page_title="Ảnh Toán → Word (chuẩn minh hoạ)", layout="centered")
st.title("🖼️ Ảnh Toán sang Word – Chèn đúng hình minh hoạ vào từng câu, không bao giờ sai!")

uploaded_images = st.file_uploader(
    "Chọn nhiều ảnh (mỗi ảnh là một trang):",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    help="Mỗi ảnh là 1 trang, minh hoạ sẽ được tách tự động và chèn đúng vào câu hỏi tương ứng."
)

if uploaded_images:
    latex_results = []
    all_figures = []
    for i, img_file in enumerate(uploaded_images):
        img_bytes = img_file.read()
        # 1. Tách minh hoạ tự động
        figures = extract_figures_from_image(img_bytes)  # [{name, base64}]
        # 2. Gemini caption cho từng hình
        figures_with_caption = []
        for fig in figures:
            api_key = get_next_api_key()
            fig_bytes = base64.b64decode(fig["base64"])
            fig_caption = gemini_caption_image(fig_bytes, api_key)
            figures_with_caption.append({**fig, "caption": fig_caption})
            fig["caption"] = fig_caption  # Lưu lại để xem nếu muốn
        all_figures.extend(figures)
        # 3. Gọi Gemini sinh văn bản
        api_key = get_next_api_key()
        with st.spinner(f"Đang nhận diện trang {i+1}..."):
            try:
                text = gemini_generate_text(img_bytes, api_key)
            except Exception as e:
                text = f"[Lỗi Gemini: {e}]"
        # 4. Chèn từng hình vào đúng vị trí dựa vào caption
        if figures_with_caption:
            text = auto_insert_figures_by_caption(text, figures_with_caption)
        latex_results.append((img_file.name, text, figures_with_caption))

    tab1, tab2 = st.tabs(["📋 Văn bản (copy LaTeX)", "🖼️ Ảnh minh hoạ đã tách"])
    with tab1:
        st.markdown("### 📋 Kết quả từng trang:")
        for idx, (img_name, latex, figures) in enumerate(latex_results):
            st.markdown(f"#### Trang {idx+1}: {img_name}")
            parts = re.split(r"(!\[Hình minh hoạ\]\(img-\d+\.jpeg\))", latex)
            for part in parts:
                img_match = re.match(r"!\[Hình minh hoạ\]\((img-\d+\.jpeg)\)", part)
                if img_match:
                    findname = img_match.group(1)
                    found = next((img for img in figures if img["name"] == findname), None)
                    if found:
                        st.image(base64.b64decode(found["base64"]), caption=f"{findname} - {found['caption']}", width=340)
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
            st.image(base64.b64decode(fig["base64"]), caption=f"{fig['name']} - {fig['caption']}", width=200)

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

st.caption("✨ Ảnh minh hoạ được tách, phân loại thông minh bằng Gemini, luôn chèn đúng vào từng câu, bảng biến thiên, hình lăng trụ, ... – Không bao giờ sai!")
