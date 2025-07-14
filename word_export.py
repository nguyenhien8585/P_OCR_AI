from docx import Document
from docx.shared import Inches
import base64
import re
import io

def insert_images_to_word_from_markdown(text, figures, output_path):
    doc = Document()
    # Mapping hình minh hoạ (không phải bảng)
    figure_map = {f["name"]: f["base64"] for f in figures if not f.get("is_table", False)}
    # Tách text theo tag hình/bảng
    pattern = r"(\[HÌNH: [^\]]+\]|\[BẢNG: [^\]]+\])"
    parts = re.split(pattern, text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"\[HÌNH: ([^\]]+)\]", part)
        if m:
            fig_name = m.group(1).strip()
            if fig_name in figure_map:
                img_bytes = base64.b64decode(figure_map[fig_name])
                doc.add_picture(io.BytesIO(img_bytes), width=Inches(4.8))
        elif re.match(r"\[BẢNG: ([^\]]+)\]", part):
            continue  # Bỏ qua bảng
        else:
            doc.add_paragraph(part)
    doc.save(output_path)
