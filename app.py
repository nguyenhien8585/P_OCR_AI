import streamlit as st
import base64
import io
import os
import re
import tempfile
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import fitz  # PyMuPDF
import pdf2image
from docx import Document
from docx.shared import Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
import requests
from typing import List, Tuple, Optional
import json
import numpy as np

# Try to import OpenCV, fallback if not available
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    st.warning("⚠️ OpenCV không có sẵn. Tính năng Smart Crop sẽ bị tắt.")

# Page configuration
st.set_page_config(
    page_title="P_OCR PDF AI 2025",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class ImageProcessor:
    """Class for image processing"""
    
    @staticmethod
    def enhance_image(image: Image.Image) -> Image.Image:
        """Enhance image quality"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Auto-level
            image = ImageOps.autocontrast(image)
            
            return image
        except Exception as e:
            st.warning(f"Không thể cải thiện ảnh: {str(e)}")
            return image
    
    @staticmethod
    def smart_crop(image: Image.Image) -> Image.Image:
        """Smart crop to remove borders"""
        if not OPENCV_AVAILABLE:
            return ImageProcessor.simple_crop(image)
        
        try:
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.width - x, w + 2 * padding)
                h = min(image.height - y, h + 2 * padding)
                
                cropped = image.crop((x, y, x + w, y + h))
                
                if w * h < 0.8 * image.width * image.height:
                    return cropped
            
            return image
        except Exception as e:
            st.warning(f"Smart crop failed: {str(e)}")
            return image
    
    @staticmethod
    def simple_crop(image: Image.Image) -> Image.Image:
        """Simple crop using PIL only"""
        try:
            gray = image.convert('L')
            img_array = np.array(gray)
            coords = np.argwhere(img_array < 250)
            
            if len(coords) > 0:
                y0, x0 = coords.min(axis=0)
                y1, x1 = coords.max(axis=0)
                
                padding = 20
                x0 = max(0, x0 - padding)
                y0 = max(0, y0 - padding)
                x1 = min(image.width, x1 + padding)
                y1 = min(image.height, y1 + padding)
                
                cropped = image.crop((x0, y0, x1, y1))
                
                if (x1-x0) * (y1-y0) < 0.8 * image.width * image.height:
                    return cropped
            
            return image
        except Exception as e:
            st.warning(f"Simple crop failed: {str(e)}")
            return image
    
    @staticmethod
    def process_image_for_word(image: Image.Image) -> Image.Image:
        """Complete image processing pipeline"""
        # Smart crop
        image = ImageProcessor.smart_crop(image)
        # Enhance quality
        image = ImageProcessor.enhance_image(image)
        # Resize if too large
        if image.width > 800:
            ratio = 800 / image.width
            new_height = int(image.height * ratio)
            image = image.resize((800, new_height), Image.Resampling.LANCZOS)
        
        return image

class OCRProcessor:
    def __init__(self):
        self.mistral_api_key = None
        self.image_processor = ImageProcessor()
        
    def setup_api(self, mistral_key: str):
        """Setup Mistral API key"""
        self.mistral_api_key = mistral_key
    
    def extract_images_from_pdf(self, pdf_file, enhance=True) -> List[Image.Image]:
        """Extract high-quality images from PDF"""
        images = []
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_path = tmp_file.name
            
            pdf_document = fitz.open(tmp_path)
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)
                        
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            # Filter out very small images (decorative/logos)
                            if pix.width < 100 or pix.height < 100:
                                pix = None
                                continue
                            
                            # Filter out very large images (likely page scans)
                            if pix.width > 2000 or pix.height > 2000:
                                pix = None
                                continue
                            
                            img_data = pix.tobytes("png")
                            img_pil = Image.open(io.BytesIO(img_data))
                            
                            # Additional filtering by aspect ratio
                            aspect_ratio = img_pil.width / img_pil.height
                            if 0.1 < aspect_ratio < 10:  # Normal aspect ratios
                                if enhance:
                                    img_pil = self.image_processor.process_image_for_word(img_pil)
                                images.append(img_pil)
                        
                        pix = None
                    except Exception as e:
                        st.warning(f"Lỗi xử lý ảnh {img_index} trang {page_num + 1}: {str(e)}")
                        continue
            
            pdf_document.close()
            os.unlink(tmp_path)
            
        except Exception as e:
            st.error(f"Lỗi trích xuất ảnh từ PDF: {str(e)}")
        
        return images
    
    def convert_pdf_to_images(self, pdf_file) -> List[Image.Image]:
        """Convert PDF pages to images for OCR"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_path = tmp_file.name
            
            pages = pdf2image.convert_from_path(tmp_path, dpi=300)
            os.unlink(tmp_path)
            
            return pages
        except Exception as e:
            st.error(f"Lỗi chuyển đổi PDF: {str(e)}")
            return []
    
    def wrap_math_formulas(self, text: str) -> str:
        """Wrap mathematical formulas with LaTeX syntax"""
        patterns = [
            r'\b([a-zA-Z]\w*\s*[\+\-\*/\^=]\s*[a-zA-Z0-9\+\-\*/\^=\s\(\)]+)\b',
            r'\b\d+/\d+\b',
            r'\b[a-zA-Z]\d*\^\d+\b',
            r'√\([^)]+\)|√\d+',
            r'\b(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega)\b',
            r'[∫∑∏∆∇±×÷≤≥≠≈∞]',
            r'\b[a-zA-Z]\d*[_\^][a-zA-Z0-9]+\b',
        ]
        
        processed_text = text
        
        for pattern in patterns:
            matches = re.finditer(pattern, processed_text)
            for match in reversed(list(matches)):
                formula = match.group()
                start_pos = match.start()
                end_pos = match.end()
                
                before = processed_text[:start_pos]
                after = processed_text[end_pos:]
                
                if not (before.endswith('${') or '${' in before[-10:]):
                    if not (after.startswith('}$') or '}$' in after[:10]):
                        wrapped_formula = f"${{{formula}}}$"
                        processed_text = (processed_text[:start_pos] + 
                                        wrapped_formula + 
                                        processed_text[end_pos:])
        
        return processed_text
    
    def ocr_with_mistral(self, image: Image.Image) -> str:
        """Perform OCR using Mistral API with image reference markers"""
        if not self.mistral_api_key:
            return "Mistral API key không được cung cấp"
        
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            headers = {
                'Authorization': f'Bearer {self.mistral_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = """
            Trích xuất tất cả văn bản từ hình ảnh này. Yêu cầu đặc biệt:
            
            1. Nhận diện chính xác tất cả văn bản
            2. Bọc công thức toán học bằng ${...}$ 
            3. Khi gặp hình ảnh/biểu đồ/sơ đồ trong nội dung, hãy đánh dấu vị trí bằng cú pháp:
               ![Hình X](imageX.png) 
               trong đó X là số thứ tự hình ảnh (1, 2, 3...)
            4. Giữ nguyên định dạng và bố cục văn bản
            5. Hỗ trợ tiếng Việt và tiếng Anh
            
            Ví dụ: Nếu có biểu đồ trong trang, hãy viết "Như thể hiện trong ![Hình 1](image1.png), ta thấy..."
            
            Trả về văn bản đã được xử lý với các marker ảnh được đánh dấu đúng vị trí.
            """
            
            payload = {
                "model": "mistral-small-latest",
                "temperature": 0.3,
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]
                    }
                ]
            }
            
            response = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                extracted_text = result['choices'][0]['message']['content']
                return self.wrap_math_formulas(extracted_text)
            else:
                return f"Lỗi Mistral API: {response.status_code} - {response.text}"
            
        except Exception as e:
            return f"Lỗi Mistral API: {str(e)}"

class WordExporter:
    def __init__(self):
        self.doc = Document()
        self.setup_document_style()
    
    def setup_document_style(self):
        """Setup document styling"""
        section = self.doc.sections[0]
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
    
    def add_content(self, text: str, images: List[Image.Image] = None):
        """Add content to Word document with image replacement"""
        # Add title
        title = self.doc.add_heading('Kết quả OCR - P_OCR PDF AI 2025', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add timestamp
        from datetime import datetime
        timestamp = self.doc.add_paragraph(f'Ngày tạo: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
        timestamp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add main content with image replacement
        self.doc.add_heading('Nội dung văn bản được trích xuất:', level=1)
        self._add_text_with_image_replacement(text, images or [])
    
    def _add_text_with_image_replacement(self, text: str, images: List[Image.Image]):
        """Add text and replace image markers with actual images"""
        # Split text by paragraphs
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            # Check for image markers in paragraph
            image_pattern = r'!\[Hình (\d+)\]\(image\d+\.png\)'
            matches = list(re.finditer(image_pattern, para))
            
            if matches:
                # Process paragraph with image replacements
                current_pos = 0
                p = self.doc.add_paragraph()
                
                for match in matches:
                    # Add text before image
                    before_text = para[current_pos:match.start()].strip()
                    if before_text:
                        if '${' in before_text and '}$' in before_text:
                            self._add_text_with_formulas(p, before_text)
                        else:
                            p.add_run(before_text)
                    
                    # Add image
                    image_num = int(match.group(1))
                    if 1 <= image_num <= len(images):
                        img = images[image_num - 1]
                        self._insert_image_inline(p, img, f"Hình {image_num}")
                    else:
                        # Image not found, keep original text
                        p.add_run(match.group())
                    
                    current_pos = match.end()
                
                # Add remaining text after last image
                remaining_text = para[current_pos:].strip()
                if remaining_text:
                    if '${' in remaining_text and '}$' in remaining_text:
                        self._add_text_with_formulas(p, remaining_text)
                    else:
                        p.add_run(remaining_text)
            
            else:
                # Regular paragraph without images
                if '${' in para and '}$' in para:
                    self._add_paragraph_with_formulas(para)
                else:
                    self.doc.add_paragraph(para.strip())
        
        # Add remaining images that weren't referenced
        used_images = set()
        for match in re.finditer(r'!\[Hình (\d+)\]', text):
            used_images.add(int(match.group(1)))
        
        unused_images = []
        for i, img in enumerate(images, 1):
            if i not in used_images:
                unused_images.append((i, img))
        
        if unused_images:
            self.doc.add_page_break()
            self.doc.add_heading('Hình ảnh bổ sung:', level=1)
            for img_num, img in unused_images:
                self._insert_image_with_caption(img, f"Hình {img_num}")
    
    def _add_paragraph_with_formulas(self, text: str):
        """Add paragraph with LaTeX formulas highlighted"""
        p = self.doc.add_paragraph()
        self._add_text_with_formulas(p, text)
    
    def _add_text_with_formulas(self, paragraph, text: str):
        """Add text with formula highlighting to existing paragraph"""
        parts = re.split(r'(\$\{[^}]+\}\$)', text)
        
        for part in parts:
            if part.startswith('${') and part.endswith('}$'):
                run = paragraph.add_run(part)
                run.bold = True
                run.italic = True
            else:
                paragraph.add_run(part)
    
    def _insert_image_inline(self, paragraph, img: Image.Image, caption: str):
        """Insert image inline within paragraph"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                img.save(tmp_img.name, 'PNG', quality=95)
                
                # Calculate size
                max_width = Cm(12)
                if img.width > 400:
                    width_ratio = 400 / img.width
                    final_width = Cm(img.width / 96 * width_ratio)
                else:
                    final_width = Cm(img.width / 96)
                
                final_width = min(final_width, max_width)
                
                # Add line break and image
                paragraph.add_run().add_break()
                run = paragraph.add_run()
                run.add_picture(tmp_img.name, width=final_width)
                paragraph.add_run().add_break()
                
                # Add caption
                caption_run = paragraph.add_run(f"({caption})")
                caption_run.italic = True
                paragraph.add_run().add_break()
                
                os.unlink(tmp_img.name)
                
        except Exception as e:
            # Fallback: add text description
            paragraph.add_run(f"[{caption}: Không thể chèn ảnh - {str(e)}]")
    
    def _insert_image_with_caption(self, img: Image.Image, caption: str):
        """Insert image with caption as separate element"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                img.save(tmp_img.name, 'PNG', quality=95)
                
                max_width = Cm(14)
                width_ratio = max_width.cm / (img.width / 96)
                scale_ratio = min(width_ratio, 1.0)
                
                final_width = Cm(img.width / 96 * scale_ratio)
                
                # Add caption
                caption_p = self.doc.add_paragraph()
                caption_run = caption_p.add_run(caption + ":")
                caption_run.bold = True
                caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Add image
                img_p = self.doc.add_paragraph()
                img_run = img_p.add_run()
                img_run.add_picture(tmp_img.name, width=final_width)
                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Add spacing
                self.doc.add_paragraph()
                
                os.unlink(tmp_img.name)
                
        except Exception as e:
            error_p = self.doc.add_paragraph(f'{caption}: Không thể chèn ảnh - {str(e)}')
            error_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def add_statistics(self, images: List[Image.Image], text: str):
        """Add statistics section"""
        self.doc.add_page_break()
        self.doc.add_heading('Thống kê tài liệu:', level=1)
        
        word_count = len(text.split())
        char_count = len(text)
        formula_count = len(re.findall(r'\$\{[^}]+\}\$', text))
        image_refs = len(re.findall(r'!\[Hình \d+\]', text))
        
        stats_table = self.doc.add_table(rows=5, cols=2)
        stats_table.style = 'Table Grid'
        
        stats_data = [
            ['Số từ:', f'{word_count:,}'],
            ['Số ký tự:', f'{char_count:,}'],
            ['Công thức LaTeX:', f'{formula_count}'],
            ['Hình ảnh trích xuất:', f'{len(images)}'],
            ['Tham chiếu ảnh:', f'{image_refs}']
        ]
        
        for i, (label, value) in enumerate(stats_data):
            stats_table.cell(i, 0).text = label
            stats_table.cell(i, 1).text = value
    
    def save(self) -> bytes:
        """Save document and return bytes"""
        buffer = io.BytesIO()
        self.doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

# Main App
def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>📄 P_OCR PDF AI 2025</h1>
        <p>Ứng dụng OCR thông minh với Mistral AI</p>
        <p>Trích xuất văn bản và chèn ảnh tự động vào đúng vị trí</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize OCR processor
    if 'ocr_processor' not in st.session_state:
        st.session_state.ocr_processor = OCRProcessor()
    
    # Sidebar
    with st.sidebar:
        st.header("🔧 Cấu hình")
        
        mistral_key = st.text_input(
            "Mistral API Key",
            type="password",
            help="Nhập API key của Mistral AI"
        )
        
        if st.button("💾 Lưu cấu hình"):
            st.session_state.ocr_processor.setup_api(mistral_key)
            st.success("✅ Đã lưu cấu hình!")
        
        st.markdown("---")
        
        # Processing options
        st.header("🖼️ Tùy chọn xử lý")
        enhance_images = st.checkbox(
            "Cải thiện chất lượng ảnh",
            value=True,
            help="Tự động cắt và cải thiện ảnh"
        )
        
        st.markdown("---")
        
        # Features info
        st.header("✨ Tính năng")
        st.markdown("""
        - 📄 OCR PDF với Mistral AI
        - 🖼️ Tách ảnh chính xác
        - 🔢 Nhận diện công thức LaTeX
        - 📍 Chèn ảnh theo marker `![Hình X]`
        - 📤 Xuất Word chuyên nghiệp
        - 🌐 Hỗ trợ tiếng Việt/Anh
        """)
        
        # Current session info
        if 'extracted_images' in st.session_state:
            st.markdown("---")
            st.subheader("📊 Session hiện tại")
            st.write(f"**Ảnh đã trích xuất**: {len(st.session_state.extracted_images)}")
            if 'extracted_text' in st.session_state:
                image_refs = len(re.findall(r'!\[Hình \d+\]', st.session_state.extracted_text))
                st.write(f"**Tham chiếu ảnh**: {image_refs}")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📁 Upload File")
        
        uploaded_file = st.file_uploader(
            "Chọn file PDF hoặc hình ảnh",
            type=['pdf', 'png', 'jpg', 'jpeg'],
            help="Hỗ trợ file PDF và hình ảnh"
        )
        
        if uploaded_file is not None:
            file_type = uploaded_file.type
            st.info(f"📄 File: {uploaded_file.name} ({file_type})")
            
            if st.button("🚀 Bắt đầu OCR", type="primary"):
                with st.spinner("🔄 Đang xử lý..."):
                    try:
                        extracted_text = ""
                        extracted_images = []
                        
                        if file_type == "application/pdf":
                            st.info("📄 Đang xử lý PDF...")
                            
                            # Extract images first
                            pdf_file_copy = io.BytesIO(uploaded_file.read())
                            extracted_images = st.session_state.ocr_processor.extract_images_from_pdf(
                                pdf_file_copy, enhance=enhance_images
                            )
                            st.success(f"🖼️ Đã trích xuất {len(extracted_images)} ảnh chất lượng")
                            
                            # Convert pages for OCR
                            uploaded_file.seek(0)
                            page_images = st.session_state.ocr_processor.convert_pdf_to_images(uploaded_file)
                            
                            # OCR each page
                            for i, page_img in enumerate(page_images):
                                st.info(f"🔍 OCR trang {i+1}/{len(page_images)}...")
                                
                                if enhance_images:
                                    page_img = st.session_state.ocr_processor.image_processor.enhance_image(page_img)
                                
                                page_text = st.session_state.ocr_processor.ocr_with_mistral(page_img)
                                extracted_text += f"\n--- Trang {i+1} ---\n{page_text}\n"
                        
                        else:
                            st.info("🖼️ Đang xử lý hình ảnh...")
                            image = Image.open(uploaded_file)
                            
                            if enhance_images:
                                image = st.session_state.ocr_processor.image_processor.process_image_for_word(image)
                            
                            extracted_text = st.session_state.ocr_processor.ocr_with_mistral(image)
                        
                        # Store results
                        st.session_state.extracted_text = extracted_text
                        st.session_state.extracted_images = extracted_images
                        
                        st.success("✅ Hoàn thành OCR!")
                        
                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")
    
    with col2:
        st.header("📊 Thống kê")
        
        if 'extracted_text' in st.session_state:
            text = st.session_state.extracted_text
            
            word_count = len(text.split())
            char_count = len(text)
            formula_count = len(re.findall(r'\$\{[^}]+\}\$', text))
            image_refs = len(re.findall(r'!\[Hình \d+\]', text))
            
            st.metric("Số từ", word_count)
            st.metric("Số ký tự", char_count)
            st.metric("Công thức LaTeX", formula_count)
            st.metric("Tham chiếu ảnh", image_refs)
            
            if 'extracted_images' in st.session_state:
                st.metric("Ảnh trích xuất", len(st.session_state.extracted_images))
    
    # Results section
    if 'extracted_text' in st.session_state:
        st.markdown("---")
        st.header("📋 Kết quả OCR")
        
        # Display extracted text
        with st.expander("📝 Văn bản đã trích xuất", expanded=True):
            text = st.session_state.extracted_text
            
            # Highlight image markers
            highlighted_text = re.sub(
                r'(!\[Hình \d+\]\([^)]+\))',
                r'**\1**',
                text
            )
            
            st.text_area(
                "Nội dung (image markers được highlight):",
                highlighted_text,
                height=300,
                disabled=True
            )
        
        # Display extracted images
        if 'extracted_images' in st.session_state and st.session_state.extracted_images:
            with st.expander(f"🖼️ Ảnh đã trích xuất ({len(st.session_state.extracted_images)} ảnh)", expanded=True):
                
                if enhance_images:
                    st.info("✨ Ảnh đã được cải thiện chất lượng")
                
                cols = st.columns(3)
                for i, img in enumerate(st.session_state.extracted_images[:9]):
                    with cols[i % 3]:
                        st.image(img, caption=f"Hình {i+1}", use_column_width=True)
                        st.caption(f"Kích thước: {img.width}×{img.height}px")
                
                if len(st.session_state.extracted_images) > 9:
                    st.info(f"➕ Còn {len(st.session_state.extracted_images) - 9} ảnh khác")
        
        # Export section
        st.markdown("---")
        st.header("📤 Xuất Word")
        
        col1, col2 = st.columns(2)
        with col1:
            include_stats = st.checkbox("Thêm thống kê tài liệu", value=True)
        
        st.info("📍 Ảnh sẽ được chèn tự động vào vị trí có marker ![Hình X](imageX.png)")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("📄 Tạo file Word", type="primary"):
                with st.spinner("📝 Đang tạo file Word..."):
                    try:
                        exporter = WordExporter()
                        
                        images_to_export = []
                        if 'extracted_images' in st.session_state:
                            images_to_export = st.session_state.extracted_images
                        
                        exporter.add_content(st.session_state.extracted_text, images_to_export)
                        
                        if include_stats:
                            exporter.add_statistics(images_to_export, st.session_state.extracted_text)
                        
                        word_bytes = exporter.save()
                        
                        # Success metrics
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Văn bản", f"{len(st.session_state.extracted_text.split())} từ")
                        with col_b:
                            st.metric("Ảnh", f"{len(images_to_export)} ảnh")
                        with col_c:
                            st.metric("Kích thước", f"{len(word_bytes)/1024:.1f} KB")
                        
                        # Download button
                        st.download_button(
                            label="⬇️ Tải file Word",
                            data=word_bytes,
                            file_name=f"OCR_Mistral_{uploaded_file.name.split('.')[0]}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        
                        st.success("🎉 File Word đã được tạo với ảnh tự động chèn!")
                        
                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem;">
        <p>🚀 <strong>P_OCR PDF AI 2025</strong> - Powered by Mistral AI</p>
        <p>📍 <strong>Smart Image Insertion</strong> - Tự động chèn ảnh đúng vị trí</p>
        <p>💻 Phát triển bởi AI Assistant</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
