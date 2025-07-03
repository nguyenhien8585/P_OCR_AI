import streamlit as st
import fitz  # PyMuPDF
import requests
from PIL import Image
import base64
import io
import json
import os
from docx import Document
from docx.shared import Inches

# Nhập key ngay trên giao diện
api_key_input = st.text_input("🔑 Nhập AI_API_KEY lấy từ https://api.sv2.llm.ai.vn (không lưu lại):", type="password")
API_KEY = api_key_input.strip() if api_key_input.strip() else os.getenv("AI_API_KEY", "demo-key")

GPT4O_API_URL = "https://api.sv2.llm.ai.vn/v1/chat/completions"
GEMINI_API_URL = "https://api.sv2.llm.ai.vn"

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
    # Cho phép nhập Gemini API key riêng
    gemini_key = st.session_state.get("gemini_key", "")
    if not gemini_key:
        gemini_key = st.text_input("🔑 Nhập Google Gemini API Key (lấy ở https://makersuite.google.com/app/apikey):", key="gemini_api_key", type="password")
        st.session_state["gemini_key"] = gemini_key

    if not gemini_key:
        st.warning("Vui lòng nhập Gemini API Key để dùng chức năng tách ảnh minh họa bằng Google Gemini!")
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        resp = r.json()
        if "candidates" in resp:
            text = resp["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        else:
            st.warning(f"Lỗi Gemini: {resp.get('error', resp)}")
            return []
    except Exception as e:
        st.warning(f"Lỗi Gemini: {e}")
        return []

def extract_cropped_images(image: Image.Image, regions: list):
    output = []
    for idx, region in enumerate(regions):
        try:
            x, y, w, h = region["x"], region["y"], region["width"], region["height"]
            cropped = image.crop((x, y, x + w, y + h))
            output.append({"label": region.get("label", f"hinh_{idx+1}"), "image": cropped})
        except Exception as e:
            st.warning(f"Lỗi cắt hình: {e}")
            continue
    return output

def call_gpt4o(image: Image.Image, mode="latex"):
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
        headers = {"Authorization": f"Bearer {API_KEY}"}
        r = requests.post(GPT4O_API_URL, json=payload, headers=headers, timeout=120)
        data = r.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        else:
            return f"Lỗi GPT-4o: {data.get('error', data)}"
    except Exception as e:
        return f"Lỗi gọi GPT-4o: {e}"

def process_pdf_all_pages(uploaded_file, mode):
    results = []
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_number in range(doc.page_count):
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        regions = detect_image_regions(img)
        cropped_images = extract_cropped_images(img, regions)
        text = call_gpt4o(img, mode=mode)
        results.append({
            "page": page_number + 1,
            "text": text,
            "images": cropped_images
        })
    return results

def save_latex_with_images(results):
    latex_content = ""
    image_paths = []
    for item in results:
        latex_content += f"% ===== Trang {item['page']} =====\n"
        text = item['text']
        for idx, im in enumerate(item['images']):
            image_name = f"figure_trang{item['page']}_{idx+1}.png"
            latex_content += f"\n\\begin{{figure}}[H]\n\\centering\n\\includegraphics[width=0.7\\textwidth]{{{image_name}}}\n\\end{{figure}}\n"
            image_paths.append((image_name, im['image']))
        latex_content += f"\n{text}\n"
    return latex_content, image_paths

def save_word_with_images(results):
    doc = Document()
    for item in results:
        doc.add_heading(f"Trang {item['page']}", level=1)
        doc.add_paragraph(item['text'])
        for im in item['images']:
            img_stream = io.BytesIO()
            im['image'].save(img_stream, format='PNG')
            img_stream.seek(0)
            doc.add_picture(img_stream, width=Inches(4))
            doc.add_paragraph(im['label'])
    out_stream = io.BytesIO()
    doc.save(out_stream)
    out_stream.seek(0)
    return out_stream

st.set_page_config(page_title="PDF sang LaTeX/Word", layout="wide")
st.title("📄 Chuyển PDF sang LaTeX hoặc Word kèm hình minh họa")

uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])
mode = st.radio("Chế độ xuất", ["latex", "word"], horizontal=True)

if uploaded_file and API_KEY and st.button("🚀 Chuyển đổi"):
    with st.spinner("Đang xử lý toàn bộ các trang..."):
        results = process_pdf_all_pages(uploaded_file, mode)
    st.success("✅ Xử lý xong! Xem kết quả bên dưới hoặc xuất ra file.")

    for item in results:
        st.markdown(f"### Trang {item['page']}")
        st.code(item['text'], language="latex" if mode == "latex" else "markdown")
        for im in item['images']:
            st.image(im['image'], caption=im['label'], use_column_width=False)

    # Xuất file
    if mode == "latex":
        latex_content, image_paths = save_latex_with_images(results)
        st.download_button("⬇️ Tải LaTeX (.tex)", latex_content, file_name="output.tex")
        for image_name, im in image_paths:
            img_bytes = io.BytesIO()
            im.save(img_bytes, format="PNG")
            st.download_button(f"⬇️ Tải {image_name}", img_bytes.getvalue(), file_name=image_name, mime="image/png")
    else:
        doc_stream = save_word_with_images(results)
        st.download_button("⬇️ Tải file Word (.docx)", doc_stream, file_name="output.docx")
