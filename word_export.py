import re
from docx import Document
from docx.shared import Inches
import base64
import io

def insert_images_to_word_from_markdown(text, image_list, output_path):
    # image_list: list dict {"name": ..., "base64": ...}
    doc = Document()
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    pos = 0
    for match in re.finditer(pattern, text):
        start, end = match.span()
        caption, img_name = match.groups()
        # Add text before image
        doc.add_paragraph(text[pos:start])
        # Chèn đúng ảnh theo tên
        found = False
        for img in image_list:
            if img["name"] == img_name:
                img_bytes = base64.b64decode(img["base64"])
                doc.add_picture(io.BytesIO(img_bytes), width=Inches(3.5))
                found = True
                if caption:
                    doc.add_paragraph(f"(Hình: {caption})")
                break
        if not found:
            doc.add_paragraph(f"[Không tìm thấy ảnh: {img_name}]")
        pos = end
    # Add phần còn lại cuối
    doc.add_paragraph(text[pos:])
    doc.save(output_path)
