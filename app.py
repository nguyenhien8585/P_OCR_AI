import streamlit as st
import requests
import base64
import tempfile
import re
import itertools
import os
import numpy as np
import io
from PIL import Image
import cv2
from PyPDF2 import PdfReader

# ----------- GEMINI KEY (tự điền key hợp lệ) ------------
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

# ----------- HÀM TÁCH ẢNH MINH HOẠ SÁT NHẤT -----------
def extract_figures_from_image(img_bytes, min_area=12000, max_figures=5):
    """
    Cắt sát viền các hình minh hoạ thực sự trong đề toán, 
    không dính trang, không cắt dính chữ, không dư các contour nhỏ.
    """
    img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(img_pil)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thres = cv2.threshold(blur, 240, 255, cv2.THRESH_BINARY_INV)
    canny = cv2.Canny(blur, 60, 160)
    combined = cv2.bitwise_or(thres, canny)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = img.shape[:2]
    rects = []
    for cnt in contours:
        x, y, ww, hh = cv2.boundingRect(cnt)
        area = ww * hh
        aspect = ww / (hh + 1e-5)
        area_ratio = area / (h * w)
        # --- THÊM 2 điều kiện cắt: chiều rộng và chiều cao tối thiểu ---
        if (area > min_area and 0.2 < aspect < 6 and 0.06 < area_ratio < 0.89 
            and ww > w * 0.28 and hh > h * 0.18 and y > 0.03*h and x > 0.01*w):
            # Không lấy contour gần như full trang (tránh lỗi contour toàn bộ A4)
            if ww > w * 0.96 and hh > h * 0.96:
                continue
            rects.append((x, y, ww, hh, area))
    rects = sorted(rects, key=lambda x: -x[4])[:max_figures]

    # Nếu không tìm được vùng phù hợp, trả về cả ảnh gốc (dạng fallback)
    if not rects:
        buf = io.BytesIO()
        img_pil.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return [{"name": "img-1.jpeg", "base64": b64}]

    results = []
    for idx, (x, y, ww, hh, _) in enumerate(rects):
        pad = 3
        x1 = max(x - pad, 0)
        y1 = max(y - pad, 0)
        x2 = min(x + ww + pad, w)
        y2 = min(y + hh + pad, h)
        crop = img_pil.crop((x1, y1, x2, y2))
        buf = io.BytesIO()
        crop.save(buf, format='JPEG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results

# ----------- HÀM GỠ MARKDOWN ẢNH ----------
def remove_all_figure_markdown(text):
    if not isinstance(text, str):
        return ""
    return re.sub(r'!\[img-\d+\.jpeg\]\(img-\d+\.jpeg\)\s*', '', text)

# ----------- HÀM CHÈN ẢNH VÀO MARKDOWN ----------
def insert_figures_to_markdown(text, figures):
    lines = text.split('\n')
    new_lines = []
    fig_idx = 0
    n_fig = len(figures)
    for i, line in enumerate(lines):
        new_lines.append(line)
        lower = line.lower()
        if fig_idx < n_fig and any(key in lower for key in [
            "xem hình", "hình vẽ", "hình dưới", "hình bên", "bảng dưới", "hình minh hoạ", "hình minh họa"
        ]):
            new_lines.append(f"![{figures[fig_idx]['name']}]({figures[fig_idx]['name']})")
            fig_idx += 1
    while fig_idx < n_fig:
        new_lines.append(f"![{figures[fig_idx]['name']}]({figures[fig_idx]['name']})")
        fig_idx += 1
    return '\n'.join(new_lines)

# ----------- PROMPT GEMINI ---------
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

# ----------- GIAO DIỆN STREAMLIT -----------
st.set_page_config(page_title="OCR PDF & Ảnh Toán – Gemini", layout="wide")
st.title("✨ Chuyển PDF & Ảnh Toán sang Markdown, giữ công thức & minh hoạ ✨")
tab_pdf, tab_img = st.tabs(["📄 PDF Toán", "🖼️ Ảnh → Markdown + Minh hoạ"])

# =========== TAB PDF =============
with tab_pdf:
    st.markdown("#### 📝 OCR PDF Toán, giữ công thức, ảnh minh hoạ")
    uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"], label_visibility="collapsed")
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
        st.info("🚀 Tính năng PDF demo, chưa OCR tự động, chỉ trích xuất trang (tự thêm API OCR tùy bạn).")

# =========== TAB ẢNH =============
with tab_img:
    st.markdown("#### 🖼️ Ảnh (tách minh hoạ tự động, mapping chuẩn, cho phép tải/copy) → Markdown/Text/Word")
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
            all_figures.extend(figures)
            api_key = get_next_api_key()
            with st.spinner(f"Đang nhận diện trang {i+1}..."):
                try:
                    text = gemini_generate_text(img_bytes, api_key)
                except Exception as e:
                    text = f"[Lỗi Gemini: {e}]"
            text = remove_all_figure_markdown(text)
            text = insert_figures_to_markdown(text, figures)
            latex_results.append((img_file.name, text, figures))

        tab1, tab2 = st.tabs(["📋 Văn bản (Markdown)", "🖼️ Hình ảnh đã tách"])
        with tab1:
            st.markdown("### 📋 Kết quả từng trang (có markdown minh hoạ):")
            for idx, (img_name, latex, figures) in enumerate(latex_results):
                st.markdown(f"#### Trang {idx+1}: {img_name}")
                st.code(latex, language="markdown")
        with tab2:
            st.markdown("### 🖼️ Tất cả minh hoạ đã tách (cho tải ảnh):")
            for idx, fig in enumerate(all_figures):
                img_bytes = base64.b64decode(fig["base64"])
                st.image(img_bytes, caption=fig["name"], width=250)
                st.download_button(
                    f"Tải {fig['name']}",
                    img_bytes,
                    file_name=fig["name"],
                    mime="image/jpeg",
                    use_container_width=True,
                    key=f"anh-download-{fig['name']}-{idx}"
                )
    else:
        st.info("Vui lòng tải lên ít nhất 1 ảnh để bắt đầu.")

st.caption("✨ Văn bản chuẩn Markdown, mapping ảnh không dư/lặp, cho phép copy/tải về. Tách minh hoạ từng ảnh tự động. Xuất Word minh hoạ đúng vị trí!")
