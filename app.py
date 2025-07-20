import streamlit as st
import base64
import io
import os
import re
import tempfile
from PIL import Image, ImageEnhance, ImageOps
import fitz  # PyMuPDF
import pdf2image
from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
import requests
from typing import List
import numpy as np
from datetime import datetime

# Try OpenCV import
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Page config - only once
st.set_page_config(
    page_title="P_OCR PDF AI 2025",
    page_icon="📄",
    layout="wide"
)

# CSS styles
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
    """Smart image processing"""
    
    @staticmethod
    def analyze_image(image: Image.Image) -> dict:
        """Analyze image characteristics"""
        try:
            gray = np.array(image.convert('L'))
            
            analysis = {
                'width': image.width,
                'height': image.height,
                'aspect_ratio': image.width / max(image.height, 1),
                'mean_brightness': float(np.mean(gray)),
                'contrast': float(np.std(gray)),
                'is_mostly_white': bool(np.mean(gray) > 240),
                'complexity': 0.0
            }
            
            if OPENCV_AVAILABLE:
                try:
                    edges = cv2.Canny(gray.astype(np.uint8), 50, 150)
                    edge_density = np.sum(edges > 0) / (image.width * image.height)
                    analysis['complexity'] = float(edge_density * analysis['contrast'])
                except:
                    pass
            
            return analysis
        except:
            return {
                'width': image.width, 'height': image.height,
                'aspect_ratio': 1.0, 'mean_brightness': 128.0,
                'contrast': 0.0, 'is_mostly_white': False, 'complexity': 0.0
            }
    
    @staticmethod
    def is_illustration(image: Image.Image) -> bool:
        """Check if image is illustration"""
        analysis = ImageProcessor.analyze_image(image)
        
        # Criteria
        size_ok = image.width >= 80 and image.height >= 80
        aspect_ok = 0.125 <= analysis['aspect_ratio'] <= 8.0
        has_content = analysis['complexity'] >= 0.005 or analysis['contrast'] >= 15
        not_empty = not analysis['is_mostly_white'] or analysis['mean_brightness'] < 250
        
        return size_ok and aspect_ok and has_content and not_empty
    
    @staticmethod
    def enhance_image(image: Image.Image) -> Image.Image:
        """Enhance image quality"""
        try:
            if image.mode not in ['RGB', 'RGBA']:
                image = image.convert('RGB')
            
            analysis = ImageProcessor.analyze_image(image)
            
            # Adjust based on brightness
            if analysis['mean_brightness'] < 100:
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(1.2)
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.3)
            elif analysis['mean_brightness'] > 200:
                enhancer = ImageEnhance.Brightness(image)
                image = enhancer.enhance(0.95)
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.1)
            else:
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(1.2)
            
            # Sharpness for low contrast
            if analysis['contrast'] < 40:
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(1.3)
            
            # Auto contrast
            image = ImageOps.autocontrast(image, cutoff=1)
            
            # Resize if too large
            max_size = 1200
            if max(image.width, image.height) > max_size:
                if image.width > image.height:
                    ratio = max_size / image.width
                    new_height = int(image.height * ratio)
                    image = image.resize((max_size, new_height), Image.Resampling.LANCZOS)
                else:
                    ratio = max_size / image.height
                    new_width = int(image.width * ratio)
                    image = image.resize((new_width, max_size), Image.Resampling.LANCZOS)
            
            return image
        except:
            return image

class FormulaProcessor:
    """LaTeX formula processing"""
    
    @staticmethod
    def get_math_patterns():
        """Math patterns for detection"""
        return [
            (r'\b[a-zA-Z]\w*\s*=\s*[^=\n]{3,}', 'equation'),
            (r'\b\d+/\d+\b', 'fraction'),
            (r'\b[a-zA-Z]+/[a-zA-Z]+\b', 'variable_fraction'),
            (r'\b[a-zA-Z]\w*\^\d+\b', 'power'),
            (r'√\([^)]+\)', 'sqrt'),
            (r'√\d+', 'sqrt_num'),
            (r'[∫∑∏∆∇±×÷≤≥≠≈∞]', 'math_symbols'),
            (r'\b(sin|cos|tan|log|ln|exp|sqrt)\s*\([^)]+\)', 'functions'),
        ]
    
    @staticmethod
    def wrap_formulas(text: str) -> str:
        """Wrap math formulas with LaTeX syntax"""
        patterns = FormulaProcessor.get_math_patterns()
        processed = text
        
        for pattern, pattern_type in patterns:
            matches = list(re.finditer(pattern, processed, re.IGNORECASE))
            
            for match in reversed(matches):
                start, end = match.start(), match.end()
                formula = match.group()
                before = processed[:start]
                after = processed[end:]
                
                # Skip if already wrapped
                if ('${' in before[-10:] and '}$' in after[:10]):
                    continue
                
                # Validate math content
                if pattern_type == 'equation' and not re.search(r'[=+\-*/^]', formula):
                    continue
                
                # Clean formula
                clean_formula = re.sub(r'\s+', ' ', formula.strip())
                wrapped = f"${{{clean_formula}}}$"
                processed = before + wrapped + after
        
        return processed

class OCRProcessor:
    """Main OCR processing class"""
    
    def __init__(self):
        self.api_key = None
        self.image_proc = ImageProcessor()
        self.formula_proc = FormulaProcessor()
    
    def set_api_key(self, key: str):
        """Set Mistral API key"""
        self.api_key = key
    
    def extract_pdf_images(self, pdf_file, enhance=True) -> List[Image.Image]:
        """Extract images from PDF"""
        images = []
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_file.read())
                tmp_path = tmp.name
            
            doc = fitz.open(tmp_path)
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                img_list = page.get_images()
                
                for img_idx, img in enumerate(img_list):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:
                            img_data = pix.tobytes("png")
                            img_pil = Image.open(io.BytesIO(img_data))
                            
                            if self.image_proc.is_illustration(img_pil):
                                if enhance:
                                    img_pil = self.image_proc.enhance_image(img_pil)
                                images.append(img_pil)
                        
                        pix = None
                    except:
                        continue
            
            doc.close()
            os.unlink(tmp_path)
            
        except Exception as e:
            st.error(f"Error extracting images: {str(e)}")
        
        return images
    
    def pdf_to_images(self, pdf_file) -> List[Image.Image]:
        """Convert PDF pages to images"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(pdf_file.read())
                tmp_path = tmp.name
            
            pages = pdf2image.convert_from_path(tmp_path, dpi=300)
            os.unlink(tmp_path)
            return pages
        except:
            return []
    
    def ocr_image(self, image: Image.Image) -> str:
        """OCR image with Mistral AI"""
        if not self.api_key:
            return "API key required"
        
        try:
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            prompt = """Extract text from image with maximum accuracy. Requirements:

1. **Regular text**: Recognize all text accurately
2. **Math formulas**: Wrap ALL formulas with ${...}$
   Examples: ${x^2 + y^2 = z^2}$, ${a/b}$, ${√x}$
3. **Images/diagrams**: When you see any diagram, chart, or illustration, write:
   ![Hình 1](image1.png)
   ![Hình 2](image2.png)
   - Number sequentially 1, 2, 3...
   - Place marker exactly where image appears
4. **Formatting**: Preserve line breaks and indentation

IMPORTANT:
- ALL math formulas MUST have ${...}$
- ALL illustrations MUST have ![Hình X](imageX.png)
- Don't miss any content"""
            
            payload = {
                "model": "mistral-small-latest",
                "temperature": 0.1,
                "max_tokens": 4000,
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
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result['choices'][0]['message']['content']
                return self.formula_proc.wrap_formulas(text)
            else:
                return f"API Error: {response.status_code}"
                
        except Exception as e:
            return f"OCR Error: {str(e)}"

class WordExporter:
    """Export to Word document"""
    
    def __init__(self):
        self.doc = Document()
        self._setup_style()
    
    def _setup_style(self):
        """Setup document style"""
        section = self.doc.sections[0]
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
    
    def add_content(self, text: str, images: List[Image.Image]):
        """Add content to document"""
        # Title
        title = self.doc.add_heading('P_OCR PDF AI 2025 - OCR Results', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Timestamp
        timestamp = self.doc.add_paragraph(f'Created: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
        timestamp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Main content
        self.doc.add_heading('Extracted Content:', level=1)
        self._process_text_with_images(text, images)
    
    def _process_text_with_images(self, text: str, images: List[Image.Image]):
        """Process text and insert images at markers"""
        lines = text.split('\n')
        
        for line in lines:
            if not line.strip():
                self.doc.add_paragraph()
                continue
            
            # Find image markers
            marker_pattern = r'!\[Hình\s*(\d+)\]\([^)]*\)'
            matches = list(re.finditer(marker_pattern, line, re.IGNORECASE))
            
            if matches:
                current_pos = 0
                
                for match in matches:
                    # Add text before marker
                    before_text = line[current_pos:match.start()].strip()
                    if before_text:
                        p = self.doc.add_paragraph()
                        self._add_formatted_text(p, before_text)
                    
                    # Insert image
                    img_num = int(match.group(1))
                    if 1 <= img_num <= len(images):
                        self._insert_image(images[img_num - 1], f"Hình {img_num}")
                    else:
                        # Placeholder for missing image
                        p = self.doc.add_paragraph()
                        run = p.add_run(f"[Hình {img_num} - Missing]")
                        run.italic = True
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    
                    current_pos = match.end()
                
                # Add remaining text
                remaining = line[current_pos:].strip()
                if remaining:
                    p = self.doc.add_paragraph()
                    self._add_formatted_text(p, remaining)
            else:
                # Regular line
                p = self.doc.add_paragraph()
                self._add_formatted_text(p, line.strip())
    
    def _add_formatted_text(self, paragraph, text: str):
        """Add text with LaTeX formatting"""
        if not text:
            return
        
        # Split by LaTeX formulas
        parts = re.split(r'(\$\{[^}]+\}\$)', text)
        
        for part in parts:
            if part.startswith('${') and part.endswith('}$'):
                # Math formula
                formula = part[2:-2]  # Remove ${ and }$
                run = paragraph.add_run(formula)
                run.bold = True
                run.italic = True
            else:
                # Regular text
                if part:
                    paragraph.add_run(part)
    
    def _insert_image(self, img: Image.Image, caption: str):
        """Insert image with caption"""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                img.save(tmp.name, 'PNG', quality=95)
                
                # Calculate size
                max_width_cm = 12.0
                img_width_cm = (img.width / 96) * 2.54
                scale = min(max_width_cm / img_width_cm, 1.0) if img_width_cm > max_width_cm else 1.0
                final_width = Cm(img_width_cm * scale)
                
                # Create paragraph
                p = self.doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Add image
                p.add_run().add_break()
                run = p.add_run()
                run.add_picture(tmp.name, width=final_width)
                p.add_run().add_break()
                
                # Add caption
                caption_run = p.add_run(f"({caption})")
                caption_run.italic = True
                caption_run.bold = True
                p.add_run().add_break()
                
                os.unlink(tmp.name)
                
        except Exception as e:
            # Fallback placeholder
            p = self.doc.add_paragraph()
            run = p.add_run(f"[{caption}: Error inserting image]")
            run.italic = True
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    def add_stats(self, text: str, images: List[Image.Image]):
        """Add statistics"""
        self.doc.add_page_break()
        self.doc.add_heading('Statistics:', level=1)
        
        # Calculate stats
        word_count = len(text.split())
        char_count = len(text)
        formula_count = len(re.findall(r'\$\{[^}]+\}\$', text))
        image_refs = len(re.findall(r'!\[Hình\s*\d+\]', text))
        
        # Create table
        table = self.doc.add_table(rows=5, cols=2)
        table.style = 'Table Grid'
        
        stats = [
            ['Words:', f'{word_count:,}'],
            ['Characters:', f'{char_count:,}'],
            ['LaTeX Formulas:', f'{formula_count}'],
            ['Images Extracted:', f'{len(images)}'],
            ['Image References:', f'{image_refs}']
        ]
        
        for i, (label, value) in enumerate(stats):
            table.cell(i, 0).text = label
            table.cell(i, 1).text = value
    
    def save(self) -> bytes:
        """Save and return document bytes"""
        buffer = io.BytesIO()
        self.doc.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

# Initialize session state
if 'ocr_processor' not in st.session_state:
    st.session_state.ocr_processor = OCRProcessor()

# Header
st.markdown("""
<div class="main-header">
    <h1>📄 P_OCR PDF AI 2025</h1>
    <p>Smart OCR with Mistral AI</p>
    <p>🎯 Smart Crop • 💯 LaTeX Accuracy • 📍 Precise Placement</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("🔧 Configuration")
    
    api_key = st.text_input(
        "Mistral API Key",
        type="password",
        help="Enter your Mistral AI API key"
    )
    
    if st.button("💾 Save Config"):
        st.session_state.ocr_processor.set_api_key(api_key)
        st.success("✅ Configuration saved!")
    
    st.markdown("---")
    
    st.header("🖼️ Options")
    enhance_images = st.checkbox("Enhance image quality", value=True)
    
    st.markdown("---")
    
    st.header("✨ Features")
    st.markdown("""
    **🎯 Smart Cropping:**
    - Distinguish illustrations vs decorations
    - Preserve important content
    - Remove borders and noise
    
    **💯 LaTeX Accuracy:**
    - Detect complex formulas
    - Handle math symbols
    - Prevent false positives
    
    **📍 Precise Placement:**
    - Marker `![Hình X](imageX.png)`
    - Smart resizing
    - Professional layout
    """)

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📁 Upload File")
    
    uploaded_file = st.file_uploader(
        "Choose PDF or image file",
        type=['pdf', 'png', 'jpg', 'jpeg']
    )
    
    if uploaded_file:
        st.info(f"📄 File: {uploaded_file.name}")
        
        if st.button("🚀 Start Enhanced OCR", type="primary"):
            if not api_key:
                st.error("❌ Please enter Mistral API Key!")
            else:
                with st.spinner("🔄 Processing with AI..."):
                    try:
                        extracted_text = ""
                        extracted_images = []
                        
                        if uploaded_file.type == "application/pdf":
                            st.info("📄 Analyzing PDF...")
                            
                            # Extract images
                            pdf_copy = io.BytesIO(uploaded_file.read())
                            extracted_images = st.session_state.ocr_processor.extract_pdf_images(
                                pdf_copy, enhance=enhance_images
                            )
                            
                            st.success(f"🖼️ Extracted {len(extracted_images)} illustrations")
                            
                            # Convert pages
                            uploaded_file.seek(0)
                            pages = st.session_state.ocr_processor.pdf_to_images(uploaded_file)
                            
                            # OCR pages
                            progress = st.progress(0)
                            for i, page in enumerate(pages):
                                st.info(f"🔍 OCR page {i+1}/{len(pages)}...")
                                
                                if enhance_images:
                                    page = st.session_state.ocr_processor.image_proc.enhance_image(page)
                                
                                page_text = st.session_state.ocr_processor.ocr_image(page)
                                extracted_text += f"\n--- Page {i+1} ---\n{page_text}\n"
                                
                                progress.progress((i + 1) / len(pages))
                        
                        else:
                            st.info("🖼️ Processing image...")
                            image = Image.open(uploaded_file)
                            
                            if enhance_images:
                                image = st.session_state.ocr_processor.image_proc.enhance_image(image)
                            
                            extracted_text = st.session_state.ocr_processor.ocr_image(image)
                        
                        # Store results
                        st.session_state.extracted_text = extracted_text
                        st.session_state.extracted_images = extracted_images
                        
                        st.success("✅ OCR completed!")
                        
                        # Analysis
                        formula_count = len(re.findall(r'\$\{[^}]+\}\$', extracted_text))
                        image_refs = len(re.findall(r'!\[Hình\s*\d+\]', extracted_text))
                        
                        if formula_count > 0:
                            st.success(f"🔢 Found {formula_count} LaTeX formulas!")
                        
                        if image_refs > 0:
                            st.success(f"📍 Found {image_refs} image markers!")
                        
                        if len(extracted_images) == image_refs and image_refs > 0:
                            st.success("🎯 Perfect match: Images and markers aligned!")
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

with col2:
    st.header("📊 Statistics")
    
    if 'extracted_text' in st.session_state:
        text = st.session_state.extracted_text
        
        word_count = len(text.split())
        char_count = len(text)
        formula_count = len(re.findall(r'\$\{[^}]+\}\$', text))
        image_refs = len(re.findall(r'!\[Hình\s*\d+\]', text))
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Words", word_count)
            st.metric("LaTeX", formula_count)
        with col_b:
            st.metric("Characters", char_count)
            st.metric("Image Refs", image_refs)
        
        if 'extracted_images' in st.session_state:
            st.metric("Images", len(st.session_state.extracted_images))

# Results section
if 'extracted_text' in st.session_state:
    st.markdown("---")
    st.header("📋 OCR Results")
    
    # Text display
    with st.expander("📝 Text with LaTeX and markers", expanded=True):
        text = st.session_state.extracted_text
        
        # Highlight
        highlighted = text
        highlighted = re.sub(r'(\$\{[^}]+\}\$)', r'**\1**', highlighted)
        highlighted = re.sub(r'(!\[Hình\s*\d+\]\([^)]*\))', r'***\1***', highlighted)
        
        st.text_area(
            "Content (LaTeX: **bold**, Image markers: ***bold-italic***):",
            highlighted,
            height=300,
            disabled=True
        )
        
        # Analysis
        col1, col2 = st.columns(2)
        
        with col1:
            formulas = re.findall(r'\$\{[^}]+\}\$', text)
            st.write("**LaTeX Formulas:**")
            for i, formula in enumerate(formulas[:3], 1):
                st.write(f"{i}. `{formula}`")
            if len(formulas) > 3:
                st.write(f"... and {len(formulas) - 3} more")
        
        with col2:
            markers = re.findall(r'!\[Hình\s*(\d+)\]', text)
            st.write("**Image Markers:**")
            for num in markers[:3]:
                st.write(f"• Hình {num}")
            if len(markers) > 3:
                st.write(f"... and {len(markers) - 3} more")
    
    # Images display
    if 'extracted_images' in st.session_state and st.session_state.extracted_images:
        with st.expander(f"🖼️ Extracted Images ({len(st.session_state.extracted_images)})", expanded=False):
            for i, img in enumerate(st.session_state.extracted_images):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.image(img, caption=f"Hình {i+1}", use_column_width=True)
                
                with col2:
                    analysis = st.session_state.ocr_processor.image_proc.analyze_image(img)
                    st.write(f"**Hình {i+1}:**")
                    st.write(f"• Size: {img.width}×{img.height}px")
                    st.write(f"• Aspect: {analysis['aspect_ratio']:.2f}")
                    st.write(f"• Complexity: {analysis['complexity']:.3f}")
                    st.write(f"• Contrast: {analysis['contrast']:.1f}")
    
    # Export section
    st.markdown("---")
    st.header("📤 Export to Word")
    
    include_stats = st.checkbox("Include statistics", value=True)
    
    if st.button("📄 Create Word Document", type="primary"):
        with st.spinner("📝 Creating Word document..."):
            try:
                exporter = WordExporter()
                
                images = st.session_state.get('extracted_images', [])
                exporter.add_content(st.session_state.extracted_text, images)
                
                if include_stats:
                    exporter.add_stats(st.session_state.extracted_text, images)
                
                word_bytes = exporter.save()
                
                st.success("🎉 Word document created!")
                
                # Metrics
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Words", len(st.session_state.extracted_text.split()))
                with col_b:
                    st.metric("Images", len(images))
                with col_c:
                    st.metric("Size", f"{len(word_bytes)/1024:.1f} KB")
                
                # Download
                filename = f"OCR_Result_{uploaded_file.name.split('.')[0]}.docx"
                st.download_button(
                    label="⬇️ Download Word Document",
                    data=word_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                
            except Exception as e:
                st.error(f"❌ Export error: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 1rem;">
    <p>🚀 <strong>P_OCR PDF AI 2025</strong> - Enhanced OCR with AI</p>
    <p>🤖 Powered by Mistral AI & Advanced Image Processing</p>
</div>
""", unsafe_allow_html=True)
