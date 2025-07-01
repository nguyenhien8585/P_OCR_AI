import streamlit as st
import fitz
from PIL import Image
import io, os, base64
import requests
from docx import Document

st.set_page_config(page_title="PDF/Ảnh sang LaTeX/Word (ChatGPT-4o AI.VN)", layout="wide")
st.title("🪄 Chuyển PDF/Ảnh sang LaTeX hoặc Word bằng ChatGPT-4o (AI.VN)")

api_key = st.sidebar.text_input("AI.VN API Key (GPT-4o)", type="password")
api_url = "https://api.sv2.llm.ai.vn/v1/chat/completions"  # endpoint AI.VN cho GPT-4o

# ---- Prompt Generator ----
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

# ---- PDF sang ảnh ----
def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

# ---- Gửi ảnh sang GPT-4o để OCR + định dạng ----
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

# ---- Lưu Word với hình ----
def save_word(doc_text, images, output_path="output_word.docx"):
    doc = Document()
    doc.add_paragraph(doc_text)
    for img in images:
        img_stream = io.BytesIO()
        img.save(img_stream, format="PNG")
        img_stream.seek(0)
        doc.add_picture(img_stream, width=docx.shared.Inches(4))
    doc.save(output_path)

# ---- GIAO DIỆN ----
uploaded = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
mode = st.radio("Chọn chế độ xuất", ["latex", "word"])
st.info("Sử dụng GPT-4o (AI.VN) để nhận diện nội dung và định dạng LaTeX/Word. Hỗ trợ crop ảnh thủ công.")

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
        st.image(img, caption=f"Trang {idx+1}", use_column_width=True)
        st.write("Cắt vùng hình minh họa bằng chuột (nếu cần, không bắt buộc):")
        # ---- Crop bằng Pillow trực tiếp (nếu có nhu cầu) ----
        left = st.number_input(f"left_{idx}", 0, img.width, 0, 1)
        top = st.number_input(f"top_{idx}", 0, img.height, 0, 1)
        width = st.number_input(f"width_{idx}", 1, img.width, img.width, 1)
        height = st.number_input(f"height_{idx}", 1, img.height, img.height, 1)
        if st.button(f"Crop hình minh họa trang {idx+1}", key=f"crop{idx}"):
            cropped_img = img.crop((left, top, left + width, top + height))
            st.image(cropped_img, caption=f"Hình minh họa đã cắt Trang {idx+1}", use_column_width=True)
            all_cropped_imgs.append(cropped_img)
        else:
            all_cropped_imgs.append(img)  # Nếu không crop thì lấy nguyên ảnh

        if st.button(f"Nhận diện và định dạng trang {idx+1} bằng GPT-4o", key=f"ocr{idx}"):
            with st.spinner("GPT-4o đang xử lý..."):
                result = gpt4o_ocr_format(img, api_key, mode)
                st.code(result, language="latex" if mode == "latex" else "markdown")
                all_results.append(result)
                st.session_state[f"ocr_{idx}"] = result
        else:
            old_result = st.session_state.get(f"ocr_{idx}")
            if old_result:
                st.code(old_result, language="latex" if mode == "latex" else "markdown")
                all_results.append(old_result)

    # Kết hợp và xuất file cuối cùng
    if st.button(f"Tải về {'LaTeX' if mode=='latex' else 'Word'} hoàn chỉnh"):
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
