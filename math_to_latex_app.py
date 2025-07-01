import streamlit as st
import openai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re
import json

def get_prompt(mode):
    return """
Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
1. Gõ lại TẤT CẢ văn bản, thứ tự, định dạng, cấu trúc dòng giống ảnh.
2. KHÔNG thêm giải thích, KHÔNG tự bịa nội dung mới.
3. Công thức Toán dưới dạng $...$, hệ: $\\begin{cases}...\\end{cases}$.
4. Khi gặp hình minh hoạ/biểu đồ, thay vào văn bản bằng {image_n}, với n là số thứ tự xuất hiện hình trên trang.
5. Chỉ trả về bounding box bao toàn bộ mỗi HÌNH VẼ/MINH HOẠ/BIỂU ĐỒ.
6. Sau phần văn bản, chỉ trả về một dòng duy nhất:
BoundingBox: [{"left":x1,"top":y1,"right":x2,"bottom":y2},...]
**Chỉ trả về box bao trọn hình, KHÔNG trả về box cho text hoặc các phần nhỏ khác!**
"""

def img_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def ask_gpt4o_with_image(pil_img, prompt, client):
    img_b64 = img_to_base64(pil_img)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]
        }
    ]
    response = client.chat.completions.create(
        model="openai:gpt-4o",
        messages=messages,
        max_tokens=4096,
        temperature=0.1
    )
    return response.choices[0].message.content

def parse_gpt_output(text):
    pattern = r'BoundingBox:\s*(\[.*\])'
    match = re.search(pattern, text, re.DOTALL)
    boxes = []
    if match:
        try:
            boxes = json.loads(match.group(1))
        except Exception as e:
            boxes = []
        content = text[:match.start()].strip()
    else:
        content = text.strip()
    return content, boxes

def filter_boxes_auto(boxes):
    # Lấy 2 box có diện tích lớn nhất (auto lọc box hình)
    box_areas = [
        ((b["right"]-b["left"])*(b["bottom"]-b["top"]), idx) for idx, b in enumerate(boxes)
        if all(k in b for k in ("left","top","right","bottom"))
    ]
    box_areas = sorted(box_areas, reverse=True)
    top_idx = [idx for area, idx in box_areas[:2]]
    return [boxes[idx] for idx in top_idx]

def crop_images(pil_img, boxes):
    crops = []
    for i, box in enumerate(boxes):
        left, top, right, bottom = int(box['left']), int(box['top']), int(box['right']), int(box['bottom'])
        crop = pil_img.crop((left, top, right, bottom))
        crops.append((f"image_{i+1}.png", crop))
    return crops

def insert_images_latex(content, crops):
    for idx, (fname, _) in enumerate(crops, 1):
        img_latex = f"\\begin{{center}}\\includegraphics[width=0.5\\textwidth]{{{fname}}}\\end{{center}}"
        content = content.replace(f"{{image_{idx}}}", img_latex)
    return content

st.set_page_config(page_title="Chuyển đề Toán thành LaTeX + Hình tự động", layout="wide")
st.title("Chuyển đề Toán (PDF/Ảnh) thành LaTeX kèm hình minh hoạ (TỰ ĐỘNG GPT-4o)")

api_key = st.text_input("Nhập API Key GPT-4o:", type="password")
uploaded_file = st.file_uploader("Tải lên file PDF hoặc ảnh", type=['pdf', 'jpg', 'png'])

if uploaded_file and api_key:
    try:
        client = openai.OpenAI(api_key=api_key, base_url="https://api.sv2.llm.ai.vn/v1")
        images = []
        if uploaded_file.type == "application/pdf":
            with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("png")
                    images.append(Image.open(io.BytesIO(img_bytes)))
        else:
            images = [Image.open(uploaded_file)]

        st.info(f"Phát hiện {len(images)} trang để xử lý.")

        img = images[0]
        st.image(img, caption="Trang PDF gốc")

        prompt = get_prompt("latex")
        with st.spinner("Đang nhận diện GPT-4o..."):
            gpt_output = ask_gpt4o_with_image(img, prompt, client)
        content, boxes = parse_gpt_output(gpt_output)
        st.subheader("Văn bản nhận diện (LaTeX):")
        st.code(content, language="latex")

        # --- Lọc tự động 2 box lớn nhất ---
        filtered_boxes = filter_boxes_auto(boxes)
        if len(filtered_boxes) < 2:
            st.warning("Chỉ phát hiện được <2 hình. Nếu crop chưa đúng, bạn có thể thử lại hoặc kiểm tra prompt/ảnh đầu vào.")
        crops = crop_images(img, filtered_boxes)
        st.success(f"Auto crop thành công {len(crops)} hình minh hoạ!")

        # Ghép nội dung với ảnh
        full_text = insert_images_latex(content, crops)

        tab1, tab2 = st.tabs(["Nội dung LaTeX", "Ảnh minh hoạ"])
        with tab1:
            st.subheader("Kết quả LaTeX toàn bộ file:")
            st.code(full_text, language="latex")
            st.download_button("Tải về LaTeX", full_text, file_name="ketqua.tex")
        with tab2:
            st.write(f"Đã crop {len(crops)} hình minh hoạ:")
            for fname, crop in crops:
                st.image(crop, caption=fname)
                img_io = io.BytesIO()
                crop.save(img_io, format='PNG')
                st.download_button(f"Tải {fname}", img_io.getvalue(), file_name=fname)

    except Exception as e:
        st.error(f"Lỗi kết nối hoặc xử lý: {e}")

elif uploaded_file and not api_key:
    st.warning("Vui lòng nhập API Key trước khi xử lý.")
elif not uploaded_file:
    st.info("Hãy tải lên file PDF hoặc ảnh đề toán để bắt đầu.")

with st.expander("Hướng dẫn", expanded=False):
    st.markdown("""
**Cách hoạt động:**
- AI sẽ tự động nhận diện và trả về bounding box cho hình minh hoạ/biểu đồ trong trang.
- Code chỉ giữ lại 2 box có diện tích lớn nhất (gần như chắc chắn là 2 hình bạn cần).
- Bạn không cần nhập tọa độ thủ công.

**Nếu hình vẫn crop chưa đúng:**  
- Tối ưu lại prompt cho AI rõ hơn, hoặc crop tay theo hướng dẫn các trả lời phía trên.
    """)
