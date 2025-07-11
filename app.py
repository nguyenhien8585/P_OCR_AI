# app.py
import streamlit as st
import pdfplumber
from PIL import Image
from docx import Document
import io
import os
import base64
import re
import tempfile

# Thiết lập trang Streamlit
st.set_page_config(layout="wide", page_title="PDF to Word/LaTeX Converter")

# Tiêu đề ứng dụng
st.title("PDF to Word/LaTeX Converter with Image Preservation")

# Mô tả ứng dụng
st.markdown("""
This tool converts PDF files to Word (.docx) or LaTeX format while preserving:
- Text content
- Page layouts
- Embedded images
""")

# Tạo layout 2 cột
main_col1, main_col2 = st.columns([1, 1], gap="large")

def extract_images_from_page(page, temp_dir):
    """Trích xuất hình ảnh từ trang PDF"""
    images = []
    image_objects = page.images
    for img in image_objects:
        try:
            img_data = img["stream"].get_data()
            img_obj = Image.open(io.BytesIO(img_data))
            img_path = os.path.join(temp_dir, f"img_{len(images)}.png")
            img_obj.save(img_path)
            images.append(img_path)
        except Exception as e:
            st.warning(f"Could not extract image: {e}")
    return images

def pdf_to_word(pdf_path, temp_dir):
    """Chuyển PDF sang Word với hình ảnh"""
    doc = Document()
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            # Thêm văn bản
            text = page.extract_text()
            if text:
                doc.add_paragraph(text)
            
            # Thêm hình ảnh
            images = extract_images_from_page(page, temp_dir)
            for img_path in images:
                doc.add_picture(img_path, width=Inches(4))  # Điều chỉnh kích thước ảnh
            
            # Thêm ngắt trang (trừ trang cuối)
            if i < len(pdf.pages) - 1:
                doc.add_page_break()
    
    return doc

def format_latex_image(img_path):
    """Tạo mã LaTeX cho hình ảnh"""
    return f"""
\\begin{{figure}}[h]
\\centering
\\includegraphics[width=0.8\\textwidth]{{{img_path}}}
\\caption{{Image extracted from PDF}}
\\label{{fig:img_{os.path.basename(img_path)}}}
\\end{{figure}}
"""

def pdf_to_latex(pdf_path, temp_dir):
    """Chuyển PDF sang LaTeX với hình ảnh"""
    latex_content = "\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n"
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                latex_content += text.replace("\\", "\\textbackslash").replace("&", "\\&") + "\n\n"
            
            images = extract_images_from_page(page, temp_dir)
            for img_path in images:
                latex_content += format_latex_image(img_path)
    
    latex_content += "\\end{document}"
    return latex_content

def get_binary_file_downloader_html(bin_data, file_label, file_name):
    """Tạo link download file"""
    bin_str = base64.b64encode(bin_data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{file_name}">{file_label}</a>'
    return href

def main():
    with main_col1:
        uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
        output_format = st.radio("Select output format:", ["Word (.docx)", "LaTeX (.tex)"])
    
    if uploaded_file is not None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pdf_path = os.path.join(temp_dir, "uploaded.pdf")
            with open(temp_pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            with pdfplumber.open(temp_pdf_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text()
                
                # Hiển thị văn bản và hình ảnh trong giao diện
                with main_col1:
                    st.subheader("Extracted Text")
                    if text:
                        st.text_area("Text from first page (preview):", value=text, height=300)
                    else:
                        st.warning("No text found in the first page")
                    
                    # Hiển thị hình ảnh từ trang đầu tiên
                    images = extract_images_from_page(first_page, temp_dir)
                    if images:
                        st.subheader("Extracted Images")
                        for img_path in images:
                            st.image(img_path, use_column_width=True)
                    else:
                        st.warning("No images found in the first page")
                
                with main_col2:
                    if output_format == "Word (.docx)":
                        st.subheader("Word Document Generation")
                        doc = pdf_to_word(temp_pdf_path, temp_dir)
                        output_path = os.path.join(temp_dir, "output.docx")
                        doc.save(output_path)
                        
                        with open(output_path, "rb") as f:
                            st.markdown(get_binary_file_downloader_html(
                                f.read(), "Download Word Document", "converted.docx"),
                                unsafe_allow_html=True)
                    
                    elif output_format == "LaTeX (.tex)":
                        st.subheader("LaTeX Document Generation")
                        latex_content = pdf_to_latex(temp_pdf_path, temp_dir)
                        st.text_area("LaTeX Output Preview:", value=latex_content[:5000] + ("..." if len(latex_content) > 5000 else ""), height=300)
                        
                        output_path = os.path.join(temp_dir, "output.tex")
                        with open(output_path, "w", encoding="utf-8") as f:
                            f.write(latex_content)
                        
                        with open(output_path, "rb") as f:
                            st.markdown(get_binary_file_downloader_html(
                                f.read(), "Download LaTeX File", "converted.tex"),
                                unsafe_allow_html=True)

if __name__ == "__main__":
    from docx.shared import Inches  # Import sau để tránh lỗi với Streamlit
    main()
