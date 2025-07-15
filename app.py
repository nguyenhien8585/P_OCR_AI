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
            "minh họa", "hình bên", "hình minh hoạ", "hình minh họa" 
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
                    "keyword_lines": [] 
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
        # Tìm từ khóa trong một "cửa sổ" xung quanh dòng hiện tại
        # Ví dụ: 3 dòng trước và 3 dòng sau
        search_window_size = 3 
        
        for i in range(q_block["start_line"], q_block["end_line"] + 1):
            # Tạo ngữ cảnh cho dòng hiện tại
            context_lines = []
            for j in range(max(0, i - search_window_size), min(len(lines), i + search_window_size + 1)):
                context_lines.append(lines[j].lower())
            context_text = " ".join(context_lines)

            if any(kw in context_text for kw in keywords) or any(kw in context_text for kw in table_kw):
                q_block["keyword_lines"].append(i)
        
        # Thêm vị trí của placeholder từ Gemini nếu có
        for i in range(q_block["start_line"], q_block["end_line"] + 1):
            if "[HÌNH_PLACEHOLDER]" in lines[i] or "[BẢNG_PLACEHOLDER]" in lines[i]:
                q_block["keyword_lines"].append(i) 
        q_block["keyword_lines"] = sorted(list(set(q_block["keyword_lines"]))) 

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
            q_end_y = (q_block["end_line"] + 1) * (img_h / len(lines)) 
            
            # Thêm một khoảng đệm nhỏ cho phạm vi Y của câu hỏi
            padding_y = img_h * 0.05 # 5% chiều cao ảnh làm đệm
            
            if (q_start_y - padding_y) <= fig_y_center <= (q_end_y + padding_y):
                if dist < min_y_dist:
                    min_y_dist = dist
                    best_q_match = q_block["num"]
        
        if best_q_match:
            figure_to_question_map[fig["name"]] = best_q_match
        else:
            pass # Để hình ảnh không được gán, sẽ chèn vào cuối

    # Bước 3: Xây dựng lại văn bản, chèn hình ảnh vào vị trí tối ưu trong khối câu hỏi
    current_buffer = ""
    
    for idx, line in enumerate(lines):
        line_strip = line.strip()
        
        # Kiểm tra xem dòng hiện tại có phải là đầu một câu hỏi mới không
        is_new_question_start = re.match(r"^Câu\s*\d+\.?", line_strip)
        
        # Kiểm tra xem buffer hiện tại có kết thúc một câu hoàn chỉnh không
        buffer_ends_sentence = re.search(r'[.!?…:]\s*$', current_buffer.strip())

        # Điều kiện để flush buffer và bắt đầu đoạn mới
        # Flush khi:
        # 1. Dòng hiện tại là đầu câu hỏi mới
        # 2. Dòng hiện tại là dòng trống
        # 3. Buffer hiện tại kết thúc bằng dấu câu VÀ dòng hiện tại không phải là phần tiếp theo của câu đó
        # (ví dụ: không phải là một từ trong câu)
        if current_buffer and (is_new_question_start or not line_strip or buffer_ends_sentence):
            final_processed_lines.append(current_buffer.strip())
            current_buffer = ""
        
        # Thêm dòng hiện tại vào buffer
        if line_strip:
            if current_buffer and not is_new_question_start and not buffer_ends_sentence:
                current_buffer += " " + line_strip
            else:
                current_buffer = line_strip
        elif not line_strip: # Nếu là dòng trống
            if current_buffer:
                final_processed_lines.append(current_buffer.strip())
                current_buffer = ""
            final_processed_lines.append("") # Giữ dòng trống

        # Logic chèn hình ảnh tại vị trí ngữ cảnh
        # Tìm khối câu hỏi mà dòng hiện tại thuộc về
        current_q_block = None
        for q_block in question_blocks:
            if q_block["start_line"] <= idx <= q_block["end_line"]:
                current_q_block = q_block
                break
        
        if current_q_block:
            # Lấy các hình ảnh thuộc về câu hỏi này và chưa được chèn
            figs_for_this_q_uninserted = [f for f in available_figures if f is not None and figure_to_question_map.get(f["name"]) == current_q_block["num"] and f["name"] not in inserted_figures_names]
            figs_for_this_q_uninserted.sort(key=lambda f: (f['bbox'][1], f['bbox'][0]))

            # Kiểm tra các điểm chèn cụ thể trong dòng hiện tại
            # Ưu tiên placeholder
            if "[HÌNH_PLACEHOLDER]" in line_strip or "[BẢNG_PLACEHOLDER]" in line_strip:
                fig_to_insert_now = None
                if "[HÌNH_PLACEHOLDER]" in line_strip:
                    for i, fig in enumerate(figs_for_this_q_uninserted):
                        if not fig["is_table"]:
                            fig_to_insert_now = fig
                            available_figures[available_figures.index(fig)] = None # Đánh dấu đã dùng
                            break
                elif "[BẢNG_PLACEHOLDER]" in line_strip:
                    for i, fig in enumerate(figs_for_this_q_uninserted):
                        if fig["is_table"]:
                            fig_to_insert_now = fig
                            available_figures[available_figures.index(fig)] = None # Đánh dấu đã dùng
                            break
                
                if fig_to_insert_now:
                    # Thay thế placeholder trong buffer hiện tại
                    if fig_to_insert_now["is_table"]:
                        current_buffer = current_buffer.replace("[BẢNG_PLACEHOLDER]", f"[BẢNG: {fig_to_insert_now['name']}]")
                    else:
                        current_buffer = current_buffer.replace("[HÌNH_PLACEHOLDER]", f"[HÌNH: {fig_to_insert_now['name']}]")
                    inserted_figures_names.add(fig_to_insert_now["name"])
            
            # Sau đó là từ khóa mạnh
            elif idx in current_q_block["keyword_lines"] and not re.search(r'\[(HÌNH|BẢNG):.*?\]', current_buffer): # Chỉ chèn nếu chưa có hình/bảng ở buffer này
                best_fig_for_keyword = None
                min_dist_for_keyword = float('inf')
                
                current_line_y_center = idx * (img_h / len(lines))

                for fig in figs_for_this_q_uninserted:
                    if fig is None: continue
                    
                    fig_y_center = fig['bbox'][1] + fig['bbox'][3] / 2
                    dist = abs(fig_y_center - current_line_y_center)

                    line_lower = line_strip.lower()
                    if ((fig["is_table"] and any(kw in line_lower for kw in table_kw)) or
                        (not fig["is_table"] and any(kw in line_lower for kw in keywords))):
                        if dist < min_dist_for_keyword:
                            min_dist_for_keyword = dist
                            best_fig_for_keyword = fig
                
                if best_fig_for_keyword:
                    # Flush buffer và chèn hình ảnh vào dòng mới
                    if current_buffer:
                        final_processed_lines.append(current_buffer.strip())
                        current_buffer = ""
                    
                    if best_fig_for_keyword["is_table"]:
                        final_processed_lines.append(f"[BẢNG: {best_fig_for_keyword['name']}]")
                    else:
                        final_processed_lines.append(f"[HÌNH: {best_fig_for_keyword['name']}]")
                    inserted_figures_names.add(best_fig_for_keyword["name"])
                    available_figures[available_figures.index(best_fig_for_keyword)] = None # Đánh dấu đã dùng

    # Flush buffer cuối cùng sau khi duyệt hết tất cả các dòng
    if current_buffer:
        final_processed_lines.append(current_buffer.strip())

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
            st.write(f"**Loại file:** {mime_file.type}")
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
