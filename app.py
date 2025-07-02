import streamlit as st
from PIL import Image
import numpy as np
from paddleocr import PPStructure, save_structure_res
from streamlit_cropper import st_cropper
import io

st.set_page_config(page_title="Auto-crop minh họa tài liệu", layout="wide")
st.title("📄 Auto-crop hình minh họa tài liệu (PaddleOCR layout)")

st.markdown("""
- **Tải lên ảnh scan, trang PDF (chuyển ảnh trước), đề thi, sách, v.v...**
- **Auto detect & crop vùng hình minh họa (figure/image) bằng AI**
- **Nếu không đúng, crop lại bằng chuột!**
""")

uploaded = st.file_uploader("Tải lên ảnh tài liệu (jpg, png, jpeg)", type=["jpg", "jpeg", "png"])
if uploaded:
    img = Image.open(uploaded).convert("RGB")
    st.image(img, caption="Ảnh gốc", use_container_width=True)

    with st.spinner("Đang chạy AI nhận diện layout (figure/image/table)..."):
        ocr = PPStructure(layout=True, show_log=False)
        # PaddleOCR nhận đầu vào là mảng np.uint8
        result = ocr(np.array(img))
        # Tìm các vùng 'figure' hoặc 'image'
        figure_blocks = [b for b in result if b['type'] in ("figure", "image")]

    if figure_blocks:
        st.success(f"Đã phát hiện {len(figure_blocks)} vùng hình minh họa.")
        crops = []
        for i, block in enumerate(figure_blocks):
            x1, y1, x2, y2 = block['bbox']
            crop = img.crop((x1, y1, x2, y2))
            st.image(crop, caption=f"Minh họa tự động {i+1}", use_container_width=True)
            crops.append(crop)
        st.info("Nếu crop chưa đúng, crop lại bằng chuột ở dưới:")
    else:
        st.warning("KHÔNG tự động phát hiện được hình minh họa. Bạn có thể crop tay bằng chuột:")
        crops = []

    # Cho phép crop tay trên ảnh gốc (dù đã auto hay chưa)
    n_crop = st.number_input("Số hình muốn crop tay", 0, 10, 0, 1)
    manual_crops = []
    for i in range(n_crop):
        box = st_cropper(img, box_color='#FF0000', aspect_ratio=None, key=f"manual_crop_{i}", return_type='box')
        if box:
            left = box.get("left", 0)
            top = box.get("top", 0)
            width = box.get("width", img.width)
            height = box.get("height", img.height)
            if width > 10 and height > 10:
                crop = img.crop((left, top, left + width, top + height))
                st.image(crop, caption=f"Minh họa crop tay {i+1}", use_container_width=True)
                manual_crops.append(crop)

    # Tổng hợp các crop lại
    all_crops = crops + manual_crops
    if all_crops:
        st.markdown("---")
        st.subheader("Tải về các ảnh minh họa đã crop")
        for i, crop in enumerate(all_crops):
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            st.download_button(f"Tải hình crop {i+1}", buf.getvalue(), file_name=f"crop_{i+1}.png", mime="image/png")
else:
    st.info("Vui lòng tải lên một ảnh scan/trang tài liệu để bắt đầu.")

st.caption("✨ Dùng PaddleOCR layout detection: nhẹ, AI auto-crop tốt, chạy trên cả cloud/public.")
