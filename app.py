import streamlit as st
from streamlit_cropper import st_cropper
from PIL import Image
import fitz
import io
import os
import base64
import requests
from docx import Document

st.set_page_config(page_title="Crop & OCR PDF/Ảnh sang LaTeX/Word (GPT-4o AI.VN)", layout="wide")
st.title("📄 Crop ảnh, OCR và chuyển sang LaTeX/Word (GPT-4o, AI.VN)")

api_key = st.sidebar.text_input("AI.VN API Key (GPT-4o)", type="password")
api_url = "https://api.sv2.llm.ai.vn/v1/chat/completions"

def getPrompt(mode):
    if mode == "latex":
        return """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
QUY TẮC ĐỊNH DẠNG VĂN BẢN VÀ CÔNG THỨC:
1. Với câu hỏi trắc nghiệm không lời giải (bắt đầu bằng 'Câu X:' hoặc 'Câu X.'): 
   - Thay 'Câu X:' bằng \\begin{ex}
   - Thêm \\choice trước phương án A
   - Đặt mỗi phương án trong cặp dấy {}, ví dụ A. $x^2+2x+1.$ sẽ thành {$x^2+2x+1$}, bỏ phần A., B., C., D. và dấu . cuối phương án
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
    else:
        return """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh
2. Giữ nguyên cấu trúc đoạn văn và xuống dòng
3. Với công thức toán học: gõ lại chính xác, tất cả công thức Toán dưới dạng \\${...}\\$
   - Inline: \\${x^2 + 2x + 1}\\$
   - Hệ: \\$\\begin{cases} ... \\end{cases}\\$
   - Ký hiệu: các từ đặt tên cho tên bằng chữ A,B,C... hoặc các cụm từ AB, CD, Oxyz,... hoặc các số 1,2,3,..., tỉ lệ phần trăm 1%,0.1% , 0,1%,.... ví dụ \\${Oxyz}\\$, \\${A}\\$, \\${AB}\\$, \\${0{,}1\\%}\\$, \\${CD}\\$, \\${1}\\$,...
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

def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

def gpt4o_ocr_format(image, api_key, mode="latex"):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    prompt = getPrompt(mode)
    payload = {
        "model": "openai:gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]
            }
        ],
        "max_tokens": 2048,
        "temperature": 0.0
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=180)
        data = resp.json()
        st.write("DEBUG GPT-4o:", data)
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            return f"[Lỗi GPT-4o: {data['error'].get('message', str(data['error']))}]"
        else:
            return f"[Lỗi GPT-4o: Không có dữ liệu trả về | {data}]"
    except Exception as e:
        return f"[Lỗi gọi GPT-4o: {e}]"

def save_word(doc_text, images, output_path="output_word.docx"):
    doc = Document()
    doc.add_paragraph(doc_text)
    for img in images:
        img_stream = io.BytesIO()
        img.save(img_stream, format="PNG")
        img_stream.seek(0)
        doc.add_picture(img_stream, width=docx.shared.Inches(4))
    doc.save(output_path)

uploaded = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
mode = st.radio("Chọn chế độ xuất", ["latex", "word"])
st.info("Cắt vùng hình minh họa bằng chuột, OCR bằng GPT-4o AI.VN, định dạng LaTeX hoặc Word.")

if uploaded and api_key:
    if uploaded.name.lower().endswith(".pdf"):
        images = pdf_to_images(uploaded.read())
        st.success(f"Đã tách {len(images)} trang từ PDF.")
    else:
        images = [Image.open(uploaded)]
        st.success("Đã tải lên 1 ảnh.")

    all_results = []
    all_cropped_imgs = []
    for idx, img in enumerate(images):
        st.markdown(f"---\n### Trang {idx+1}")
        st.image(img, caption=f"Trang {idx+1}", use_container_width=True)
        st.write("**Crop vùng hình minh họa thủ công bằng chuột nếu muốn**")

        # --- Sử dụng streamlit-cropper cho từng trang ---
        box = st_cropper(
            img,
            box_color='#00FF00',
            aspect_ratio=None,
            key=f"cropper_{idx}",
            return_type='box'
        )

        cropped = img
        if box:
            if isinstance(box, dict):
                left = box.get("left", 0)
                top = box.get("top", 0)
                width = box.get("width", img.width)
                height = box.get("height", img.height)
            elif isinstance(box, (tuple, list)):
                left, top, width, height = box
            else:
                left, top, width, height = 0, 0, img.width, img.height
            if width > 10 and height > 10:
                cropped = img.crop((left, top, left + width, top + height))
            st.image(cropped, caption=f"Hình đã crop Trang {idx+1}", use_container_width=True)
        all_cropped_imgs.append(cropped)

        # Lưu vào biến cục bộ, không dùng session_state!
        if st.button(f"OCR + Định dạng trang {idx+1} (GPT-4o)", key=f"ocr_{idx}"):
            with st.spinner("GPT-4o AI.VN đang xử lý..."):
                result = gpt4o_ocr_format(cropped, api_key, mode)
                st.code(result, language="latex" if mode == "latex" else "markdown")
                all_results.append(result)
        # Không còn truy cập session_state để lấy lại kết quả cũ nữa!

    # Kết hợp và xuất file cuối cùng
    if all_results and st.button(f"Tải về {'LaTeX' if mode=='latex' else 'Word'} hoàn chỉnh"):
        full_text = "\n\n".join(all_results)
        if mode == "word":
            save_word(full_text, all_cropped_imgs, "output_word.docx")
            with open("output_word.docx", "rb") as f:
                st.download_button("Tải file Word", f, "output_word.docx")
        else:
            latex_file = "output_latex.tex"
            with open(latex_file, "w", encoding="utf-8") as f:
                f.write(full_text)
            with open(latex_file, "rb") as f:
                st.download_button("Tải file LaTeX", f, latex_file)
        # Tải từng hình minh họa đã crop
        for idx, img in enumerate(all_cropped_imgs):
            img_path = f"img_{idx+1}.png"
            img.save(img_path)
            with open(img_path, "rb") as f:
                st.download_button(f"Tải hình {img_path}", f, img_path)
