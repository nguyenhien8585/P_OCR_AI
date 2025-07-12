from docx import Document
from docx.shared import Inches
import base64
import io

def save_to_word(text_blocks, images_blocks, file_path):
    doc = Document()
    doc.add_heading('Kết quả OCR', level=1)
    for idx, block in enumerate(text_blocks):
        doc.add_paragraph(block["text"])
        if block.get("has_image"):
            img_b64 = images_blocks[block["img_idx"]]["image_b64"]
            img_bytes = base64.b64decode(img_b64)
            doc.add_picture(io.BytesIO(img_bytes), width=Inches(3.5))
            doc.add_paragraph(f"(Hình minh họa trang {block['img_idx']+1})")
    doc.save(file_path)
