import streamlit as st
from pdf2image import convert_from_path
from PIL import Image
import requests
import base64
import json
import tempfile
from io import BytesIO
from docx import Document
from docx.shared import Inches
import os
import re
from dotenv import load_dotenv

# ====== Config & Load API keys =======
load_dotenv()
API_KEYS = [v for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v.strip()]
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

st.set_page_config(layout="wide", page_title="PDF to Word/LaTeX with Images Gemini 2.0")
st.title("📄➡️📘 PDF to Word/LaTeX (Math/Images) by Gemini 2.0 Flash")

uploaded_file = st.file_uploader("📎 Upload a PDF file", type="pdf")
output_format = st.radio("Select Output Format", ["Word (.docx)", "LaTeX (.tex)"])

# ==== Utilities ====
def image_to_stream(image):
    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return buf

def crop_image_by_bbox(image, bbox):
    width, height = image.size
    x1, y1, x2, y2 = map(int, bbox)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    return image.crop((x1, y1, x2, y2))

def crop_and_save_images(image, elements, page_num):
    """
    Cắt ảnh từ các bbox trong elements trả về từ Gemini.
    Trả về: dict {placeholder: path_ảnh}
    """
    image_map = {}
    idx = 0
    for el in elements:
        if el.get("type") == "image" and "bbox" in el:
            cropped = crop_image_by_bbox(image, el["bbox"])
            img_filename = f"figure_{page_num}_{idx}.png"
            out_path = os.path.join(tempfile.gettempdir(), img_filename)
            cropped.save(out_path)
            placeholder = f"[IMAGE_{page_num}_{idx}]"
            image_map[placeholder] = out_path
            idx += 1
    return image_map

def extract_structured_content_with_gemini(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
    prompt = """
Trích xuất CHÍNH XÁC toàn bộ nội dung đề thi (bao gồm văn bản, công thức Toán học, biểu thức, bảng biến thiên, đồ thị, hình học...).
Nếu có hình minh họa, hãy tách bbox và sinh caption, trả về kết quả JSON chuẩn như sau:
{
  "elements": [
    {"type": "text", "content": "..."},
    {"type": "image", "bbox": [x1,y1,x2,y2], "caption": "..."},
    ...
  ]
}
Tuyệt đối chỉ trả về JSON, không thêm chú thích, markdown hoặc văn bản ngoài JSON.
"""
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {
                    "mime_type": "image/png",
                    "data": img_b64
                }}
            ]
        }]
    }

    for key in API_KEYS:
        try:
            response = requests.post(f"{ENDPOINT}?key={key}", json=payload)
            if response.status_code != 200:
                st.warning(f"Key {key[:10]}... HTTP {response.status_code}")
                continue

            result_json = response.json()
            parts = result_json.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            raw_text = parts[0].get("text", "") if parts else ""
            # Loại bỏ markdown hoặc dấu ```json nếu có
            raw_text = re.sub(r'^```[a-zA-Z]*\n|```$|^"""|"""$', '', raw_text.strip(), flags=re.DOTALL)
            parsed = json.loads(raw_text)
            return parsed.get("elements", []), image

        except Exception as e:
            st.warning(f"Key {key[:10]}... failed: {e}")
            continue

    st.error("❌ All Gemini keys failed. Check your .env file.")
    return [], image

def insert_images_to_word(text, image_map):
    doc = Document()
    # Chia văn bản theo placeholder [IMAGE_X_Y]
    pattern = r'(\IMAGE_\\d+_\\d+\)'
    parts = re.split(pattern, text)
    for part in parts:
        if re.match(r'\IMAGE_\\d+_\\d+\', part):
            img_path = image_map.get(part)
            if img_path and os.path.exists(img_path):
                doc.add_picture(img_path, width=Inches(4))
        elif part.strip():
            doc.add_paragraph(part)
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
    doc.save(path)
    return path

def insert_images_to_latex(text, image_map):
    lines = [
        "\\documentclass{article}",
        "\\usepackage{graphicx}",
        "\\usepackage{amsmath}",
        "\\begin{document}"
    ]
    pattern = r'(\IMAGE_\\d+_\\d+\)'
    parts = re.split(pattern, text)
    for part in parts:
        if re.match(r'\IMAGE_\\d+_\\d+\', part):
            img_path = image_map.get(part)
            if img_path and os.path.exists(img_path):
                fname = os.path.basename(img_path)
                lines.append("\\begin{figure}[h]")
                lines.append("\\centering")
                lines.append(f"\\includegraphics[width=0.8\\textwidth]{{{fname}}}")
                lines.append("\\end{figure}")
        elif part.strip():
            lines.append(part)
    lines.append("\\end{document}")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".tex").name
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path

# ==== Main ====
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    images = convert_from_path(pdf_path, dpi=200)
    st.success(f"✅ Extracted {len(images)} page(s).")

    # Gộp toàn bộ text và hình cho tất cả trang
    all_text = ""
    all_image_map = {}

    for page_num, img in enumerate(images, 1):
        col1, col2 = st.columns(2)
        col1.image(img, caption=f"📄 Page {page_num}")
        with st.spinner(f"🧠 Analyzing Page {page_num} with Gemini..."):
            elements, original_img = extract_structured_content_with_gemini(img)
        # Tách text và chèn placeholder cho ảnh
        img_idx = 0
        for el in elements:
            if el["type"] == "text":
                all_text += el["content"] + "\n"
            elif el["type"] == "image":
                placeholder = f"[IMAGE_{page_num}_{img_idx}]"
                all_text += placeholder + "\n"
                img_idx += 1
        # Tách và lưu ảnh ra file tạm
        image_map = crop_and_save_images(original_img, elements, page_num)
        all_image_map.update(image_map)
        # Hiển thị lên web
        with col2:
            for el in elements:
                if el["type"] == "text":
                    st.markdown(el["content"])
                elif el["type"] == "image":
                    placeholder = f"[IMAGE_{page_num}_{img_idx}]"
                    cropped = crop_image_by_bbox(original_img, el["bbox"])
                    st.image(cropped, caption=el.get("caption", "Minh họa"))
    # Kết xuất
    if output_format.startswith("Word"):
        file_path = insert_images_to_word(all_text, all_image_map)
        with open(file_path, "rb") as f:
            st.download_button("📥 Download Word (All Pages)", f, file_name="converted_all.docx")
    else:
        file_path = insert_images_to_latex(all_text, all_image_map)
        with open(file_path, "rb") as f:
            st.download_button("📥 Download LaTeX (All Pages)", f, file_name="converted_all.tex")
