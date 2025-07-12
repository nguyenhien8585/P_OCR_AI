import base64

def save_images_to_files(images_blocks, prefix="image_"):
    for idx, img in enumerate(images_blocks):
        with open(f"{prefix}{idx}.png", "wb") as f:
            f.write(base64.b64decode(img["image_b64"]))

def save_to_latex(text_blocks, images_blocks, file_path, image_prefix="image_"):
    latex_content = "\\documentclass{article}\n\\usepackage{graphicx}\n\\usepackage[utf8]{inputenc}\n\\begin{document}\n"
    for idx, block in enumerate(text_blocks):
        latex_content += block["text"].replace('\n', '\\\\') + "\n\n"
        if block.get("has_image"):
            img_file = f"{image_prefix}{block['img_idx']}.png"
            latex_content += f"\\begin{{center}}\n\\includegraphics[width=0.7\\linewidth]{{{img_file}}}\n\\end{{center}}\n"
    latex_content += "\\end{document}"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
