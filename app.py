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

# Load API key
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

st.set_page_config(layout="wide", page_title="PDF to Word/LaTeX with Images")
st.title("📄➡️📝 PDF to Word/LaTeX Converter with Gemini 2.0")

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

# Call Gemini 2.0 Flash API
def extract_structured_content_with_gemini(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    st.write("📦 Image base64 size (KB):", len(img_b64) // 1024)

    payload = {
        "contents": [{
            "parts": [
                {"text": """
Trích xuất văn bản và ảnh minh họa trong ảnh đề thi sau. Trả JSON:
{
  "text_parts": ["..."],
  "images": [{"bbox": [x1,y1,x2,y2], "caption": "..."}]
}
""" },
                {"inline_data": {
                    "mime_type": "image/png",
                    "data": img_b64
                }}
            ]
        }]
    }

    try:
        response = requests.post(f"{ENDPOINT}?key={API_KEY}", json=payload)
        st.write("🔁 Response code:", response.status_code)
        st.write("🔁 Response raw text:", response.text[:500])  # show preview

        if response.status_code != 200:
            st.error(f"Gemini API lỗi {response.status_code}: {response.text}")
            return {"text_parts": ["[ERROR]"], "images": [], "original_image": image}

        result_json = response.json()
        if "candidates" not in result_json or not result_json["candidates"]:
            st.error("❗ Gemini không trả về nội dung nào.")
            return {"text_parts": ["[EMPTY]"], "images": [], "original_image": image}

        raw_text = result_json["candidates"][0]["content"]["parts"][0].get("text", "")
        if not raw_text.strip():
            st.error("⚠️ Gemini trả về văn bản rỗng.")
            return {"text_parts": ["[BLANK]"], "images": [], "original_image": image}

        parsed = json.loads(raw_text)
        parsed['original_image'] = image
        return parsed

    except Exception as e:
        st.error(f"Gemini parsing failed: {e}")
        return {"text_parts": ["[EXCEPTION]"], "images": [], "original_image": image}


# Export to Word
def export_structured_to_word(structured_data_list):
    doc = Document()
    for page_data in structured_data_list:
        for part in page_data["text_parts"]:
            doc.add_paragraph(part)
        for img_data in page_data["images"]:
            cropped = crop_image_by_bbox(page_data["original_image"], img_data["bbox"])
            doc.add_picture(image_to_stream(cropped), width=Inches(4))
            if img_data.get("caption"):
                doc.add_paragraph(img_data["caption"], style='Caption')
        doc.add_page_break()
    path = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
    doc.save(path)
    return path

# Export to LaTeX
def export_structured_to_latex(structured_data_list):
    lines = [
        "\\documentclass{article}",
        "\\usepackage{graphicx}",
        "\\begin{document}"
    ]
    for idx, page_data in enumerate(structured_data_list):
        for part in page_data["text_parts"]:
            lines.append(part)
        for i, img_data in enumerate(page_data["images"]):
            cropped = crop_image_by_bbox(page_data["original_image"], img_data["bbox"])
            img_path = f"figure_{idx+1}_{i+1}.png"
            cropped.save(img_path)
            lines.append(f"\\begin{{figure}}[h]")
            lines.append(f"\\centering")
            lines.append(f"\\includegraphics[width=0.8\\textwidth]{{{img_path}}}")
            if img_data.get("caption"):
                lines.append(f"\\caption{{{img_data['caption']}}}")
            lines.append(f"\\end{{figure}}")
        lines.append("\\newpage")
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

    structured_data = []
    for i, img in enumerate(images):
        col1, col2 = st.columns(2)
        col1.image(img, caption=f"📄 Page {i+1}")
        with st.spinner(f"🧠 Analyzing Page {i+1} with Gemini..."):
            data = extract_structured_content_with_gemini(img)
        with col2:
            for part in data["text_parts"]:
                st.markdown(part)
            for img_data in data["images"]:
                cropped = crop_image_by_bbox(img, img_data["bbox"])
                st.image(cropped, caption=img_data.get("caption", "Minh họa"))
        structured_data.append(data)

    # Export
    if output_format.startswith("Word"):
        file_path = export_structured_to_word(structured_data)
        with open(file_path, "rb") as f:
            st.download_button("📥 Download Word Document", f, file_name="converted.docx")
    else:
        file_path = export_structured_to_latex(structured_data)
        with open(file_path, "rb") as f:
            st.download_button("📥 Download LaTeX File", f, file_name="converted.tex")
