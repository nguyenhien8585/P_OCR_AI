import streamlit as st
import base64
from ocr_client_api import EnhancedSmartOCRClient
from config import API_URL, API_KEY
from word_export import save_to_word
from latex_export import save_to_latex, save_images_to_files
import os

st.set_page_config(page_title="Smart OCR - Streamlit", layout="centered")
st.title("📄 Smart OCR (API) – Xuất Word/LaTeX, kèm ảnh minh hoạ")

client = EnhancedSmartOCRClient(API_URL, API_KEY)

st.write("**Nhận diện văn bản + trích xuất ảnh từ PDF/ảnh, dùng API key. Xuất Word/LaTeX chèn đúng vị trí ảnh.**")

uploaded_file = st.file_uploader("Chọn file PDF/ảnh (multi-page)", type=["pdf", "jpg", "jpeg", "png"])
if uploaded_file:
    file_bytes = uploaded_file.read()
    mime_type = uploaded_file.type
    file_name = uploaded_file.name

    with st.spinner("Đang nhận diện OCR qua API..."):
        result = client.convert(file_bytes, file_name, mime_type)
    
    if not result.get("success"):
        st.error("OCR thất bại: " + str(result.get("error")))
    else:
        data = result["data"]
        st.success(f"OCR thành công! Số trang: {data.get('page_count')}, Ngôn ngữ: {data.get('language_detected')}")
        st.text_area("Văn bản trích xuất", data.get("text_content", ""), height=250)

        # ======= HIỂN THỊ VÀ XUẤT ẢNH ==========
        images_b64 = data.get("images", [])  # API trả về mảng base64 ảnh (nếu hỗ trợ)
        text_blocks, images_blocks = [], []
        if images_b64:
            st.subheader("Các ảnh minh hoạ tách được:")
            for idx, img_b64 in enumerate(images_b64):
                st.image(img_b64, caption=f"Hình {idx+1}", use_column_width=True)
                text_blocks.append({"text": f"Ảnh minh hoạ {idx+1}", "has_image": True, "img_idx": idx})
                images_blocks.append({"image_b64": img_b64})
        else:
            st.info("Không tìm thấy ảnh minh hoạ hoặc API chưa trả về.")

        # Bổ sung 1 block text chính cho Word/LaTeX demo (ghép text chính với các ảnh)
        text_blocks.insert(0, {"text": data.get("text_content", ""), "has_image": False})

        # Xuất Word
        if st.button("📥 Xuất file Word (.docx)"):
            word_file = "ket_qua_ocr.docx"
            save_to_word(text_blocks, images_blocks, word_file)
            with open(word_file, "rb") as f:
                st.download_button("Tải về file Word", f, file_name=word_file)
            os.remove(word_file)

        # Xuất LaTeX
        if st.button("📥 Xuất file LaTeX (.tex, kèm ảnh PNG)"):
            latex_file = "ket_qua_ocr.tex"
            save_images_to_files(images_blocks, prefix="image_")
            save_to_latex(text_blocks, images_blocks, latex_file, image_prefix="image_")
            with open(latex_file, "r", encoding="utf-8") as f:
                st.download_button("Tải về file LaTeX", f, file_name=latex_file)
            os.remove(latex_file)
            for idx in range(len(images_blocks)):
                if os.path.exists(f"image_{idx}.png"):
                    os.remove(f"image_{idx}.png")

    # Các chức năng kiểm tra tài khoản/usage nếu muốn:
    with st.expander("Kiểm tra tài khoản/usage"):
        if st.button("Xem tài khoản"):
            st.json(client.get_account())
        if st.button("Xem usage"):
            st.json(client.get_usage("month"))
        if st.button("Xem status API"):
            st.json(client.get_status())

st.markdown("---")
st.caption("Phiên bản dùng API key giống GAS, code Python/Streamlit xuất Word/LaTeX.")
