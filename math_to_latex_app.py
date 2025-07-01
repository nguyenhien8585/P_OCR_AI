import streamlit as st
import openai
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import re
import json

# --- PROMPT ---
def get_prompt(mode):
    if mode == "latex":
        return """
Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
1. Gõ lại TẤT CẢ văn bản, thứ tự, định dạng, cấu trúc dòng giống ảnh.
2. KHÔNG thêm giải thích, KHÔNG tự bịa nội dung mới.
3. Công thức Toán dưới dạng $...$, hệ: $\\begin{cases}...\\end{cases}$.
4. Khi gặp hình minh hoạ/biểu đồ, thay vào văn bản bằng {image_n}, với n là số thứ tự xuất hiện hình trong trang.
5. Sau phần văn bản, hãy trả về một dòng duy nhất:
BoundingBox: [{"left":x1,"top":y1,"right":x2,"bottom":y2},...]
Chỉ trả về BoundingBox nếu trong ảnh có hình minh hoạ/biểu đồ.
"""
    else:
        return """
Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này. Giữ nguyên cấu trúc dòng, định dạng. Công thức toán học để dạng $...$. 
Khi gặp hình minh hoạ/biểu đồ, thay bằng {image_n} (n là thứ tự hình).
Sau phần văn bản, hãy trả về một dòng duy nhất:
BoundingBox: [{"left":x1,"top":y1,"right":x2,"bottom":y2},...]
"""

# --- Hàm convert PIL Image sang base64 ---
def img_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- Gửi GPT-4o ---
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
        model="gpt-4o",
        messages=messages,
        max_tokens=4096,
        temperature=0.1
    )
    return response.choices[0].message.content

# --- Tách content và bounding box từ trả về GPT-4o ---
def parse_gpt_output(text):
    # Tìm dòng BoundingBox
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

# --- Crop hình minh hoạ theo box ---
def crop_images(pil_img, boxes):
    crops = []
    for i, box in enumerate(boxes):
        # Bắt lỗi box không đủ 4 keys
        if not all(k in box for k in ("left","top","right","bottom")): continue
        left, top, right, bottom = int(box['left']), int(box['top']), int(box['right']), int(box['bottom'])
        crop = pil_img.crop((left, top, right, bottom))
        crops.append((f"image_{i+1}.png", crop))
    return crops

# --- Thay {image_n} bằng lệnh LaTeX chèn ảnh ---
def insert_images_latex(content, crops):
    for idx, (fname, _) in enumerate(crops, 1):
        img_latex = f"\\begin{{center}}\\includegraphics[width=0.5\\textwidth]{{{fname}}}\\end{{center}}"
        content = content.replace(f"{{image_{idx}}}", img_latex)
    return content

# --- App giao diện Streamlit ---
st.set_page_config(page_title="Chuyển đề Toán thành LaTeX/Word + Hình", layout="wide")
st.title("Chuyển đề Toán (PDF/Ảnh) thành LaTeX/Word kèm hình minh hoạ (GPT-4o)")

api_key = st.text_input("Nhập API Key GPT-4o (https://api.sv2.llm.ai.vn/v1):", type="password")
mode = st.radio("Chọn định dạng xuất:", ["LaTeX"])
uploaded_file = st.file_uploader("Tải lên file PDF hoặc ảnh", type=['pdf', 'jpg', 'png'])

if uploaded_file and api_key:
    # --- Kết nối API ---
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

        full_text = ""
        all_crops = []
        error_pages = []
        with st.spinner("Đang nhận diện từng trang..."):
            for idx, img in enumerate(images):
                st.image(img, caption=f"Trang {idx+1}")
                prompt = get_prompt("latex")
                try:
                    gpt_output = ask_gpt4o_with_image(img, prompt, client)
                except Exception as e:
                    st.error(f"Lỗi gửi API trang {idx+1}: {e}")
                    error_pages.append(idx+1)
                    continue
                content, boxes = parse_gpt_output(gpt_output)
                st.markdown(f"**Văn bản trang {idx+1}:**")
                st.code(content, language="latex")
                # Crop hình minh hoạ
                crops = crop_images(img, boxes)
                for fname, crop in crops:
                    all_crops.append((f"page{idx+1}_{fname}", crop))  # Đánh số ảnh cho rõ
                # Ghép văn bản
                full_text += f"\n\n%--- Trang {idx+1} ---\n\n" + content

        # Thay {image_n} bằng lệnh LaTeX
        if mode == "LaTeX":
            full_text = insert_images_latex(full_text, all_crops)

        # Tabs kết quả và hình
        tab1, tab2 = st.tabs(["Nội dung LaTeX", "Ảnh minh hoạ"])
        with tab1:
            st.subheader("Kết quả LaTeX toàn bộ file:")
            st.code(full_text, language="latex")
            st.download_button("Tải về LaTeX", full_text, file_name="ketqua.tex")

        with tab2:
            st.write(f"Đã crop {len(all_crops)} hình:")
            for fname, crop in all_crops:
                st.image(crop, caption=fname)
                img_io = io.BytesIO()
                crop.save(img_io, format='PNG')
                st.download_button(f"Tải {fname}", img_io.getvalue(), file_name=fname)

        if error_pages:
            st.warning(f"Lỗi xử lý các trang: {', '.join(str(i) for i in error_pages)} (thử lại, hoặc kiểm tra API Key và kết nối mạng)")

    except Exception as e:
        st.error(f"Lỗi kết nối hoặc xử lý: {e}")

elif uploaded_file and not api_key:
    st.warning("Vui lòng nhập API Key trước khi xử lý.")
elif not uploaded_file:
    st.info("Hãy tải lên file PDF hoặc ảnh đề toán để bắt đầu.")

# ------- Hướng dẫn sử dụng -------
with st.expander("Hướng dẫn sử dụng chi tiết", expanded=False):
    st.markdown("""
**Bước 1:** Đăng ký lấy API key tại https://api.sv2.llm.ai.vn  
**Bước 2:** Dán API key vào ô trên.  
**Bước 3:** Tải lên file PDF đề toán hoặc ảnh chụp.  
**Bước 4:** Đợi xử lý từng trang, kết quả LaTeX + hình sẽ hiển thị và có nút tải về.  
**Bước 5:** Dùng file LaTeX và hình cho soạn đề, import vào Word hoặc Overleaf.

- Nếu file lớn hoặc nhiều trang, có thể xử lý từng ảnh/trang riêng lẻ.
- Nếu gặp lỗi về box ảnh (bounding box), thử lại hoặc sửa prompt cho rõ hơn.
- Bạn có thể chỉnh sửa hoặc dịch prompt cho phù hợp với đề các môn khác.
    """)
