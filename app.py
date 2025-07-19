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
from docx.enum.section import WD_SECTION
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

class ImageProcessor:
    """Class for advanced image processing"""
    
    @staticmethod
    def enhance_image(image: Image.Image) -> Image.Image:
        """Enhance image quality for better OCR"""
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Auto-level (improve brightness)
            image = ImageOps.autocontrast(image)
            
            return image
        except Exception as e:
            st.warning(f"Không thể cải thiện chất lượng ảnh: {str(e)}")
            return image
    
    @staticmethod
    def smart_crop(image: Image.Image) -> Image.Image:
        """Smart crop to remove unnecessary borders"""
        if not OPENCV_AVAILABLE:
            # Fallback: simple border detection using PIL
            return ImageProcessor.simple_crop(image)
        
        try:
            # Convert to numpy array for processing
            img_array = np.array(image)
            
            # Convert to grayscale for edge detection
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
            # Find edges
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find the largest contour (likely the main content)
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                
                # Add some padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(image.width - x, w + 2 * padding)
                h = min(image.height - y, h + 2 * padding)
                
                # Crop the image
                cropped = image.crop((x, y, x + w, y + h))
                
                # Only return cropped if it's significantly smaller than original
                if w * h < 0.8 * image.width * image.height:
                    return cropped
            
            return image
        except Exception as e:
            st.warning(f"Không thể cắt ảnh thông minh: {str(e)}")
            return image
    
    @staticmethod
    def simple_crop(image: Image.Image) -> Image.Image:
        """Simple crop using PIL only (fallback when OpenCV not available)"""
        try:
            # Convert to grayscale to detect borders
            gray = image.convert('L')
            
            # Get image as numpy array
            img_array = np.array(gray)
            
            # Find non-white pixels
            coords = np.argwhere(img_array < 250)  # Non-white pixels
            
            if len(coords) > 0:
                # Find bounding box
                y0, x0 = coords.min(axis=0)
                y1, x1 = coords.max(axis=0)
                
                # Add padding
                padding = 20
                x0 = max(0, x0 - padding)
                y0 = max(0, y0 - padding)
                x1 = min(image.width, x1 + padding)
                y1 = min(image.height, y1 + padding)
                
                # Crop
                cropped = image.crop((x0, y0, x1, y1))
                
                # Only return if significantly smaller
                if (x1-x0) * (y1-y0) < 0.8 * image.width * image.height:
                    return cropped
            
            return image
        except Exception as e:
            st.warning(f"Không thể thực hiện simple crop: {str(e)}")
            return image
    
    @staticmethod
    def resize_for_word(image: Image.Image, max_width: int = 800) -> Image.Image:
        """Resize image appropriately for Word document"""
        try:
            # Calculate new size maintaining aspect ratio
            if image.width > max_width:
                ratio = max_width / image.width
                new_height = int(image.height * ratio)
                image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            return image
        except Exception as e:
            st.warning(f"Không thể resize ảnh: {str(e)}")
            return image
    
    @staticmethod
    def process_image_for_word(image: Image.Image) -> Image.Image:
        """Complete image processing pipeline for Word insertion"""
        # Step 1: Smart crop
        image = ImageProcessor.smart_crop(image)
        
        # Step 2: Enhance quality
        image = ImageProcessor.enhance_image(image)
        
        # Step 3: Resize for Word
        image = ImageProcessor.resize_for_word(image)
        
        return image

class OCRProcessor:
    def __init__(self):
        self.mistral_api_key = None
        self.gemini_api_key = None
        self.image_processor = ImageProcessor()
        
    def setup_apis(self, mistral_key: str, gemini_key: str):
        """Setup API keys for Mistral and Gemini"""
        self.mistral_api_key = mistral_key
        self.gemini_api_key = gemini_key
    
    def extract_images_from_pdf(self, pdf_file, enhance=True) -> List[Image.Image]:
        """Extract and process all images from PDF"""
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
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)
                        
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                            img_pil = Image.open(io.BytesIO(img_data))
                            
                            # Skip very small images (likely decorative)
                            if img_pil.width > 100 and img_pil.height > 100:
                                if enhance:
                                    img_pil = self.image_processor.process_image_for_word(img_pil)
                                images.append(img_pil)
                        
                        pix = None
                    except Exception as e:
                        st.warning(f"Lỗi xử lý ảnh {img_index} trang {page_num + 1}: {str(e)}")
                        continue
            
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
    def analyze_image_content(self, image: Image.Image, model: str = "Gemini") -> dict:
        """Analyze image content to determine optimal placement and description"""
        if model == "Gemini" and not self.gemini_api_key:
            return {"description": "Gemini API key không được cung cấp", "category": "unknown", "placement_hint": ""}
        elif model == "Mistral" and not self.mistral_api_key:
            return {"description": "Mistral API key không được cung cấp", "category": "unknown", "placement_hint": ""}
        
        try:
            # Convert image to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            prompt = """
            Phân tích hình ảnh này và cung cấp thông tin sau dạng JSON:
            
            {
                "description": "Mô tả chi tiết nội dung ảnh (tiếng Việt)",
                "category": "diagram|chart|photo|formula|table|illustration|other",
                "placement_hint": "Gợi ý vị trí chèn phù hợp trong văn bản",
                "related_keywords": ["từ khóa", "liên quan", "đến ảnh"],
                "content_type": "mathematical|scientific|business|general"
            }
            
            Hãy phân tích kỹ và đưa ra gợi ý vị trí chèn thông minh.
            """
            
            if model == "Gemini":
                # Gemini API call
                headers = {'Content-Type': 'application/json'}
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1000}
                }
                
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and len(result['candidates']) > 0:
                        content = result['candidates'][0]['content']['parts'][0]['text']
                        try:
                            return json.loads(content)
                        except:
                            return {"description": content, "category": "unknown", "placement_hint": ""}
            
            else:  # Mistral
                headers = {
                    'Authorization': f'Bearer {self.mistral_api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    "model": "mistral-small-latest",
                    "temperature": 0.1,
                    "max_tokens": 1000,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                        ]
                    }]
                }
                
                response = requests.post(
                    "https://api.mistral.ai/v1/chat/completions",
                    headers=headers, json=payload, timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    try:
                        return json.loads(content)
                    except:
                        return {"description": content, "category": "unknown", "placement_hint": ""}
            
            return {"description": "Không thể phân tích ảnh", "category": "unknown", "placement_hint": ""}
            
        except Exception as e:
            return {"description": f"Lỗi phân tích ảnh: {str(e)}", "category": "unknown", "placement_hint": ""}

class WordExporter:
    def __init__(self):
        self.doc = Document()
        self.setup_document_style()
    
    def setup_document_style(self):
        """Setup document styling"""
        # Set page margins
        section = self.doc.sections[0]
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
    
    def add_content(self, text: str, images: List[Image.Image] = None, image_analyses: List[dict] = None, image_placement: str = "inline"):
        """Add content to Word document with AI-guided image placement"""
        # Add title
        title = self.doc.add_heading('Kết quả OCR - P_OCR PDF AI 2025', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add timestamp
        from datetime import datetime
        timestamp = self.doc.add_paragraph(f'Ngày tạo: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
        timestamp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add main content
        self.doc.add_heading('Nội dung văn bản được trích xuất:', level=1)
        
        # Process text and handle LaTeX formulas with smart image placement
        if image_placement == "inline" and images and image_analyses:
            # Smart placement: use AI analysis to position images
            self._add_content_with_smart_placement(text, images, image_analyses)
        elif image_placement == "inline" and images:
            # Regular inline placement
            self._add_content_with_inline_images(text, images)
        else:
            # Separate sections for text and images
            self._add_text_content(text)
            if images:
                if image_analyses:
                    self._add_images_section_with_analysis(images, image_analyses)
                else:
                    self._add_images_section(images)
    
    def _add_content_with_smart_placement(self, text: str, images: List[Image.Image], image_analyses: List[dict]):
        """Add content with AI-guided smart image placement"""
        paragraphs = text.split('\n')
        used_images = set()
        
        for i, para in enumerate(paragraphs):
            if para.strip():
                self._add_paragraph_with_formulas(para.strip())
                
                # Check if any image should be placed after this paragraph
                for img_idx, analysis in enumerate(image_analyses):
                    if img_idx in used_images:
                        continue
                    
                    # Check if paragraph content matches image keywords
                    para_lower = para.lower()
                    keywords = analysis.get('related_keywords', [])
                    
                    # Smart matching logic
                    keyword_matches = sum(1 for keyword in keywords if keyword.lower() in para_lower)
                    
                    # Placement rules based on content type
                    should_place = False
                    
                    if analysis.get('category') == 'formula' and ('${' in para or 'công thức' in para_lower):
                        should_place = True
                    elif analysis.get('category') == 'diagram' and ('sơ đồ' in para_lower or 'biểu đồ' in para_lower):
                        should_place = True
                    elif analysis.get('category') == 'chart' and ('biểu đồ' in para_lower or 'đồ thị' in para_lower):
                        should_place = True
                    elif analysis.get('category') == 'table' and ('bảng' in para_lower or 'table' in para_lower):
                        should_place = True
                    elif keyword_matches >= 2:  # At least 2 keyword matches
                        should_place = True
                    elif 'hình' in para_lower and str(img_idx + 1) in para:  # References like "Hình 1"
                        should_place = True
                    
                    if should_place:
                        # Add image with analysis-based caption
                        caption = f"Hình {img_idx + 1}: {analysis.get('description', 'Hình minh họa')}"
                        self._insert_image_with_caption(images[img_idx], caption)
                        used_images.add(img_idx)
                        break
        
        # Add remaining images at the end
        for img_idx, img in enumerate(images):
            if img_idx not in used_images:
                analysis = image_analyses[img_idx] if img_idx < len(image_analyses) else {}
                caption = f"Hình {img_idx + 1}: {analysis.get('description', 'Hình minh họa')}"
                self._insert_image_with_caption(img, caption)
    
    def _add_images_section_with_analysis(self, images: List[Image.Image], image_analyses: List[dict]):
        """Add dedicated images section with AI analysis descriptions"""
        self.doc.add_page_break()
        self.doc.add_heading('Hình ảnh được trích xuất từ tài liệu:', level=1)
        
        for i, img in enumerate(images[:15]):  # Limit to 15 images
            analysis = image_analyses[i] if i < len(image_analyses) else {}
            
            # Enhanced caption with analysis
            description = analysis.get('description', 'Hình minh họa')
            category = analysis.get('category', 'unknown')
            
            caption = f"Hình {i + 1} ({category}): {description}"
            self._insert_image_with_caption(img, caption)
            
            # Add analysis details if available
            if analysis.get('placement_hint'):
                hint_p = self.doc.add_paragraph(f"💡 Gợi ý: {analysis['placement_hint']}")
                hint_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                hint_p.runs[0].italic = True
            
            # Add page break after every 2 images to avoid overcrowding
            if (i + 1) % 2 == 0 and i < len(images) - 1:
                self.doc.add_page_break()
    
    def _add_text_content(self, text: str):
        """Add text content with proper formatting"""
        paragraphs = text.split('\n')
        for para in paragraphs:
            if para.strip():
                # Check if paragraph contains LaTeX formulas
                if '${' in para and '}$' in para:
                    self._add_paragraph_with_formulas(para)
                else:
                    p = self.doc.add_paragraph(para.strip())
    
    def _add_paragraph_with_formulas(self, text: str):
        """Add paragraph with LaTeX formulas highlighted"""
        p = self.doc.add_paragraph()
        
        # Split text by LaTeX formulas
        parts = re.split(r'(\$\{[^}]+\}\$)', text)
        
        for part in parts:
            if part.startswith('${') and part.endswith('}$'):
                # This is a LaTeX formula - make it bold and italic
                run = p.add_run(part)
                run.bold = True
                run.italic = True
            else:
                # Regular text
                p.add_run(part)
    
    def _add_content_with_inline_images(self, text: str, images: List[Image.Image]):
        """Add content with images placed inline where appropriate"""
        paragraphs = text.split('\n')
        image_index = 0
        
        for i, para in enumerate(paragraphs):
            if para.strip():
                self._add_paragraph_with_formulas(para.strip())
                
                # Insert image after every few paragraphs
                if image_index < len(images) and (i + 1) % 3 == 0:
                    self._insert_image_with_caption(images[image_index], f"Hình {image_index + 1}")
                    image_index += 1
        
        # Add remaining images at the end
        while image_index < len(images):
            self._insert_image_with_caption(images[image_index], f"Hình {image_index + 1}")
            image_index += 1
    
    def _add_images_section(self, images: List[Image.Image]):
        """Add dedicated images section"""
        self.doc.add_page_break()
        self.doc.add_heading('Hình ảnh được trích xuất từ tài liệu:', level=1)
        
        for i, img in enumerate(images[:15]):  # Limit to 15 images
            self._insert_image_with_caption(img, f"Hình {i + 1}")
            
            # Add page break after every 3 images to avoid overcrowding
            if (i + 1) % 3 == 0 and i < len(images) - 1:
                self.doc.add_page_break()
    
    def _insert_image_with_caption(self, img: Image.Image, caption: str):
        """Insert image with proper sizing and caption"""
        try:
            # Save image temporarily with high quality
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                # Save with high quality
                img.save(tmp_img.name, 'PNG', quality=95, optimize=True)
                
                # Calculate appropriate size
                max_width = Cm(14)  # Maximum width in cm
                max_height = Cm(10)  # Maximum height in cm
                
                # Calculate scaling to fit within bounds
                width_ratio = max_width.cm / (img.width / 96)  # Convert pixels to cm (96 DPI)
                height_ratio = max_height.cm / (img.height / 96)
                scale_ratio = min(width_ratio, height_ratio, 1.0)  # Don't upscale
                
                final_width = Cm(img.width / 96 * scale_ratio)
                final_height = Cm(img.height / 96 * scale_ratio)
                
                # Add caption paragraph
                caption_p = self.doc.add_paragraph()
                caption_run = caption_p.add_run(caption + ":")
                caption_run.bold = True
                caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Add image
                img_p = self.doc.add_paragraph()
                img_run = img_p.add_run()
                img_run.add_picture(tmp_img.name, width=final_width, height=final_height)
                img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Add spacing
                self.doc.add_paragraph()
                
                # Clean up
                os.unlink(tmp_img.name)
                
        except Exception as e:
            # Fallback: add text description
            error_p = self.doc.add_paragraph(f'{caption}: Không thể chèn ảnh - {str(e)}')
            error_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def add_image_statistics(self, images: List[Image.Image], text: str):
        """Add statistics section"""
        self.doc.add_page_break()
        self.doc.add_heading('Thống kê tài liệu:', level=1)
        
        # Text statistics
        word_count = len(text.split())
        char_count = len(text)
        formula_count = len(re.findall(r'\$\{[^}]+\}\$', text))
        line_count = len([line for line in text.split('\n') if line.strip()])
        
        stats_table = self.doc.add_table(rows=5, cols=2)
        stats_table.style = 'Table Grid'
        
        stats_data = [
            ['Số từ:', f'{word_count:,}'],
            ['Số ký tự:', f'{char_count:,}'],
            ['Số dòng:', f'{line_count:,}'],
            ['Công thức LaTeX:', f'{formula_count}'],
            ['Hình ảnh trích xuất:', f'{len(images)}']
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
        st.header("🤖 Chọn AI Models")
        
        # OCR Model selection
        st.subheader("📝 Model OCR (Trích xuất văn bản)")
        ocr_model = st.selectbox(
            "Model OCR:",
            ["Gemini", "Mistral"],
            help="Model để OCR và trích xuất văn bản từ PDF/ảnh"
        )
        
        # Image Analysis Model selection  
        st.subheader("🖼️ Model phân tích ảnh (Vị trí chèn)")
        image_model = st.selectbox(
            "Model phân tích ảnh:",
            ["Gemini", "Mistral"],
            index=1 if ocr_model == "Gemini" else 0,  # Default to different model
            help="Model để phân tích nội dung ảnh và xác định vị trí chèn phù hợp"
        )
        
        # Show current selection
        st.info(f"🔄 **OCR**: {ocr_model} | 🖼️ **Ảnh**: {image_model}")
        
        # Advanced options
        with st.expander("⚙️ Tùy chọn nâng cao"):
            smart_positioning = st.checkbox(
                "Chèn ảnh thông minh theo nội dung",
                value=True,
                help="Sử dụng AI để phân tích nội dung ảnh và chèn vào vị trí phù hợp"
            )
            
            image_context_analysis = st.checkbox(
                "Phân tích ngữ cảnh ảnh",
                value=True,
                help="AI sẽ phân tích nội dung ảnh để hiểu và mô tả"
            )
        
        # Image processing options
        st.header("🖼️ Tùy chọn xử lý ảnh")
        enhance_images = st.checkbox(
            "Cải thiện chất lượng ảnh",
            value=True,
            help="Tự động cắt, cải thiện độ tương phản và độ nét"
        )
        
        image_placement = st.selectbox(
            "Cách bố trí ảnh trong Word:",
            ["inline", "separate"],
            format_func=lambda x: "Xen kẽ với văn bản" if x == "inline" else "Phần riêng biệt",
            help="Chọn cách sắp xếp ảnh trong tài liệu Word"
        )
        
        st.markdown("---")
        
        # Features info
        st.header("✨ Tính năng v2.0")
        st.markdown("""
        - 📄 OCR PDF đa trang
        - 🖼️ OCR hình ảnh  
        - 🤖 **Dual AI Models**
        - 🔢 Nhận diện công thức LaTeX
        - 🎯 **Smart positioning**
        - ✨ Xử lý ảnh thông minh
        - 📤 Xuất Word AI-powered
        - 🌐 Hỗ trợ tiếng Việt/Anh
        """)
        
        st.markdown("---")
        
        # Current session info
        if 'ocr_model' in st.session_state:
            st.subheader("📊 Session hiện tại")
            st.write(f"**OCR**: {st.session_state.get('ocr_model', 'Chưa chọn')}")
            st.write(f"**Ảnh**: {st.session_state.get('image_model', 'Chưa chọn')}")
            if 'extracted_images' in st.session_state:
                st.write(f"**Ảnh đã xử lý**: {len(st.session_state.extracted_images)}")
            if 'image_analyses' in st.session_state:
                st.write(f"**Ảnh đã phân tích**: {len(st.session_state.image_analyses)}")
    
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
            
            # Get current settings
            current_ocr = ocr_model
            current_image = image_model
            current_enhance = enhance_images
            current_smart = smart_positioning
            current_placement = image_placement
            
            # Show current configuration
            st.markdown(f"""
            **🔧 Cấu hình hiện tại:**
            - OCR Model: `{current_ocr}`
            - Image Model: `{current_image}` 
            - Cải thiện ảnh: `{'Bật' if current_enhance else 'Tắt'}`
            - Smart positioning: `{'Bật' if current_smart else 'Tắt'}`
            - Bố trí: `{'Xen kẽ' if current_placement == 'inline' else 'Riêng biệt'}`
            """)
            
            # Process file
            if st.button("🚀 Bắt đầu OCR", type="primary"):
                with st.spinner("🔄 Đang xử lý..."):
                    try:
                        extracted_text = ""
                        extracted_images = []
                        image_analyses = []
                        
                        if file_type == "application/pdf":
                            # Process PDF
                            st.info("📄 Đang xử lý file PDF...")
                            
                            # Extract images from PDF
                            pdf_file_copy = io.BytesIO(uploaded_file.read())
                            extracted_images = st.session_state.ocr_processor.extract_images_from_pdf(
                                pdf_file_copy, enhance=enhance_images
                            )
                            
                            # Convert PDF pages to images for OCR
                            uploaded_file.seek(0)  # Reset file pointer
                            page_images = st.session_state.ocr_processor.convert_pdf_to_images(uploaded_file)
                            
                            # Perform OCR on each page
                            for i, page_img in enumerate(page_images):
                                st.info(f"🔍 Đang xử lý trang {i+1}/{len(page_images)} với {ocr_model}...")
                                
                                # Enhance page image if requested
                                if enhance_images:
                                    page_img = st.session_state.ocr_processor.image_processor.enhance_image(page_img)
                                
                                if ocr_model == "Gemini":
                                    page_text = st.session_state.ocr_processor.ocr_with_gemini(page_img)
                                else:
                                    page_text = st.session_state.ocr_processor.ocr_with_mistral(page_img)
                                
                                extracted_text += f"\n--- Trang {i+1} ---\n{page_text}\n"
                            
                            # Analyze extracted images with second model if smart positioning enabled
                            image_analyses = []
                            if extracted_images and smart_positioning:
                                st.info(f"🔍 Đang phân tích {len(extracted_images)} ảnh với {image_model}...")
                                for i, img in enumerate(extracted_images):
                                    st.info(f"🖼️ Phân tích ảnh {i+1}/{len(extracted_images)}...")
                                    analysis = st.session_state.ocr_processor.analyze_image_content(img, image_model)
                                    image_analyses.append(analysis)
                        
                        else:
                            # Process single image
                            st.info(f"🖼️ Đang xử lý hình ảnh với {ocr_model}...")
                            image = Image.open(uploaded_file)
                            
                            # Enhance image if requested
                            if enhance_images:
                                image = st.session_state.ocr_processor.image_processor.process_image_for_word(image)
                            
                            if ocr_model == "Gemini":
                                extracted_text = st.session_state.ocr_processor.ocr_with_gemini(image)
                            else:
                                extracted_text = st.session_state.ocr_processor.ocr_with_mistral(image)
                            
                            # Analyze the single image if enabled
                            image_analyses = []
                            if smart_positioning:
                                st.info(f"🔍 Đang phân tích ảnh với {image_model}...")
                                analysis = st.session_state.ocr_processor.analyze_image_content(image, image_model)
                                image_analyses.append(analysis)
                                extracted_images = [image]  # Add to extracted images for processing
                        
                        # Store results in session state
                        st.session_state.extracted_text = extracted_text
                        st.session_state.extracted_images = extracted_images
                        st.session_state.image_analyses = image_analyses
                        st.session_state.image_placement = image_placement
                        st.session_state.ocr_model = ocr_model
                        st.session_state.image_model = image_model
                        st.session_state.smart_positioning = smart_positioning
                        
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
            with st.expander(f"🖼️ Hình ảnh đã xử lý ({len(st.session_state.extracted_images)} ảnh)", expanded=True):
                
                # Show processing info
                if enhance_images:
                    st.info("✨ Ảnh đã được cải thiện: cắt thông minh, tăng độ tương phản, độ nét")
                
                # Show AI analysis info
                if 'image_analyses' in st.session_state and st.session_state.image_analyses:
                    st.success(f"🤖 Đã phân tích bằng {st.session_state.get('image_model', 'AI')} để chèn thông minh")
                
                # Display images in grid with analysis
                cols = st.columns(3)
                for i, img in enumerate(st.session_state.extracted_images[:9]):  # Show max 9 images
                    with cols[i % 3]:
                        st.image(img, caption=f"Ảnh {i+1}", use_column_width=True)
                        
                        # Show image info
                        st.caption(f"Kích thước: {img.width}×{img.height}px")
                        
                        # Show AI analysis if available
                        if 'image_analyses' in st.session_state and i < len(st.session_state.image_analyses):
                            analysis = st.session_state.image_analyses[i]
                            
                            # Category badge
                            category = analysis.get('category', 'unknown')
                            if category != 'unknown':
                                st.markdown(f"**🏷️ Loại:** `{category}`")
                            
                            # Description
                            description = analysis.get('description', '')
                            if description and len(description) > 10:
                                st.markdown(f"**📝 Mô tả:** {description[:100]}{'...' if len(description) > 100 else ''}")
                            
                            # Placement hint
                            hint = analysis.get('placement_hint', '')
                            if hint:
                                st.markdown(f"**💡 Vị trí:** {hint[:80]}{'...' if len(hint) > 80 else ''}")
                
                if len(st.session_state.extracted_images) > 9:
                    st.info(f"➕ Còn {len(st.session_state.extracted_images) - 9} ảnh khác sẽ được đưa vào Word")
        
        # Export to Word
        st.markdown("---")
        st.header("📤 Xuất Word")
        
        # Export options
        col1, col2 = st.columns(2)
        with col1:
            include_stats = st.checkbox("Thêm thống kê tài liệu", value=True)
        with col2:
            include_timestamp = st.checkbox("Thêm thời gian tạo", value=True)
        
        # Preview placement
        if 'extracted_images' in st.session_state and st.session_state.extracted_images:
            placement = st.session_state.get('image_placement', 'separate')
            smart_pos = st.session_state.get('smart_positioning', False)
            
            if placement == 'inline' and smart_pos:
                ocr_model = st.session_state.get('ocr_model', 'Gemini')
                img_model = st.session_state.get('image_model', 'Mistral')
                st.info(f"🤖 **AI thông minh**: OCR với {ocr_model}, phân tích ảnh với {img_model}")
                st.success("✨ Ảnh sẽ được chèn vào vị trí phù hợp dựa trên nội dung văn bản")
            elif placement == 'inline':
                st.info("📝 Ảnh sẽ được xen kẽ với văn bản trong tài liệu Word")
            else:
                st.info("📝 Ảnh sẽ được đặt trong phần riêng biệt cuối tài liệu")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("📄 Tạo file Word thông minh", type="primary"):
                with st.spinner("📝 Đang tạo file Word với AI positioning..."):
                    try:
                        exporter = WordExporter()
                        
                        # Get images, analyses and placement
                        images_to_export = []
                        image_analyses = []
                        
                        if 'extracted_images' in st.session_state:
                            images_to_export = st.session_state.extracted_images
                        
                        if 'image_analyses' in st.session_state:
                            image_analyses = st.session_state.image_analyses
                        
                        placement = st.session_state.get('image_placement', 'separate')
                        
                        # Add content with AI-guided placement
                        exporter.add_content(
                            st.session_state.extracted_text, 
                            images_to_export,
                            image_analyses if image_analyses else None,
                            image_placement=placement
                        )
                        
                        # Add statistics if requested
                        if include_stats:
                            exporter.add_image_statistics(images_to_export, st.session_state.extracted_text)
                        
                        word_bytes = exporter.save()
                        
                        # Success metrics
                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            st.metric("Văn bản", f"{len(st.session_state.extracted_text.split())} từ")
                        with col_b:
                            analyzed_count = len(image_analyses) if image_analyses else 0
                            st.metric("Ảnh phân tích", f"{analyzed_count}/{len(images_to_export)}")
                        with col_c:
                            st.metric("Kích thước", f"{len(word_bytes)/1024:.1f} KB")
                        
                        # Show AI models used
                        ocr_model = st.session_state.get('ocr_model', 'Unknown')
                        img_model = st.session_state.get('image_model', 'Unknown')
                        st.success(f"✅ **AI Models**: OCR: {ocr_model} | Ảnh: {img_model}")
                        
                        # Download button
                        st.download_button(
                            label="⬇️ Tải file Word thông minh",
                            data=word_bytes,
                            file_name=f"OCR_Smart_{uploaded_file.name.split('.')[0]}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                        
                        st.success("🎉 File Word thông minh đã được tạo với AI positioning!")
                        
                    except Exception as e:
                        st.error(f"❌ Lỗi khi tạo file Word: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem;">
        <p>🚀 <strong>P_OCR PDF AI 2025 v2.0</strong> - Dual AI Models: Mistral & Gemini 2.0 Flash</p>
        <p>🤖 <strong>New:</strong> Dual AI Processing + Smart Image Positioning</p>
        <p>💻 Phát triển bởi AI Assistant | 📧 Hỗ trợ 24/7</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
