import streamlit as st
import base64
import io
import os
import re
import tempfile
from PIL import Image
import fitz  # PyMuPDF
import pdf2image
from docx import Document
from docx.shared import Inches
import requests
from typing import List, Tuple, Optional
import json

# Page configuration
st.set_page_config(
    page_title="P_OCR PDF AI 2025",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern interface
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
    .feature-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 1rem 0;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
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

class OCRProcessor:
    def __init__(self):
        self.mistral_api_key = None
        self.gemini_api_key = None
        
    def setup_apis(self, mistral_key: str, gemini_key: str):
        """Setup API keys for Mistral and Gemini"""
        self.mistral_api_key = mistral_key
        self.gemini_api_key = gemini_key
    
    def extract_images_from_pdf(self, pdf_file) -> List[Image.Image]:
        """Extract all images from PDF"""
        images = []
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_path = tmp_file.name
            
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(tmp_path)
            
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("png")
                        img_pil = Image.open(io.BytesIO(img_data))
                        images.append(img_pil)
                    pix = None
            
            pdf_document.close()
            os.unlink(tmp_path)  # Clean up temporary file
            
        except Exception as e:
            st.error(f"Lỗi khi trích xuất hình ảnh từ PDF: {str(e)}")
        
        return images
    
    def convert_pdf_to_images(self, pdf_file) -> List[Image.Image]:
        """Convert PDF pages to images"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_path = tmp_file.name
            
            # Convert PDF pages to images
            pages = pdf2image.convert_from_path(tmp_path, dpi=300)
            os.unlink(tmp_path)  # Clean up
            
            return pages
        except Exception as e:
            st.error(f"Lỗi khi chuyển đổi PDF sang hình ảnh: {str(e)}")
            return []
    
    def wrap_math_formulas(self, text: str) -> str:
        """Automatically wrap mathematical formulas with LaTeX syntax"""
        # Enhanced regex patterns for mathematical formulas
        patterns = [
            # Equations with equals sign
            r'\b([a-zA-Z]\w*\s*[\+\-\*/\^=]\s*[a-zA-Z0-9\+\-\*/\^=\s\(\)]+)\b',
            # Fractions
            r'\b\d+/\d+\b',
            # Exponents
            r'\b[a-zA-Z]\d*\^\d+\b',
            # Square roots
            r'√\([^)]+\)|√\d+',
            # Greek letters (common in math)
            r'\b(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|omega)\b',
            # Mathematical operators and symbols
            r'[∫∑∏∆∇±×÷≤≥≠≈∞]',
            # Subscripts and superscripts pattern
            r'\b[a-zA-Z]\d*[_\^][a-zA-Z0-9]+\b',
            # Complex expressions with parentheses
            r'\([a-zA-Z0-9\+\-\*/\^=\s]+\)'
        ]
        
        processed_text = text
        
        # Apply each pattern
        for pattern in patterns:
            matches = re.finditer(pattern, processed_text)
            for match in reversed(list(matches)):  # Reverse to maintain positions
                formula = match.group()
                # Check if already wrapped
                start_pos = match.start()
                end_pos = match.end()
                
                # Check if already within ${...}$
                before = processed_text[:start_pos]
                after = processed_text[end_pos:]
                
                if not (before.endswith('${') or '${' in before[-10:]):
                    if not (after.startswith('}$') or '}$' in after[:10]):
                        # Wrap the formula
                        wrapped_formula = f"${{{formula}}}$"
                        processed_text = (processed_text[:start_pos] + 
                                        wrapped_formula + 
                                        processed_text[end_pos:])
        
        return processed_text
    
    def ocr_with_mistral(self, image: Image.Image) -> str:
        """Perform OCR using Mistral API"""
        if not self.mistral_api_key:
            return "Mistral API key không được cung cấp"
        
        try:
            # Convert image to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            headers = {
                'Authorization': f'Bearer {self.mistral_api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = """
            Trích xuất tất cả văn bản từ hình ảnh này. Đặc biệt chú ý:
            - Nhận diện chính xác tất cả công thức toán học
            - Bọc mọi công thức toán học bằng ${...}$
            - Giữ nguyên định dạng và bố cục văn bản
            - Hỗ trợ tiếng Việt và tiếng Anh
            
            Hãy phân tích hình ảnh và trả về văn bản đã được trích xuất với đầy đủ công thức được bọc LaTeX.
            """
            
            payload = {
                "model": "mistral-small-latest",
                "temperature": 0.3,
                "top_p": 1,
                "max_tokens": 4000,
                "stream": False,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                "safe_prompt": True
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
    
    def ocr_with_gemini(self, image: Image.Image) -> str:
        """Perform OCR using Gemini 2.0 Flash API"""
        if not self.gemini_api_key:
            return "Gemini API key không được cung cấp"
        
        try:
            # Convert image to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            prompt = """
            Trích xuất tất cả văn bản từ hình ảnh này một cách chính xác nhất. Yêu cầu đặc biệt:
            
            1. Nhận diện tất cả công thức toán học và bọc chúng bằng ${...}$
            2. Ví dụ: x^2 + y^2 = z^2 phải thành ${x^2 + y^2 = z^2}$
            3. Giữ nguyên định dạng và bố cục văn bản gốc
            4. Hỗ trợ cả tiếng Việt và tiếng Anh
            5. Không bỏ sót bất kỳ nội dung nào
            6. Đối với các ký hiệu toán học đặc biệt, sử dụng ký hiệu LaTeX phù hợp
            
            Hãy trả về văn bản đã được xử lý với tất cả công thức được bọc đúng định dạng.
            """
            
            # Prepare request for Gemini 2.0 Flash
            headers = {
                'Content-Type': 'application/json',
            }
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            },
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": img_b64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "topK": 32,
                    "topP": 1,
                    "maxOutputTokens": 4096,
                }
            }
            
            # Make API call to Gemini 2.0 Flash
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    extracted_text = result['candidates'][0]['content']['parts'][0]['text']
                    return self.wrap_math_formulas(extracted_text)
                else:
                    return "Không thể trích xuất văn bản từ phản hồi Gemini"
            else:
                return f"Lỗi Gemini API: {response.status_code} - {response.text}"
            
        except Exception as e:
            return f"Lỗi Gemini API: {str(e)}"

class WordExporter:
    def __init__(self):
        self.doc = Document()
    
    def add_content(self, text: str, images: List[Image.Image] = None):
        """Add content to Word document"""
        # Add title
        title = self.doc.add_heading('Kết quả OCR - P_OCR PDF AI 2025', 0)
        title.alignment = 1  # Center alignment
        
        # Add main content
        self.doc.add_heading('Nội dung văn bản:', level=1)
        
        # Split text into paragraphs and process
        paragraphs = text.split('\n')
        for para in paragraphs:
            if para.strip():
                p = self.doc.add_paragraph(para)
        
        # Add images if available
        if images:
            self.doc.add_heading('Hình ảnh trích xuất:', level=1)
            for i, img in enumerate(images[:10]):  # Limit to 10 images
                try:
                    # Save image temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                        img.save(tmp_img.name, 'PNG')
                        self.doc.add_paragraph(f'Hình {i+1}:')
                        self.doc.add_picture(tmp_img.name, width=Inches(4))
                        os.unlink(tmp_img.name)
                except Exception as e:
                    self.doc.add_paragraph(f'Không thể thêm hình {i+1}: {str(e)}')
    
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
        <p>Ứng dụng OCR thông minh với AI Mistral & Gemini</p>
        <p>Trích xuất văn bản, nhận diện công thức toán học LaTeX, xuất Word chuyên nghiệp</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize OCR processor
    if 'ocr_processor' not in st.session_state:
        st.session_state.ocr_processor = OCRProcessor()
    
    # Sidebar for API configuration
    with st.sidebar:
        st.header("🔧 Cấu hình API")
        
        mistral_key = st.text_input(
            "Mistral API Key",
            type="password",
            help="Nhập API key của Mistral AI"
        )
        
        gemini_key = st.text_input(
            "Gemini API Key", 
            type="password",
            help="Nhập API key của Google Gemini"
        )
        
        if st.button("💾 Lưu cấu hình"):
            st.session_state.ocr_processor.setup_apis(mistral_key, gemini_key)
            st.success("✅ Đã lưu cấu hình API!")
        
        st.markdown("---")
        
        # AI Model selection
        st.header("🤖 Chọn AI Model")
        ai_model = st.selectbox(
            "Model OCR:",
            ["Gemini", "Mistral"],
            help="Chọn AI model để thực hiện OCR"
        )
        
        st.markdown("---")
        
        # Features info
        st.header("✨ Tính năng")
        st.markdown("""
        - 📄 OCR PDF đa trang
        - 🖼️ OCR hình ảnh  
        - 🔢 Nhận diện công thức LaTeX
        - 📤 Xuất Word chuyên nghiệp
        - 🌐 Hỗ trợ tiếng Việt/Anh
        """)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📁 Upload File")
        
        # File upload
        uploaded_file = st.file_uploader(
            "Chọn file PDF hoặc hình ảnh",
            type=['pdf', 'png', 'jpg', 'jpeg'],
            help="Hỗ trợ file PDF và hình ảnh (PNG, JPG, JPEG)"
        )
        
        if uploaded_file is not None:
            file_type = uploaded_file.type
            
            # Display file info
            st.info(f"📄 File: {uploaded_file.name} ({file_type})")
            
            # Process file
            if st.button("🚀 Bắt đầu OCR", type="primary"):
                with st.spinner("🔄 Đang xử lý..."):
                    try:
                        extracted_text = ""
                        extracted_images = []
                        
                        if file_type == "application/pdf":
                            # Process PDF
                            st.info("📄 Đang xử lý file PDF...")
                            
                            # Extract images from PDF
                            pdf_file_copy = io.BytesIO(uploaded_file.read())
                            extracted_images = st.session_state.ocr_processor.extract_images_from_pdf(pdf_file_copy)
                            
                            # Convert PDF pages to images for OCR
                            uploaded_file.seek(0)  # Reset file pointer
                            page_images = st.session_state.ocr_processor.convert_pdf_to_images(uploaded_file)
                            
                            # Perform OCR on each page
                            for i, page_img in enumerate(page_images):
                                st.info(f"🔍 Đang xử lý trang {i+1}/{len(page_images)}...")
                                
                                if ai_model == "Gemini":
                                    page_text = st.session_state.ocr_processor.ocr_with_gemini(page_img)
                                else:
                                    page_text = st.session_state.ocr_processor.ocr_with_mistral(page_img)
                                
                                extracted_text += f"\n--- Trang {i+1} ---\n{page_text}\n"
                        
                        else:
                            # Process single image
                            st.info("🖼️ Đang xử lý hình ảnh...")
                            image = Image.open(uploaded_file)
                            
                            if ai_model == "Gemini":
                                extracted_text = st.session_state.ocr_processor.ocr_with_gemini(image)
                            else:
                                extracted_text = st.session_state.ocr_processor.ocr_with_mistral(image)
                        
                        # Store results in session state
                        st.session_state.extracted_text = extracted_text
                        st.session_state.extracted_images = extracted_images
                        
                        st.success("✅ Hoàn thành OCR!")
                        
                    except Exception as e:
                        st.error(f"❌ Lỗi khi xử lý: {str(e)}")
    
    with col2:
        st.header("📊 Thống kê")
        
        if 'extracted_text' in st.session_state:
            text = st.session_state.extracted_text
            
            # Statistics
            word_count = len(text.split())
            char_count = len(text)
            formula_count = len(re.findall(r'\$\{[^}]+\}\$', text))
            
            st.metric("Số từ", word_count)
            st.metric("Số ký tự", char_count)
            st.metric("Công thức LaTeX", formula_count)
            
            if 'extracted_images' in st.session_state:
                st.metric("Hình ảnh trích xuất", len(st.session_state.extracted_images))
    
    # Results section
    if 'extracted_text' in st.session_state:
        st.markdown("---")
        st.header("📋 Kết quả OCR")
        
        # Display extracted text
        with st.expander("📝 Văn bản đã trích xuất", expanded=True):
            st.text_area(
                "Nội dung:",
                st.session_state.extracted_text,
                height=300,
                disabled=True
            )
        
        # Display extracted images
        if 'extracted_images' in st.session_state and st.session_state.extracted_images:
            with st.expander(f"🖼️ Hình ảnh trích xuất ({len(st.session_state.extracted_images)} ảnh)"):
                cols = st.columns(3)
                for i, img in enumerate(st.session_state.extracted_images[:9]):  # Show max 9 images
                    with cols[i % 3]:
                        st.image(img, caption=f"Ảnh {i+1}", use_column_width=True)
        
        # Export to Word
        st.markdown("---")
        st.header("📤 Xuất Word")
        
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
                        word_bytes = exporter.save()
                        
                        # Download button
                        st.download_button(
                            label="⬇️ Tải file Word",
                            data=word_bytes,
                            file_name=f"OCR_Result_{uploaded_file.name.split('.')[0]}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        
                        st.success("✅ File Word đã được tạo!")
                        
                    except Exception as e:
                        st.error(f"❌ Lỗi khi tạo file Word: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem;">
        <p>🚀 <strong>P_OCR PDF AI 2025</strong> - Powered by Mistral & Gemini AI</p>
        <p>💻 Phát triển bởi AI Assistant | 📧 Hỗ trợ 24/7</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
