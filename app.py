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
def extract_figures_and_tables(img_bytes, min_area_ratio=0.005, min_area_abs=1500, min_w=50, min_h=50, max_figures=8):
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
        if area < min_area_abs or area_ratio < min_area_ratio or area_ratio > 0.6: # Điều chỉnh ngưỡng tối đa
            continue
        
        # Lọc theo kích thước tối thiểu
        if ww < min_w or hh < min_h:
            continue

        # Lọc theo tỷ lệ khung hình hợp lý cho hình ảnh/bảng
        if not (0.1 < aspect < 12.0): # Phạm vi rộng hơn một chút
            continue

        # Không lấy vùng quá sát mép giấy (chừa 1.5% mép)
        if x < 0.015*w or y < 0.015*h or (x+ww) > 0.985*w or (y+hh) > 0.985*h:
            continue
        
        # Logic nhận dạng bảng: chiều rộng lớn, tỷ lệ khung hình rộng
        # Cân nhắc lại ngưỡng cho bảng, có thể cần linh hoạt hơn
        is_table = (ww > 0.2*w and hh > 0.04*h and aspect > 2.0 and aspect < 10.0) 
        
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

# Helper function to find the best matching figure
def find_best_matching_figure(figures_pool, is_table_needed, current_line_lower, keywords, table_kw):
    """
    Tìm hình ảnh/bảng phù hợp nhất từ pool dựa trên loại và từ khóa.
    Ưu tiên khớp loại (bảng/hình ảnh) và sau đó là từ khóa.
    """
    # Tìm kiếm chính xác loại và từ khóa
    for fig in figures_pool:
        if fig["is_table"] == is_table_needed:
            if (is_table_needed and any(kw in current_line_lower for kw in table_kw)) or \
               (not is_table_needed and any(kw in current_line_lower for kw in keywords)):
                return fig
            
    return None

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
            "minh họa", "hình bên", "hình minh hoạ", "hình minh họa" 
        ]
    if table_kw is None:
        table_kw = [
            "bảng biến thiên", "bảng giá trị", "bảng tần số", "bảng sau", "bảng dưới"
        ]
    
    lines = [l.rstrip() for l in text.split('\n')]
    processed_lines = []
    
    inserted_figures_names = set()
    
    buffer = "" 
    
    # Tạo một bản sao của danh sách figures để dễ dàng quản lý các hình đã được chèn
    available_figures = list(figures) 
    
    # Sắp xếp lại available_figures theo vị trí để xử lý tuần tự
    available_figures.sort(key=lambda f: (f['bbox'][1], f['bbox'][0]))

    # Bước 1: Phân tích văn bản để xác định các khối câu hỏi và vị trí từ khóa
    question_blocks = [] # List of (question_number, start_line_idx, end_line_idx, [keyword_line_indices])
    current_question_num = None
    current_question_start_line = 0
    
    for idx, line in enumerate(lines):
        match_q = re.match(r"^Câu\s*(\d+)\.?", line.strip())
        if match_q:
            if current_question_num is not None:
                question_blocks.append({
                    "num": current_question_num,
                    "start_line": current_question_start_line,
                    "end_line": idx - 1,
                    "keyword_lines": [] # Sẽ điền sau
                })
            current_question_num = int(match_q.group(1))
            current_question_start_line = idx
        
        # Xử lý dòng cuối cùng hoặc khi gặp "HẾT"
        if idx == len(lines) - 1 or re.match(r"^(HẾT|Trang|Mã đề|----+)$", line.strip()):
            if current_question_num is not None:
                question_blocks.append({
                    "num": current_question_num,
                    "start_line": current_question_start_line,
                    "end_line": idx,
                    "keyword_lines": []
                })
            current_question_num = None # Reset
    
    # Điền keyword_lines cho từng khối câu hỏi
    for q_block in question_blocks:
        for i in range(q_block["start_line"], q_block["end_line"] + 1):
            line_content = lines[i].lower()
            if any(kw in line_content for kw in keywords) or any(kw in line_content for kw in table_kw):
                q_block["keyword_lines"].append(i)
        # Thêm vị trí của placeholder từ Gemini nếu có
        for i in range(q_block["start_line"], q_block["end_line"] + 1):
            if "[HÌNH_PLACEHOLDER]" in lines[i] or "[BẢNG_PLACEHOLDER]" in lines[i]:
                q_block["keyword_lines"].append(i) # Coi placeholder là một dạng keyword line
        q_block["keyword_lines"] = sorted(list(set(q_block["keyword_lines"]))) # Loại bỏ trùng lặp và sắp xếp

    # Bước 2: Gán hình ảnh cho các khối câu hỏi
    figure_to_question_map = {} # {figure_name: question_number}
    
    for fig in available_figures:
        if fig is None: continue
        
        fig_y_center = fig['bbox'][1] + fig['bbox'][3] / 2
        
        best_q_match = None
        min_y_dist = float('inf')
        
        for q_block in question_blocks:
            q_block_y_center = (q_block["start_line"] + q_block["end_line"]) / 2 * (img_h / len(lines))
            dist = abs(fig_y_center - q_block_y_center)
            
            # Kiểm tra xem hình ảnh có nằm trong phạm vi Y của câu hỏi không
            q_start_y = q_block["start_line"] * (img_h / len(lines))
            q_end_y = (q_block["end_line"] + 1) * (img_h / len(lines)) # +1 để bao gồm cả dòng cuối
            
            if q_start_y <= fig_y_center <= q_end_y:
                if dist < min_y_dist:
                    min_y_dist = dist
                    best_q_match = q_block["num"]
        
        if best_q_match:
            figure_to_question_map[fig["name"]] = best_q_match
        else:
            # Nếu không khớp với câu hỏi nào, gán cho câu hỏi gần nhất (hoặc để sau)
            # Tạm thời để nó không được gán, sẽ chèn vào cuối
            pass

    # Bước 3: Xây dựng lại văn bản, chèn hình ảnh vào vị trí tối ưu trong khối câu hỏi
    figures_inserted_in_text = set() # Theo dõi các hình đã chèn vào văn bản
    
    for q_block in question_blocks:
        q_start_line = q_block["start_line"]
        q_end_line = q_block["end_line"]
        
        # Lấy các hình ảnh thuộc về câu hỏi này
        figs_for_this_q = [f for f in available_figures if f is not None and figure_to_question_map.get(f["name"]) == q_block["num"]]
        figs_for_this_q.sort(key=lambda f: (f['bbox'][1], f['bbox'][0])) # Sắp xếp theo vị trí

        # Tạo một danh sách các điểm chèn cụ thể trong khối câu hỏi này
        # (line_idx, type, fig_obj)
        q_insertion_points = []

        # Ưu tiên placeholder từ Gemini
        for line_idx in range(q_start_line, q_end_line + 1):
            line_content = lines[line_idx]
            if "[HÌNH_PLACEHOLDER]" in line_content:
                q_insertion_points.append((line_idx, 'placeholder_img'))
            elif "[BẢNG_PLACEHOLDER]" in line_content:
                q_insertion_points.append((line_idx, 'placeholder_table'))
        
        # Sau đó là các dòng có từ khóa
        for line_idx in q_block["keyword_lines"]:
            if line_idx not in [p[0] for p in q_insertion_points]: # Tránh trùng lặp với placeholder
                q_insertion_points.append((line_idx, 'keyword'))
        
        # Sắp xếp các điểm chèn theo thứ tự dòng
        q_insertion_points.sort(key=lambda x: x[0])

        # Thực hiện chèn hình ảnh vào khối câu hỏi
        current_q_buffer = []
        figs_to_insert_in_q = list(figs_for_this_q) # Bản sao để quản lý

        for line_idx in range(q_start_line, q_end_line + 1):
            line_content = lines[line_idx]
            current_q_buffer.append(line_content)

            # Kiểm tra xem có điểm chèn nào ở dòng này không
            for p_idx, (p_line_idx, p_type) in enumerate(q_insertion_points):
                if p_line_idx == line_idx:
                    # Tìm hình ảnh phù hợp nhất để chèn vào điểm này
                    fig_to_insert_now = None
                    
                    if p_type == 'placeholder_img':
                        for i, fig in enumerate(figs_to_insert_in_q):
                            if fig is not None and not fig["is_table"]:
                                fig_to_insert_now = fig
                                figs_to_insert_in_q[i] = None
                                break
                    elif p_type == 'placeholder_table':
                        for i, fig in enumerate(figs_to_insert_in_q):
                            if fig is not None and fig["is_table"]:
                                fig_to_insert_now = fig
                                figs_to_insert_in_q[i] = None
                                break
                    elif p_type == 'keyword':
                        # Tìm hình ảnh gần nhất về mặt vật lý và khớp loại/từ khóa
                        best_fig_for_keyword = None
                        min_dist_for_keyword = float('inf')
                        
                        current_line_y_center = line_idx * (img_h / len(lines))

                        for i, fig in enumerate(figs_to_insert_in_q):
                            if fig is None: continue
                            
                            fig_y_center = fig['bbox'][1] + fig['bbox'][3] / 2
                            dist = abs(fig_y_center - current_line_y_center)

                            line_lower = line_content.lower()
                            if ((fig["is_table"] and any(kw in line_lower for kw in table_kw)) or
                                (not fig["is_table"] and any(kw in line_lower for kw in keywords))):
                                if dist < min_dist_for_keyword:
                                    min_dist_for_keyword = dist
                                    best_fig_for_keyword = fig
                                    best_fig_for_keyword_idx = i
                        
                        if best_fig_for_keyword:
                            fig_to_insert_now = best_fig_for_keyword
                            figs_to_insert_in_q[best_fig_for_keyword_idx] = None

                    if fig_to_insert_now:
                        # Thay thế placeholder hoặc chèn vào sau dòng
                        if "[HÌNH_PLACEHOLDER]" in current_q_buffer[-1]:
                            current_q_buffer[-1] = current_q_buffer[-1].replace("[HÌNH_PLACEHOLDER]", f"[HÌNH: {fig_to_insert_now['name']}]")
                        elif "[BẢNG_PLACEHOLDER]" in current_q_buffer[-1]:
                            current_q_buffer[-1] = current_q_buffer[-1].replace("[BẢNG_PLACEHOLDER]", f"[BẢNG: {fig_to_insert_now['name']}]")
                        else:
                            # Chèn vào dòng mới sau dòng hiện tại
                            if fig_to_insert_now["is_table"]:
                                current_q_buffer.append(f"[BẢNG: {fig_to_insert_now['name']}]")
                            else:
                                current_q_buffer.append(f"[HÌNH: {fig_to_insert_now['name']}]")
                        figures_inserted_in_text.add(fig_to_insert_now["name"])
        
        # Thêm các dòng đã xử lý của khối câu hỏi vào processed_lines
        processed_lines.extend(current_q_buffer)
        
        # Chèn bất kỳ hình ảnh nào còn lại trong khối câu hỏi này vào cuối khối
        for fig in figs_to_insert_in_q:
            if fig is not None and fig["name"] not in figures_inserted_in_text:
                if fig["is_table"]:
                    processed_lines.append(f"[BẢNG: {fig['name']}]")
                else:
                    processed_lines.append(f"[HÌNH: {fig['name']}]")
                figures_inserted_in_text.add(fig["name"])

    # Bước 4: Xử lý các dòng không thuộc câu hỏi và các hình ảnh còn lại
    # Thêm các dòng không thuộc câu hỏi vào processed_lines
    last_processed_line_idx = -1
    if processed_lines:
        # Tìm dòng cuối cùng đã được xử lý từ các khối câu hỏi
        # Đây là một cách đơn giản, có thể cần phức tạp hơn nếu có các đoạn văn bản không phải câu hỏi xen kẽ
        for q_block in question_blocks:
            if q_block["end_line"] > last_processed_line_idx:
                last_processed_line_idx = q_block["end_line"]
    
    # Thêm các dòng từ sau khối câu hỏi cuối cùng đến hết tài liệu
    for line_idx in range(last_processed_line_idx + 1, len(lines)):
        processed_lines.append(lines[line_idx])

    # Chèn các hình/bảng còn lại ở cuối tài liệu nếu chưa được chèn
    remaining_figures = sorted([f for f in figures if f['name'] not in figures_inserted_in_text and 'bbox' in f], key=lambda f: (f['bbox'][1], f['bbox'][0]))
    for fig in remaining_figures:
        if fig["is_table"]:
            processed_lines.append(f"[BẢNG: {fig['name']}]")
        else:
            processed_lines.append(f"[HÌNH: {fig['name']}]")
        figures_inserted_in_text.add(fig["name"]) 
    
    return '\n'.join([l for l in processed_lines if l.strip()])

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
1. Đọc và gõ lại TẤT CẢ văn bản trong ảnh.
2. Nếu phát hiện nhiều hình minh hoạ (hình vẽ, đồ thị, bảng, ...), hãy đánh dấu đúng vị trí từng hình bằng cú pháp placeholder: `[HÌNH_PLACEHOLDER]` cho hình ảnh và `[BẢNG_PLACEHOLDER]` cho bảng.
3. Với mỗi placeholder, hãy chèn nó ngay sau dòng mô tả có từ “xem hình dưới”, “hình dưới đây”, “bảng biến thiên”, “bảng tần số”, “bảng giá trị”, “hình vẽ”, “biểu đồ”, hoặc ngay sau dòng câu hỏi liên quan tới hình/bảng/biểu đồ đó.
4. Giữ nguyên cấu trúc đoạn văn và xuống dòng.
5. Công thức toán học: tất cả ở dạng ${...}$ (inline, hệ, ký hiệu ... như hướng dẫn chi tiết).
6. Bảng biểu: dùng markdown nếu có thể.
7. Dạng bài: Trắc nghiệm, Đúng/Sai, Tự luận: đúng định dạng như ví dụ.
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
