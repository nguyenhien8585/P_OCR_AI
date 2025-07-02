import os
from pdf2image import convert_from_path
from utils.extract_images import extract_diagrams
from utils.gpt_vision import ask_gpt_vision
from utils.doc_writer import build_docx, build_latex

# Cấu hình
PDF_PATH = "input.pdf"
PAGE_DIR = "pages"
DIAGRAM_DIR = "diagrams"
OUTPUT_LATEX = "output.tex"
OUTPUT_WORD = "output.docx"
MODE = "latex"  # hoặc "word"
API_KEY = "sk-j4DkzI7htsVqEZqC272d3b58B0Fb49A183573dD2Fc04F71d"

# 1. Tách trang PDF
os.makedirs(PAGE_DIR, exist_ok=True)
pages = convert_from_path(PDF_PATH, dpi=300)
for i, page in enumerate(pages):
    img_path = f"{PAGE_DIR}/page_{i+1}.png"
    page.save(img_path)

# 2. Gửi từng trang đến GPT-4o để sinh nội dung
full_text = ""
for i, page in enumerate(pages):
    img_path = f"{PAGE_DIR}/page_{i+1}.png"
    content = ask_gpt_vision(img_path, MODE, API_KEY)
    full_text += content + "\n"

# 3. Tách ảnh minh họa
os.makedirs(DIAGRAM_DIR, exist_ok=True)
for i in range(len(pages)):
    extract_diagrams(f"{PAGE_DIR}/page_{i+1}.png", f"{DIAGRAM_DIR}/image_page{i+1}")

# 4. Tạo file Word hoặc LaTeX
if MODE == "word":
    build_docx(full_text, DIAGRAM_DIR, OUTPUT_WORD)
else:
    build_latex(full_text, OUTPUT_LATEX)
