# word_export.py
import re
from docx import Document
from docx.shared import Inches
import base64
import io

def insert_images_to_word_from_markdown(markdown_text, images, output_path):
    doc = Document()
    # Mapping tên ảnh sang object ảnh
    image_map = {img['name']: img for img in images}

    for line in markdown_text.split('\n'):
        m = re.match(r'\[(HÌNH|BẢNG):\s*(.*?)\]', line.strip())
        if m:
            img_name = m.group(2)
            img_obj = image_map.get(img_name)
            if img_obj:
                img_bytes = base64.b64decode(img_obj["base64"])
                stream = io.BytesIO(img_bytes)
                doc.add_picture(stream, width=Inches(4.3))  # chiều rộng ~11cm
                doc.add_paragraph(img_name)
        else:
            doc.add_paragraph(line)

    doc.save(output_path)
