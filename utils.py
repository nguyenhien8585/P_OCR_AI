import pytesseract
import openai
import base64
import io
from PIL import Image
import fitz  # PyMuPDF

# ⚠️ Nhớ thay YOUR_API_KEY thành API thực tế
openai.api_key = "sk-j4DkzI7htsVqEZqC272d3b58B0Fb49A183573dD2Fc04F71d"
openai.api_base = "https://api.sv2.llm.ai.vn/v1"

def extract_text_ocr(image):
    return pytesseract.image_to_string(image, lang="vie+eng")

def encode_image(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def call_gpt4o_ai_vn(image, raw_text):
    b64_image = encode_image(image)
    response = openai.chat.completions.create(
        model="openai:gpt-4o",
        messages=[
            {"role": "system", "content": "Bạn là trợ lý chuyên phân tích đề thi và xuất ra định dạng LaTeX/Word."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Nội dung OCR:\n{raw_text}\nHãy chuyển sang LaTeX chuẩn kèm hướng dẫn chèn ảnh."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                ]
            }
        ],
        temperature=0.2
    )
    return response.choices[0].message.content

def pdf_to_images(file_bytes):
    images = []
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
    return images
