import streamlit as st
from PIL import Image
import fitz
import io
import os
import requests
import base64
from docx import Document
from google.cloud import vision

# Set your Google Vision service account JSON path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "YOUR_GG_JSON_KEY.json"

st.set_page_config(layout="wide", page_title="PDF/Ảnh → LaTeX/Word + Auto crop minh họa (GPT-4o + GG Vision)")

st.title("📄 PDF/Ảnh ➔ LaTeX/Word (ChatGPT-4o) + Auto-crop minh họa (Google Vision)")

# GPT-4o endpoint AI.VN
api_url = "https://api.sv2.llm.ai.vn/v1/chat/completions"
api_key = st.sidebar.text_input("AI.VN GPT-4o API Key", type="password")

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
    if mode == "latex":
        prompt = "Nhận diện CHÍNH XÁC toàn bộ văn bản, công thức toán học, bảng biểu trong ảnh này và chuyển sang LaTeX. Không giải thích, không bình luận, không bịa thêm."
    else:
        prompt = "Nhận diện CHÍNH XÁC toàn bộ văn bản, công thức toán học, bảng biểu trong ảnh này và chuyển sang văn bản Word chuẩn. Không giải thích, không bình luận, không bịa thêm."
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
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            return f"[Lỗi GPT-4o: {data['error'].get('message', str(data['error']))}]"
        else:
            return f"[Lỗi GPT-4o: Không có dữ liệu trả về | {data}]"
    except Exception as e:
        return f"[Lỗi gọi GPT-4o: {e}]"

def vision_auto_crop(image_pil, page_idx=1, out_dir="vision_crops"):
    client = vision.ImageAnnotatorClient()
    buffered = io.BytesIO()
    image_pil.save(buffered, format="PNG")
    content = buffered.getvalue()
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    os.makedirs(out_dir, exist_ok=True)
    crops = []
    # Vision API trả về các block, lọc lấy hình minh họa
    try:
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                if block.block_type == vision.Document.Page.Block.BlockType.PICTURE:
                    box = block.bounding_box.vertices
                    x1 = min(v.x for v in box)
                    y1 = min(v.y for v in box)
                    x2 = max(v.x for v in box)
                    y2 = max(v.y for v in box)
                    crop = image_pil.crop((x1, y1, x2, y2))
                    crop_path = f"{out_dir}/img_p{page_idx}_{len(crops)+1}.png"
                    crop.save(crop_path)
                    crops.append(crop_path)
    except Exception as e:
        st.warning(f"Lỗi Vision crop: {e}")
    return crops

def save_word(text_list, image_dict, output_path):
    doc = Document()
    for idx, txt in enumerate(text_list):
        doc.add_paragraph(txt)
        # Chèn ảnh minh họa từng trang vào sau nội dung
        if (idx+1) in image_dict:
            for img_path in image_dict[idx+1]:
                doc.add_picture(img_path, width=docx.shared.Inches(4))
    doc.save(output_path)

uploaded = st.file_uploader("Chọn file PDF hoặc ảnh", type=["pdf", "png", "jpg", "jpeg"])
mode = st.radio("Chọn chế độ xuất", ["latex", "word"])
if uploaded and api_key:
    if uploaded.name.lower().endswith(".pdf"):
        images = pdf_to_images(uploaded.read())
        st.success(f"Đã tách {len(images)} trang từ PDF.")
    else:
        images = [Image.open(uploaded)]
        st.success("Đã tải lên 1 ảnh.")

    ocr_results = []
    all_crops = {}
    for idx, img in enumerate(images):
        st.markdown(f"---\n### Trang {idx+1}")
        st.image(img, caption=f"Trang {idx+1}", use_container_width=True)

        with st.spinner("Tự động crop hình minh họa bằng Google Vision..."):
            crops = vision_auto_crop(img, page_idx=idx+1)
            st.write(f"Đã crop tự động {len(crops)} hình minh họa.")
            for crop_path in crops:
                st.image(crop_path, caption=f"Minh họa {os.path.basename(crop_path)}", use_container_width=True)
            all_crops[idx+1] = crops

        if st.button(f"OCR toàn bộ trang {idx+1} (GPT-4o)", key=f"ocr_{idx}"):
            with st.spinner("GPT-4o đang nhận diện nội dung..."):
                ocr_text = gpt4o_ocr_format(img, api_key, mode=mode)
                st.code(ocr_text, language="latex" if mode=="latex" else "markdown")
                ocr_results.append(ocr_text)

    if ocr_results and st.button(f"Tải về {'LaTeX' if mode=='latex' else 'Word'} hoàn chỉnh"):
        full_text = "\n\n".join(ocr_results)
        if mode == "word":
            save_word(ocr_results, all_crops, "output_word.docx")
            with open("output_word.docx", "rb") as f:
                st.download_button("Tải file Word", f, "output_word.docx")
        else:
            latex_file = "output_latex.tex"
            # Chèn hình minh họa vào cuối mỗi trang
            with open(latex_file, "w", encoding="utf-8") as f:
                for idx, txt in enumerate(ocr_results):
                    f.write(txt + "\n\n")
                    if (idx+1) in all_crops:
                        for img_path in all_crops[idx+1]:
                            f.write(f"\\includegraphics[width=0.7\\linewidth]{{{os.path.basename(img_path)}}}\n")
            with open(latex_file, "rb") as f:
                st.download_button("Tải file LaTeX", f, latex_file)
            # Cho tải riêng từng hình
            for idx in all_crops:
                for img_path in all_crops[idx]:
                    with open(img_path, "rb") as f:
                        st.download_button(f"Tải hình {os.path.basename(img_path)}", f, os.path.basename(img_path))
