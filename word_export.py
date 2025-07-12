import re
from docx import Document
from docx.shared import Inches
import base64
import io

def insert_images_to_word_from_markdown(text, image_list, output_path):
    """
    Chuyển văn bản OCR + marker ảnh ![img](img-x.jpeg) thành file Word.
    - Tự động chuyển tất cả $...$ về ${...}$ (MathType)
    - Chèn ảnh đúng vị trí gọi marker
    - Đoạn văn cách nhau 1 dòng
    - Ảnh không tìm thấy sẽ cảnh báo trong file Word
    """
    def convert_math_expr(s):
        # Chuyển tất cả $...$ thành ${...}$ (MathType)
        return re.sub(r'\$(.+?)\$', r'${\1}$', s, flags=re.DOTALL)

    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    text = convert_math_expr(text)

    doc = Document()
    pos = 0
    for match in re.finditer(pattern, text):
        start, end = match.span()
        caption, img_name = match.groups()

        # Thêm văn bản trước ảnh (theo đoạn, tách \n)
        before = text[pos:start].strip("\n")
        for para in before.split("\n"):
            if para.strip():
                doc.add_paragraph(para)
        # Chèn đúng ảnh theo tên
        found = False
        for img in image_list:
            if img["name"] == img_name:
                img_bytes = base64.b64decode(img["base64"])
                doc.add_picture(io.BytesIO(img_bytes), width=Inches(3.7))
                found = True
                if caption and not caption.startswith("img-"):
                    doc.add_paragraph(f"(Hình: {caption})").italic = True
                break
        if not found:
            doc.add_paragraph(f"[Không tìm thấy ảnh: {img_name}]").italic = True
        pos = end
    # Thêm phần cuối văn bản
    after = text[pos:].strip("\n")
    for para in after.split("\n"):
        if para.strip():
            doc.add_paragraph(para)
    doc.save(output_path)
