import streamlit as st
from PIL import Image
import fitz
import io, os, base64
import requests
from docx import Document
from streamlit_cropper import st_cropper
import shutil

# --- Cấu hình API ---
API_ENDPOINT = "https://api.sv2.llm.ai.vn/v1/chat/completions"
API_KEY = "sk-j4DkzI7htsVqEZqC272d3b58B0Fb49A183573dD2Fc04F71d"  # <-- Điền API KEY AI.VN

# --- Hàm gửi ảnh lên AI.VN để nhận diện ---
def gemini_image_to_text(image, latex=True):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    prompt = "Nhận diện toàn bộ nội dung, chuyển công thức toán thành LaTeX." if latex else "Mô tả hình minh họa."
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
    try:
        resp = requests.post(API_ENDPOINT, headers=headers, json=payload, timeout=120)
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"[Lỗi API: {e}]"

# --- PDF sang ảnh ---
def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

# --- Xuất Word ---
def save_word(text_list, images, captions, output_path):
    doc = Document()
    for i, txt in enumerate(text_list):
        doc.add_paragraph(txt)
        if i < len(images):
            img_stream = io.BytesIO()
            images[i].save(img_stream, format="PNG")
            img_stream.seek(0)
            doc.add_picture(img_stream, width=docx.shared.Inches(4))
            if captions and i < len(captions):
                doc.add_paragraph(captions[i], style='Caption')
    doc.save(output_path)

# --- Xuất LaTeX ---
def save_latex(text_list, images, captions, out_dir="output", out_path="output/output.tex"):
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\\documentclass{article}\n\\usepackage{graphicx}\n\\begin{document}\n")
        for i, txt in enumerate(text_list):
            f.write(txt + "\n\n")
            if i < len(images):
                img_path = f"{out_dir}/img-{i+1}.png"
                images[i].save(img_path)
                f.write(f"\\begin{{figure}}[h]\n\\centering\n\\includegraphics[width=0.7\\linewidth]{{img-{i+1}.png}}\n")
                if captions and i < len(captions):
                    f.write(f"\\caption{{{captions[i]}}}\n")
                f.write("\\end{figure}\n\n")
        f.write("\\end{document}\n")

# --- MAIN APP ---
st.set_page_config(layout="wide", page_title="P_PDF with AI 6/2025")
if not os.path.exists("output"): os.makedirs("output")

st.markdown("""
# 📄 P_PDF with AI 6/2025  
⭑ Chuyển đổi PDF/Image thành văn bản có thể chỉnh sửa với AI
""")

tab1, tab2, tab3 = st.tabs(["OCR PDF", "OCR Image", "Sửa lỗi chính tả"])

with tab1:
    st.markdown("### OCR cho file PDF")
    uploaded = st.file_uploader("Chọn file PDF để xử lý OCR", type=["pdf"])
    log = []
    if uploaded:
        st.info("Tải lên thành công! Đang chuyển PDF sang ảnh...")
        images = pdf_to_images(uploaded.read())
        num_pages = len(images)
        file_info = {
            "Tên file": uploaded.name,
            "Loại file": uploaded.type,
            "Kích thước": f"{uploaded.size/1024:.1f} KB",
            "Số trang": num_pages
        }
        with st.expander("🛈 Thông tin file"):
            for k, v in file_info.items():
                st.write(f"- **{k}:** {v}")

        st.subheader("Xem & crop minh họa từng trang")
        text_results = []
        img_results = []
        caption_results = []
        for i, img in enumerate(images):
            st.markdown(f"---\n#### Trang {i+1}")
            st.image(img, caption=f"Trang {i+1}", use_column_width=True)
            st.write("**Chọn vùng hình minh họa bằng chuột (nếu có):**")
            cropped = st_cropper(img, box_color='#00FF00', aspect_ratio=None, return_type="PIL", key=f"cropper{i}")
            st.image(cropped, caption=f"Hình minh họa đã cắt (Trang {i+1})", use_column_width=True)
            colbt1, colbt2 = st.columns(2)
            with colbt1:
                if st.button(f"OCR văn bản + công thức (trang {i+1})", key=f"btnocr-{i}"):
                    with st.spinner("Đang nhận diện..."):
                        ocr_text = gemini_image_to_text(img, latex=True)
                        text_results.append(ocr_text)
                        st.success("Hoàn thành nhận diện!")
                        st.code(ocr_text, language="latex")
            with colbt2:
                if st.button(f"Mô tả hình minh họa (trang {i+1})", key=f"btnimg-{i}"):
                    with st.spinner("Đang mô tả hình minh họa..."):
                        img_caption = gemini_image_to_text(cropped, latex=False)
                        img_results.append(cropped)
                        caption_results.append(img_caption)
                        st.success("Đã mô tả xong!")
                        st.write(f"**Caption:** {img_caption}")

        st.markdown("---")
        if st.button("Tạo file Word + LaTeX", type="primary"):
            with st.spinner("Đang xuất..."):
                save_word(text_results, img_results, caption_results, "output/word.docx")
                save_latex(text_results, img_results, caption_results)
                st.success("Đã xuất xong file!")
                with open("output/word.docx", "rb") as f:
                    st.download_button("Tải file Word", f, "output.docx")
                with open("output/output.tex", "r", encoding="utf-8") as f:
                    st.download_button("Tải file LaTeX", f, "output.tex")

    with st.expander("📊 Nhật ký hoạt động"):
        st.write("Hành động, trạng thái xử lý sẽ hiển thị ở đây.")

with tab2:
    st.markdown("### OCR cho ảnh (bổ sung)")
    uploaded_img = st.file_uploader("Chọn ảnh để OCR", type=["png", "jpg", "jpeg"])
    if uploaded_img:
        img = Image.open(uploaded_img)
        st.image(img, caption="Ảnh đã chọn", use_column_width=True)
        st.write("Chọn vùng hình minh họa bằng chuột:")
        cropped_img = st_cropper(img, box_color='#FF0000')
        st.image(cropped_img, caption="Ảnh đã cắt", use_column_width=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("OCR nội dung ảnh"):
                with st.spinner("Đang nhận diện..."):
                    text = gemini_image_to_text(img, latex=True)
                    st.code(text, language="latex")
        with col2:
            if st.button("Mô tả vùng hình minh họa"):
                with st.spinner("Đang mô tả..."):
                    caption = gemini_image_to_text(cropped_img, latex=False)
                    st.write(f"**Caption:** {caption}")

with tab3:
    st.markdown("### Sửa lỗi chính tả")
    st.info("Tính năng sẽ cập nhật sau.")
