import re
import base64

def save_images_to_files(image_list, prefix=""):
    for img in image_list:
        img_path = f"{prefix}{img['name']}"
        with open(img_path, "wb") as f:
            f.write(base64.b64decode(img["base64"]))

def insert_images_to_latex_from_markdown(text, image_list, tex_path, image_prefix=""):
    latex = "\\documentclass{article}\n\\usepackage{graphicx}\n\\usepackage[utf8]{inputenc}\n\\begin{document}\n"
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    pos = 0
    for match in re.finditer(pattern, text):
        start, end = match.span()
        caption, img_name = match.groups()
        latex += text[pos:start].replace('\n', '\\\\') + "\n"
        found = False
        for img in image_list:
            if img["name"] == img_name:
                latex += f"\\begin{{center}}\\includegraphics[width=0.6\\linewidth]{{{image_prefix}{img_name}}}\\end{{center}}\n"
                found = True
                break
        if not found:
            latex += f"[Không tìm thấy ảnh: {img_name}]\n"
        pos = end
    latex += text[pos:].replace('\n', '\\\\') + "\n\\end{document}"
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex)
