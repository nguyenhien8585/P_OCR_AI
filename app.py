import streamlit as st
import tempfile, os, base64, re, io, itertools
from PIL import Image
import numpy as np
import cv2
import requests
from PyPDF2 import PdfReader

from config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_images import extract_images_from_pdf
from word_export import insert_images_to_word_from_markdown

# ----------- Hàm tách bảng giá trị/bảng biến thiên và hình minh hoạ (chuẩn nâng cao) ----------
def extract_figures_and_tables(img_bytes, min_area_ratio=0.008, min_area_abs=2500, min_w=70, min_h=70, max_figures=8):
    img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2] 
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # Áp dụng GaussianBlur để làm mịn nhiễu (kernel nhỏ hơn để giữ chi tiết)
    gray = cv2.GaussianBlur(gray, (3,3), 0) 
    
    # Áp dụng CLAHE để tăng cường độ tương phản cục bộ
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    
    # Adaptive Thresholding (tham số cân bằng)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 10) 
    
    # Dilate để làm dày các đường nét và kết nối các phần bị đứt gãy
    kernel = np.ones((3,3),np.uint8)
    thresh = cv2.dilate(thresh, kernel, iterations=1) # Giảm iterations để tránh làm dính các đối tượng
    
    # Tìm contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    candidates = []
    for cnt in contours:
        x, y, ww, hh = cv2.boundingRect(cnt)
        area = ww * hh
        area_ratio = area / (w * h)
        aspect = ww / (hh + 1e-6)
        
        # Lọc các vùng quá nhỏ hoặc quá lớn
        # Tăng min_area_abs và min_area_ratio để loại bỏ các đối tượng nhỏ như mã đề
        if area < min_area_abs or area_ratio < min_area_ratio or area_ratio > 0.6: 
            continue
        
        # Lọc theo kích thước tối thiểu
        # Tăng min_w và min_h
        if ww < min_w or hh < min_h:
            continue

        # Lọc theo tỷ lệ khung hình hợp lý cho hình ảnh/bảng
        # Mã đề thường rất dài và mỏng, có thể loại bỏ bằng cách thắt chặt aspect ratio
        if not (0.2 < aspect < 8.0): # Thắt chặt hơn một chút
            continue

        # Không lấy vùng quá sát mép giấy (chừa 3% mép)
        # Mã đề thường nằm rất sát mép
        if x < 0.03*w or y < 0.03*h or (x+ww) > 0.97*w or (y+hh) > 0.97*h:
            continue
        
        # Thêm lọc dựa trên solidity (độ đặc của contour)
        # Mã đề thường là văn bản, có solidity thấp hơn hình ảnh đặc
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0: continue # Tránh chia cho 0
        solidity = float(area)/hull_area
        if solidity < 0.4: # Ngưỡng solidity, có thể điều chỉnh
            continue

        # Logic nhận dạng bảng: chiều rộng lớn, tỷ lệ khung hình rộng
        is_table = (ww > 0.25*w and hh > 0.05*h and aspect > 2.0 and aspect < 10.0) 
        
        candidates.append({
            "area": area, "x0": x, "y0": y, "x1": x+ww, "y1": y+hh,
            "is_table": is_table, "bbox": (x, y, ww, hh) 
        })
    
    # Sắp xếp các ứng cử viên theo diện tích giảm dần để ưu tiên các hình lớn
    candidates = sorted(candidates, key=lambda f: f['area'], reverse=True)
    
    # Giới hạn cứng số lượng đối tượng trả về là 2 (hoặc max_figures nếu muốn linh hoạt)
    candidates = candidates[:2] 

    # Sắp xếp lại theo vị trí trên trang (y, x) để đảm bảo thứ tự logic
    candidates = sorted(candidates, key=lambda box: (box["y0"], box["x0"]))

    final_figures_list = []
    img_idx = 0
    table_idx = 0
    
    # Sau khi lọc, gán lại tên và tạo base64
    for fig_data in candidates: 
        crop = img[fig_data["y0"]:fig_data["y1"], fig_data["x0"]:fig_data["x1"]]
        buf = io.BytesIO()
        Image.fromarray(crop).save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        
        # Đảm bảo tên file là duy nhất và có định dạng img-x.jpeg hoặc table-x.jpeg
        if fig_data["is_table"]:
            name = f"table-{table_idx+1}.jpeg" # Bắt đầu từ 1
            table_idx += 1
        else:
            name = f"img-{img_idx+1}.jpeg" # Bắt đầu từ 1
            img_idx += 1
        
        final_figures_list.append({
            "name": name,
            "base64": b64,
            "is_table": fig_data["is_table"],
            "bbox": fig_data["bbox"] 
        })

    # Trả về cả danh sách hình ảnh và chiều cao/rộng của ảnh gốc
    return final_figures_list, h, w

def remove_all_figure_markdown(text):
    """
    Loại bỏ các markdown hình ảnh/bảng cũ hoặc placeholder không mong muốn.
    """
    if not isinstance(text, str): return ""
    text = re.sub(r'!\[img-\d+\.jpeg\]\(img-\d+\.jpeg\)', '', text)
    text = re.sub(r'\[HÌNH:.*?\]', '', text) 
    text = re.sub(r'\[BẢNG:.*?\]', '', text) 
    text = re.sub(r'\[HÌNH_PLACEHOLDER\]', '', text)
    text = re.sub(r'\[BẢNG_PLACEHOLDER\]', '', text)
    return text

# -------- Mapping nâng cao (tách đúng đoạn, không chen giữa câu) --------
def join_paragraphs_and_insert_figures_tables(text, figures, img_h, img_w, keywords=None, table_kw=None):
    """
    Nối các đoạn văn bản và chèn hình ảnh/bảng vào đúng vị trí.
    Ưu tiên thay thế các placeholder do Gemini tạo ra, sau đó chèn bổ sung
    dựa trên từ khóa và heuristic nếu cần.
    """
    if keywords is None:
        keywords = [
            "xem hình", "hình dưới", "hình vẽ", "biểu đồ", "minh hoạ",
            "minh họa", "hình bên", "hình minh hoạ", "hình minh họa",
            "hình chữ nhật", "điểm", "cạnh", "diện tích", "vùng đất" # Thêm từ khóa cho câu hình học
        ]
    if table_kw is None:
        table_kw = [
            "bảng biến thiên", "bảng giá trị", "bảng tần số", "bảng sau", "bảng dưới"
        ]
    
    lines = [l.rstrip() for l in text.split('\n')]
    final_processed_lines = []
    
    inserted_figures_names = set()
    
    # Tạo một bản sao của danh sách figures để dễ dàng quản lý các hình đã được chèn
    available_figures = list(figures) 
    
    # Sắp xếp lại available_figures theo vị trí để xử lý tuần tự
    available_figures.sort(key=lambda f: (f['bbox'][1], f['bbox'][0]))

    # Bước 1: Phân tích các khối văn bản (câu hỏi, đoạn văn) và vị trí của chúng
    text_blocks = [] # List of (type, content_lines, start_line_idx, end_line_idx)
    current_block_type = "intro" # "intro", "question", "footer"
    current_block_lines = []
    current_block_start_idx = 0
    
    for idx, line in enumerate(lines):
        line_strip = line.strip()
        
        is_question_start = re.match(r"^Câu\s*(\d+)\.?", line_strip)
        is_footer_start = re.match(r"^(HẾT|Trang|Mã đề|----+)$", line_strip)

        if is_question_start:
            if current_block_lines:
                text_blocks.append({
                    "type": current_block_type,
                    "content_lines": list(current_block_lines),
                    "start_line_idx": current_block_start_idx,
                    "end_line_idx": idx - 1
                })
            current_block_type = "question"
            current_block_lines = [line]
            current_block_start_idx = idx
        elif is_footer_start:
            if current_block_lines:
                text_blocks.append({
                    "type": current_block_type,
                    "content_lines": list(current_block_lines),
                    "start_line_idx": current_block_start_idx,
                    "end_line_idx": idx - 1
                })
            current_block_type = "footer"
            current_block_lines = [line]
            current_block_start_idx = idx
        else:
            current_block_lines.append(line)
    
    # Thêm khối cuối cùng
    if current_block_lines:
        text_blocks.append({
            "type": current_block_type,
            "content_lines": list(current_block_lines),
            "start_line_idx": current_block_start_idx,
            "end_line_idx": len(lines) - 1
        })

    # Bước 2: Gán hình ảnh cho các khối văn bản
    figure_to_block_map = {} # {figure_name: text_block_index}
    
    for fig in available_figures:
        if fig is None: continue
        
        fig_y_center = fig['bbox'][1] + fig['bbox'][3] / 2
        
        best_block_match_idx = -1
        min_y_dist = float('inf')
        
        for block_idx, block in enumerate(text_blocks):
            block_start_y = block["start_line_idx"] * (img_h / len(lines))
            block_end_y = (block["end_line_idx"] + 1) * (img_h / len(lines))
            block_y_center = (block_start_y + block_end_y) / 2

            dist = abs(fig_y_center - block_y_center)
            
            # Kiểm tra xem hình ảnh có nằm trong phạm vi Y của khối không
            padding_y = img_h * 0.05 # 5% chiều cao ảnh làm đệm
            
            if (block_start_y - padding_y) <= fig_y_center <= (block_end_y + padding_y):
                if dist < min_y_dist:
                    min_y_dist = dist
                    best_block_match_idx = block_idx
        
        if best_block_match_idx != -1:
            figure_to_block_map[fig["name"]] = best_block_match_idx
        else:
            # Nếu không khớp với khối nào, gán cho khối gần nhất (hoặc để sau)
            # Tạm thời, nếu không khớp, nó sẽ được chèn vào cuối tài liệu
            pass

    # Bước 3: Xây dựng lại văn bản, chèn hình ảnh vào cuối khối văn bản liên quan
    for block_idx, block in enumerate(text_blocks):
        current_buffer = ""
        
        # Nối các dòng trong khối thành một đoạn văn bản
        for line_content in block["content_lines"]:
            line_strip = line_content.strip()
            
            # Nếu dòng trống, flush buffer và thêm dòng trống
            if not line_strip:
                if current_buffer:
                    final_processed_lines.append(current_buffer.strip())
                    current_buffer = ""
                final_processed_lines.append("")
            else:
                # Nối dòng vào buffer
                if current_buffer and not re.match(r"^Câu\s*(\d+)\.?", line_strip) and not re.search(r'[.!?…:]\s*$', current_buffer.strip()):
                    current_buffer += " " + line_strip
                else:
                    current_buffer = line_strip
        
        # Flush buffer cuối cùng của khối
        if current_buffer:
            final_processed_lines.append(current_buffer.strip())
        
        # Chèn hình ảnh thuộc về khối này vào cuối khối
        figures_for_this_block = [f for f in available_figures if f is not None and figure_to_block_map.get(f["name"]) == block_idx and f["name"] not in inserted_figures_names]
        figures_for_this_block.sort(key=lambda f: (f['bbox'][1], f['bbox'][0])) # Sắp xếp theo vị trí

        for fig_to_insert in figures_for_this_block:
            # Kiểm tra xem có placeholder trong buffer cuối cùng của khối không
            # Nếu có, thay thế placeholder
            last_line_in_output = final_processed_lines[-1] if final_processed_lines else ""
            
            if ("[HÌNH_PLACEHOLDER]" in last_line_in_output and not fig_to_insert["is_table"]) or \
               ("[BẢNG_PLACEHOLDER]" in last_line_in_output and fig_to_insert["is_table"]):
                if fig_to_insert["is_table"]:
                    final_processed_lines[-1] = last_line_in_output.replace("[BẢNG_PLACEHOLDER]", f"[BẢNG: {fig_to_insert['name']}]")
                else:
                    final_processed_lines[-1] = last_line_in_output.replace("[HÌNH_PLACEHOLDER]", f"[HÌNH: {fig_to_insert['name']}]")
            else:
                # Chèn vào dòng mới
                if fig_to_insert["is_table"]:
                    final_processed_lines.append(f"[BẢNG: {fig_to_insert['name']}]")
                else:
                    final_processed_lines.append(f"[HÌNH: {fig_to_insert['name']}]")
            
            inserted_figures_names.add(fig_to_insert["name"])
            # Đánh dấu hình ảnh là đã sử dụng trong available_figures
            for i, fig_item in enumerate(available_figures):
                if fig_item is not None and fig_item["name"] == fig_to_insert["name"]:
                    available_figures[i] = None
                    break

    # Chèn các hình/bảng còn lại ở cuối tài liệu nếu chưa được chèn
    remaining_figures = sorted([f for f in figures if f['name'] not in inserted_figures_names and 'bbox' in f], key=lambda f: (f['bbox'][1], f['bbox'][0]))
    for fig in remaining_figures:
        if fig["is_table"]:
            final_processed_lines.append(f"[BẢNG: {fig['name']}]")
        else:
            final_processed_lines.append(f"[HÌNH: {fig['name']}]")
        inserted_figures_names.add(fig["name"]) 
    
    return '\n'.join([l for l in final_processed_lines if l.strip()])

# --------- Key Gemini -----------
GEMINI_API_KEYS = [
    "AIzaSyCVUtoKWzyw27LvVbQPxs5D4n48eZWNw9k",
  "AIzaSyD6uAzLz6y2CwgEHg-1XVPM11iAPoEoc3E",
  "AIzaSyDCrzo3_3hKMF3jr114J7pb_wAAd2LesjI",
  "AIzaSyDbU_e892synpWo3uV8HLM2gj6CK0mC7eQ",
  "AIzaSyC_LxT0Xa1X5E03-FKPPri8okx6RwwZEd0",
  "AIzaSyCvNhReepkQxOJbJN1RX_n14wXYrZbAK5I"
]
api_key_cycle = itertools.cycle(GEMINI_API_KEYS)
def get_next_api_key():
    return next(api_key_cycle)

GEMINI_PROMPT = '''
YÊU CẦU:
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh, giữ nguyên cấu trúc đoạn văn, dấu xuống dòng và định dạng ban đầu.
2. Nếu phát hiện nhiều hình minh hoạ (hình vẽ, đồ thị, bảng, ...), hãy đánh dấu đúng vị trí từng hình bằng cú pháp placeholder:
    - `[HÌNH_PLACEHOLDER]` cho hình ảnh minh hoạ.
    - `[BẢNG_PLACEHOLDER]` cho bảng hoặc bảng số liệu.
3. Với mỗi placeholder, hãy chèn ngay sau dòng mô tả có các cụm từ như: "xem hình dưới", "hình dưới đây", "bảng biến thiên", "bảng tần số", "bảng giá trị", "hình vẽ", "biểu đồ", hoặc ngay sau dòng câu hỏi liên quan tới hình/bảng/biểu đồ đó.
4. Công thức toán học phải để ở dạng LaTeX inline: `${...}$` (bao gồm cả biểu thức, hệ phương trình, ký hiệu, ...)
5. Nếu phát hiện bảng số liệu, hãy chuyển thành bảng Markdown nếu có thể.
6. Định dạng từng loại câu hỏi như sau:

Định dạng câu hỏi

1. **Trắc nghiệm 4 phương án**
- Bắt đầu bằng "Câu X." (X là số thứ tự), sau đó là nội dung câu hỏi, rồi lần lượt các lựa chọn:
Câu X. [Nội dung câu hỏi]
A. [Đáp án A]
B. [Đáp án B]
C. [Đáp án C]
D. [Đáp án D]
2. Đúng/Sai
- Bắt đầu bằng "Câu X.", nội dung câu hỏi, cuối cùng là 2 lựa chọn trên 2 dòng riêng:
Câu X. [Nội dung câu hỏi]
A. Đúng
B. Sai
3. Trả lời ngắn
- Bắt đầu bằng "Câu X.", nội dung câu hỏi.
Câu X. [Nội dung câu hỏi]
Trả lời: ________
4. **Tự luận**
- Bắt đầu bằng "Câu X.", nội dung câu hỏi.
Câu X. [Nội dung câu hỏi]
Bài làm:
Lưu ý:
- Giữ nguyên thứ tự các câu hỏi, đáp án, nội dung gốc.
- Chỉ chèn placeholder đúng vị trí liên quan tới hình hoặc bảng.
- Không tự ý bỏ qua hay thay đổi bất kỳ chi tiết nào.
**Ví dụ minh hoạ:**
Câu 1. Cho tam giác $ABC$ có $AB = AC$. Xem hình dưới.
[HÌNH_PLACEHOLDER]
A. Tam giác cân tại $A$.
B. Tam giác vuông tại $B$.
C. Tam giác đều.
D. Tam giác tù.
Câu 2. Điền số thích hợp vào ô trống trong bảng giá trị sau:
[BẢNG_PLACEHOLDER]
Câu 3. Phát biểu nào sau đây là đúng về đồ thị hàm số $y = x^2$?
A. Đồ thị là đường thẳng.
B. Đồ thị là parabol.
C. Đồ thị là elip.
D. Đồ thị là hypebol.
Câu 4. Hãy giải phương trình $x^2 - 4 = 0$.
Hãy xuất ra văn bản theo đúng định dạng trên!
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

# ========== Giao diện ==========
st.set_page_config(page_title="OCR PDF & Ảnh Toán – Gemini", layout="wide")
st.title("✨ Chuyển PDF & Ảnh Toán sang Markdown, giữ công thức & bảng (bảng giá trị, bảng tần số, biến thiên) ✨")
tab_pdf, tab_img = st.tabs(["📄 PDF Toán", "🖼️ Ảnh → Markdown + Minh hoạ/Bảng"])

# =================== TAB ẢNH ===================
with tab_img:
    uploaded_images = st.file_uploader(
        "Chọn nhiều ảnh (mỗi ảnh là một trang):",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Mỗi ảnh là 1 trang, minh hoạ & bảng sẽ được tách tự động."
    )

    if uploaded_images:
        for img_idx, img_file in enumerate(uploaded_images):
            with st.expander("ℹ️ Thông tin file", expanded=True):
                st.write(f"**🖼️ Tên file:** {img_file.name}")
                st.write(f"**🟡 Loại file:** {img_file.type}")
                st.write(f"**✏️ Kích thước:** {img_file.size/1024:.1f} KB")

            ocr_key = f"ocr_{img_file.name}_{img_idx}"
            text_key = f"text_{img_file.name}_{img_idx}"
            fig_key = f"fig_{img_file.name}_{img_idx}"

            # Nút xử lý OCR Image cho từng ảnh
            if st.button(f"🚀 Xử lý OCR Image ({img_file.name})", key=ocr_key):
                img_bytes = img_file.read()
                # Thay đổi cách gọi hàm extract_figures_and_tables để nhận cả h và w
                figures, img_h, img_w = extract_figures_and_tables(img_bytes) 
                api_key = get_next_api_key()
                with st.spinner("Đang nhận diện..."):
                    try:
                        text = gemini_generate_text(img_bytes, api_key)
                    except Exception as e:
                        text = f"[Lỗi Gemini: {e}]"
                
                text = remove_all_figure_markdown(text) 
                # Truyền img_h và img_w vào hàm join_paragraphs_and_insert_figures_tables
                text = join_paragraphs_and_insert_figures_tables(text, figures, img_h, img_w)
                
                st.session_state[text_key] = text
                st.session_state[fig_key] = figures

            if text_key in st.session_state and fig_key in st.session_state:
                st.markdown("### 📋 Kết quả mapping nâng cao:")
                
                # --- Giao diện mới cho tab "Ảnh" ---
                tab_text_img, tab_figures_img = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])

                with tab_text_img:
                    st.code(st.session_state[text_key], language="markdown")
                    figures = st.session_state[fig_key] # Lấy lại figures để dùng trong nút tải Word
                    if figures: # Chỉ hiển thị nút tải Word nếu có hình ảnh
                        if st.button("📝 Tạo và tải file Word giữ hình & bảng đúng vị trí", use_container_width=True, key=f"word-{img_file.name}-{img_idx}"):
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                                insert_images_to_word_from_markdown(
                                    st.session_state[text_key],
                                    figures,
                                    tmp_word.name
                                )
                            with open(tmp_word.name, "rb") as f:
                                word_data = f.read()
                            st.success("✅ Đã tạo file Word thành công!")
                            st.download_button(
                                "⬇️ Tải về file Word",
                                word_data,
                                file_name=f"ket_qua_{img_file.name}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                            os.remove(tmp_word.name)
                    else:
                        st.info("Không phát hiện minh hoạ hay bảng nào trong ảnh để xuất Word.")

                with tab_figures_img:
                    figures = st.session_state[fig_key]
                    if figures:
                        st.success(f"🖼️ Đã tìm thấy {len(figures)} hình ảnh và bảng:")
                        for idx, fig in enumerate(figures):
                            try:
                                img_bytes = base64.b64decode(fig["base64"])
                                cap = f"{'Bảng' if fig['is_table'] else 'Hình'}: {fig['name']}"
                                st.image(img_bytes, caption=cap, width=350)
                                st.download_button(
                                    f"Tải {fig['name']}",
                                    img_bytes,
                                    file_name=fig["name"],
                                    mime="image/jpeg",
                                    use_container_width=True,
                                    key=f"anh-download-{fig['name']}-{idx}"
                                )
                            except Exception as e:
                                st.error(f"Không đọc được ảnh {fig['name']}: {e}")
                    else:
                        st.info("Không tìm thấy minh hoạ hay bảng nào trong ảnh.")
                # --- Kết thúc giao diện mới ---

    else:
        st.info("Vui lòng tải lên ít nhất 1 ảnh để bắt đầu.")
# =================== TAB PDF ===================
with tab_pdf:
    st.markdown("#### 📝 OCR PDF Toán, giữ công thức, ảnh minh hoạ")
    uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"], label_visibility="collapsed")
    num_pages = None
    if uploaded_file:
        pdf_bytes = uploaded_file.read()
        file_name = uploaded_file.name
        mime_type = "application/pdf"
        size_mb = len(pdf_bytes) / (1024 * 1024)
        try:
            uploaded_file.seek(0)
            reader = PdfReader(uploaded_file)
            num_pages = len(reader.pages)
            uploaded_file.seek(0)
        except:
            num_pages = "?"
        with st.expander("ℹ️ Thông tin file", expanded=True):
            st.write(f"**Tên file:** {file_name}")
            st.write(f"**Loại file:** {mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")
            st.write(f"**Số trang:** {num_pages}")

    if uploaded_file:
        if st.button("🚀 Xử lý OCR PDF", type="primary", use_container_width=True):
            st.info("⏳ Đang xử lý OCR PDF... (vui lòng chờ)")
            with st.spinner("Đang nhận diện văn bản và trích xuất hình ảnh..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                uploaded_file.seek(0)
                pdf_bytes = uploaded_file.read()
                images = extract_images_from_pdf(pdf_bytes) # extract_images_from_pdf không trả về h, w
                result = client.convert(pdf_bytes, file_name, mime_type)
            if not result.get("success"):
                st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
                st.stop()
            st.session_state["ocr_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_images"] = images
            st.session_state["ocr_done"] = True
            st.success("✅ Đã nhận diện PDF thành công!")
    if st.session_state.get("ocr_done"):
        def dollar_to_mathptn(s):
            return re.sub(r'\$(.+?)\$', r'${\1}$', s)
        raw_text = st.session_state.get("ocr_text_raw", "")
        text_content = dollar_to_mathptn(raw_text)
        images = st.session_state.get("ocr_images", [])
        tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
        with tab1:
            st.markdown("#### 📋 Kết quả OCR PDF:")
            st.text_area("Kết quả OCR PDF:", text_content, height=350, label_visibility="collapsed")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📄 Tải văn bản (TXT)",
                    text_content,
                    file_name="ket_qua_ocr.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            with col2:
                word_btn = st.button("📝 Tạo và tải file Word", use_container_width=True, key="word")
                if word_btn:
                    with st.spinner("Đang tạo file Word..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                            insert_images_to_word_from_markdown(text_content, images, tmp_word.name)
                        with open(tmp_word.name, "rb") as f:
                            word_data = f.read()
                        st.success("✅ Đã tạo file Word thành công!")
                        st.download_button(
                            "⬇️ Tải về file Word",
                            word_data,
                            file_name="ket_qua_ocr.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
                        os.remove(tmp_word.name)
        with tab2:
            if images:
                st.success(f"🖼️ Đã tìm thấy {len(images)} hình ảnh:")
                for idx, fig in enumerate(images):
                    try:
                        img_bytes = base64.b64decode(fig["base64"])
                        st.image(img_bytes, caption=fig["name"], use_container_width=True)
                        st.download_button(
                            f"Tải {fig['name']}",
                            img_bytes,
                            file_name=fig["name"],
                            mime="image/jpeg",
                            use_container_width=True,
                            key=f"pdf-download-{fig['name']}-{idx}"
                        )
                    except Exception as e:
                        st.error(f"Không đọc được ảnh {fig['name']}: {e}")
            else:
                st.warning("Không tìm thấy ảnh minh hoạ thực sự trong PDF!")
    st.markdown("---")

st.caption("✨ Mapping bảng/tách hình tự động, chuẩn layout, tách đúng bảng giá trị, bảng tần số, bảng biến thiên. Xuất Word mapping đúng vị trí minh hoạ & bảng.")
