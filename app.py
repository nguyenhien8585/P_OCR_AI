import streamlit as st
import tempfile, os, base64, re, io, itertools
from PIL import Image
import numpy as np
import cv2
import requests
import json
import time
import logging
from typing import List, Dict, Any

# Import PDF processing
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# Import Word export
try:
    from docx import Document
    from docx.shared import Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

# ========== Cấu hình ==========
MISTRAL_API_KEYS = [
    "your_mistral_api_key_1",
    "your_mistral_api_key_2", 
    "your_mistral_api_key_3"
]

api_key_cycle = itertools.cycle(MISTRAL_API_KEYS)
def get_next_api_key():
    return next(api_key_cycle)

MISTRAL_PROMPT = '''
YÊU CẦU QUAN TRỌNG:
1. GÕ LẠI CHÍNH XÁC:
- Gõ lại toàn bộ văn bản trong ảnh, không bỏ sót từ, câu, đoạn nào.
- Giữ nguyên cấu trúc xuống dòng, in đậm, in nghiêng (nếu có thể).
2. ĐÁNH DẤU HÌNH/BẢNG:
- Nếu có hình minh hoạ, ghi [HÌNH_PLACEHOLDER].
- Nếu có bảng số liệu, ghi [BẢNG_PLACEHOLDER].
3. VỊ TRÍ PLACEHOLDER:
- Chèn placeholder ngay sau dòng có từ khóa (ví dụ: "xem hình dưới", "bảng số liệu", "bảng biến thiên", "biểu đồ", "hình vẽ", "bảng giá trị", "bảng tần số", v.v...),
- Nếu không có từ khóa, chèn tại vị trí logic sát nhất với nội dung liên quan.
4. CÔNG THỨC TOÁN HỌC:
- Tất cả công thức, ký hiệu toán học dùng LaTeX inline: ${...}$.
- Hệ phương trình: ${\begin{cases} ... \end{cases}}$.
- Không dùng \(...\) hoặc \[...\].
- Các công thức dạng latex không được thiếu dấu { } trên không được thiếu nếu có mở ngoặc thì phải có đóng ngoặc.
Ví dụ: ${A B C D . A^{\prime B^{\prime C^{\prime} D^{\prime}}$ 
- Ký hiệu hình học, số liệu đặc biệt (vd: ${Oxyz}$, ${A}$, ${0,1%}$, ...) cũng đặt trong ${...}$.
5. BẢNG SỐ LIỆU:
- Nếu có bảng số liệu, chuyển thành bảng Markdown nếu hợp lý.
6. ĐỊNH DẠNG CÂU HỎI:
- Trắc nghiệm (4 lựa chọn): Nhận diện đáp án dạng A., B., C., D. hoặc a), b), c), d) hoặc a., b., c., d.. Đảm bảo mỗi lựa chọn ở một dòng riêng.
- Trắc nghiệm đúng/sai: Nếu gặp các đáp án bắt đầu bằng a), b), c), d) hoặc a., b., c., d., vẫn tách mỗi đáp án lên dòng riêng.
- Trả lời ngắn: Trả lời: ________
- Tự luận: ghi nguyên văn câu hỏi.

LƯU Ý:
+ Không bỏ sót bất kỳ chi tiết nào.
+ Không tự ý sửa đổi nội dung.
+ Chỉ thực hiện đúng yêu cầu như trên.
'''

# ========== PDF Processing Functions ==========
def extract_text_from_pdf_pymupdf(pdf_bytes: bytes) -> str:
    """Trích xuất text từ PDF bằng PyMuPDF"""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_content = ""
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_text = page.get_text()
            text_content += f"\n--- Trang {page_num + 1} ---\n{page_text}\n"
        
        doc.close()
        return text_content
    except Exception as e:
        raise Exception(f"Lỗi PyMuPDF: {str(e)}")

def extract_text_from_pdf_pypdf2(pdf_bytes: bytes) -> str:
    """Trích xuất text từ PDF bằng PyPDF2"""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text_content = ""
        
        for page_num, page in enumerate(reader.pages):
            page_text = page.extract_text()
            text_content += f"\n--- Trang {page_num + 1} ---\n{page_text}\n"
        
        return text_content
    except Exception as e:
        raise Exception(f"Lỗi PyPDF2: {str(e)}")

def extract_text_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """Trích xuất text từ PDF với fallback methods"""
    try:
        # Thử PyMuPDF trước (tốt hơn)
        if HAS_PYMUPDF:
            text_content = extract_text_from_pdf_pymupdf(pdf_bytes)
            return {
                "success": True,
                "text_content": text_content,
                "method": "PyMuPDF"
            }
        
        # Fallback sang PyPDF2
        elif HAS_PYPDF2:
            text_content = extract_text_from_pdf_pypdf2(pdf_bytes)
            return {
                "success": True,
                "text_content": text_content,
                "method": "PyPDF2"
            }
        
        else:
            return {
                "success": False,
                "error": "Không có thư viện PDF processing nào được cài đặt. Vui lòng cài PyMuPDF hoặc PyPDF2."
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Lỗi xử lý PDF: {str(e)}"
        }

def extract_images_from_pdf(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """Trích xuất hình ảnh từ PDF"""
    if not HAS_PYMUPDF:
        st.warning("PyMuPDF chưa được cài đặt. Không thể trích xuất hình ảnh từ PDF.")
        return []
    
    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        img_index = 0
        table_index = 0
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_idx, img in enumerate(image_list):
                try:
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:
                        img_data = pix.tobytes("png")
                    else:
                        pix1 = fitz.Pixmap(fitz.csRGB, pix)
                        img_data = pix1.tobytes("png")
                        pix1 = None
                    
                    pix = None
                    
                    pil_image = Image.open(io.BytesIO(img_data))
                    
                    # Resize nếu quá lớn
                    max_size = 1200
                    if max(pil_image.size) > max_size:
                        pil_image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    
                    if pil_image.mode in ('RGBA', 'LA', 'P'):
                        pil_image = pil_image.convert('RGB')
                    
                    img_buffer = io.BytesIO()
                    pil_image.save(img_buffer, format='JPEG', quality=85, optimize=True)
                    img_buffer.seek(0)
                    
                    img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                    
                    width, height = pil_image.size
                    aspect_ratio = width / height
                    
                    is_table = (
                        aspect_ratio > 2.0 or
                        (width > 400 and height > 200) or
                        (aspect_ratio > 1.5 and width > 300)
                    )
                    
                    if is_table:
                        table_index += 1
                        name = f"table-{table_index}.jpeg"
                    else:
                        img_index += 1
                        name = f"img-{img_index}.jpeg"
                    
                    images.append({
                        "name": name,
                        "base64": img_b64,
                        "is_table": is_table,
                        "page": page_num + 1,
                        "size": (width, height),
                        "aspect_ratio": aspect_ratio
                    })
                    
                except Exception as e:
                    logging.warning(f"Không thể trích xuất ảnh {img_idx} từ trang {page_num + 1}: {e}")
                    continue
        
        doc.close()
        images.sort(key=lambda x: (x['page'], x['name']))
        return images
        
    except Exception as e:
        logging.error(f"Lỗi khi trích xuất hình ảnh từ PDF: {e}")
        return []

# ========== LaTeX Processing Functions ==========
def fix_broken_latex_blocks(text):
    # Ghép block bị tách như: ${A^{\prime}$}$} C^{\prime} -> ${A^{\prime} C^{\prime}}$
    while True:
        new_text = re.sub(
            r'\$\{([^}$]+)\}\}\$\}\}?([^\$]+)\$',
            lambda m: '${' + m.group(1).strip() + ' ' + m.group(2).strip() + '}$',
            text
        )
        if new_text == text:
            break
        text = new_text

    text = re.sub(r'\$\{([^}$]+)\}\}\$+', r'${\1}$', text)
    text = re.sub(r'\$\{([^}$]+)\}\}\$([^\n]+)', r'${\1 \2}$', text)
    text = re.sub(r'\}\$\}+', '}$', text)
    return text

def clean_latex_blocks(text):
    text = re.sub(r'\}\$\s*\$\{', ' ', text)
    text = re.sub(r'\}{2,}\$', '}$', text)
    text = re.sub(r'\$\}(\w)', r'} \1', text)
    text = re.sub(r'\$\{[ \t\r\n]*\}\$', '', text)
    
    def fix_block(m):
        s = m.group(1)
        opens = s.count('{')
        closes = s.count('}')
        if opens > closes:
            s += '}' * (opens - closes)
        elif closes > opens:
            s = s.rstrip('}' * (closes - opens))
        if not s.endswith('}'):
            s += '}'
        return '${' + s + '}$'
    
    text = re.sub(r'\$\{([^}$\n]+)\$?', fix_block, text)
    text = re.sub(r'\}{2,}\$', '}$', text)
    return text

def normalize_math_latex(text):
    text = re.sub(r'\}\$\{', '', text)
    text = re.sub(r'\$\{([^\$]*)\}\$\{([^\$]*)\}\$', lambda m: '${' + m.group(1) + m.group(2) + '}$', text)
    text = re.sub(r'\$\{{2,}', '${', text)
    text = re.sub(r'\}{2,}\$', '}$', text)
    text = re.sub(r'\}\$[\.\s]*\$\{', '', text)
    text = re.sub(r'\$(?!\{)([^\$]+?)\$', lambda m: '${' + m.group(1).strip() + '}$', text)
    text = re.sub(r'\$\{\s*\}\$', '', text)
    return text

def format_exam_markdown(text):
    text = re.sub(r'([^\n])(\[BẢNG: [^\]]+\])', r'\1\n\2', text)
    text = re.sub(r'(\[BẢNG: [^\]]+\])([^\n])', r'\1\n\2', text)
    text = re.sub(r'([^\n])(\[HÌNH: [^\]]+\])', r'\1\n\2', text)
    text = re.sub(r'(\[HÌNH: [^\]]+\])([^\n])', r'\1\n\2', text)
    text = re.sub(r'(Trang\s*\d+\/\d+\s*-\s*Mã\s*đề\s*\d+)', r'\n\n---\n\1\n---\n', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<!^)\s*(?=Câu\s*\d+[.:])', r'\n', text)
    
    blocks = re.split(r'(?=^Câu\s*\d+[.:])', text, flags=re.MULTILINE)
    result_blocks = []
    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue
        blk = re.sub(r'(?<!\n)[ ]*A\.', r'\nA.', blk)
        blk = re.sub(r'(?<!\n)[ ]*B\.', r'\nB.', blk)
        blk = re.sub(r'(?<!\n)[ ]*C\.', r'\nC.', blk)
        blk = re.sub(r'(?<!\n)[ ]*D\.', r'\nD.', blk)
        blk = re.sub(r'(?<!\n)[ ]*a\)', r'\na)', blk)
        blk = re.sub(r'(?<!\n)[ ]*b\)', r'\nb)', blk)
        blk = re.sub(r'(?<!\n)[ ]*c\)', r'\nc)', blk)
        blk = re.sub(r'(?<!\n)[ ]*d\)', r'\nd)', blk)
        lines = [l.strip() for l in blk.split('\n')]
        lines = [l for i, l in enumerate(lines) if l or (i > 0 and lines[i-1])]
        result_blocks.append('\n'.join(lines))
    result = '\n\n'.join(result_blocks)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()

# ========== Image Processing Functions ==========
def filter_nested_boxes(candidates):
    filtered = []
    for i, box in enumerate(candidates):
        x0, y0, x1, y1 = box['x0'], box['y0'], box['x1'], box['y1']
        is_nested = False
        for j, other in enumerate(candidates):
            if i == j: continue
            ox0, oy0, ox1, oy1 = other['x0'], other['y0'], other['x1'], other['y1']
            if x0 >= ox0 and y0 >= oy0 and x1 <= ox1 and y1 <= oy1:
                is_nested = True
                break
        if not is_nested:
            filtered.append(box)
    return filtered

def extract_figures_and_tables(img_bytes, min_area_ratio=0.008, min_area_abs=2500, min_w=70, min_h=70, max_figures=8):
    img_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray = clahe.apply(gray)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 10)
    kernel = np.ones((3,3),np.uint8)
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        x, y, ww, hh = cv2.boundingRect(cnt)
        area = ww * hh
        area_ratio = area / (w * h)
        aspect = ww / (hh + 1e-6)
        if area < min_area_abs or area_ratio < min_area_ratio or area_ratio > 0.6:
            continue
        if ww < min_w or hh < min_h:
            continue
        if not (0.2 < aspect < 8.0):
            continue
        if x < 0.03*w or y < 0.03*h or (x+ww) > 0.97*w or (y+hh) > 0.97*h:
            continue
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0: continue
        solidity = float(area)/hull_area
        if solidity < 0.4:
            continue
        is_table = (ww > 0.25*w and hh > 0.05*h and aspect > 2.0 and aspect < 10.0)
        candidates.append({
            "area": area, "x0": x, "y0": y, "x1": x+ww, "y1": y+hh,
            "is_table": is_table, "bbox": (x, y, ww, hh)
        })
    candidates = sorted(candidates, key=lambda f: f['area'], reverse=True)
    candidates = filter_nested_boxes(candidates)
    candidates = candidates[:max_figures]
    candidates = sorted(candidates, key=lambda box: (box["y0"], box["x0"]))
    final_figures_list = []
    img_idx = 0
    table_idx = 0
    for fig_data in candidates:
        crop = img[fig_data["y0"]:fig_data["y1"], fig_data["x0"]:fig_data["x1"]]
        buf = io.BytesIO()
        Image.fromarray(crop).save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        if fig_data["is_table"]:
            name = f"table-{table_idx+1}.jpeg"
            table_idx += 1
        else:
            name = f"img-{img_idx+1}.jpeg"
            img_idx += 1
        final_figures_list.append({
            "name": name,
            "base64": b64,
            "is_table": fig_data["is_table"],
            "bbox": fig_data["bbox"]
        })
    return final_figures_list, h, w

def remove_all_figure_markdown(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'!\[img-\d+\.jpeg\]\(img-\d+\.jpeg\)', '', text)
    text = re.sub(r'\[HÌNH:.*?\]', '', text)
    text = re.sub(r'\[BẢNG:.*?\]', '', text)
    text = re.sub(r'\[HÌNH_PLACEHOLDER\]', '', text)
    text = re.sub(r'\[BẢNG_PLACEHOLDER\]', '', text)
    return text

def join_paragraphs_and_insert_figures_tables(text, figures, img_h, img_w):
    lines = []
    buffer = ""
    for line in text.split('\n'):
        stripped_line = line.strip()
        if stripped_line:
            buffer = buffer + " " + stripped_line if buffer else stripped_line
        else:
            if buffer:
                lines.append(buffer)
                buffer = ""
            lines.append('')
    if buffer:
        lines.append(buffer)
    figures_sorted = sorted(
        [fig for fig in figures if fig.get('bbox')],
        key=lambda f: (f['bbox'][1], f['bbox'][0])
    )
    used_figures = set()
    processed_lines = []
    fig_idx = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        lower = line.lower()
        processed_lines.append(line)
        inserted = False
        if (
            any(x in lower for x in ["bảng", "bảng giá trị", "bảng biến thiên", "bảng tần số"])
            or (line.strip().startswith("|") and "|" in line)
        ):
            for j in range(fig_idx, len(figures_sorted)):
                fig = figures_sorted[j]
                if fig['is_table'] and fig['name'] not in used_figures:
                    tag = f"[BẢNG: {fig['name']}]"
                    processed_lines.append(tag)
                    used_figures.add(fig['name'])
                    fig_idx = j + 1
                    inserted = True
                    break
        if (
            not inserted
            and any(x in lower for x in ["hình vẽ", "hình bên", "(hình", "xem hình", "đồ thị", "biểu đồ", "minh họa"])
        ):
            for j in range(fig_idx, len(figures_sorted)):
                fig = figures_sorted[j]
                if not fig['is_table'] and fig['name'] not in used_figures:
                    tag = f"[HÌNH: {fig['name']}]"
                    processed_lines.append(tag)
                    used_figures.add(fig['name'])
                    fig_idx = j + 1
                    break
        i += 1
    for i, line in enumerate(processed_lines):
        if re.match(r"^Câu\s*\d+[\.\:]", line) and fig_idx < len(figures_sorted):
            next_line = processed_lines[i+1] if i+1 < len(processed_lines) else ""
            if not re.match(r"\[HÌNH:.*\]", next_line) and not re.match(r"\[BẢNG:.*\]", next_line):
                while fig_idx < len(figures_sorted) and figures_sorted[fig_idx]['name'] in used_figures:
                    fig_idx += 1
                if fig_idx < len(figures_sorted):
                    fig = figures_sorted[fig_idx]
                    tag = f"[BẢNG: {fig['name']}]" if fig['is_table'] else f"[HÌNH: {fig['name']}]"
                    processed_lines.insert(i+1, tag)
                    used_figures.add(fig['name'])
                    fig_idx += 1
    return '\n'.join(processed_lines)

# ========== Mistral API Functions ==========
def mistral_generate_text(image_bytes, api_key):
    """Gọi Mistral API để OCR ảnh"""
    api_url = "https://api.mistral.ai/v1/chat/completions"
    
    b64_img = base64.b64encode(image_bytes).decode()
    
    payload = {
        "model": "pixtral-12b-2409",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": MISTRAL_PROMPT
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_img}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 4000,
        "temperature": 0.1
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        text = result["choices"][0]["message"]["content"]
        return text
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Lỗi kết nối Mistral API: {str(e)}")
    except KeyError as e:
        raise Exception(f"Lỗi format phản hồi từ Mistral: {str(e)}")
    except Exception as e:
        raise Exception(f"Lỗi không xác định: {str(e)}")

# ========== Word Export Functions ==========
def process_latex_in_text(text: str) -> str:
    """Chuyển LaTeX về dạng Unicode cho Word"""
    latex_to_unicode = {
        r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
        r'\pi': 'π', r'\sigma': 'σ', r'\theta': 'θ', r'\lambda': 'λ',
        r'\mu': 'μ', r'\phi': 'φ', r'\omega': 'ω', r'\infty': '∞',
        r'\pm': '±', r'\mp': '∓', r'\times': '×', r'\div': '÷',
        r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\approx': '≈',
        r'\subset': '⊂', r'\supset': '⊃', r'\in': '∈', r'\notin': '∉',
        r'\cup': '∪', r'\cap': '∩', r'\sum': '∑', r'\prod': '∏',
        r'\int': '∫', r'\sqrt': '√', r'\prime': '′', r'\circ': '°',
        r'\perp': '⊥', r'\parallel': '∥', r'\angle': '∠', r'\triangle': '△',
    }
    
    for latex, unicode_char in latex_to_unicode.items():
        text = text.replace(latex, unicode_char)
    
    text = re.sub(r'\$\{([^}]+)\}\$', r'\1', text)
    text = re.sub(r'\$([^$]+)\$', r'\1', text)
    text = re.sub(r'\\begin\{cases\}(.+?)\\end\{cases\}', r'{\1}', text, flags=re.DOTALL)
    text = re.sub(r'\\left\((.+?)\\right\)', r'(\1)', text)
    text = re.sub(r'\^\{([^}]+)\}', r'^(\1)', text)
    text = re.sub(r'_\{([^}]+)\}', r'_(\1)', text)
    text = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\[a-zA-Z]+', '', text)
    
    return text

def insert_images_to_word_from_markdown(markdown_text: str, figures: List[Dict[str, Any]], output_path: str):
    """Tạo Word document từ markdown với hình ảnh"""
    if not HAS_DOCX:
        raise Exception("python-docx chưa được cài đặt. Vui lòng chạy: pip install python-docx")
    
    doc = Document()
    image_map = {fig['name']: fig for fig in figures}
    
    lines = markdown_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        if not line:
            doc.add_paragraph()
            continue
            
        # Xử lý tag hình ảnh/bảng
        if line.startswith('[HÌNH:') or line.startswith('[BẢNG:'):
            match = re.search(r'\[(HÌNH|BẢNG):\s*([^\]]+)\]', line)
            if match:
                img_type = match.group(1)
                img_name = match.group(2).strip()
                
                if img_name in image_map:
                    try:
                        fig_data = image_map[img_name]
                        img_bytes = base64.b64decode(fig_data['base64'])
                        img_stream = io.BytesIO(img_bytes)
                        
                        pil_img = Image.open(img_stream)
                        img_width, img_height = pil_img.size
                        
                        max_width = Inches(6)
                        max_height = Inches(8)
                        
                        ratio = min(max_width.inches / (img_width / 72), max_height.inches / (img_height / 72))
                        display_width = Inches(img_width / 72 * ratio)
                        display_height = Inches(img_height / 72 * ratio)
                        
                        p = doc.add_paragraph()
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        
                        img_stream.seek(0)
                        run = p.add_run()
                        run.add_picture(img_stream, width=display_width, height=display_height)
                        
                        caption_p = doc.add_paragraph()
                        caption_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        caption_run = caption_p.add_run(f"{img_type}: {img_name}")
                        caption_run.italic = True
                        
                        doc.add_paragraph()
                        
                    except Exception as e:
                        p = doc.add_paragraph()
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        run = p.add_run(f"[{img_type}: {img_name} - Lỗi: {str(e)}]")
                        run.italic = True
                else:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = p.add_run(f"[{img_type}: {img_name} - Không tìm thấy]")
                    run.italic = True
            continue
            
        # Xử lý các dòng text khác
        if line.startswith('---') and line.endswith('---'):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line.strip('-').strip())
            run.bold = True
        elif re.match(r'^Câu\s*\d+[.:]', line):
            p = doc.add_paragraph()
            match = re.match(r'^(Câu\s*\d+[.:])\s*(.*)', line)
            if match:
                question_num = match.group(1)
                question_content = match.group(2)
                run1 = p.add_run(question_num + ' ')
                run1.bold = True
                if question_content:
                    run2 = p.add_run(process_latex_in_text(question_content))
            else:
                run = p.add_run(process_latex_in_text(line))
                run.bold = True
        elif re.match(r'^[A-Da-d][.)]\s', line):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.5)
            match = re.match(r'^([A-Da-d][.)]\s*)(.*)', line)
            if match:
                choice_mark = match.group(1)
                choice_content = match.group(2)
                run1 = p.add_run(choice_mark)
                run1.bold = True
                if choice_content:
                    run2 = p.add_run(process_latex_in_text(choice_content))
            else:
                run = p.add_run(process_latex_in_text(line))
        else:
            p = doc.add_paragraph()
            run = p.add_run(process_latex_in_text(line))
    
    doc.save(output_path)

# ========== Streamlit App ==========
st.set_page_config(page_title="OCR PDF & Ảnh Toán – Mistral", layout="wide")
st.title("✨ Chuyển PDF & Ảnh Toán sang Markdown với Mistral AI ✨")

# Kiểm tra dependencies
missing_deps = []
if not HAS_PYMUPDF and not HAS_PYPDF2:
    missing_deps.append("PyMuPDF hoặc PyPDF2 (cho xử lý PDF)")
if not HAS_DOCX:
    missing_deps.append("python-docx (cho xuất Word)")

if missing_deps:
    st.error(f"⚠️ Thiếu dependencies: {', '.join(missing_deps)}")
    st.code(f"pip install {'PyMuPDF' if not HAS_PYMUPDF else ''} {'python-docx' if not HAS_DOCX else ''}")

tab_img, tab_pdf = st.tabs(["🖼️ Ảnh", "📄 PDF"])

with tab_img:
    uploaded_images = st.file_uploader(
        "Chọn nhiều ảnh (mỗi ảnh là một trang):",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="Mỗi ảnh là 1 trang, minh hoạ & bảng sẽ được tách tự động."
    )
    
    if uploaded_images:
        for img_idx, img_file in enumerate(uploaded_images):
            with st.expander(f"ℹ️ Thông tin file: {img_file.name}", expanded=True):
                st.write(f"**Tên file:** {img_file.name}")
                st.write(f"**Loại file:** {img_file.type}")
                st.write(f"**Kích thước:** {img_file.size / 1024:.1f} KB")
                
            ocr_key = f"ocr_{img_file.name}_{img_idx}"
            text_key = f"text_{img_file.name}_{img_idx}"
            fig_key = f"fig_{img_file.name}_{img_idx}"
            
            if st.button(f"🚀 Xử lý ảnh với Mistral ({img_file.name})", key=ocr_key):
                img_bytes = img_file.read()
                
                # Tách hình ảnh và bảng
                figures, img_h, img_w = extract_figures_and_tables(img_bytes)
                
                # Gọi Mistral OCR
                api_key = get_next_api_key()
                with st.spinner("Đang xử lý với Mistral AI..."):
                    try:
                        if api_key == "your_mistral_api_key_1":
                            st.error("⚠️ Vui lòng cấu hình Mistral API key trong code!")
                            st.code("""
# Thay thế trong code:
MISTRAL_API_KEYS = [
    "your_actual_api_key_here"
]
                            """)
                            st.stop()
                        text = mistral_generate_text(img_bytes, api_key)
                    except Exception as e:
                        text = f"[Lỗi Mistral: {e}]"
                        st.error(f"Lỗi OCR: {e}")
                
                # Xử lý text
                text = normalize_math_latex(text)
                text = clean_latex_blocks(text)
                text = fix_broken_latex_blocks(text)
                text = remove_all_figure_markdown(text)
                text = join_paragraphs_and_insert_figures_tables(text, figures, img_h, img_w)
                formatted_text = format_exam_markdown(text)
                
                st.session_state[text_key] = formatted_text
                st.session_state[fig_key] = figures
                
            if text_key in st.session_state and fig_key in st.session_state:
                st.markdown("### 📋 Kết quả:")
                tab1, tab2 = st.tabs(["📝 Văn bản", "🖼️ Hình ảnh"])
                
                with tab1:
                    st.code(st.session_state[text_key], language="markdown")
                    st.download_button(
                        "📄 Tải văn bản (TXT)",
                        st.session_state[text_key],
                        file_name=f"ket_qua_{img_file.name}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )
                    
                    figures = st.session_state[fig_key]
                    if figures and HAS_DOCX:
                        if st.button("📝 Xuất ra Word",
                                   use_container_width=True,
                                   key=f"word-{img_file.name}-{img_idx}"):
                            try:
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
                            except Exception as e:
                                st.error(f"Lỗi tạo Word: {e}")
                    elif not HAS_DOCX:
                        st.info("Cài đặt python-docx để xuất Word: pip install python-docx")
                    else:
                        st.info("Không phát hiện minh hoạ hay bảng nào trong ảnh để xuất Word.")
                        
                with tab2:
                    figures = st.session_state[fig_key]
                    if figures:
                        for fig in figures:
                            img_bytes_fig = base64.b64decode(fig["base64"])
                            st.image(img_bytes_fig, caption=fig["name"], use_container_width=True)
                            st.download_button(
                                f"Tải {fig['name']}",
                                img_bytes_fig,
                                file_name=fig["name"],
                                mime="image/jpeg",
                                use_container_width=True,
                                key=f"img-download-{img_file.name}-{img_idx}-{fig['name']}"
                            )
                    else:
                        st.info("Không phát hiện minh hoạ hay bảng nào trong ảnh.")
    else:
        st.info("Vui lòng tải lên ít nhất 1 ảnh để bắt đầu.")

with tab_pdf:
    st.markdown("#### 📝 OCR PDF Toán với Mistral AI, giữ công thức, ảnh minh hoạ")
    uploaded_file = st.file_uploader("Chọn file PDF", type=["pdf"], key="pdf_uploader")
    
    if uploaded_file:
        pdf_bytes = uploaded_file.read()
        file_name = uploaded_file.name
        size_mb = len(pdf_bytes) / (1024 * 1024)
        
        # Hiển thị thông tin file
        try:
            if HAS_PYPDF2:
                reader = PdfReader(io.BytesIO(pdf_bytes))
                num_pages = len(reader.pages)
            else:
                num_pages = "?"
        except:
            num_pages = "?"
            
        with st.expander("ℹ️ Thông tin file", expanded=True):
            cols = st.columns(3)
            cols[0].metric("Tên file", file_name)
            cols[1].metric("Loại file", "application/pdf")
            cols[2].metric("Kích thước", f"{size_mb:.1f} MB")
            st.caption(f"Số trang: {num_pages}")

    if uploaded_file and st.button("🚀 Xử lý OCR PDF", type="primary", use_container_width=True):
        if not (HAS_PYMUPDF or HAS_PYPDF2):
            st.error("❌ Không có thư viện xử lý PDF. Vui lòng cài PyMuPDF: pip install PyMuPDF")
            st.stop()
            
        st.info("⏳ Đang xử lý OCR PDF... (vui lòng chờ)")
        with st.spinner("Đang nhận diện văn bản và trích xuất hình ảnh..."):
            # Trích xuất text từ PDF
            result = extract_text_from_pdf(pdf_bytes)
            
            if not result.get("success"):
                st.error(f"❌ Xử lý PDF thất bại: {result.get('error')}")
                st.stop()
            
            # Trích xuất hình ảnh
            images = extract_images_from_pdf(pdf_bytes)
            
        st.session_state["ocr_text_raw"] = result.get("text_content", "")
        st.session_state["ocr_images"] = images
        st.session_state["ocr_done"] = True
        st.session_state["pdf_method"] = result.get("method", "Unknown")
        st.success(f"✅ Đã nhận diện PDF thành công bằng {result.get('method', 'Unknown')}!")

    if st.session_state.get("ocr_done"):
        raw_text = st.session_state.get("ocr_text_raw", "")
        
        # Xử lý text với chuỗi các hàm sửa lỗi LaTeX
        text_content = normalize_math_latex(raw_text)
        text_content = clean_latex_blocks(text_content)
        text_content = fix_broken_latex_blocks(text_content)
        
        images = st.session_state.get("ocr_images", [])
        method = st.session_state.get("pdf_method", "Unknown")
        
        tab1, tab2 = st.tabs(["📝 Văn bản chính xác", "🖼️ Hình ảnh trích xuất"])
        
        with tab1:
            st.markdown(f"#### 📋 Kết quả OCR PDF ({method}):")
            formatted_text = format_exam_markdown(text_content)
            st.text_area("Nội dung đã được phân tích:", formatted_text, height=350, label_visibility="collapsed")
            st.download_button(
                "📄 Tải văn bản (TXT)",
                formatted_text,
                file_name="ket_qua_ocr_mistral.txt",
                mime="text/plain",
                use_container_width=True,
            )
            
            if HAS_DOCX and st.button("📝 Xuất ra Word", use_container_width=True, key="word_export"):
                try:
                    with st.spinner("Đang tạo file Word..."):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_word:
                            insert_images_to_word_from_markdown(formatted_text, images, tmp_word.name)
                        with open(tmp_word.name, "rb") as f:
                            word_data = f.read()
                        st.success("✅ Đã tạo file Word thành công!")
                        st.download_button(
                            "⬇️ Tải về file Word",
                            word_data,
                            file_name="ket_qua_ocr_mistral.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True
                        )
                        os.remove(tmp_word.name)
                except Exception as e:
                    st.error(f"Lỗi tạo Word: {e}")
            elif not HAS_DOCX:
                st.info("Cài đặt python-docx để xuất Word: pip install python-docx")
                    
        with tab2:
            if images:
                st.success(f"🖼️ Đã tìm thấy {len(images)} hình ảnh:")
                cols = st.columns(4)
                for idx, fig in enumerate(images):
                    try:
                        with cols[idx % 4]:
                            with st.expander(fig["name"], expanded=True):
                                img_bytes = base64.b64decode(fig["base64"])
                                st.image(img_bytes, use_container_width=True)
                                st.download_button(
                                    f"Tải {fig['name']}",
                                    img_bytes,
                                    file_name=fig["name"],
                                    mime="image/jpeg",
                                    use_container_width=True,
                                    key=f"pdf-download-{idx}"
                                )
                    except Exception as e:
                        st.error(f"Không đọc được ảnh {fig['name']}: {e}")
            else:
                st.warning("Không tìm thấy ảnh minh hoạ trong PDF!")
                
    st.markdown("---")
    st.caption("✨ Hệ thống sử dụng Mistral AI để nhận diện chính xác văn bản toán học và tự động mapping hình ảnh/bảng vào đúng vị trí")

# Sidebar thông tin
if st.sidebar.checkbox("ℹ️ Hiển thị thông tin kỹ thuật"):
    st.sidebar.write("**Phiên bản:** 2.0.0 - Mistral AI Standalone")
    st.sidebar.write("**Cập nhật:** 2024-07-19")
    st.sidebar.write("**AI Engine:** Mistral Pixtral-12B")
    st.sidebar.write("**PDF Engine:** " + ("PyMuPDF" if HAS_PYMUPDF else "PyPDF2" if HAS_PYPDF2 else "Không có"))
    st.sidebar.write("**Word Export:** " + ("Có" if HAS_DOCX else "Không"))
    st.sidebar.write("**Dependencies:**")
    st.sidebar.write(f"- PyMuPDF: {'✅' if HAS_PYMUPDF else '❌'}")
    st.sidebar.write(f"- PyPDF2: {'✅' if HAS_PYPDF2 else '❌'}")
    st.sidebar.write(f"- python-docx: {'✅' if HAS_DOCX else '❌'}")

# Cấu hình API keys
st.sidebar.markdown("### ⚙️ Cấu hình API")
with st.sidebar.expander("Mistral API Keys", expanded=False):
    if MISTRAL_API_KEYS[0] == "your_mistral_api_key_1":
        st.warning("⚠️ Chưa cấu hình API key!")
    else:
        st.success("✅ API key đã được cấu hình")
    st.info("Thay đổi API keys trong source code")
    st.code("""
MISTRAL_API_KEYS = [
    "3OLLsQhSn7SFx4kBzEjeRJ7S4MikrdcO"
]
    """)
    st.caption("Lấy API key tại: https://console.mistral.ai/")

# Hướng dẫn cài đặt
with st.sidebar.expander("📦 Hướng dẫn cài đặt", expanded=False):
    st.code("""
# Cài đặt dependencies
pip install streamlit
pip install PyMuPDF
pip install python-docx
pip install opencv-python
pip install Pillow
pip install numpy
pip install requests

# Chạy ứng dụng
streamlit run app.py
    """)
