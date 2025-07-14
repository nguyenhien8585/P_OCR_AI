import re
from docx import Document
from docx.shared import Inches
import base64
import io

def insert_images_to_word_from_markdown(markdown_text, images, output_path):
    doc = Document()
    # Chuyển từng đoạn (split theo \n\n để tách đoạn)
    for block in markdown_text.split('\n'):
        img_match = re.match(r"\[(HÌNH|BẢNG):\s*(.*?)\]", block.strip())
        if img_match:
            img_name = img_match.group(2)
            # Tìm đúng ảnh tương ứng
            img_obj = next((img for img in images if img["name"] == img_name), None)
            if img_obj:
                img_bytes = base64.b64decode(img_obj["base64"])
                image_stream = io.BytesIO(img_bytes)
                doc.add_picture(image_stream, width=Inches(4.5))
                doc.add_paragraph(f"{img_name}")
        else:
            # Nếu là text thuần, ghi đoạn
            doc.add_paragraph(block)
    doc.save(output_path)
