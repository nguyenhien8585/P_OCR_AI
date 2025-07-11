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
from dotenv import load_dotenv
import re

# Load all available Gemini API keys
load_dotenv()
API_KEYS = [
    v for k, v in os.environ.items()
    if k.startswith("GEMINI_API_KEY") and v.strip()
]
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

st.set_page_config(layout="wide", page_title="PDF to Word/LaTeX with Inline Images")
st.title("📄➡️📘 PDF to Word/LaTeX (Inline Images) using Gemini 2.0")

uploaded_file = st.file_uploader("📎 Upload a PDF file", type="pdf")
output_format = st.radio("Select Output Format", ["Word (.docx)", "LaTeX (.tex)"])

# Convert image to stream
def image_to_stream(image):
    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return buf

# Crop image with safe boundary check
def crop_image_by_bbox(image, bbox):
    width, height = image.size
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    return image.crop((x1, y1, x2, y2))

# Call Gemini API with retry logic
def extract_structured_content_with_gemini(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": """
Trích xuất nội dung đề thi có công thức Toán, biểu thức và ảnh minh họa. Trả về JSON với:
{
  "elements": [
    {"type": "text", "content": "..."},
    {"type": "image", "bbox": [...], "caption": "..."},
    ...
  ]
}
Không bọc kết quả trong markdown.
"""},
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
            if not parts or "text" not in parts[0]:
                st.warning(f"Key {key[:10]}... no text returned")
                continue
            raw_text = parts[0]["text"]

            if raw_text.startswith("```") or raw_text.startswith('"""'):
                raw_text = re.sub(r'^```[a-zA-Z]*\n|```$|^"""|"""$', '', raw_text.strip(), flags=re.DOTALL)

            raw_text = raw_text.encode('utf-8').decode('unicode_escape')
            parsed = json.loads(raw_text)
            elements = parsed.get("elements", [])
            return elements, image

        except Exception as e:
            st.warning(f"Key {key[:10]}... failed: {e}")
            continue

    st.error("❌ All Gemini keys failed. Check your .env configuration.")
    return [], image

# Export to Word
def export_to_word(elements, original_image):
    doc = Document()
    for el in elements:
        if el["type"] == "text":
            doc.add_paragraph(el["content"])
        elif el["type"] == "image" and "bbox" in el:
            cropped = crop_image_by_bbox(original_image, el["bbox"])
            doc.add_picture(image_to_stream(cropped), width=Inches(4))
            if el.get("caption"):
                doc.add_paragraph(el["caption"], style='Caption')
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
    doc.save(path)
    return path

# Export to LaTeX
def export_to_latex(elements, original_image, page_idx=1):
    lines = ["\\documentclass{article}", "\\usepackage{graphicx}", "\\usepackage{amsmath}", "\\begin{document}"]
    for i, el in enumerate(elements):
        if el["type"] == "text":
            lines.append(el["content"])
        elif el["type"] == "image" and "bbox" in el:
            cropped = crop_image_by_bbox(original_image, el["bbox"])
            img_path = f"figure_{page_idx}_{i}.png"
            cropped.save(img_path)
            lines.append("\\begin{figure}[h]")
            lines.append("\\centering")
            lines.append(f"\\includegraphics[width=0.8\\textwidth]{{{img_path}}}")
            if el.get("caption"):
                lines.append(f"\\caption{{{el['caption']}}}")
            lines.append("\\end{figure}")
    lines.append("\\end{document}")
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".tex").name
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path

# Main flow
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    images = convert_from_path(pdf_path, dpi=200)
    st.success(f"✅ Extracted {len(images)} page(s).")

    for page_num, img in enumerate(images, 1):
        col1, col2 = st.columns(2)
        col1.image(img, caption=f"📄 Page {page_num}")
        with st.spinner(f"🧠 Analyzing Page {page_num} with Gemini..."):
            elements, original_img = extract_structured_content_with_gemini(img)
        with col2:
            for el in elements:
                if el["type"] == "text":
                    st.markdown(el["content"])
                elif el["type"] == "image":
                    cropped = crop_image_by_bbox(original_img, el["bbox"])
                    st.image(cropped, caption=el.get("caption", "Hình minh hoạ"))

        # Export
        if output_format.startswith("Word"):
            file_path = export_to_word(elements, original_img)
            with open(file_path, "rb") as f:
                st.download_button(f"📥 Download Word (Page {page_num})", f, file_name=f"page_{page_num}.docx")
        else:
            file_path = export_to_latex(elements, original_img, page_idx=page_num)
            with open(file_path, "rb") as f:
                st.download_button(f"📥 Download LaTeX (Page {page_num})", f, file_name=f"page_{page_num}.tex")
