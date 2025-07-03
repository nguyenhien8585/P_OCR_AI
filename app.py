import streamlit as st
import fitz  # PyMuPDF
import requests
from PIL import Image
import base64
import io
import json
import uuid

# Cấu hình API
GPT4O_API_URL = "https://api.sv2.llm.ai.vn/v1/chat/completions"
GEMINI_API_URL = "https://api.sv2.llm.ai.vn/v1/models/gemini:gemini-2.5-pro-preview-06-05:generate-content"
API_KEY = "sk-j4DkzI7htsVqEZqC272d3b58B0Fb49A183573dD2Fc04F71d"  # Thay bằng API key thật

# Prompt cho GPT-4o
PROMPT_LATEX = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
1. Với câu hỏi trắc nghiệm không lời giải (bắt đầu bằng 'Câu X:' hoặc 'Câu X.'):
   - Thay 'Câu X:' bằng \begin{ex}
   - Thêm \choice trước phương án A
   - Đặt mỗi phương án trong cặp {}, ví dụ A. $x^2+2x+1.$ sẽ thành {$x^2+2x+1$}, bỏ phần A., B., C., D. và dấu . cuối phương án
   - Kết thúc bằng \end{ex}
2. Với câu hỏi trắc nghiệm có lời giải:
   - Thêm \True trước phương án đúng
   - Đặt lời giải trong \loigiai{}
3. Với bài tập tự luận (bắt đầu bằng 'Bài X:' hoặc 'Bài X.'):
   - Thay 'Bài X:' bằng \begin{bt}
   - Đặt lời giải trong \loigiai{}
   - Kết thúc bằng \end{bt}
4. Với danh sách (a), b), c)...):
   - Bọc trong \begin{enumerate} và \end{enumerate}
   - Thay mỗi chữ cái bằng \item
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

def detect_image_regions(image: Image.Image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT_GEMINI},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}}
            ]
        }]
    }
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.post(GEMINI_API_URL, json=payload, headers=headers)

    try:
        result_json = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        regions = json.loads(result_json)
        return regions
    except Exception as e:
        st.error("Lỗi phân tích vùng ảnh minh họa.")
        return []

def extract_cropped_images(image: Image.Image, regions: list):
    output = []
    for region in regions:
        x, y, w, h = region["x"], region["y"], region["width"], region["height"]
        cropped = image.crop((x, y, x + w, y + h))
        output.append({
            "label": region.get("label", "minh_hoa"),
            "image": cropped
        })
    return output

def call_gpt4o(image: Image.Image, mode="latex"):
    prompt = PROMPT_LATEX if mode == "latex" else PROMPT_WORD
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    image_bytes = buffered.getvalue()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

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
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.post(GPT4O_API_URL, json=payload, headers=headers)
    return response.json()["choices"][0]["message"]["content"]

def process_pdf(uploaded_file, mode):
    results = []
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        regions = detect_image_regions(img)
        cropped_images = extract_cropped_images(img, regions)
        latex_or_word = call_gpt4o(img, mode=mode)

        results.append({"page": i+1, "text": latex_or_word, "images": cropped_images})

    return results

st.set_page_config(page_title="PDF sang LaTeX/Word + hình minh họa", layout="wide")
st.title("📄 Chuyển PDF sang LaTeX hoặc Word kèm hình minh họa")

uploaded_file = st.file_uploader("📂 Chọn file PDF", type=["pdf"])
mode = st.radio("📄 Chế độ xuất", ["latex", "word"], horizontal=True)

if uploaded_file:
    if st.button("🚀 Bắt đầu chuyển đổi"):
        with st.spinner("Đang xử lý file PDF..."):
            output = process_pdf(uploaded_file, mode)

        for item in output:
            st.markdown(f"### Trang {item['page']}")
            st.code(item['text'], language="latex" if mode == "latex" else "markdown")
            for img_data in item["images"]:
                st.image(img_data["image"], caption=img_data["label"], width=300)

        st.success("🎉 Hoàn tất chuyển đổi!")
