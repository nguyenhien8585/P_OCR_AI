import os
import io
import fitz  # PyMuPDF
import base64
import streamlit as st
from PIL import Image
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import openai

# ================== CẤU HÌNH ==================
POPPLER_PATH = None  # Để None nếu chạy trên web (Streamlit Cloud có sẵn poppler)
SAVE_DIR = "output_images"
MODEL = "openai:gpt-4o"

# Lấy API key từ Streamlit secrets
openai.api_key = st.secrets["api_key"]
openai.api_base = st.secrets["api_base"]

ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')

# ================== HÀM CHÍNH ==================
def extract_images_near_text(pdf_file):
    os.makedirs(SAVE_DIR, exist_ok=True)

    # Đọc PDF từ uploaded file
    pdf_bytes = pdf_file.read()
    images = convert_from_path(io.BytesIO(pdf_bytes), dpi=200, poppler_path=POPPLER_PATH)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    output_paths = []

    for page_num, page in enumerate(doc):
        img = images[page_num]
        image_path = f"{SAVE_DIR}/page_{page_num + 1}.png"
        img.save(image_path)

        result = ocr_engine.ocr(image_path, cls=True)[0]

        illustration_keywords = ["hình", "vẽ", "tọạ độ", "minh họạ", "biểu diễn", "trên hình"]
        selected_regions = []

        for box in result:
            text = box[1][0].lower()
            if any(key in text for key in illustration_keywords):
                x_min = min([pt[0] for pt in box[0]])
                y_min = min([pt[1] for pt in box[0]])
                x_max = max([pt[0] for pt in box[0]])
                y_max = max([pt[1] for pt in box[0]])
                selected_regions.append(((x_min, y_min, x_max, y_max), text))

        image_list = page.get_images(full=True)
        for i, img_info in enumerate(image_list):
            xref = img_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            img = Image.open(io.BytesIO(image_bytes))

            bbox = page.get_image_bbox(img_info)
            left, top, right, bottom = bbox.x0, bbox.y0, bbox.x1, bbox.y1

            is_close = False
            for (x_min, y_min, x_max, y_max), text in selected_regions:
                if abs(y_min - top) < 300 or abs(top - y_max) < 300:
                    is_close = True
                    break

            if is_close:
                output_path = f"{SAVE_DIR}/minhhoa_page{page_num + 1}_{i + 1}.png"
                img.save(output_path)
                if is_math_related(output_path, text):
                    output_paths.append(output_path)
                else:
                    os.remove(output_path)
    return output_paths


def is_math_related(image_path, context_text):
    try:
        with open(image_path, "rb") as img_file:
            img_data = base64.b64encode(img_file.read()).decode("utf-8")
            response = openai.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý AI toán học."},
                    {"role": "user", "content": f"Đây là ảnh gần đoạn: '{context_text}'. Có phải minh họa toán học không? ĐÚNG / SAI."},
                    {"role": "user", "content": f"<img src='data:image/png;base64,{img_data}'>"}
                ],
                temperature=0.0,
                max_tokens=10
            )
            result = response.choices[0].message.content.strip()
            return "ĐÚNG" in result.upper()
    except Exception as e:
        st.warning(f"GPT lỗi: {e}")
        return False

# ================== GIAO DIỆN ==================
st.set_page_config(page_title="Tách ảnh minh họa Toán học", layout="wide")
st.title("🧠 Trích xuất ảnh minh họa toán học từ PDF")

uploaded_file = st.file_uploader("📄 Tải lên file PDF đề toán", type="pdf")

if uploaded_file:
    with st.spinner("🔍 Đang xử lý..."):
        images = extract_images_near_text(uploaded_file)

    if images:
        st.success(f"✅ Đã phát hiện {len(images)} ảnh minh họa toán học")
        for img_path in images:
            st.image(img_path, caption=img_path, use_column_width=True)
    else:
        st.warning("⚠️ Không tìm thấy ảnh minh họa toán học nào.")
