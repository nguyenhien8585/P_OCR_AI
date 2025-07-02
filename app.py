import streamlit as st
from PIL import Image
import fitz
import io
import os
import base64
import requests
import cv2
from ultralytics import YOLO
from docx import Document
import numpy as np

st.set_page_config(page_title="PDF/Ảnh ➔ Auto-crop minh họa ➔ LaTeX/Word (YOLO + GPT-4o)", layout="wide")
st.title("📄 Auto-crop minh họa, OCR và chuyển sang LaTeX/Word (YOLOv8 + GPT-4o AI.VN)")

api_key = st.sidebar.text_input("AI.VN API Key (GPT-4o)", type="password")
api_url = "https://api.sv2.llm.ai.vn/v1/chat/completions"

# --- YOLOv8 model ---
@st.cache_resource
def load_yolo():
    return YOLO("yolov8n.pt")
yolo_model = load_yolo()

def getPrompt(mode, n_img=0):
    if mode == "latex":
        prompt = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
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
5. Công thức toán học: Giữ nguyên định dạng LaTeX như $...$ hoặc $$...$$"""
    else:
        prompt = """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.
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
   - Tự luận: Câu X: ... (Lời giải...)"""
    if n_img > 0:
        img_str = ", ".join([f"img_{i+1}.png" for i in range(n_img)])
        prompt += f"\nTrong văn bản, hãy CHÈN ký hiệu <<IMG_1>>, <<IMG_2>>, ... vào vị trí phù hợp với các hình minh họa ({img_str}) theo đúng nội dung/câu hỏi."
    prompt += "\nKHÔNG thêm giải thích hay bình luận gì thêm. Chỉ trả về văn bản đã được định dạng."
    return prompt

def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

def yolo_auto_crop(image: Image.Image, conf=0.35):
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    results = yolo_model(img_cv, conf=conf)
    crops = []
    for i, box in enumerate(results[0].boxes.xyxy):
        x1, y1, x2, y2 = map(int, box)
        crop = img_cv[y1:y2, x1:x2]
        pil_crop = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        crops.append(pil_crop)
    return crops

def gpt4o_ocr_format(image, api_key, mode="latex", n_img=0):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    prompt = getPrompt(mode, n_img=n_img)
    payload = {
        "model": "gpt-4o",
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

def insert_images_latex(latex_text, images):
    for idx, _ in enumerate(images):
        tag = f"<<IMG_{idx+1}>>"
        fig_str = f"""
\\begin{{figure}}[h]
\\centering
\\includegraphics[width=0.7\\linewidth]{{img_{idx+1}.png}}
\\end{{figure}}
"""
        latex_text = latex_text.replace(tag, fig_str)
    return latex_text

def insert_images_word(doc_text, images, output_path="output_word.docx"):
    doc = Document()
    paragraphs = doc_text.split("\n")
    img_idx = 0
    for para in paragraphs:
        # Tìm và thay <<IMG_n>> trong từng đoạn
        while f"<<IMG_{img_idx+1}>>" in para and img_idx < len(images):
            para = para.replace(f"<<IMG_{img_idx+1}>>", "")
            img_stream = io.BytesIO()
            images[img_idx].save(img_stream, format="PNG")
            img_stream.seek(0)
            doc.add_picture(img_stream, width=docx.shared.Inches(4))
            img_idx += 1
        doc.add_paragraph(para)
    doc.save(output_path)

uploaded = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
mode = st.radio("Chọn chế độ xuất", ["latex", "word"])
st.info("PDF/Ảnh sẽ được tách trang, YOLO tự động cắt từng hình minh họa, GPT-4o OCR văn bản, tự động chèn ảnh đúng vị trí câu hỏi.")

if uploaded and api_key:
    if uploaded.name.lower().endswith(".pdf"):
        images = pdf_to_images(uploaded.read())
        st.success(f"Đã tách {len(images)} trang từ PDF.")
    else:
        images = [Image.open(uploaded)]
        st.success("Đã tải lên 1 ảnh.")

    all_ocr_results = []
    all_auto_crops = []

    for idx, img in enumerate(images):
        st.markdown(f"---\n### Trang {idx+1}")
        st.image(img, caption=f"Trang {idx+1}", use_container_width=True)

        with st.spinner("YOLOv8 đang tự động nhận diện và crop các hình minh họa..."):
            crops = yolo_auto_crop(img)
        st.write(f"Đã tự động crop {len(crops)} hình minh họa trang {idx+1}")
        for i, crop in enumerate(crops):
            st.image(crop, caption=f"Minh họa {i+1} - Trang {idx+1}", use_container_width=True)
        all_auto_crops += crops

        if st.button(f"OCR toàn bộ trang {idx+1} bằng GPT-4o", key=f"ocr_{idx}"):
            with st.spinner("GPT-4o AI.VN đang nhận diện nội dung..."):
                result = gpt4o_ocr_format(img, api_key, mode=mode, n_img=len(crops))
                st.code(result, language="latex" if mode == "latex" else "markdown")
                all_ocr_results.append(result)

    # Ghép file cuối cùng, chèn ảnh đúng vị trí
    if all_ocr_results and st.button(f"Tải về {'LaTeX' if mode=='latex' else 'Word'} hoàn chỉnh"):
        full_text = "\n\n".join(all_ocr_results)
        if mode == "word":
            insert_images_word(full_text, all_auto_crops, "output_word.docx")
            with open("output_word.docx", "rb") as f:
                st.download_button("Tải file Word", f, "output_word.docx")
        else:
            latex_full = insert_images_latex(full_text, all_auto_crops)
            with open("output_latex.tex", "w", encoding="utf-8") as f:
                f.write(latex_full)
            with open("output_latex.tex", "rb") as f:
                st.download_button("Tải file LaTeX", f, "output_latex.tex")
        # Tải từng hình minh họa đã crop
        for i, img in enumerate(all_auto_crops):
            img_path = f"img_{i+1}.png"
            img.save(img_path)
            with open(img_path, "rb") as f:
                st.download_button(f"Tải hình {img_path}", f, img_path)
