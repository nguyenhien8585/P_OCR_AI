import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image
import base64
import io

def extract_text_and_images(pdf_bytes, lang='vie+eng'):
    # Chuyển PDF thành từng trang ảnh
    pages = convert_from_bytes(pdf_bytes)
    results = []
    for idx, img in enumerate(pages):
        # OCR text toàn trang
        text = pytesseract.image_to_string(img, lang=lang)
        # Encode ảnh thành base64 để nhúng vào file Word/LaTeX
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({
            "text": text,
            "image_b64": img_b64,
            "page_num": idx + 1
        })
    return results
