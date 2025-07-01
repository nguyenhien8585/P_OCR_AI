import streamlit as st
import fitz
from PIL import Image
import io, os, base64
import requests
from docx import Document
from streamlit_cropper import st_cropper

# === API Keys ===
st.set_page_config(page_title="Gemini Vision + Mistral AI", layout="wide")
st.title("🎯 Chuyển đề Toán PDF/Ảnh sang LaTeX hoặc Word, giữ hình minh họa")

gemini_api_key = st.sidebar.text_input("Gemini API Key (Google Cloud)", type="password")
mistral_api_key = st.sidebar.text_input("Mistral AI Key", type="password")

# ==== Hàm gọi Gemini Flash cho ảnh ====
def gemini_flash_vision(image, api_key, prompt="Mô tả hình vẽ/ảnh minh họa."):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
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
    st.write("🟦 Gemini API trả về:", result) # debug
    if "candidates" in result and result["candidates"]:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    elif "error" in result:
        return f"[Lỗi Gemini: {result['error'].get('message', str(result['error']))}]"
    else:
        return f"[Lỗi Gemini: Không có dữ liệu trả về | {result}]"

# ==== Hàm gọi Mistral AI để chuyển văn bản sang LaTeX/Word ====
def mistral_convert(prompt, mistral_api_key):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {mistral_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    st.write("🟦 Mistral API trả về:", data)  # debug
    if 'choices' in data and data['choices']:
        return data['choices'][0]['message']['content']
    elif 'error' in data:
        return f"[Lỗi Mistral: {data['error']}]"
    else:
        return f"[Lỗi Mistral: Không có dữ liệu trả về | {data}]"

# ==== PDF sang ảnh ====
def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

# ==== Lưu Word với hình ====
def save_word(doc_text, images, captions, outpath="output_word.docx"):
    doc = Document()
    doc.add_paragraph(doc_text)
    for idx, img in enumerate(images):
        img_stream = io.BytesIO()
        img.save(img_stream, format="PNG")
        img_stream.seek(0)
        doc.add_picture(img_stream, width=docx.shared.Inches(4))
        if captions and idx < len(captions):
            doc.add_paragraph(captions[idx], style='Caption')
    doc.save(outpath)

# ==== Tabs giao diện ====
tab1, tab2 = st.tabs(["Cắt ảnh minh họa (Gemini)", "Chuyển sang LaTeX/Word (Mistral)"])

# ---------- TAB 1: CẮT ẢNH MINH HỌA BẰNG GEMINI ----------
with tab1:
    st.subheader("1️⃣ Upload PDF hoặc Ảnh")
    uploaded = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
    images = []
    img_captions = []
    outdir = "output_imgs"
    os.makedirs(outdir, exist_ok=True)

    if uploaded:
        if uploaded.name.lower().endswith(".pdf"):
            images = pdf_to_images(uploaded.read())
        else:
            images = [Image.open(uploaded)]

        st.success(f"Đã chuyển thành {len(images)} trang ảnh.")

        crop_imgs = []
        img_captions = []
        st.info("Chọn, crop vùng hình minh họa bằng chuột với mỗi trang/ảnh. Sau đó gửi cho Gemini để mô tả/xác nhận.")

        for i, img in enumerate(images):
            st.markdown(f"---\n#### Trang {i+1}")
            st.image(img, caption=f"Trang {i+1}", use_column_width=True)
            box = st_cropper(img, box_color='#00FF00', aspect_ratio=None, key=f"cropper{i}")
            cropped = None
            left = top = width = height = None
            if box:
                if isinstance(box, dict):
                    left = box.get("left")
                    top = box.get("top")
                    width = box.get("width")
                    height = box.get("height")
                elif isinstance(box, (tuple, list)) and len(box) == 4:
                    left, top, width, height = box
                if None not in (left, top, width, height):
                    cropped = img.crop((left, top, left + width, top + height))
                    st.image(cropped, caption=f"Ảnh minh họa cắt (Trang {i+1})", use_column_width=True)
                    crop_imgs.append(cropped)
                    # Xác nhận/mô tả bằng Gemini
                    if gemini_api_key and st.button(f"Mô tả hình minh họa Trang {i+1} (Gemini)", key=f"desimg{i}"):
                        with st.spinner("Gemini đang phân tích..."):
                            caption = gemini_flash_vision(cropped, gemini_api_key, prompt="Mô tả chi tiết hình minh họa Toán học này (cho caption LaTeX hoặc tiếng Việt ngắn gọn).")
                            img_captions.append(caption)
                            st.write("**Caption Gemini:**", caption)
                else:
                    st.warning("Vui lòng crop đủ vùng ảnh!")
        # Lưu danh sách ảnh & caption cho tab sau
        st.session_state["crop_imgs"] = crop_imgs
        st.session_state["img_captions"] = img_captions

# ---------- TAB 2: CHUYỂN SANG LATEX/WORD (MISTRAL) ----------
with tab2:
    st.subheader("2️⃣ Chuyển sang LaTeX hoặc Word")
    crop_imgs = st.session_state.get("crop_imgs", [])
    img_captions = st.session_state.get("img_captions", [])
    st.markdown(f"Bạn đã crop **{len(crop_imgs)}** hình minh họa.")

    doc_type = st.radio("Chọn kiểu xuất", ["LaTeX", "Word"])
    text_input = st.text_area("Dán hoặc nhập toàn bộ đề (text, công thức toán, ...)", height=250)

    # Gợi ý prompt cho Mistral
    prompt = ""
    if doc_type == "LaTeX":
        img_latex = "\n".join([f"\\includegraphics{{img-{i+1}.png}}" for i in range(len(crop_imgs))])
        prompt = f"""
Chuyển toàn bộ văn bản đề Toán dưới đây thành LaTeX chuẩn, giữ nguyên công thức, bảng, biểu diễn Toán học.
Chèn hình minh họa vào đúng vị trí bằng lệnh \\includegraphics{{img-<index>.png}}, caption nếu có, lấy theo thứ tự: {img_latex}.
Đề toán:
{text_input}
"""
    else:
        prompt = f"""
Chuyển toàn bộ văn bản đề Toán dưới đây thành file Word chuẩn, giữ nguyên công thức, bảng.
Chèn hình minh họa vào đúng vị trí (theo thứ tự img-1.png, img-2.png...), caption nếu có, dựa trên chú thích đã phân tích trước đó (nếu có).
Đề toán:
{text_input}
"""

    mistral_ok = mistral_api_key and text_input
    if mistral_ok and st.button("Chuyển đổi bằng Mistral AI"):
        with st.spinner("Đang gửi tới Mistral AI..."):
            result = mistral_convert(prompt, mistral_api_key)
            st.markdown("**Kết quả chuyển đổi:**")
            st.code(result, language="latex" if doc_type=="LaTeX" else "markdown")

            # Cho phép tải về file kết quả (Word/LaTeX) và các ảnh
            if doc_type == "Word":
                save_word(result, crop_imgs, img_captions, "output_word.docx")
                with open("output_word.docx", "rb") as f:
                    st.download_button("Tải file Word", f, "output_word.docx")
            else:
                out_latex = "output_latex.tex"
                with open(out_latex, "w", encoding="utf-8") as f:
                    f.write(result)
                with open(out_latex, "rb") as f:
                    st.download_button("Tải file LaTeX", f, out_latex)
            # Tải từng hình minh họa đã crop
            for idx, img in enumerate(crop_imgs):
                img_path = f"img-{idx+1}.png"
                img.save(img_path)
                with open(img_path, "rb") as f:
                    st.download_button(f"Tải {img_path}", f, img_path)
