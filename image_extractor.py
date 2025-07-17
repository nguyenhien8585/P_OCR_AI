import cv2
import numpy as np
from PIL import Image
import base64
import io
import re

class ImageExtractor:
    """
    Class để tách ảnh/bảng từ ảnh gốc và chèn vào đúng vị trí trong văn bản
    """
    
    def __init__(self):
        self.min_area_ratio = 0.008    # Diện tích tối thiểu (% của ảnh gốc)
        self.min_area_abs = 2500       # Diện tích tối thiểu (pixel)
        self.min_width = 70            # Chiều rộng tối thiểu
        self.min_height = 70           # Chiều cao tối thiểu
        self.max_figures = 8           # Số lượng ảnh tối đa
    
    def extract_figures_and_tables(self, image_bytes):
        """
        Tách ảnh và bảng từ ảnh gốc
        
        Args:
            image_bytes: Dữ liệu ảnh dạng bytes
            
        Returns:
            tuple: (danh_sách_ảnh, chiều_cao, chiều_rộng)
        """
        # 1. Đọc ảnh
        img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = np.array(img_pil)
        h, w = img.shape[:2]
        
        # 2. Tiền xử lý ảnh
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        
        # 3. Tăng cường độ tương phản
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        
        # 4. Tạo ảnh nhị phân (đen trắng)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
            cv2.THRESH_BINARY_INV, 25, 10
        )
        
        # 5. Làm dày các đường viền
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=1)
        
        # 6. Tìm các contour (đường viền)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 7. Lọc và phân loại các vùng
        candidates = []
        for cnt in contours:
            # Tính toán thông số hình học
            x, y, ww, hh = cv2.boundingRect(cnt)
            area = ww * hh
            area_ratio = area / (w * h)
            aspect_ratio = ww / (hh + 1e-6)  # Tỷ lệ khung hình
            
            # Loại bỏ các vùng quá nhỏ hoặc quá lớn
            if (area < self.min_area_abs or 
                area_ratio < self.min_area_ratio or 
                area_ratio > 0.6):
                continue
            
            # Loại bỏ các vùng có kích thước không phù hợp
            if ww < self.min_width or hh < self.min_height:
                continue
            
            # Loại bỏ các vùng có tỷ lệ khung hình không hợp lý
            if not (0.2 < aspect_ratio < 8.0):
                continue
            
            # Loại bỏ các vùng ở rìa ảnh
            if (x < 0.03*w or y < 0.03*h or 
                (x+ww) > 0.97*w or (y+hh) > 0.97*h):
                continue
            
            # Kiểm tra độ đặc của hình
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            if hull_area == 0:
                continue
            solidity = float(area) / hull_area
            if solidity < 0.4:
                continue
            
            # Phân loại: Bảng hay Hình
            is_table = (ww > 0.25*w and hh > 0.05*h and 
                       aspect_ratio > 2.0 and aspect_ratio < 10.0)
            
            candidates.append({
                "area": area,
                "x0": x, "y0": y, "x1": x+ww, "y1": y+hh,
                "is_table": is_table,
                "bbox": (x, y, ww, hh)
            })
        
        # 8. Sắp xếp theo diện tích (lớn nhất trước)
        candidates = sorted(candidates, key=lambda f: f['area'], reverse=True)
        
        # 9. Loại bỏ các box lồng nhau
        candidates = self._filter_nested_boxes(candidates)
        
        # 10. Giới hạn số lượng và sắp xếp theo vị trí
        candidates = candidates[:self.max_figures]
        candidates = sorted(candidates, key=lambda box: (box["y0"], box["x0"]))
        
        # 11. Tạo danh sách ảnh kết quả
        final_figures = []
        img_idx = 0
        table_idx = 0
        
        for fig_data in candidates:
            # Cắt ảnh
            crop = img[fig_data["y0"]:fig_data["y1"], fig_data["x0"]:fig_data["x1"]]
            
            # Chuyển thành base64
            buf = io.BytesIO()
            Image.fromarray(crop).save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            
            # Đặt tên file
            if fig_data["is_table"]:
                name = f"table-{table_idx+1}.jpeg"
                table_idx += 1
            else:
                name = f"img-{img_idx+1}.jpeg"
                img_idx += 1
            
            final_figures.append({
                "name": name,
                "base64": b64,
                "is_table": fig_data["is_table"],
                "bbox": fig_data["bbox"]
            })
        
        return final_figures, h, w
    
    def _filter_nested_boxes(self, candidates):
        """
        Loại bỏ các box nằm bên trong box khác
        """
        filtered = []
        for i, box in enumerate(candidates):
            x0, y0, x1, y1 = box['x0'], box['y0'], box['x1'], box['y1']
            is_nested = False
            
            # Kiểm tra xem box này có nằm trong box nào khác không
            for j, other in enumerate(candidates):
                if i == j:
                    continue
                ox0, oy0, ox1, oy1 = other['x0'], other['y0'], other['x1'], other['y1']
                
                # Nếu box hiện tại nằm hoàn toàn trong box khác
                if x0 >= ox0 and y0 >= oy0 and x1 <= ox1 and y1 <= oy1:
                    is_nested = True
                    break
            
            if not is_nested:
                filtered.append(box)
        
        return filtered
    
    def insert_figures_into_text(self, text, figures, img_h, img_w):
        """
        Chèn ảnh/bảng vào đúng vị trí trong văn bản
        
        Args:
            text: Văn bản gốc
            figures: Danh sách ảnh đã tách
            img_h, img_w: Kích thước ảnh gốc
            
        Returns:
            str: Văn bản đã chèn ảnh/bảng
        """
        # 1. Tiền xử lý văn bản thành các dòng
        lines = self._preprocess_text_lines(text)
        
        # 2. Sắp xếp ảnh theo vị trí (từ trên xuống, trái sang phải)
        figures_sorted = sorted(
            [fig for fig in figures if fig.get('bbox')],
            key=lambda f: (f['bbox'][1], f['bbox'][0])  # (y, x)
        )
        
        # 3. Chèn ảnh/bảng vào văn bản
        processed_lines = []
        used_figures = set()
        fig_idx = 0
        
        for i, line in enumerate(lines):
            processed_lines.append(line)
            
            # Kiểm tra các từ khóa để chèn ảnh/bảng
            inserted = self._try_insert_figure(
                line, figures_sorted, used_figures, 
                processed_lines, fig_idx
            )
            
            if inserted:
                fig_idx = inserted
        
        # 4. Chèn các ảnh còn lại vào câu hỏi
        processed_lines = self._insert_remaining_figures(
            processed_lines, figures_sorted, used_figures, fig_idx
        )
        
        return '\n'.join(processed_lines)
    
    def _preprocess_text_lines(self, text):
        """
        Tiền xử lý văn bản thành các dòng hợp lý
        """
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
        
        return lines
    
    def _try_insert_figure(self, line, figures_sorted, used_figures, processed_lines, fig_idx):
        """
        Thử chèn ảnh/bảng dựa trên từ khóa trong dòng
        """
        lower_line = line.lower()
        
        # Từ khóa cho bảng
        table_keywords = [
            "bảng", "bảng giá trị", "bảng biến thiên", 
            "bảng tần số", "bảng số liệu"
        ]
        
        # Từ khóa cho hình
        image_keywords = [
            "hình vẽ", "hình bên", "(hình", "xem hình", 
            "đồ thị", "biểu đồ", "minh họa", "hình"
        ]
        
        # Kiểm tra và chèn bảng
        if (any(keyword in lower_line for keyword in table_keywords) or 
            (line.strip().startswith("|") and "|" in line)):
            
            for j in range(fig_idx, len(figures_sorted)):
                fig = figures_sorted[j]
                if fig['is_table'] and fig['name'] not in used_figures:
                    tag = f"[BẢNG: {fig['name']}]"
                    processed_lines.append(tag)
                    used_figures.add(fig['name'])
                    return j + 1
        
        # Kiểm tra và chèn hình
        elif any(keyword in lower_line for keyword in image_keywords):
            for j in range(fig_idx, len(figures_sorted)):
                fig = figures_sorted[j]
                if not fig['is_table'] and fig['name'] not in used_figures:
                    tag = f"[HÌNH: {fig['name']}]"
                    processed_lines.append(tag)
                    used_figures.add(fig['name'])
                    return j + 1
        
        return fig_idx
    
    def _insert_remaining_figures(self, processed_lines, figures_sorted, used_figures, fig_idx):
        """
        Chèn các ảnh còn lại vào đầu các câu hỏi
        """
        for i, line in enumerate(processed_lines):
            # Tìm các câu hỏi (Câu 1., Câu 2., ...)
            if re.match(r"^Câu\s*\d+[\.\:]", line) and fig_idx < len(figures_sorted):
                # Kiểm tra dòng tiếp theo có phải là tag ảnh/bảng không
                next_line = processed_lines[i+1] if i+1 < len(processed_lines) else ""
                
                if (not re.match(r"\[HÌNH:.*\]", next_line) and 
                    not re.match(r"\[BẢNG:.*\]", next_line)):
                    
                    # Tìm ảnh chưa sử dụng
                    while (fig_idx < len(figures_sorted) and 
                           figures_sorted[fig_idx]['name'] in used_figures):
                        fig_idx += 1
                    
                    # Chèn ảnh
                    if fig_idx < len(figures_sorted):
                        fig = figures_sorted[fig_idx]
                        tag = (f"[BẢNG: {fig['name']}]" if fig['is_table'] 
                               else f"[HÌNH: {fig['name']}]")
                        processed_lines.insert(i+1, tag)
                        used_figures.add(fig['name'])
                        fig_idx += 1
        
        return processed_lines


# ==================== EXAMPLE USAGE ====================

def example_usage():
    """
    Ví dụ sử dụng ImageExtractor
    """
    # Khởi tạo
    extractor = ImageExtractor()
    
    # Giả sử có ảnh và văn bản
    with open("example_image.png", "rb") as f:
        image_bytes = f.read()
    
    text = """
    Câu 1. Cho hàm số y = x^2 + 2x + 1. Hãy vẽ đồ thị hàm số.
    
    Xem bảng giá trị sau đây:
    
    Câu 2. Tính giá trị của biểu thức theo hình vẽ bên dưới.
    """
    
    # Tách ảnh
    figures, h, w = extractor.extract_figures_and_tables(image_bytes)
    print(f"Đã tách được {len(figures)} ảnh:")
    for fig in figures:
        print(f"- {fig['name']} ({'Bảng' if fig['is_table'] else 'Hình'})")
    
    # Chèn ảnh vào văn bản
    result_text = extractor.insert_figures_into_text(text, figures, h, w)
    print("\nVăn bản sau khi chèn ảnh:")
    print(result_text)


if __name__ == "__main__":
    example_usage()
