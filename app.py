import streamlit as st
from streamlit_cropper import st_cropper
from PIL import Image
import fitz
import io
import base64
import requests
from docx import Document

# =============== CONFIG ===============
GEMINI_FLASH_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
API_GPT4O_ENDPOINT = "https://api.sv2.llm.ai.vn/v1/chat/completions"
st.set_page_config(page_title="Auto-crop minh họa (Gemini Flash) + OCR GPT-4o", layout="wide")
st.title("📄 Auto-crop minh họa (Gemini Flash), OCR và chuyển sang LaTeX/Word (GPT-4o AI.VN)")

g_api_key = st.sidebar.text_input("Google Gemini Flash API Key", type="password")
api_key = st.sidebar.text_input("AI.VN API Key (GPT-4o)", type="password")

# ===== GEMINI FLASH detect box minh họa & OCR =====
def gemini_flash(image, g_api_key, ocr_only=False):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()

    if ocr_only:
        prompt = "Nhận diện TẤT CẢ văn bản và công thức Toán trong ảnh. Gõ lại CHÍNH XÁC toàn bộ nội dung (ưu tiên định dạng LaTeX nếu là công thức), không giải thích gì thêm."
    else:
        prompt = (
            "Detect all illustration/figure/image regions in this image. "
            "Return for each region an array [left, top, width, height] (pixel, integer). "
            "If no region, return []. No explanation."
        )
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": img_b64,
                        }
                    }
                ]
            }
        ]
    }
    headers = {"Content-Type": "application/json"}
    url = f"{GEMINI_FLASH_ENDPOINT}?key={g_api_key}"
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        data = resp.json()
        st.write("DEBUG Gemini Flash:", data)
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return text
    except Exception as e:
        return f"[Lỗi Gemini Flash: {e}]"

# ===== PDF sang ảnh =====
def pdf_to_images(pdf_bytes):
    images = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            images.append(img)
    return images

# ====== GPT-4o chuyển đổi LaTeX/Word ======
def gpt4o_format(text, api_key, mode="latex"):
    if not text.strip():
        return ""
    prompt = (
        "Chuyển đoạn văn dưới đây sang định dạng "
        + ("LaTeX." if mode == "latex" else "Word. Đảm bảo định dạng bảng, công thức nếu có.")
        + "\nĐoạn văn:\n"
        + text
        + "\nKHÔNG giải thích gì thêm."
    )
    payload = {
        "model": "openai:gpt-4o",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2048,
        "temperature": 0.0
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(API_GPT4O_ENDPOINT, headers=headers, json=payload, timeout=180)
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
st.info("Ảnh sẽ được Gemini Flash tự động detect/crop minh họa. Nếu thất bại, bạn crop tay bằng chuột. Text OCR bởi Gemini Flash, chuyển định dạng bằng GPT-4o (AI.VN).")

if uploaded and (g_api_key or api_key):
    if uploaded.name.lower().endswith(".pdf"):
        images = pdf_to_images(uploaded.read())
        st.success(f"Đã tách {len(images)} trang từ PDF.")
    else:
        images = [Image.open(uploaded)]
        st.success("Đã tải lên 1 ảnh.")

    all_formats = []
    all_crops = []

    for idx, img in enumerate(images):
        st.markdown(f"---\n### Trang {idx+1}")
        st.image(img, caption=f"Trang {idx+1}", use_container_width=True)

        # ----- AUTO CROP bằng Gemini Flash -----
        boxes = []
        if g_api_key:
            with st.spinner("Gemini Flash đang tự động nhận diện vùng hình minh họa..."):
                text_boxes = gemini_flash(img, g_api_key, ocr_only=False)
            import re
            boxes = re.findall(r'\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]', text_boxes)
            boxes = [tuple(map(int, b)) for b in boxes]
        crops_this_page = []
        if boxes:
            st.write(f"Gemini detect {len(boxes)} vùng minh họa:")
            for i, (left, top, width, height) in enumerate(boxes):
                crop = img.crop((left, top, left + width, top + height))
                st.image(crop, caption=f"Auto minh họa {i+1} Trang {idx+1}", use_container_width=True)
                crops_this_page.append(crop)
        else:
            st.warning("Gemini KHÔNG detect được minh họa. Bạn có thể crop tay:")
            n_crop = st.number_input(f"Số hình minh họa muốn crop ở trang {idx+1}", 1, 10, 1, 1)
            for i in range(n_crop):
                st.write(f"Minh họa {i+1} Trang {idx+1}:")
                box = st_cropper(img, box_color='#FF0000', aspect_ratio=None, key=f"cropper_{idx}_{i}", return_type='box')
                if box:
                    left = box.get("left", 0)
                    top = box.get("top", 0)
                    width = box.get("width", img.width)
                    height = box.get("height", img.height)
                    if width > 10 and height > 10:
                        crop = img.crop((left, top, left + width, top + height))
                        st.image(crop, caption=f"Minh họa {i+1} Trang {idx+1}", use_container_width=True)
                        crops_this_page.append(crop)
        all_crops += crops_this_page

        if st.button(f"OCR toàn bộ trang {idx+1} bằng Gemini Flash & chuyển LaTeX/Word", key=f"ocr_{idx}"):
            ocr_text = ""
            with st.spinner("Gemini Flash đang nhận diện nội dung..."):
                ocr_text = gemini_flash(img, g_api_key, ocr_only=True)
                st.code(ocr_text, language="latex")
            if api_key:
                with st.spinner("GPT-4o AI.VN đang chuyển định dạng..."):
                    formatted = gpt4o_format(ocr_text, api_key, mode=mode)
                    st.code(formatted, language="latex" if mode == "latex" else "markdown")
                    all_formats.append(formatted)
            else:
                all_formats.append(ocr_text)

    if all_formats and st.button(f"Tải về {'LaTeX' if mode=='latex' else 'Word'} hoàn chỉnh"):
        full_text = "\n\n".join(all_formats)
        if mode == "word":
            insert_images_word(full_text, all_crops, "output_word.docx")
            with open("output_word.docx", "rb") as f:
                st.download_button("Tải file Word", f, "output_word.docx")
        else:
            latex_full = insert_images_latex(full_text, all_crops)
            with open("output_latex.tex", "w", encoding="utf-8") as f:
                f.write(latex_full)
            with open("output_latex.tex", "rb") as f:
                st.download_button("Tải file LaTeX", f, "output_latex.tex")
        for i, img in enumerate(all_crops):
            img_path = f"img_{i+1}.png"
            img.save(img_path)
            with open(img_path, "rb") as f:
                st.download_button(f"Tải hình {img_path}", f, img_path)
