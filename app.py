import streamlit as st
import fitz  # PyMuPDF
import requests
from PIL import Image
import base64
import io
import json
import os
import re

# Nhập API key trên giao diện
aivn_key = st.text_input("🔑 Nhập AI.VN API Key (GPT-4o, https://api.sv2.llm.ai.vn)", type="password")
gemini_key = st.text_input("🔑 Nhập Google Gemini API Key (https://makersuite.google.com/app/apikey)", type="password")

GPT4O_API_URL = "https://api.sv2.llm.ai.vn/v1/chat/completions"

PROMPT_LATEX = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
1. Với câu hỏi trắc nghiệm không lời giải (bắt đầu bằng 'Câu X:' hoặc 'Câu X.'):
   - Thay 'Câu X:' bằng \\begin{ex}
   - Thêm \\choice trước phương án A
   - Đặt mỗi phương án trong cặp {}, ví dụ A. $x^2+2x+1.$ sẽ thành {$x^2+2x+1$}, bỏ phần A., B., C., D. và dấu . cuối phương án
   - Kết thúc bằng \\end{ex}
2. Với câu hỏi trắc nghiệm có lời giải:
   - Thêm \\True trước phương án đúng
   - Đặt lời giải trong \\loigiai{}
3. Với bài tập tự luận (bắt đầu bằng 'Bài X:' hoặc 'Bài X.'):
   - Thay 'Bài X:' bằng \\begin{bt}
   - Đặt lời giải trong \\loigiai{}
   - Kết thúc bằng \\end{bt}
4. Với danh sách (a), b), c)...):
   - Bọc trong \\begin{enumerate} và \\end{enumerate}
   - Thay mỗi chữ cái bằng \\item
5. Công thức toán học: Giữ nguyên định dạng LaTeX như $...$ hoặc $$...$$
KHÔNG thêm giải thích hay bình luận gì thêm. Trả về văn bản đã được định dạng LaTeX."""

PROMPT_WORD = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh
2. Giữ nguyên cấu trúc đoạn văn và xuống dòng
3. Với công thức toán học: gõ lại chính xác, tất cả công thức Toán dưới dạng \${...}\$
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
KHÔNG giải thích. KHÔNG bịa thêm. Trả về văn bản gốc."""

PROMPT_GEMINI = """Trong ảnh sau, hãy tìm ra các vùng ảnh minh họa (biểu đồ, hình vẽ, bảng, sơ đồ,...) và trả về danh sách các tọa độ (x, y, width, height) cho từng vùng ảnh đó. Kết quả phải ở dạng JSON như sau:
[
  {"label": "hinh_1", "x": 120, "y": 230, "width": 300, "height": 200},
  {"label": "hinh_2", "x": 450, "y": 700, "width": 280, "height": 180}
]"""

def call_gpt4o(image: Image.Image, mode="latex"):
    if not aivn_key:
        return "❌ Vui lòng nhập AI.VN API Key (GPT-4o)"
    try:
        prompt = PROMPT_LATEX if mode == "latex" else PROMPT_WORD
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        payload = {
            "model": "openai:gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                ]
            }],
            "temperature": 0.3
        }
        headers = {"Authorization": f"Bearer {aivn_key}"}
        r = requests.post(GPT4O_API_URL, json=payload, headers=headers, timeout=120)
        data = r.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        else:
            return f"Lỗi GPT-4o: {data.get('error', data)}"
    except Exception as e:
        return f"Lỗi gọi GPT-4o: {e}"

def detect_image_regions(image: Image.Image):
    if not gemini_key:
        st.warning("Vui lòng nhập Google Gemini API Key để tách ảnh minh họa!")
        return []
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": PROMPT_GEMINI},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": image_b64
                            }
                        }
                    ]
                }
            ]
        }
        headers = {"Content-Type": "application/json"}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-thinking-exp-01-21:generateContent?key={gemini_key}"
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        resp = r.json()
        if "candidates" in resp:
            text = resp["candidates"][0]["content"]["parts"][0]["text"]
            # Xử lý chuỗi JSON nằm trong code block
            code_blocks = re.findall(r"```(?:json)?(.*?)```", text, re.DOTALL)
            if code_blocks:
                code = code_blocks[0]
            else:
                code = text
            code = code.strip()
            # Vá một số lỗi format nếu có
            code = code.replace("\n", "").replace(",]", "]")
            try:
                data = json.loads(code)
                return data
            except Exception as e:
                st.error(f"Lỗi parse JSON từ Gemini: {e}\nNội dung nhận được:\n{code}")
                return []
        elif "error" in resp:
            st.error(f"Lỗi Gemini: {resp['error']}")
            return []
        else:
            st.error("Gemini không trả về kết quả phân vùng ảnh!")
            return []
    except Exception as e:
        st.warning(f"Lỗi Gemini: {e}")
        return []

def extract_cropped_images(image: Image.Image, regions: list):
    output = []
    for region in regions:
        try:
            x, y, w, h = region["x"], region["y"], region["width"], region["height"]
            cropped = image.crop((x, y, x + w, y + h))
            output.append({"label": region.get("label", "minh_hoa"), "image": cropped})
        except Exception as e:
            st.warning(f"Lỗi cắt hình: {e}")
            continue
    return output

def process_pdf(uploaded_file, mode):
    results = []
    try:
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if doc.page_count == 0:
            st.error("PDF không có trang nào.")
            return []
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        # 1. Gửi ảnh GỐC lên GPT-4o để sinh text/công thức
        text = call_gpt4o(img, mode=mode)
        # 2. Tách bounding box ảnh minh họa từ ảnh GỐC
        regions = detect_image_regions(img)
        cropped_images = extract_cropped_images(img, regions)
        results.append({"page": 1, "text": text, "images": cropped_images})
    except Exception as e:
        st.error(f"Lỗi xử lý PDF: {e}")
    return results

st.set_page_config(page_title="PDF sang LaTeX/Word", layout="wide")
st.markdown("""
    <style>
    .stApp {background-color: #f6f7fa;}
    .block-container {padding-top: 2rem;}
    </style>
""", unsafe_allow_html=True)
st.title("📄 Chuyển PDF sang LaTeX hoặc Word kèm hình minh họa")

st.markdown("""
- 📂 **Bước 1:** Nhập key AI.VN (GPT-4o) và Google Gemini
- 📁 **Bước 2:** Chọn file PDF
- ⚙️ **Bước 3:** Chọn chế độ xuất (LaTeX hoặc Word)
- 🚀 **Bước 4:** Nhấn nút chuyển đổi, chờ 10–20 giây
""")

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])
mode = st.radio("Chế độ xuất", ["latex", "word"], horizontal=True)

if uploaded_file:
    st.info("👉 Chỉ xử lý 1 trang đầu để demo.")
    if st.button("🚀 Chuyển đổi"):
        with st.spinner("Đang xử lý... Vui lòng chờ 10–20 giây."):
            result = process_pdf(uploaded_file, mode)
        for item in result:
            st.markdown(f"### Trang {item['page']}")
            st.code(item['text'], language="latex" if mode == "latex" else "markdown")
            for im in item['images']:
                st.image(im['image'], caption=im['label'], use_container_width=True)
        st.success("✅ Xử lý xong!")
