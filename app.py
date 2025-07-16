import streamlit as st
import tempfile, os, base64, re, io, itertools
from PIL import Image
import numpy as np
import cv2
import requests

# ===================== ĐỊNH DẠNG ĐỀ MARKDOWN CHUẨN GIÁO VIÊN =====================
def format_exam_markdown(text):
    # Đưa tag [BẢNG:...], [HÌNH:...] xuống dòng riêng
    text = re.sub(r'([^\n])(\[BẢNG: [^\]]+\])', r'\1\n\2', text)
    text = re.sub(r'(\[BẢNG: [^\]]+\])([^\n])', r'\1\n\2', text)
    text = re.sub(r'([^\n])(\[HÌNH: [^\]]+\])', r'\1\n\2', text)
    text = re.sub(r'(\[HÌNH: [^\]]+\])([^\n])', r'\1\n\2', text)

    # Chia từng block "Câu X." kể cả nhiều dòng, tách đáp án xuống dòng riêng
    blocks, curr = [], []
    for line in text.split('\n'):
        if re.match(r'^(Câu|Câu\s*)\s*\d+[.:]', line.strip()):
            if curr:
                blocks.append('\n'.join(curr).strip())
                curr = []
        curr.append(line)
    if curr:
        blocks.append('\n'.join(curr).strip())
    def fix_choices(block):
        block = re.sub(r'(\s|^)(A\.)', r'\nA.', block)
        block = re.sub(r'(\s|^)(B\.)', r'\nB.', block)
        block = re.sub(r'(\s|^)(C\.)', r'\nC.', block)
        block = re.sub(r'(\s|^)(D\.)', r'\nD.', block)
        block = re.sub(r'([^\n])(\|)', r'\1\n\2', block)
        return block.strip()
    result = '\n\n'.join([fix_choices(b) for b in blocks if b.strip()])
    # Ngăn trang/mã đề nổi bật
    result = re.sub(r'(Trang\s*\d+\/\d+\s*-\s*Mã đề\s*\d+)', r'\n\n---\n\1\n---\n', result)
    return result.strip()

def fix_markdown_tables_in_exam(text):
    # Lấy tất cả bảng (Markdown và tag [BẢNG: ...])
    table_blocks = []
    pattern_md = r'((\|.*\|(?:\n\|.*\|)+))'
    for m in re.finditer(pattern_md, text):
        table_blocks.append((m.start(), m.group(1)))
    pattern_img = r'(\[BẢNG: [^\]]+\])'
    for m in re.finditer(pattern_img, text):
        table_blocks.append((m.start(), m.group(1)))
    table_blocks.sort()
    text_wo_tables = text
    for _, tbl in reversed(table_blocks):
        text_wo_tables = text_wo_tables.replace(tbl, '')
    result_lines = []
    tbl_idx = 0
    lines = text_wo_tables.splitlines()
    for i, line in enumerate(lines):
        result_lines.append(line)
        if tbl_idx < len(table_blocks):
            if re.search(r'(bảng|tần số|biến thiên|bảng số liệu|bảng giá trị)', line, re.IGNORECASE):
                next_line = lines[i+1].strip() if i+1 < len(lines) else ""
                if not (next_line.startswith('|') or '[BẢNG:' in next_line):
                    result_lines.append(table_blocks[tbl_idx][1])
                    tbl_idx += 1
    while tbl_idx < len(table_blocks):
        result_lines.append(table_blocks[tbl_idx][1])
        tbl_idx += 1
    return '\n'.join(result_lines)

# ================== TÁCH HÌNH VẼ/BẢNG ===================
def filter_nested_boxes(candidates):
    filtered = []
    for i, box in enumerate(candidates):
        x0, y0, x1, y1 = box['x0'], box['y0'], box['x1'], box['y1']
        is_nested = False
        for j, other in enumerate(candidates):
            if i == j: continue
            ox0, oy0, ox1, oy1 = other['x0'], other['y0'], other['x1'], other['y1']
            if x0 >= ox0 and y0 >= oy0 and x1 <= ox1 and y1 <= oy1:
                is_nested = True
                break
        if not is_nested:
            filtered.append(box)
    return filtered

def extract_figures_and_tables(img_bytes, min_area_ratio=0.008, min_area_abs=2500, min_w=70, min_h=70, max_figures=8):
    img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 10)
    kernel = np.ones((3,3),np.uint8)
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        x, y, ww, hh = cv2.boundingRect(cnt)
        area = ww * hh
        area_ratio = area / (w * h)
        aspect = ww / (hh + 1e-6)
        if area < min_area_abs or area_ratio < min_area_ratio or area_ratio > 0.6:
            continue
        if ww < min_w or hh < min_h:
            continue
        if not (0.2 < aspect < 8.0):
            continue
        if x < 0.03*w or y < 0.03*h or (x+ww) > 0.97*w or (y+hh) > 0.97*h:
            continue
         hull = cv2. convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0: continue
        solidity = float(area)/hull_area
        if solidity < 0.4:
            continue
        is_table = (ww > 0.25*w and hh > 0.05*h and aspect > 2.0 and aspect < 10.0)
        candidates.append({
            "area": area, "x0": x, "y0": y, "x1": x+ww, "y1": y+hh,
            "is_table": is_table, "bbox": (x, y, ww, hh)
        })
    candidates = sorted(candidates, key=lambda f: f['area'], reverse=True)
    candidates = filter_nested_boxes(candidates)
    candidates = candidates[:max_figures]
    candidates = sorted(candidates, key=lambda box: (box["y0"], box["x0"]))
    final_figures_list = []
    img_idx = 0
    table_idx = 0
    for fig_data in candidates:
        crop = img[fig_data["y0"]:fig_data["y1"], fig_data["x0"]:fig_data["x1"]]
        buf = io.BytesIO()
        Image.fromarray(crop).save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        if fig_data["is_table"]:
            name = f"table-{table_idx+1}.jpeg"
            table_idx += 1
        else:
            name = f"img-{img_idx+1}.jpeg"
            img_idx += 1
        final_figures_list.append({
            "name": name,
            "base64": b64,
            "is_table": fig_data["is_table"],
            "bbox": fig_data["bbox"]
        })
    return final_figures_list, h, w

def remove_all_figure_markdown(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'!\[img-\d+\.jpeg\]\(img-\d+\.jpeg\)', '', text)
    text = re.sub(r'\[HÌNH:.*?\]', '', text)
    text = re.sub(r'\[BẢNG:.*?\]', '', text)
    text = re.sub(r'\[HÌNH_PLACEHOLDER\]', '', text)
    text = re.sub(r'\[BẢNG_PLACEHOLDER\]', '', text)
    return text

def join_paragraphs_and_insert_figures_tables(text, figures, img_h, img_w):
    lines, buffer = [], ""
    for line in text.split('\n'):
        stripped_line = line.strip()
        if stripped_line:
            buffer = buffer + " " + stripped_line if buffer else stripped_line
        else:
            if buffer:
                lines.append(buffer)
                buffer = ""
            lines.append('')
    if buffer:
        lines.append(buffer)
    figures_sorted = sorted(
        [fig for fig in figures if fig.get('bbox')],
        key=lambda f: (f['bbox'][1], f['bbox'][0])
    )
    used_figures = set()
    processed_lines = []
    fig_idx = 0
    for idx, line in enumerate(lines):
        processed_lines.append(line)
        if any(x in line.lower() for x in ["hình vẽ", "hình bên", "(hình", "xem hình", "đồ thị", "biểu đồ", "minh họa", "bảng", "tần số"]):
            while fig_idx < len(figures_sorted) and figures_sorted[fig_idx]['name'] in used_figures:
                fig_idx += 1
            if fig_idx < len(figures_sorted):
                fig = figures_sorted[fig_idx]
                tag = f"[BẢNG: {fig['name']}]" if fig['is_table'] else f"[HÌNH: {fig['name']}]"
                processed_lines.append(tag)
                used_figures.add(fig['name'])
                fig_idx += 1
    for i, line in enumerate(processed_lines):
        if re.match(r"^Câu\s*\d+[\.\:]", line) and fig_idx < len(figures_sorted):
            next_line = processed_lines[i+1] if i+1 < len(processed_lines) else ""
            if not re.match(r"\[HÌNH:.*\]", next_line) and not re.match(r"\[BẢNG:.*\]", next_line):
                while fig_idx < len(figures_sorted) and figures_sorted[fig_idx]['name'] in used_figures:
                    fig_idx += 1
                if fig_idx < len(figures_sorted):
                    fig = figures_sorted[fig_idx]
                    tag = f"[BẢNG: {fig['name']}]" if fig['is_table'] else f"[HÌNH: {fig['name']}]"
                    processed_lines.insert(i+1, tag)
                    used_figures.add(fig['name'])
                    fig_idx += 1
    return '\n'.join(processed_lines)

# ==================== GEMINI API ===================
GEMINI_API_KEYS = [
    "AIzaSyC_LxT0Xa1X5E03-FKPPri8okx6RwwZEd0",
    "AIzaSyCvNhReepkQxOJbJN1RX_n14wXYrZbAK5I"
]
api_key_cycle = itertools.cycle(GEMINI_API_KEYS)
def get_next_api_key():
    return next(api_key_cycle)
GEMINI_PROMPT = '''
YÊU CẦU QUAN TRỌNG:
1. GÕ LẠI CHÍNH XÁC TẤT CẢ VĂN BẢN TRONG ẢNH. Đánh dấu vị trí hình minh hoạ hoặc bảng số liệu bằng placeholder đúng chỗ: [HÌNH_PLACEHOLDER] hoặc [BẢNG_PLACEHOLDER].
2. Công thức Toán học phải bọc trong ${...}$ hoặc $...$.
3. Không thêm bất kỳ nội dung nào ngoài ảnh.
4. Nếu có bảng, chuyển về Markdown nếu đọc được.
Ví dụ:
Câu 1. ...
[HÌNH_PLACEHOLDER]
A. ...
B. ...
C. ...
D. ...
'''
def gemini_generate_text(image_bytes, api_key):
    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    b64_img = base64.b64encode(image_bytes).decode()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": GEMINI_PROMPT},
                {"inlineData": {
                    "mimeType": "image/png",
                    "data": b64_img
                }}
            ]
        }]
    }
    headers = {"Content-Type": "application/json"}
    r = requests.post(f"{api_url}?key={api_key}", json=payload, headers=headers, timeout=90)
    r.raise_for_status()
    res = r.json()
    text = res["candidates"][0]["content"]["parts"][0]["text"]
    return text

# ==================== UI STREAMLIT ===================
st.set_page_config(page_title="OCR Đề Toán AI Gemini", layout="wide")
st.title("📷 Chuyển đề Toán ảnh/PDF sang Markdown, mapping bảng và hình tự động (Chuẩn giáo viên)")

uploaded_images = st.file_uploader(
    "Chọn ảnh đề Toán (1 hoặc nhiều trang):",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    help="Tải lên các trang đề Toán dạng ảnh. Hệ thống sẽ tự động nhận diện bảng và hình."
)

if uploaded_images:
    for img_idx, img_file in enumerate(uploaded_images):
        st.subheader(f"📄 Trang {img_idx+1}: {img_file.name}")
        st.image(img_file, use_column_width=True)
        if st.button(f"🚀 Chuyển ảnh sang Markdown (Trang {img_idx+1})", key=f"ocr_btn_{img_idx}"):
            img_bytes = img_file.read()
            figures, img_h, img_w = extract_figures_and_tables(img_bytes)
            api_key = get_next_api_key()
            with st.spinner("Đang nhận diện văn bản bằng Gemini..."):
                try:
                    text = gemini_generate_text(img_bytes, api_key)
                except Exception as e:
                     text = f"[Lỗi Gemini:  {e}]" f"[Lỗi Gemini:  {e}]"
            text = remove_all_figure_markdown(text)
            text = join_paragraphs_and_insert_figures_tables(text, figures, img_h, img_w)
            formatted_text = format_exam_markdown(text)
            formatted_text = fix_markdown_tables_in_exam(formatted_text)
            st.markdown("### 📋 Markdown Chuẩn Giáo Viên:")
# ===================== ĐỊNH DẠNG ĐỀ MARKDOWN CHUẨN GIÁO VIÊN =====================
            st.download_button(
     # Đưa tag [BẢNG:...], [HÌNH:...] xuống dòng riêng "📄 Tải Markdown (.txt)",
                formatted_text,
     text = re.sub(r'(\[BẢNG: [^\]]+\])([^\n])', r'\1\n\2', text) f"ket_qua_{img_file.name}.txt",
     text = re.sub(r'([^\n])(\[HÌNH: [^\]]+\])', r'\1\n\2', text) "text/plain"
     text = re.sub(r'(\[HÌNH: [^\]]+\])([^\n])', r'\1\n\2', text) )
            st.markdown("### 🖼️ Các hình/bảng đã tách:")
     # Chia từng block "Câu X." kể cả nhiều dòng, tách đáp án xuống dòng riêng for fig in figures:
                img_bytes_fig = base64.b64decode(fig["base64"])
                st.image(img_bytes_fig, caption=fig["name"], use_column_width=True)
                st.download_button(
                    f"Tải {fig['name']}",
                    img_bytes_fig,
                    file_name=fig["name"],
                    mime="image/jpeg",
                    key=f"download_{img_file.name}_{fig['name']}"
                )
else:
    st.info("Hãy tải lên ảnh đề Toán để bắt đầu.")
