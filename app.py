import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import requests
import io
import base64
import os
from ultralytics import YOLO

# --- Load YOLO model (lần đầu hơi lâu, lần sau cực nhanh)
@st.cache_resource
def load_model():
    return YOLO("yolov8x.pt")  # Model lớn nhất, chuẩn nhất

model = load_model()

# --- Hàm tách bounding box bằng YOLO
def detect_objects(img_pil):
    results = model(img_pil)
    bboxes = []
    for box in results[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        label = results[0].names[int(box.cls[0])] if hasattr(results[0], "names") else "object"
        bboxes.append({
            "x": int(x1), "y": int(y1),
            "width": int(x2 - x1), "height": int(y2 - y1),
            "label": label
        })
    return bboxes

# --- Hàm cắt các ảnh minh hoạ (bounding box)
def extract_cropped_images(img_pil, regions):
    w_img, h_img = img_pil.size
    crops = []
    for idx, region in enumerate(regions):
        x = max(0, min(region["x"], w_img - 1))
        y = max(0, min(region["y"], h_img - 1))
        w = max(1, min(region["width"], w_img - x))
        h = max(1, min(region["height"], h_img - y))
        crop = img_pil.crop((x, y, x + w, y + h))
        crops.append({"label": region.get("label", f"minh_hoa_{idx+1}"), "image": crop})
    return crops

# --- Gửi GPT-4o nhận diện văn bản, công thức, LaTeX/Word
def call_gpt4o(image, mode, api_key):
    PROMPT_LATEX = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
1. Với câu hỏi trắc nghiệm không lời giải (bắt đầu bằng 'Câu X:' hoặc 'Câu X.'):
   - Thay 'Câu X:' bằng \\begin{ex}
   - Thêm \\choice trước phương án A
   - Đặt mỗi phương án trong cặp {}, ví dụ A. $x^2+2x+1.$ sẽ thành {$x^2+2x+1$}, bỏ phần A., B., C., D. và dấu . cuối phương án
   - Kết thúc bằng \\end{ex}
2. Với câu hỏi trắc nghiệm có lời giải:
   - Thêm \\True trước phương án đúng
   - Đặt lời giải trong \\loigiai{}
3. Với bài tập tự luận (bắt đầu bằng 'Bài X:' hoặc 'Bài X.'):
   - Thay 'Bài X:' bằng \\begin{bt}
   - Đặt lời giải trong \\loigiai{}
   - Kết thúc bằng \\end{bt}
4. Với danh sách (a), b), c)...):
   - Bọc trong \\begin{enumerate} và \\end{enumerate}
   - Thay mỗi chữ cái bằng \\item
5. Công thức toán học: Giữ nguyên định dạng LaTeX như $...$ hoặc $$...$$
KHÔNG thêm giải thích hay bình luận gì thêm. Trả về văn bản đã được định dạng LaTeX."""
    PROMPT_WORD = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh
2. Giữ nguyên cấu trúc đoạn văn và xuống dòng
3. Với công thức toán học: gõ lại chính xác, tất cả công thức Toán dưới dạng \${...}\$
4. Với bảng biểu: dùng markdown nếu có thể
5. Dạng bài:
   - Trắc nghiệm:
     Câu X: Nội dung
     A. Đáp án A
     B. Đáp án B
     C. Đáp án C
     D. Đáp án D
   - Đúng/Sai: a), b), c)...
   - Tự luận: Câu X: ... (Lời giải...)
KHÔNG giải thích. KHÔNG bịa thêm. Trả về văn bản gốc."""
    prompt = PROMPT_LATEX if mode == "latex" else PROMPT_WORD
    try:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        image_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        payload = {
            "model": "openai:gpt-4o",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                ]
            }],
            "temperature": 0.3
        }
        headers = {"Authorization": f"Bearer {api_key}"}
        API_URL = "https://api.sv2.llm.ai.vn/v1/chat/completions"
        r = requests.post(API_URL, json=payload, headers=headers, timeout=120)
        data = r.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        else:
            return f"Lỗi GPT-4o: {data.get('error', data)}"
    except Exception as e:
        return f"Lỗi gọi GPT-4o: {e}"

# --- Streamlit UI
st.title("📄 Chuyển PDF sang LaTeX/Word + Tách ảnh minh hoạ CHUẨN (YOLOv8)")
st.markdown("- **Không cần API Gemini, YOLO nhận diện chuẩn mọi hình học, bảng, biểu đồ, ...**\n"
            "- **Text/công thức vẫn dùng GPT-4o AI.VN**")

api_key = st.text_input("🔑 Nhập AI.VN API Key (GPT-4o)", type="password")
uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"])
mode = st.radio("Chế độ xuất", ["latex", "word"], horizontal=True)

if uploaded_file and api_key:
    st.info("👉 Chỉ xử lý 1 trang đầu để demo.")
    if st.button("🚀 Chuyển đổi"):
        with st.spinner("Đang xử lý..."):
            pdf_bytes = uploaded_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(dpi=150)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            # 1. Nhận diện text/công thức
            gpt_result = call_gpt4o(img, mode, api_key)
            # 2. Tách ảnh minh hoạ CHUẨN bằng YOLO
            regions = detect_objects(img)
            crops = extract_cropped_images(img, regions)

        st.markdown("## Kết quả")
        st.code(gpt_result, language="latex" if mode == "latex" else "markdown")
        if len(crops) == 0:
            st.warning("Không tìm thấy vùng ảnh minh hoạ nào!")
        else:
            for crop in crops:
                st.image(crop['image'], caption=crop['label'], use_container_width=True)
        st.success("✅ Đã xử lý xong!")

