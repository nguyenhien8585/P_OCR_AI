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
def extract_figures_and_tables(img_bytes, min_area_abs=1400, max_figures=10):
    img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    blur = cv2.GaussianBlur(gray, (3,3), 0)
    th = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 25, 10)
    
    # Tách bảng bằng morphology line horizontal + vertical
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (int(w*0.18),1))
    detected_lines = cv2.morphologyEx(th, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,int(h*0.08)))
    detected_columns = cv2.morphologyEx(th, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    table_mask = cv2.addWeighted(detected_lines, 0.5, detected_columns, 0.5, 0.0)
    
    # Find table contours
    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tables = []
    table_count = 0 # <-- Thêm bộ đếm riêng cho bảng
    for cnt in contours: # Không dùng enumerate ở đây
        x, y, ww, hh = cv2.boundingRect(cnt)
        area = ww * hh
        if area > min_area_abs and ww > 40 and hh > 20:
            crop = img[y:y+hh, x:x+ww]
            buf = io.BytesIO()
            Image.fromarray(crop).save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            tables.append({"name": f"table-{table_count}.jpeg", "base64": b64, "is_table": True, "bbox": (x, y, ww, hh)})
            table_count += 1 # Tăng bộ đếm khi thêm bảng

    # Tách hình minh hoạ (contour không phải bảng)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    figures = []
    figure_count = 0 # <-- Thêm bộ đếm riêng cho hình ảnh
    for cnt in contours: # Không dùng enumerate ở đây
        x, y, ww, hh = cv2.boundingRect(cnt)
        area = ww * hh
        if area > min_area_abs and ww > 50 and hh > 50:
            # Loại bỏ vùng bảng đã nhận phía trên
            overlapped = False
            for t in tables:
                tb_x, tb_y, tb_w, tb_h = t['bbox'] 
                if abs(tb_x-x)<12 and abs(tb_y-y)<12 and abs(tb_w-ww)<25 and abs(tb_h-hh)<25:
                    overlapped = True
                    break
            if not overlapped:
                crop = img[y:y+hh, x:x+ww]
                buf = io.BytesIO()
                Image.fromarray(crop).save(buf, format="JPEG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                figures.append({"name": f"img-{figure_count}.jpeg", "base64": b64, "is_table": False})
                figure_count += 1 # Tăng bộ đếm khi thêm hình ảnh
    return tables + figures

def remove_all_figure_markdown(text):
    """
    Loại bỏ các markdown hình ảnh/bảng cũ hoặc placeholder không mong muốn.
    """
    if not isinstance(text, str): return ""
    # Loại bỏ các định dạng cũ nếu Gemini vẫn tạo ra
    text = re.sub(r'!\[img-\d+\.jpeg\]\(img-\d+\.jpeg\)', '', text)
    text = re.sub(r'\[HÌNH:.*?\]', '', text) # Loại bỏ placeholder cũ nếu có
    text = re.sub(r'\[BẢNG:.*?\]', '', text) # Loại bỏ placeholder cũ nếu có
    # Loại bỏ các placeholder mới nếu chúng không được xử lý đúng cách
    text = re.sub(r'\[HÌNH_PLACEHOLDER\]', '', text)
    text = re.sub(r'\[BẢNG_PLACEHOLDER\]', '', text)
    return text

# -------- Mapping nâng cao (tách đúng đoạn, không chen giữa câu) --------
def join_paragraphs_and_insert_figures_tables(text, figures, keywords=None, table_kw=None):
    """
    Nối các đoạn văn bản và chèn hình ảnh/bảng vào đúng vị trí.
    Ưu tiên thay thế các placeholder do Gemini tạo ra, sau đó chèn bổ sung
    dựa trên từ khóa và heuristic nếu cần.
    """
    if keywords is None:
        keywords = [
            "xem hình", "hình dưới", "hình vẽ", "biểu đồ", "minh hoạ",
            "minh họa", "bảng dưới", "hình bên", "hình minh hoạ", "hình minh họa"
        ]
    if table_kw is None:
        table_kw = [
            "bảng biến thiên", "bảng giá trị", "bảng tần số", "bảng sau", "bảng dưới"
        ]
    
    lines = [l.rstrip() for l in text.split('\n')]
    processed_lines = []
    fig_idx = 0 # Chỉ số cho danh sách figures đã tách
    n_fig = len(figures)
    
    buffer = "" # Buffer để xây dựng các đoạn văn bản
    
    for idx, line in enumerate(lines):
        line_strip = line.strip()

        # --- Xử lý Placeholder từ Gemini ---
        # Nếu dòng chứa placeholder do Gemini tạo ra, ưu tiên xử lý nó
        if "[HÌNH_PLACEHOLDER]" in line_strip or "[BẢNG_PLACEHOLDER]" in line_strip:
            if buffer: # Nếu có nội dung trong buffer, thêm nó vào processed_lines trước
                processed_lines.append(buffer.strip())
                buffer = ""
            
            # Thay thế placeholder bằng hình ảnh/bảng thực tế từ danh sách figures
            if "[HÌNH_PLACEHOLDER]" in line_strip and fig_idx < n_fig and not figures[fig_idx]["is_table"]:
                processed_lines.append(line_strip.replace("[HÌNH_PLACEHOLDER]", f"[HÌNH: {figures[fig_idx]['name']}]"))
                fig_idx += 1
            elif "[BẢNG_PLACEHOLDER]" in line_strip and fig_idx < n_fig and figures[fig_idx]["is_table"]:
                processed_lines.append(line_strip.replace("[BẢNG_PLACEHOLDER]", f"[BẢNG: {figures[fig_idx]['name']}]"))
                fig_idx += 1
            else: 
                # Nếu placeholder không khớp với hình/bảng tiếp theo, hoặc không còn hình/bảng
                # Loại bỏ placeholder không được thay thế
                processed_lines.append(line_strip.replace("[HÌNH_PLACEHOLDER]", "").replace("[BẢNG_PLACEHOLDER]", "").strip())
            continue # Đã xử lý dòng này, chuyển sang dòng tiếp theo

        # --- Xử lý các dòng văn bản thông thường ---
        # Nếu dòng là dấu phân cách hoặc trống, kết thúc đoạn hiện tại
        if not line_strip or re.match(r"^(HẾT|Trang|Mã đề|----+)$", line_strip):
            if buffer:
                processed_lines.append(buffer.strip())
                buffer = ""
            processed_lines.append(line_strip)
            continue

        # Kiểm tra xem đây có phải là một câu hỏi mới không
        is_new_question = re.match(r"^Câu\s*\d+\.?", line_strip)

        # Nếu buffer đã có nội dung và kết thúc bằng một câu hoàn chỉnh (dấu câu)
        # hoặc nếu đây là một câu hỏi mới, thì kết thúc đoạn hiện tại
        if buffer and (re.search(r"[.!?…:]$", buffer) or is_new_question):
            processed_lines.append(buffer.strip())
            buffer = "" # Reset buffer sau khi thêm đoạn

        # Thêm dòng hiện tại vào buffer
        if buffer:
            buffer += " " + line_strip
        else:
            buffer = line_strip

        lower_buffer = buffer.lower()

        # --- Logic chèn hình/bảng dựa trên từ khóa (bổ sung nếu Gemini không chèn) ---
        # Chỉ chèn nếu chưa có hình/bảng nào được chèn ở vị trí này trong buffer
        # và còn hình/bảng trong danh sách figures
        
        # Kiểm tra xem đã có hình/bảng nào được chèn ở các dòng gần đây chưa
        # (để tránh chèn lặp nếu logic từ khóa đã chèn)
        already_inserted_near = False
        if processed_lines:
            # Kiểm tra dòng cuối cùng đã được thêm vào processed_lines
            last_line = processed_lines[-1]
            if re.search(r'\[(HÌNH|BẢNG):.*?\]', last_line):
                already_inserted_near = True

        if not already_inserted_near and fig_idx < n_fig:
            # Ưu tiên chèn bảng nếu có từ khóa bảng và bảng còn
            if figures[fig_idx]["is_table"] and any(kw in lower_buffer for kw in table_kw):
                processed_lines.append(buffer.strip()) # Thêm đoạn văn bản trước khi chèn bảng
                processed_lines.append(f"[BẢNG: {figures[fig_idx]['name']}]")
                fig_idx += 1
                buffer = "" # Reset buffer sau khi chèn
            # Ưu tiên chèn hình nếu có từ khóa hình và hình còn
            elif not figures[fig_idx]["is_table"] and any(kw in lower_buffer for kw in keywords):
                processed_lines.append(buffer.strip()) # Thêm đoạn văn bản trước khi chèn hình
                processed_lines.append(f"[HÌNH: {figures[fig_idx]['name']}]")
                fig_idx += 1
                buffer = "" # Reset buffer sau khi chèn
            # Heuristic cho câu hỏi mới nếu chưa có từ khóa cụ thể
            # Điều chỉnh heuristic này để chỉ chèn nếu dòng hiện tại là một câu hỏi
            # và chưa có hình/bảng nào được chèn ngay sau nó
            elif is_new_question:
                # Nếu là câu hỏi mới và chưa có từ khóa cụ thể, chèn hình/bảng tiếp theo
                # (có thể tinh chỉnh thêm điều kiện ở đây nếu muốn chặt chẽ hơn)
                if figures[fig_idx]["is_table"]:
                    processed_lines.append(f"[BẢNG: {figures[fig_idx]['name']}]")
                else:
                    processed_lines.append(f"[HÌNH: {figures[fig_idx]['name']}]")
                fig_idx += 1
                # Reset buffer để đảm bảo ảnh nằm trên dòng riêng sau câu hỏi
                buffer = "" 

    # --- Xử lý buffer cuối cùng và các hình/bảng còn lại ---
    if buffer:
        processed_lines.append(buffer.strip())

    # Chèn các hình/bảng còn lại ở cuối tài liệu nếu chưa được chèn
    while fig_idx < n_fig:
        if figures[fig_idx]["is_table"]:
            processed_lines.append(f"[BẢNG: {figures[fig_idx]['name']}]")
        else:
            processed_lines.append(f"[HÌNH: {figures[fig_idx]['name']}]")
        fig_idx += 1
    
    # Lọc bỏ các dòng trống không cần thiết và trả về văn bản đã xử lý
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
                figures = extract_figures_and_tables(img_bytes)
                api_key = get_next_api_key()
                with st.spinner("Đang nhận diện..."):
                    try:
                        text = gemini_generate_text(img_bytes, api_key)
                    except Exception as e:
                        text = f"[Lỗi Gemini: {e}]"
                
                # Loại bỏ các markdown/placeholder cũ hoặc không mong muốn từ Gemini
                text = remove_all_figure_markdown(text) 
                
                # Chèn hình ảnh/bảng đã tách vào văn bản
                text = join_paragraphs_and_insert_figures_tables(text, figures)
                
                # Lưu vào session
                st.session_state[text_key] = text
                st.session_state[fig_key] = figures

            # Nếu đã xử lý => Hiện kết quả và cho phép xuất Word
            if text_key in st.session_state and fig_key in st.session_state:
                st.markdown("### 📋 Kết quả mapping nâng cao:")
                st.code(st.session_state[text_key], language="markdown")
                figures = st.session_state[fig_key]

                if figures:
                    if st.button("📝 Tạo và tải file Word giữ hình & bảng đúng vị trí", key=f"word-{img_file.name}-{img_idx}"):
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
                    st.markdown("### 🖼️ Hình & Bảng đã tách:")
                    for idx, fig in enumerate(figures):
                        img_bytes = base64.b64decode(fig["base64"])
                        cap = f"{'Bảng' if fig['is_table'] else 'Hình'}: {fig['name']}"
                        st.image(img_bytes, caption=cap, width=350)
                        st.download_button(
                            f"Tải {fig['name']}",
                            img_bytes,
                            file_name=fig["name"],
                            mime="image/jpeg",
                            use_container_width=True,
                            key=f"anh-download-{fig['name']}-{idx}-{img_file.name}"
                        )
                else:
                    st.info("Không phát hiện minh hoạ hay bảng nào trong ảnh.")
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
                result = client.convert(pdf_bytes, file_name, mime_type)
                images = extract_images_from_pdf(pdf_bytes)
            if not result.get("success"):
                st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
                st.stop()
            st.session_state["ocr_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_images"] = images
            st.session_state["ocr_done"] = True
            st.success("✅ Đã nhận diện PDF thành công!")
    if st.session_state.get("ocr_done"):
        def dollar_to_mathptn(s):
            # Chuyển đổi $...$ thành ${...}$ để đảm bảo định dạng LaTeX nhất quán
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
                for idx, img in enumerate(images):
                    try:
                        img_bytes = base64.b64decode(img["base64"])
                        st.image(img_bytes, caption=img["name"], use_container_width=True)
                        st.download_button(
                            f"Tải {img['name']}",
                            img_bytes,
                            file_name=img["name"],
                            mime="image/jpeg",
                            use_container_width=True,
                            key=f"pdf-download-{img['name']}-{idx}"
                        )
                    except Exception as e:
                        st.error(f"Không đọc được ảnh {img['name']}: {e}")
            else:
                st.warning("Không tìm thấy ảnh minh hoạ thực sự trong PDF!")
    st.markdown("---")

st.caption("✨ Mapping bảng/tách hình tự động, chuẩn layout, tách đúng bảng giá trị, bảng tần số, bảng biến thiên. Xuất Word mapping đúng vị trí minh hoạ & bảng.")
