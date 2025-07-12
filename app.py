import streamlit as st
from app_config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_figures_from_image_pillow import extract_figures_from_image
from word_export import insert_images_to_word_from_markdown
import os
import base64
import re
from PyPDF2 import PdfReader
import tempfile
from PIL import Image
import io

st.set_page_config(page_title="OCR PDF & Image", layout="centered")

tab1, tab2 = st.tabs([
    "📄 OCR PDF",
    "🖼️ OCR Image"
])

# ----------- HÀM FILTER TOÁN HỌC TỐI ƯU ----------
def format_math_ocr(text):
    # Bỏ các dấu *, # dư thừa
    text = text.replace("*", "").replace("#", "")
    # Danh sách loại trừ không bọc
    excluded_keywords = [
        "BỘ GIÁO DỤC VÀ ĐÀO TẠO", "KỲ THI", "ĐỀ THI", "Môn thi", "Họ, tên thí sinh",
        "Sổ báo danh", "Mã đề", "Trang", "Thời gian làm bài", "PHẦN", "Bảng", "BẢNG"
    ]
    def should_exclude(line):
        for kw in excluded_keywords:
            if line.strip().startswith(kw): return True
        if re.match(r'^\s*Trang\b', line): return True
        if re.match(r'^\s*Mã đề\b', line): return True
        return False
    def is_choice_line(line):
        return re.match(r"^\s*[ABCD]\.", line) or re.match(r"^\s*[ABCD]\s*[).]", line)
    # Regex cho công thức toán học, điểm, số, ký hiệu
    math_pattern = r'(?<![\w\$])([A-Z][\.A-Z\'\d]*|Oxyz|n̄|[0-9]+(?:/[0-9]+)?|f\(x\)|P|OA|OB|OC|AB|AC|BC|A\'|B\'|C\'|x|y|z|t|n|C|ad|bc|ac|(-?\d+))(?![\w\$])'
    lines = text.split("\n")
    output = []
    for line in lines:
        l = line.strip()
        if should_exclude(l) or is_choice_line(l) or l == "":
            output.append(l)
        else:
            # Xử lý Câu 1: ... giữ nguyên số thứ tự không bọc
            m = re.match(r'^(Câu\s*\d+[:：])\s*(.*)', l)
            if m:
                header, rest = m.groups()
                formatted = re.sub(math_pattern, lambda m: "${}$".format(m.group(0)), rest)
                output.append(f"{header} {formatted}".strip())
            else:
                formatted = re.sub(math_pattern, lambda m: "${}$".format(m.group(0)), l)
                output.append(formatted)
    return "\n".join(output)

# ================ TAB 1: OCR PDF ==================
with tab1:
    st.markdown("### 📄 OCR cho file PDF")
    uploaded_pdf = st.file_uploader("Chọn file PDF để xử lý OCR", type=["pdf"])
    num_pages = None

    if uploaded_pdf:
        pdf_bytes = uploaded_pdf.read()
        file_name = uploaded_pdf.name
        mime_type = "application/pdf"
        size_mb = len(pdf_bytes) / (1024 * 1024)

        try:
            uploaded_pdf.seek(0)
            reader = PdfReader(uploaded_pdf)
            num_pages = len(reader.pages)
            uploaded_pdf.seek(0)
        except:
            num_pages = "?"

        with st.expander("ℹ️ Thông tin file", expanded=True):
            st.write(f"**Tên file:** {file_name}")
            st.write(f"**Loại file:** {mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")
            st.write(f"**Số trang:** {num_pages}")

    if uploaded_pdf:
        if st.button("🚀 Xử lý OCR PDF", key="ocr_pdf_btn", use_container_width=True):
            st.info("⏳ Đang xử lý OCR PDF... (quá trình này có thể mất vài phút)")
            with st.spinner("Đang nhận diện văn bản và tách ảnh minh hoạ..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                uploaded_pdf.seek(0)
                pdf_bytes = uploaded_pdf.read()
                result = client.convert(pdf_bytes, file_name, mime_type)
                from pdf2image import convert_from_bytes
                pdf_images = convert_from_bytes(pdf_bytes)
                images = []
                for i, im in enumerate(pdf_images):
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG")
                    page_bytes = buf.getvalue()
                    page_figs = extract_figures_from_image(page_bytes, min_area=1200, max_figures=7)
                    for fig in page_figs:
                        fig['name'] = f"page-{i+1}-{fig['name']}"
                    images.extend(page_figs)
            if not result.get("success"):
                st.error("❌ Xử lý OCR PDF thất bại: " + str(result.get("error")))
                st.stop()

            st.session_state["ocr_pdf_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_pdf_images"] = images
            st.session_state["ocr_pdf_done"] = True
            st.success("✅ Xử lý OCR PDF hoàn tất thành công!")

    if st.session_state.get("ocr_pdf_done"):
        raw_text = st.session_state.get("ocr_pdf_text_raw", "")
        # Áp dụng filter toán học
        text_content = format_math_ocr(raw_text)
        images = st.session_state.get("ocr_pdf_images", [])

        tab_pdf_img, tab_pdf_text = st.tabs(["🖼️ Hình ảnh", "📝 Văn bản"])
        with tab_pdf_img:
            st.markdown("#### 🖼️ Hình minh hoạ trích xuất:")
            if images:
                st.success(f"🖼️ Đã tách {len(images)} vùng nghi là hình minh hoạ.")
                cols = st.columns(2)
                for i, fig in enumerate(images):
                    with cols[i % 2]:
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
            else:
                st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")

        with tab_pdf_text:
            st.markdown("#### 📋 Kết quả OCR PDF (MathType):")
            st.text_area("Kết quả OCR PDF:", text_content, height=350, label_visibility="collapsed")
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr.txt",
                mime="text/plain",
                use_container_width=True,
            )

            selected_fig_names = []
            with st.expander("🖼️ Chọn hình minh hoạ cho file Word"):
                if images:
                    st.success(f"🖼️ Tick chọn đúng hình bên dưới trước khi xuất Word:")
                    cols = st.columns(2)
                    for i, fig in enumerate(images):
                        with cols[i % 2]:
                            checked = st.checkbox(f"Chọn {fig['name']}", value=True, key=f"pdf_figcheck{i}")
                            st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                            if checked:
                                selected_fig_names.append(fig["name"])
                else:
                    st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")
            export_figures = [fig for fig in images if fig["name"] in selected_fig_names]
            if st.button("📝 Tạo và tải file Word", key="word_pdf_create", use_container_width=True):
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, export_figures, tmp_word.name)
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

# ================ TAB 2: OCR IMAGE ==================
with tab2:
    st.markdown("### 🖼️ OCR cho hình ảnh")
    uploaded_img = st.file_uploader("Chọn hình ảnh để xử lý OCR", type=["png", "jpg", "jpeg", "webp"])
    img_file_name = None

    if uploaded_img:
        img_bytes_orig = uploaded_img.read()
        try:
            img = Image.open(io.BytesIO(img_bytes_orig))
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()
            img_file_name = uploaded_img.name if uploaded_img.name.endswith(".jpg") or uploaded_img.name.endswith(".jpeg") else uploaded_img.name.split(".")[0]+".jpg"
        except Exception as e:
            st.error(f"Ảnh upload không hợp lệ hoặc không đọc được: {e}")
            st.stop()

        img_mime_type = "image/jpeg"
        size_mb = len(img_bytes) / (1024 * 1024)
        with st.expander("ℹ️ Thông tin file", expanded=True):
            st.write(f"**Tên file:** {img_file_name}")
            st.write(f"**Loại file:** {img_mime_type}")
            st.write(f"**Kích thước:** {size_mb:.1f} MB")
        st.image(img_bytes, caption="Ảnh đã upload", use_container_width=True)

        with st.spinner("Đang tách các hình minh hoạ..."):
            figures = extract_figures_from_image(img_bytes, min_area=1200, max_figures=10)
        st.session_state["ocr_img_figures"] = figures

        if st.button("🚀 Xử lý OCR Image", key="ocr_img_btn", use_container_width=True):
            st.info("⏳ Đang nhận diện văn bản từ ảnh...")
            with st.spinner("Đang nhận diện văn bản từ ảnh..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                result = client.convert(img_bytes, img_file_name, img_mime_type)
            if not result.get("success"):
                st.error("❌ Xử lý OCR ảnh thất bại: " + str(result.get("error")))
                st.stop()
            st.session_state["ocr_img_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_img_done"] = True
            st.success("✅ Xử lý OCR Ảnh hoàn tất thành công!")

    if st.session_state.get("ocr_img_done"):
        raw_text = st.session_state.get("ocr_img_text_raw", "")
        text_content = format_math_ocr(raw_text)
        figures = st.session_state.get("ocr_img_figures", [])

        tab_img_fig, tab_img_text = st.tabs(["🖼️ Hình ảnh", "📝 Văn bản"])
        with tab_img_fig:
            st.markdown("#### 🖼️ Hình minh hoạ tách tự động:")
            if figures:
                st.success(f"🖼️ Đã tách {len(figures)} vùng nghi là hình minh hoạ.")
                cols = st.columns(2)
                for i, fig in enumerate(figures):
                    with cols[i % 2]:
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
            else:
                st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")

        with tab_img_text:
            st.markdown("#### 📋 Kết quả OCR Ảnh (MathType):")
            st.text_area("Kết quả OCR Ảnh:", text_content, height=350, label_visibility="collapsed")
            st.download_button(
                "📄 Tải văn bản (TXT)",
                text_content,
                file_name="ket_qua_ocr_anh.txt",
                mime="text/plain",
                use_container_width=True,
            )

            selected_fig_names = []
            with st.expander("🖼️ Chọn hình minh hoạ cho file Word"):
                if figures:
                    st.success(f"🖼️ Tick chọn đúng hình bên dưới trước khi xuất Word:")
                    cols = st.columns(2)
                    for i, fig in enumerate(figures):
                        with cols[i % 2]:
                            checked = st.checkbox(f"Chọn {fig['name']}", value=True, key=f"img_figcheck{i}")
                            st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
                            if checked:
                                selected_fig_names.append(fig["name"])
                else:
                    st.warning("Không phát hiện được vùng nghi là hình minh hoạ.")
            export_figures = [fig for fig in figures if fig["name"] in selected_fig_names]
            if st.button("📝 Tạo và tải file Word", key="word_img_create", use_container_width=True):
                with st.spinner("Đang tạo file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, export_figures, tmp_word.name)
                    with open(tmp_word.name, "rb") as f:
                        word_data = f.read()
                    st.success("✅ Đã tạo file Word thành công!")
                    st.download_button(
                        "⬇️ Tải về file Word",
                        word_data,
                        file_name="ket_qua_ocr_anh.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                    os.remove(tmp_word.name)

st.markdown("---")
st.caption(
    "<b>OCR PDF & Ảnh: hỗ trợ MathType, ảnh minh hoạ, xuất Word/TXT. Giao diện hiện đại.</b>",
    unsafe_allow_html=True
)
