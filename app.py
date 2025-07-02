import streamlit as st
from PIL import Image
import fitz
import io
import layoutparser as lp
from streamlit_cropper import st_cropper

st.set_page_config(page_title="Auto-crop minh họa PubLayNet", layout="wide")
st.title("📄 Auto-crop hình minh họa bằng PubLayNet + crop thủ công")

@st.cache_resource
def load_model():
    model = lp.Detectron2LayoutModel(
        "lp://PubLayNet/faster_rcnn_R_50_FPN_3x/config",
        extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5],
        label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"}
    )
    return model

model = load_model()

def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

uploaded = st.file_uploader("Chọn PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
if uploaded:
    if uploaded.name.lower().endswith(".pdf"):
        images = pdf_to_images(uploaded.read())
        st.success(f"Đã tách {len(images)} trang từ PDF.")
    else:
        images = [Image.open(uploaded)]
        st.success("Đã tải lên 1 ảnh.")

    for idx, img in enumerate(images):
        st.markdown(f"---\n### Trang {idx+1}")
        st.image(img, caption=f"Trang {idx+1}", use_container_width=True)

        with st.spinner("AI đang tự động nhận diện vùng hình minh họa (PubLayNet)..."):
            layout = model.detect(img)
            figures = [b for b in layout if b.type == "Figure"]
        crops_this_page = []
        if figures:
            st.success(f"AI phát hiện {len(figures)} hình minh họa! Nếu không đúng, crop lại bên dưới.")
            for i, block in enumerate(figures):
                x1, y1, x2, y2 = map(int, block.coordinates)
                crop = img.crop((x1, y1, x2, y2))
                st.image(crop, caption=f"Auto Minh họa {i+1} Trang {idx+1}", use_container_width=True)
                crops_this_page.append(crop)
        else:
            st.warning("Không tự động phát hiện được hình minh họa. Crop tay bên dưới!")
        
        # Luôn cho phép crop thủ công để chỉnh lại vùng AI nhận sai
        n_crop = st.number_input(f"Số vùng muốn crop tay (Trang {idx+1})", 0, 10, 0, 1)
        for i in range(n_crop):
            st.write(f"Crop tay Minh họa {i+1} Trang {idx+1}:")
            box = st_cropper(img, box_color='#FF0000', aspect_ratio=None, key=f"cropper_{idx}_{i}", return_type='box')
            if box:
                left = box.get("left", 0)
                top = box.get("top", 0)
                width = box.get("width", img.width)
                height = box.get("height", img.height)
                if width > 10 and height > 10:
                    crop = img.crop((left, top, left + width, top + height))
                    st.image(crop, caption=f"Minh họa tay {i+1} Trang {idx+1}", use_container_width=True)
                    crops_this_page.append(crop)

        # Cho tải về từng ảnh đã crop
        if crops_this_page:
            st.subheader("Tải về từng hình đã crop")
            for i, crop in enumerate(crops_this_page):
                buf = io.BytesIO()
                crop.save(buf, format="PNG")
                st.download_button(
                    f"Tải hình crop {i+1} Trang {idx+1}", buf.getvalue(),
                    file_name=f"crop_{i+1}_page_{idx+1}.png", mime="image/png"
                )
else:
    st.info("Tải lên file PDF hoặc ảnh để bắt đầu.")

st.caption("✨ AI layout PubLayNet (Detectron2) cho auto-crop hình minh họa. Luôn hỗ trợ crop tay chỉnh lại (an toàn tuyệt đối). Chạy local/VPS riêng.")
