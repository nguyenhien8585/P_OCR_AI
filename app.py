import streamlit as st
from PIL import Image
import fitz
import io
import os
import base64
import requests
from docx import Document

# === Config ===
st.set_page_config(page_title="PDF/Ảnh ➔ Word/LaTeX (Gemini + Mistral)", layout="wide")
st.title("📄 Chuyển PDF/Ảnh sang Word hoặc LaTeX (auto cắt hình minh họa bằng Gemini, định dạng Mistral)")

# === API Keys ===
gemini_api_key = st.sidebar.text_input("Gemini API Key (Google Cloud)", type="password")
mistral_api_key = st.sidebar.text_input("Mistral AI Key", type="password")

# === PROMPT GEN ===
def getPrompt(mode):
    if mode == "latex":
        return """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này và áp dụng các quy tắc định dạng LaTeX sau:
QUY TẮC ĐỊNH DẠNG VĂN BẢN VÀ CÔNG THỨC:
1. Với câu hỏi trắc nghiệm không lời giải (bắt đầu bằng 'Câu X:' hoặc 'Câu X.'): 
   - Thay 'Câu X:' bằng \begin{ex}
   - Thêm \choice trước phương án A
   - Đặt mỗi phương án trong cặp dấy {}, ví dụ A. $x^2+2x+1.$ sẽ thành {$x^2+2x+1$}, bỏ phần A., B., C., D. và dấu . cuối phương án
   - Kết thúc bằng \end{ex}
2. Với câu hỏi trắc nghiệm có lời giải:
   - Thêm \True trước phương án đúng
   - Đặt lời giải trong \loigiai{}
3. Với bài tập tự luận (bắt đầu bằng 'Bài X:' hoặc 'Bài X.'):
   - Thay 'Bài X:' bằng \begin{bt}
   - Đặt lời giải trong \loigiai{}
   - Kết thúc bằng \end{bt}
4. Với danh sách (a), b), c)...):
   - Bọc trong \begin{enumerate} và \end{enumerate}
   - Thay mỗi chữ cái bằng \item
5. Công thức toán học: Giữ nguyên định dạng LaTeX như $...$ hoặc $$...$$
KHÔNG thêm giải thích hay bình luận gì thêm. Trả về văn bản đã được định dạng LaTeX."""
    else:
        return """Gõ lại CHÍNH XÁC toàn bộ nội dung văn bản có trong ảnh này.
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh
2. Giữ nguyên cấu trúc đoạn văn và xuống dòng
3. Với công thức toán học: gõ lại chính xác, tất cả công thức Toán dưới dạng \${...}\$
   - Inline: \${x^2 + 2x + 1}\$
   - Hệ: \$\begin{cases} ... \end{cases}\$
   - Ký hiệu: các từ đặt tên cho tên bằng chữ A,B,C... hoặc các cụm từ AB, CD, Oxyz,... hoặc các số 1,2,3,..., tỉ lệ phần trăm 1%,0.1% , 0,1%,.... ví dụ \${Oxyz}\$, \${A}\$, \${AB}\$, \${0{,}1\%}\$, \${CD}\$, \${1}\$,\${Oxyz}\$, \${S.ABCD}\$.....
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
✅ Gợi ý thêm:
- Nếu ảnh dài hoặc nhiều trang, chia nhỏ xử lý từng ảnh để tránh thiếu trang.
- Khi lưu kết quả, nên xuất file Word định dạng .docx để hiển thị tiếng Việt chuẩn và hỗ trợ tốt Unicode.
KHÔNG giải thích. KHÔNG bịa thêm. Trả về văn bản gốc."""

# === PDF sang ảnh ===
def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

# === Gemini crop tự động hình minh họa ===
def gemini_auto_crop(image, api_key):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    # Yêu cầu Gemini trả về tọa độ vùng hình minh họa
    prompt = "Hãy trả về duy nhất một danh sách các vùng hình minh họa (biểu đồ, hình vẽ, hình học, đồ thị) dưới dạng [(left,top,width,height),...]. Nếu không có thì trả về []."
    data = {
        "contents": [{
            "parts": [
                {"inlineData": {"mimeType": "image/png", "data": img_b64}},
                {"text": prompt}
            ]
        }]
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(api_url, headers=headers, json=data)
    result = resp.json()
    st.write("DEBUG Gemini crop:", result)
    if "candidates" in result and result["candidates"]:
        answer = result["candidates"][0]["content"]["parts"][0]["text"]
        try:
            # Parse list vùng crop trả về dạng Python list
            return eval(answer)
        except:
            return []
    else:
        return []

# === Gọi Mistral AI ===
def mistral_ocr(image, mistral_api_key, mode="latex"):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    prompt = getPrompt(mode)
    full_prompt = f"{prompt}\nĐây là ảnh base64:\n{img_b64}\n"
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {mistral_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": full_prompt}]
    }
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    st.write("DEBUG Mistral:", data)
    if 'choices' in data and data['choices']:
        return data['choices'][0]['message']['content']
    elif 'error' in data:
        return f"[Lỗi Mistral: {data['error']}]"
    else:
        return f"[Lỗi Mistral: Không có dữ liệu trả về | {data}]"

# === Lưu Word với hình ===
def save_word(doc_text, images, output_path="output_word.docx"):
    doc = Document()
    doc.add_paragraph(doc_text)
    for img in images:
        img_stream = io.BytesIO()
        img.save(img_stream, format="PNG")
        img_stream.seek(0)
        doc.add_picture(img_stream, width=docx.shared.Inches(4))
    doc.save(output_path)

# === GIAO DIỆN ===

uploaded = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
mode = st.radio("Chọn chế độ xuất", ["latex", "word"])
st.info("Gemini sẽ tự động cắt ảnh minh họa (auto), Mistral sẽ OCR từng trang/ảnh và chuyển sang LaTeX hoặc Word đúng format prompt.")

if uploaded and gemini_api_key and mistral_api_key:
    # Tách ảnh
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

        # 1. Cắt hình minh họa tự động bằng Gemini
        if st.button(f"Gemini crop tự động hình minh họa trang {idx+1}", key=f"autocrop{idx}"):
            with st.spinner("Gemini đang phân tích vùng hình minh họa..."):
                crop_boxes = gemini_auto_crop(img, gemini_api_key)
                st.write(f"Gemini trả về vùng crop: {crop_boxes}")
                cropped_imgs = []
                for j, box in enumerate(crop_boxes):
                    try:
                        left, top, width, height = box
                        cropped_img = img.crop((left, top, left + width, top + height))
                        st.image(cropped_img, caption=f"Hình minh họa {j+1} trang {idx+1}", use_column_width=True)
                        cropped_imgs.append(cropped_img)
                    except Exception as e:
                        st.warning(f"Lỗi crop: {e}")
                all_cropped_imgs.extend(cropped_imgs)
                st.session_state[f"cropped_imgs_{idx}"] = cropped_imgs
        else:
            # Cho phép crop lại hoặc bỏ qua
            cropped_imgs = st.session_state.get(f"cropped_imgs_{idx}", [])
            for j, cropped_img in enumerate(cropped_imgs):
                st.image(cropped_img, caption=f"Hình minh họa {j+1} trang {idx+1}", use_column_width=True)

        # 2. Gửi trang ảnh này sang Mistral để nhận kết quả OCR định dạng
        if st.button(f"Chuyển ảnh trang {idx+1} sang {'LaTeX' if mode=='latex' else 'Word'} với Mistral", key=f"ocr{idx}"):
            with st.spinner("Mistral AI đang xử lý..."):
                result = mistral_ocr(img, mistral_api_key, mode)
                st.code(result, language="latex" if mode=="latex" else "markdown")
                all_results.append(result)
                st.session_state[f"ocr_{idx}"] = result
        else:
            old_result = st.session_state.get(f"ocr_{idx}")
            if old_result:
                st.code(old_result, language="latex" if mode=="latex" else "markdown")
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
        # Tải từng hình minh họa
        for idx, img in enumerate(all_cropped_imgs):
            img_path = f"img_{idx+1}.png"
            img.save(img_path)
            with open(img_path, "rb") as f:
                st.download_button(f"Tải hình {img_path}", f, img_path)
