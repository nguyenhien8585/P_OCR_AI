from docx import Document
from docx.shared import Inches

def build_docx(text, image_dir, output_path):
    doc = Document()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("<<image_"):
            img = line.replace("<<", "").replace(">>", "")
            doc.add_picture(f"{image_dir}/{img}", width=Inches(4))
        elif line:
            doc.add_paragraph(line)
    doc.save(output_path)

def build_latex(content, output_path):
    preamble = r"""
\documentclass{article}
\usepackage{amsmath,graphicx}
\begin{document}
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(preamble)
        f.write(content)
        f.write("\n\\end{document}")
