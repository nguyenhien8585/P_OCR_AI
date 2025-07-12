import streamlit as st
from app_config import API_URL, API_KEY
from ocr_client_api import EnhancedSmartOCRClient
from extract_figures_from_image_pillow import extract_figures_from_image
from word_export import insert_images_to_word_from_markdown
from format_math_ocr import format_math_ocr
import os
import base64
import tempfile
from PyPDF2 import PdfReader
from PIL import Image
import io
from pdf2image import convert_from_bytes

st.set_page_config(page_title="OCR PDF & Image", layout="centered")

# Tabs cho PDF và Image
tab1, tab2 = st.tabs(["\ud83d\udcc4 OCR PDF", "\ud83d\uddbc\ufe0f OCR Image"])

# ======================== TAB 1: OCR PDF ========================
with tab1:
    st.markdown("### \ud83d\udcc4 OCR cho file PDF")
    uploaded_pdf = st.file_uploader("Ch\u1ecdn file PDF", type=["pdf"])

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

        with st.expander("\u2139\ufe0f Th\u00f4ng tin file", expanded=True):
            st.write(f"**T\u00ean file:** {file_name}")
            st.write(f"**Lo\u1ea1i file:** {mime_type}")
            st.write(f"**K\u00edch th\u01b0\u1edbc:** {size_mb:.1f} MB")
            st.write(f"**S\u1ed1 trang:** {num_pages}")

        if st.button("\ud83d\ude80 X\u1eed l\u00fd OCR PDF", key="ocr_pdf_btn", use_container_width=True):
            st.info("\u23f3 \u0110ang x\u1eed l\u00fd PDF...")
            with st.spinner("Tr\xedch v\0103n b\1ea3n & h\xecnh minh ho\u1ea1..."):
                client = EnhancedSmartOCRClient(API_URL, API_KEY)
                result = client.convert(pdf_bytes, file_name, mime_type)
                images = []
                pdf_images = convert_from_bytes(pdf_bytes)
                for i, im in enumerate(pdf_images):
                    buf = io.BytesIO()
                    im.save(buf, format="JPEG")
                    page_bytes = buf.getvalue()
                    figs = extract_figures_from_image(page_bytes, min_area=1200, max_figures=7)
                    for fig in figs:
                        fig['name'] = f"page-{i+1}-{fig['name']}"
                    images.extend(figs)
            if not result.get("success"):
                st.error("\u274c L\u1ed7i OCR: " + result.get("error", ""))
                st.stop()

            st.session_state["ocr_pdf_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_pdf_images"] = images
            st.session_state["ocr_pdf_done"] = True
            st.success("\u2705 Ho\u00e0n t\u1ea5t OCR PDF!")

    if st.session_state.get("ocr_pdf_done"):
        raw_text = st.session_state["ocr_pdf_text_raw"]
        text_content = format_math_ocr(raw_text)
        images = st.session_state.get("ocr_pdf_images", [])

        tab_img, tab_text = st.tabs(["\ud83d\uddbc\ufe0f H\xecnh ", "\ud83d\udcdd V\0103n b\1ea3n"])
        with tab_img:
            st.markdown("#### \ud83d\uddbc\ufe0f H\xecnh minh ho\u1ea1:")
            if images:
                cols = st.columns(2)
                for i, fig in enumerate(images):
                    with cols[i % 2]:
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
            else:
                st.warning("\u26a0\ufe0f Kh\u00f4ng c\u00f3 h\xecnh minh ho\u1ea1.")

        with tab_text:
            st.markdown("#### \ud83d\udccb K\u1ebf t\u1ee7a OCR:")
            st.text_area("K\u1ebf t\u1ee7a:", text_content, height=350, label_visibility="collapsed")
            st.download_button("\ud83d\udcc4 T\u1ea3i TXT", text_content, "ket_qua_ocr.txt", mime="text/plain")

            selected_figs = []
            with st.expander("\ud83d\uddbc\ufe0f Ch\u1ecdn h\xecnh cho Word"):
                cols = st.columns(2)
                for i, fig in enumerate(images):
                    with cols[i % 2]:
                        if st.checkbox(f"{fig['name']}", value=True, key=f"fig_{i}"):
                            selected_figs.append(fig)
                        st.image(base64.b64decode(fig["base64"]), use_container_width=True)

            if st.button("\ud83d\udcdd Xu\u1ea5t Word", key="word_pdf_create", use_container_width=True):
                with st.spinner("\u0110ang t\u1ea1o file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, selected_figs, tmp_word.name)
                    with open(tmp_word.name, "rb") as f:
                        word_data = f.read()
                    st.success("\u2705 T\u1ea1o file Word th\u00e0nh c\u00f4ng!")
                    st.download_button("\u2b07\ufe0f T\u1ea3i Word", word_data, file_name="ket_qua_ocr.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    os.remove(tmp_word.name)

# ======================== TAB 2: OCR IMAGE ========================
with tab2:
    st.markdown("### \ud83d\uddbc\ufe0f OCR cho h\xecnh \u1ea3nh")
    uploaded_img = st.file_uploader("Ch\u1ecdn h\xecnh \u1ea3nh", type=["png", "jpg", "jpeg", "webp"])

    if uploaded_img:
        img_bytes_orig = uploaded_img.read()
        try:
            img = Image.open(io.BytesIO(img_bytes_orig)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()
        except Exception as e:
            st.error(f"\u274c L\u1ed7i \u0111\u1ecdc \u1ea3nh: {e}")
            st.stop()

        st.image(img_bytes, caption="\u1ea2nh upload", use_container_width=True)

        with st.spinner("T\u00e1ch h\xecnh minh ho\u1ea1..."):
            figures = extract_figures_from_image(img_bytes, min_area=1200, max_figures=10)
        st.session_state["ocr_img_figures"] = figures

        if st.button("\ud83d\ude80 X\u1eed l\u00fd OCR Ảnh", key="ocr_img_btn", use_container_width=True):
            st.info("\u23f3 \u0110ang OCR...")
            client = EnhancedSmartOCRClient(API_URL, API_KEY)
            result = client.convert(img_bytes, uploaded_img.name, "image/jpeg")
            if not result.get("success"):
                st.error("\u274c L\u1ed7i OCR: " + result.get("error", ""))
                st.stop()
            st.session_state["ocr_img_text_raw"] = result["data"].get("text_content", "")
            st.session_state["ocr_img_done"] = True
            st.success("\u2705 OCR Ảnh xong!")

    if st.session_state.get("ocr_img_done"):
        raw_text = st.session_state["ocr_img_text_raw"]
        text_content = format_math_ocr(raw_text)
        figures = st.session_state.get("ocr_img_figures", [])

        tab_img, tab_text = st.tabs(["\ud83d\uddbc\ufe0f H\xecnh", "\ud83d\udcdd V\0103n b\1ea3n"])
        with tab_img:
            st.markdown("#### \ud83d\uddbc\ufe0f H\xecnh minh ho\u1ea1:")
            if figures:
                cols = st.columns(2)
                for i, fig in enumerate(figures):
                    with cols[i % 2]:
                        st.image(base64.b64decode(fig["base64"]), caption=fig["name"], use_container_width=True)
            else:
                st.warning("\u26a0\ufe0f Kh\u00f4ng t\u00ecm th\u1ea5y h\xecnh minh ho\u1ea1.")

        with tab_text:
            st.markdown("#### \ud83d\udccb K\u1ebf t\u1ee7a OCR:")
            st.text_area("K\u1ebf t\u1ee7a:", text_content, height=350, label_visibility="collapsed")
            st.download_button("\ud83d\udcc4 T\u1ea3i TXT", text_content, "ket_qua_ocr_anh.txt", mime="text/plain")

            selected_figs = []
            with st.expander("\ud83d\uddbc\ufe0f Ch\u1ecdn h\xecnh cho Word"):
                cols = st.columns(2)
                for i, fig in enumerate(figures):
                    with cols[i % 2]:
                        if st.checkbox(f"{fig['name']}", value=True, key=f"fig_img_{i}"):
                            selected_figs.append(fig)
                        st.image(base64.b64decode(fig["base64"]), use_container_width=True)

            if st.button("\ud83d\udcdd Xu\u1ea5t Word", key="word_img_create", use_container_width=True):
                with st.spinner("\u0110ang t\u1ea1o file Word..."):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                        insert_images_to_word_from_markdown(text_content, selected_figs, tmp_word.name)
                    with open(tmp_word.name, "rb") as f:
                        word_data = f.read()
                    st.success("\u2705 Xu\u1ea5t file Word th\u00e0nh c\u00f4ng!")
                    st.download_button("\u2b07\ufe0f T\u1ea3i Word", word_data, file_name="ket_qua_ocr_anh.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                    os.remove(tmp_word.name)

st.markdown("---")
st.caption("<b>OCR PDF & Ảnh: hỗ trợ MathType, tách hình minh hoạ, xuất Word & TXT.</b>", unsafe_allow_html=True)
