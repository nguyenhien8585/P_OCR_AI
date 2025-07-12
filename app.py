import streamlit as st
import base64
from ocr_util import extract_text_and_images
from word_export import save_to_word
from latex_export import save_to_latex, save_images_to_files
import os

st.set_page_config(page_title="Smart OCR - PDF/Image to Text + Word/LaTeX", layout="centered")
st.title("📄 Smart OCR (PDF/Ảnh ➡️ Text + Word + LaTeX + Ảnh minh họa)")

st.write("""
- OCR tài liệu PDF, ảnh (hỗ trợ tiếng Việt/Anh)
- Tách từng trang thành văn bản và ảnh minh họa
- **Xuất Word hoặc LaTeX, ảnh chèn đúng vị trí**
- Code Python, chạy trên Streamlit, không cần API ngoài!
""")

uploaded_file = st.file_uploader("Chọn file PDF hoặc ảnh (multi-page)", type=["pdf", "jpg", "jpeg", "png"])
if uploaded_file:
    file_bytes = uploaded_file.read()
    file_type = uploaded_file.type
    is_pdf = uploaded_file.name.lower().endswith('.pdf')

    st.info("⏳ Đang xử lý, vui lòng chờ...")
    ocr_results = extract_text_and_images(file_bytes)

    st.success(f"Đã nhận diện {len(ocr_results)} trang!")

    # Hiển thị kết quả từng trang
    text_blocks, images_blocks = [], []
    for page in ocr_results:
        st.subheader(f"Trang {page['page_num']}")
        st.text_area(f"Text (Trang {page['page_num']})", page['text'], height=180)
        st.image(base64.b64decode(page["image_b64"]), caption=f"Hình (Trang {page['page_num']})", use_column_width=True)
        text_blocks.append({"text": page['text'], "has_image": True, "img_idx": len(images_blocks)})
        images_blocks.append({"image_b64": page["image_b64"]})

    # Xuất file Word
    if st.button("📥 Xuất file Word (.docx)"):
        word_file = "ket_qua_ocr.docx"
        save_to_word(text_blocks, images_blocks, word_file)
        with open(word_file, "rb") as f:
            st.download_button("Tải về file Word", f, file_name=word_file)
        os.remove(word_file)

    # Xuất file LaTeX
    if st.button("📥 Xuất file LaTeX (.tex, kèm ảnh PNG)"):
        latex_file = "ket_qua_ocr.tex"
        save_images_to_files(images_blocks, prefix="image_")
        save_to_latex(text_blocks, images_blocks, latex_file, image_prefix="image_")
        with open(latex_file, "r", encoding="utf-8") as f:
            st.download_button("Tải về file LaTeX", f, file_name=latex_file)
        os.remove(latex_file)
        # Xóa ảnh tạm
        for idx in range(len(images_blocks)):
            if os.path.exists(f"image_{idx}.png"):
                os.remove(f"image_{idx}.png")

    st.caption("Nếu cần xuất Word/LaTeX nhiều dạng hoặc mapping ảnh vào vị trí khác, hãy liên hệ hoặc gửi file mẫu!")

st.markdown("---")
st.markdown("**Made by [yourname] - Full code Python/Streamlit, hỗ trợ tiếng Việt**")

