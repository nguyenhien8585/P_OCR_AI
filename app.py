import streamlit as st
import requests
import base64
import tempfile
import re
import itertools
import os
from extract_figures_from_image_pillow import extract_figures_from_image
from word_export import insert_images_to_word_from_markdown

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
2. Nếu phát hiện nhiều hình minh hoạ (hình vẽ, đồ thị, bảng, ...), hãy đánh dấu đúng vị trí từng hình bằng cú pháp markdown: ![img-x.jpeg](img-x.jpeg) với x là số thứ tự hình đã tách từ trên xuống dưới trong ảnh này (bắt đầu từ 1).
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

def gemini_caption_image(image_bytes, api_key):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    b64_img = base64.b64encode(image_bytes).decode()
    prompt = "Hãy mô tả ngắn gọn (dưới 10 từ, không giải thích) về nội dung hình này, ví dụ: 'bảng biến thiên', 'hình lăng trụ', 'hình chóp', 'đồ thị hàm số', 'hình học phẳng', 'sơ đồ cây',... Nếu biết, ghi rõ số câu nếu có trong đề."
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

def insert_figures_no_duplicate(text, figures):
    lines = text.split('\n')
    n = len(figures)
    fig_used = [False] * n
    new_lines = []
    positions = []
    for idx, fig in enumerate(figures):
        inserted = False
        for i, line in enumerate(lines):
            if not inserted and not any(p[0]==i for p in positions):  # dòng này chưa có hình nào
                if 'bảng biến thiên' in fig['caption'] and 'bảng biến thiên' in line.lower():
                    positions.append((i, idx))
                    inserted = True
                elif 'lăng trụ' in fig['caption'] and 'lăng trụ' in line.lower():
                    positions.append((i, idx))
                    inserted = True
                elif 'chóp' in fig['caption'] and 'chóp' in line.lower():
                    positions.append((i, idx))
                    inserted = True
                elif 'đồ thị' in fig['caption'] and 'đồ thị' in line.lower():
                    positions.append((i, idx))
                    inserted = True
                elif 'hình' in fig['caption'] and 'hình' in line.lower():
                    positions.append((i, idx))
                    inserted = True
    for i, line in enumerate(lines):
        new_lines.append(line)
        for pos, idx_fig in positions:
            if pos == i and not fig_used[idx_fig]:
                new_lines.append(f"![img-{idx_fig+1}.jpeg](img-{idx_fig+1}.jpeg)")
                fig_used[idx_fig] = True
    for idx, used in enumerate(fig_used):
        if not used:
            new_lines.append(f"![img-{idx+1}.jpeg](img-{idx+1}.jpeg)")
            fig_used[idx] = True
    return '\n'.join(new_lines)

def remove_all_figure_markdown(text):
    # Xóa mọi dòng markdown ảnh ![img-x.jpeg]...
    return re.sub(r'!\[img-\d+\.jpeg\]\(img-\d+\.jpeg\)\s*', '', text)

st.set_page_config(page_title="Ảnh Toán sang Markdown", layout="wide")
st.title("🖼️ Ảnh Toán sang Markdown + Minh hoạ (chuẩn PDF)")

tab1, tab2 = st.tabs(["📋 Văn bản (Markdown)", "🖼️ Hình ảnh đã tách"])

uploaded_images = st.file_uploader(
    "Chọn nhiều ảnh (mỗi ảnh là một trang):",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    help="Mỗi ảnh là 1 trang, minh hoạ sẽ được tách tự động, nhận diện caption và chèn đúng vị trí."
)

if uploaded_images:
    latex_results = []
    all_figures = []
    for i, img_file in enumerate(uploaded_images):
        img_bytes = img_file.read()
        figures = extract_figures_from_image(img_bytes)
        figures_with_caption = []
        for idx, fig in enumerate(figures):
            api_key = get_next_api_key()
            fig_bytes = base64.b64decode(fig["base64"])
            fig_caption = gemini_caption_image(fig_bytes, api_key)
            figures_with_caption.append({**fig, "caption": fig_caption})
            fig["caption"] = fig_caption
        all_figures.extend(figures)
        api_key = get_next_api_key()
        with st.spinner(f"Đang nhận diện trang {i+1}..."):
            try:
                text = gemini_generate_text(img_bytes, api_key)
            except Exception as e:
                text = f"[Lỗi Gemini: {e}]"
        # Xóa mọi markdown hình Gemini đã sinh ra (nếu có)
        text = remove_all_figure_markdown(text)
        # Chèn từng hình đúng vị trí (không lặp/dư)
        if figures_with_caption:
            text = insert_figures_no_duplicate(text, figures_with_caption)
        latex_results.append((img_file.name, text, figures_with_caption))

    with tab1:
        st.markdown("### 📋 Kết quả từng trang (có markdown minh hoạ):")
        full_markdown = ""
        for idx, (img_name, latex, figures) in enumerate(latex_results):
            st.markdown(f"#### Trang {idx+1}: {img_name}")
            st.code(latex, language="markdown")
            full_markdown += latex + "\n\n"
        st.download_button(
            "📄 Tải toàn bộ markdown",
            full_markdown,
            file_name="ket_qua_ocr_anh.md",
            mime="text/markdown",
            use_container_width=True,
        )
        # Nếu muốn preview trực tiếp: st.markdown(full_markdown)

    with tab2:
        st.markdown("### 🖼️ Tất cả minh hoạ đã tách (kèm caption):")
        for fig in all_figures:
            st.image(base64.b64decode(fig["base64"]), caption=f"{fig['name']} - {fig['caption']}", width=250)
else:
    with tab1:
        st.info("Vui lòng tải lên ít nhất 1 ảnh để bắt đầu.")
    with tab2:
        st.info("Chưa có ảnh nào để xem.")

st.caption("✨ Văn bản chuẩn Markdown, mapping ảnh không dư/lặp, có thể copy/tải về. Tách minh hoạ và caption từng ảnh hoàn toàn tự động.")
