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
import time

# ======= CONFIG =======
load_dotenv()
OCR_CLIENT_CONFIG = {
    "API_URL": "https://script.google.com/macros/s/AKfycby6GUWKFttjWTDJuQuX5IAeGAzS5tQULLja3SHbSfZIhQyaWVMuxyRNAE-fykxnznkqIw/exec",
    "API_KEY": "sk_nguyenhien21022020_pro_mcwzovbjz11wklh8zk",    # <-- ĐIỀN KEY THẬT VÀO ĐÂY
    "TIMEOUT": 120,
    "MAX_RETRIES": 3,
    "RETRY_DELAY_BASE": 2,
    "BATCH_DELAY": 2,
    "WEBHOOK_URL": ""
}

class SmartOCRClient:
    def __init__(self, config=None):
        self.config = config or OCR_CLIENT_CONFIG
        self.api_url = self.config["API_URL"]
        self.api_key = self.config["API_KEY"]
        self.webhook_url = self.config.get("WEBHOOK_URL")
        self.usage = {"total": 0, "success": 0, "fail": 0}

    def _make_request(self, data, max_retries=None):
        max_retries = max_retries if max_retries is not None else self.config["MAX_RETRIES"]
        for attempt in range(max_retries):
            try:
                resp = requests.post(self.api_url, headers={'Content-Type': 'application/json'}, json=data, timeout=self.config["TIMEOUT"])
                if resp.status_code != 200:
                    time.sleep(self.config["RETRY_DELAY_BASE"] * (attempt + 1))
                    continue
                return resp.json()
            except Exception as ex:
                time.sleep(self.config["RETRY_DELAY_BASE"] * (attempt + 1))
        return {"success": False, "error": f"Failed after {max_retries} retries"}

    def convert(self, file_bytes, filename, mime_type, options=None):
        # Thêm "endpoint": "convert" đúng yêu cầu GAS server!
        base64_str = base64.b64encode(file_bytes).decode()
        data = {
            "endpoint": "convert",    # Fix: THÊM trường này
            "api_key": self.api_key,
            "file": {
                "name": filename,
                "mimeType": mime_type,
                "base64": base64_str
            },
            "options": options or {
                "language": "auto",
                "output_format": "json"
            }
        }
        result = self._make_request(data)
        self.usage["total"] += 1
        if result.get("success"):
            self.usage["success"] += 1
        else:
            self.usage["fail"] += 1
        return result

    def convert_batch(self, files, options=None, progress_cb=None):
        results = []
        for i, f in enumerate(files):
            res = self.convert(f["bytes"], f["name"], f["mime"], options)
            if progress_cb:
                progress_cb(i+1, len(files), res)
            results.append(res)
            time.sleep(self.config["BATCH_DELAY"])
        return results

def image_from_base64(base64_str):
    try:
        return Image.open(BytesIO(base64.b64decode(base64_str)))
    except Exception as e:
        st.warning(f"Không giải mã được ảnh minh họa: {e}")
        return None

def parse_ocr_json(elements):
    out = []
    for el in elements:
        if el.get("type") == "text" and el.get("content"):
            out.append({"type": "text", "content": el["content"]})
        elif el.get("type") == "image" and el.get("base64"):
            out.append({"type": "image", "base64": el["base64"], "caption": el.get("caption", "")})
    return out

def export_to_word(elements, doc=None):
    if doc is None:
        doc = Document()
    for el in elements:
        if el["type"] == "text":
            doc.add_paragraph(el["content"])
        elif el["type"] == "image" and el.get("base64"):
            img = image_from_base64(el["base64"])
            if img:
                doc.add_picture(image_to_stream(img), width=Inches(4))
                if el.get("caption"):
                    doc.add_paragraph(el["caption"], style='Caption')
    return doc

def export_to_latex(elements, page_idx=1):
    lines = [
        "\\documentclass{article}",
        "\\usepackage{graphicx}",
        "\\begin{document}"
    ]
    for i, el in enumerate(elements):
        if el["type"] == "text":
            lines.append(el["content"])
        elif el["type"] == "image" and el.get("base64"):
            img = image_from_base64(el["base64"])
            if img:
                img_path = f"figure_{page_idx}_{i+1}.png"
                img.save(img_path)
                lines.append("\\begin{figure}[h]")
                lines.append("\\centering")
                lines.append(f"\\includegraphics[width=0.8\\textwidth]{{{img_path}}}")
                if el.get("caption"):
                    lines.append(f"\\caption{{{el['caption']}}}")
                lines.append("\\end{figure}")
    lines.append("\\end{document}")
    return "\n".join(lines)

def image_to_stream(image):
    buf = BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return buf

st.set_page_config(layout="wide", page_title="Smart OCR Client (API)")
st.title("📄➡️📘 Smart OCR Client (API) — PDF/Image to Word/LaTeX + Minh họa")

uploaded_file = st.file_uploader("📎 Upload a PDF file", type="pdf")
output_format = st.radio("Select Output Format", ["Word (.docx)", "LaTeX (.tex)"])
client = SmartOCRClient()

if uploaded_file:
    # Convert PDF to image(s)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    images = convert_from_path(pdf_path, dpi=200)
    st.success(f"✅ Extracted {len(images)} page(s).")
    all_elements = []

    # Batch process
    for page_num, img in enumerate(images, 1):
        col1, col2 = st.columns(2)
        col1.image(img, caption=f"📄 Page {page_num}")

        img_buf = BytesIO()
        img.save(img_buf, format="PNG")
        img_bytes = img_buf.getvalue()

        with st.spinner(f"🧠 SmartOCR API Page {page_num}..."):
            result = client.convert(
                img_bytes,
                filename=f"page_{page_num}.png",
                mime_type="image/png",
                options={"output_format": "json"}
            )

        # Parse response
        elements = []
        if result.get("success"):
            try:
                parsed = result["data"]
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                elements = parse_ocr_json(parsed.get("elements", []))
            except Exception as e:
                st.warning(f"Lỗi parse kết quả API: {e}")
        else:
            st.error(f"Lỗi SmartOCR: {result.get('error')}")
        all_elements.append(elements)

        # Hiển thị kết quả OCR
        with col2:
            for el in elements:
                if el["type"] == "text":
                    st.markdown(el["content"])
                elif el["type"] == "image" and el.get("base64"):
                    img_anno = image_from_base64(el["base64"])
                    if img_anno:
                        st.image(img_anno, caption=el.get("caption", "Minh họa"))
                        with st.expander("Base64"):
                            st.code(el["base64"][:200] + "...", language="text")

    # EXPORT FULL DOC
    if output_format.startswith("Word"):
        doc = Document()
        for elements in all_elements:
            export_to_word(elements, doc)
            doc.add_page_break()
        path = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
        doc.save(path)
        with open(path, "rb") as f:
            st.download_button("📥 Download Full Word Document", f, file_name="converted.docx")
    else:
        latex_pages = []
        for i, elements in enumerate(all_elements, 1):
            latex_pages.append(export_to_latex(elements, page_idx=i))
        latex_full = "\n\\newpage\n".join(latex_pages)
        path = tempfile.NamedTemporaryFile(delete=False, suffix=".tex").name
        with open(path, "w", encoding="utf-8") as f:
            f.write(latex_full)
        with open(path, "rb") as f:
            st.download_button("📥 Download Full LaTeX File", f, file_name="converted.tex")

with st.expander("📊 Usage / Batch Log"):
    st.write(f"Total: {client.usage['total']} | Success: {client.usage['success']} | Fail: {client.usage['fail']}")
