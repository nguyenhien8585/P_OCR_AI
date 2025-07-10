import streamlit as st
from pdf_utils import convert_pdf_to_images
from gemini_api import extract_content_with_gemini
from output_utils import export_to_word, export_to_latex
import tempfile

st.set_page_config(layout="wide", page_title="PDF to Word/LaTeX Converter")

st.title("📄🔁 Convert PDF to Word or LaTeX with Gemini 2.0 Flash")

uploaded_file = st.file_uploader("Upload PDF file", type="pdf")
output_format = st.radio("Select output format", ["Word (.docx)", "LaTeX (.tex)"])

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    images = convert_pdf_to_images(pdf_path)
    st.success(f"Extracted {len(images)} page(s).")

    extracted_content = []
    for i, image in enumerate(images):
        st.image(image, caption=f"Page {i+1}")
        with st.spinner(f"Analyzing Page {i+1}..."):
            content = extract_content_with_gemini(image)
            extracted_content.append((image, content))

    if output_format.startswith("Word"):
        output_path = export_to_word(extracted_content)
        with open(output_path, "rb") as f:
            st.download_button("⬇️ Download Word file", f, file_name="output.docx")
    else:
        output_path = export_to_latex(extracted_content)
        with open(output_path, "rb") as f:
            st.download_button("⬇️ Download LaTeX file", f, file_name="output.tex")
