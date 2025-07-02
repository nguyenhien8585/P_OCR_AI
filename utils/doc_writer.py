from docx import Document

def build_docx(text, output_path):
    doc = Document()
    for line in text.splitlines():
        if line.strip():
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

