import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
import requests
from docx import Document

# ==== Cấu hình AI.VN API ====
API_ENDPOINT = "https://api.sv2.llm.ai.vn/v1/chat/completions"
API_KEY = "sk-j4DkzI7htsVqEZqC272d3b58B0Fb49A183573dD2Fc04F71d"  # <-- Thay bằng API KEY thực của bạn

def gemini_image_to_text(image, latex=True):
    # Chuyển ảnh sang base64
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    # Prompt cho AI.VN
    prompt = "Nhận diện toàn bộ nội dung, chuyển công thức toán thành LaTeX." if latex else "Trích xuất nội dung ảnh sang văn bản."
    payload = {
        "model": "gemini-2.5-pro-preview-0605",
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_b64]
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=120)
    data = resp.json()
    try:
        return data['choices'][0]['message']['content']
    except Exception:
        return "[Lỗi xử lý AI.VN]"

def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

def save_word(text_list, images_list, image_captions, output_path):
    doc = Document()
    for i, txt in enumerate(text_list):
        doc.add_paragraph(txt)
        if i < len(images_list):
            img_stream = io.BytesIO()
            images_list[i].save(img_stream, format="PNG")
            doc.add_picture(img_stream, width=docx.shared.Inches(4))
            if image_captions and i < len(image_captions):
                doc.add_paragraph(image_captions[i], style='Caption')
    doc.save(output_path)

def save_latex(text_list, images_list, image_captions, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n")
        for i, txt in enumerate(text_list):
            f.write(txt + "\n\n")
            if i < len(images_list):
                img_path = f"img_{i+1}.png"
                images_list[i].save(f"output/{img_path}")
                f.write(f"\\begin{{figure}}[h]\n\\centering\n\\includegraphics[width=0.7\\linewidth]{{{img_path}}}\n")
                if image_captions and i < len(image_captions):
                    f.write(f"\\caption{{{image_captions[i]}}}\n")
                f.write("\\end{figure}\n\n")
        f.write("\\end{document}\n")

import base64

st.set_page_config(layout="wide", page_title="PDF/Ảnh ➔ Word/LaTeX + Hình minh họa")
st.title("📄 Chuyển PDF/Ảnh sang Word/LaTeX (có hình minh họa)")

uploaded = st.file_uploader("Tải lên PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
if uploaded:
    # Đọc file PDF thành ảnh
    if uploaded.type == "application/pdf":
        images = pdf_to_images(uploaded.read())
    else:
        img = Image.open(uploaded)
        images = [img]

    st.subheader("Xem trước từng trang/ảnh")
    img_idx = st.number_input("Trang/ảnh số:", min_value=1, max_value=len(images), value=1, step=1)
    current_img = images[img_idx-1]

    st.image(current_img, caption=f"Trang/ảnh {img_idx}", use_column_width=True)

    st.info("Chọn vùng chứa hình minh họa để cắt (bằng chuột, nhập toạ độ hoặc dùng code bổ sung OpenCV cho auto detect). Ở bản đơn giản này, hãy nhập toạ độ vùng cắt bên dưới.")

    col1, col2 = st.columns(2)
    with col1:
        st.write("**Toạ độ vùng hình minh họa (x, y, w, h):**")
        x = st.number_input("x", 0, current_img.width-1, 0)
        y = st.number_input("y", 0, current_img.height-1, 0)
        w = st.number_input("w", 1, current_img.width-x, current_img.width)
        h = st.number_input("h", 1, current_img.height-y, current_img.height)
        if st.button("Cắt và nhận diện"):
            # Cắt hình minh họa
            box = (x, y, x+w, y+h)
            cropped_img = current_img.crop(box)
            st.image(cropped_img, caption="Hình minh họa đã cắt", use_column_width=True)
            # Nhận diện nội dung chính (text+LaTeX)
            with st.spinner("Đang gửi ảnh lên AI.VN để nhận diện nội dung..."):
                latex_text = gemini_image_to_text(current_img, latex=True)
                st.markdown("**Nội dung nhận diện:**")
                st.code(latex_text, language="latex")
            # Nhận diện caption hình vẽ
            with st.spinner("Đang mô tả hình minh họa..."):
                img_caption = gemini_image_to_text(cropped_img, latex=False)
                st.markdown("**Mô tả hình minh họa:**")
                st.write(img_caption)

            # Lưu kết quả để xuất file
            if st.button("Xuất file Word + LaTeX"):
                save_word([latex_text], [cropped_img], [img_caption], "output/word.docx")
                save_latex([latex_text], [cropped_img], [img_caption], "output/tex_output.tex")
                st.success("Đã xuất xong file!")
                with open("output/word.docx", "rb") as f:
                    st.download_button("Tải file Word", f, "word.docx")
                with open("output/tex_output.tex", "r", encoding="utf-8") as f:
                    st.download_button("Tải file LaTeX", f, "tex_output.tex")

    with col2:
        st.write("**Hiển thị song song:**")
        st.image(current_img, caption="Ảnh/trang gốc", use_column_width=True)
        # Nếu đã có kết quả
        if "latex_text" in locals():
            st.markdown("**LaTeX/Văn bản nhận diện:**")
            st.code(latex_text, language="latex")
        if "cropped_img" in locals():
            st.image(cropped_img, caption="Hình minh họa cắt", use_column_width=True)
        if "img_caption" in locals():
            st.write("**Mô tả hình minh họa:**")
            st.write(img_caption)
