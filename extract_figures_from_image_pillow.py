from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def preprocess_img(img):
    # Tăng sáng và tương phản, làm nét nhẹ
    img = img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.8)  # tăng tương phản
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.1)  # tăng sáng
    img = img.filter(ImageFilter.MedianFilter(3)) # giảm nhiễu
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=200)) # làm nét
    return img

def extract_figures_from_image(
    img_bytes,
    max_figures=3,
    min_area=1200,
    min_aspect=0.25,
    max_aspect=5.0,
    min_area_ratio=0.005,
    max_area_ratio=0.45,
    margin=0.01
):
    """
    Tự động tăng nét & tách đúng các hình vẽ lớn + bảng biến thiên.
    """
    # --- Tiền xử lý ảnh ---
    orig_img = Image.open(io.BytesIO(img_bytes))
    img = preprocess_img(orig_img)
    arr = np.array(img)
    h, w = arr.shape
    img_blur = img.filter(ImageFilter.GaussianBlur(1))
    arr_blur = np.array(img_blur)
    edge = np.abs(arr.astype(np.int16) - arr_blur.astype(np.int16))
    edge = (edge > 7).astype(np.uint8)
    labeled, num = label(edge)
    objects = find_objects(labeled)
    color_img = orig_img.convert("RGB")
    candidates = []
    for obj in objects:
        if obj is None: continue
        y0, y1 = obj[0].start, obj[0].stop
        x0, x1 = obj[1].start, obj[1].stop
        area = (x1-x0)*(y1-y0)
        aspect = (x1-x0)/(y1-y0+1e-5)
        area_ratio = area/(h*w)
        crop_arr = arr[y0:y1, x0:x1]
        mean_pixel = crop_arr.mean()
        std_pixel = crop_arr.std()
        # Không lấy block nhỏ, block dị, block sát mép, block có nhiều text (mean thấp, std thấp)
        if (
            area > min_area and
            min_aspect < aspect < max_aspect and
            min_area_ratio < area_ratio < max_area_ratio and
            x0 > margin*w and x1 < (1-margin)*w and y0 > margin*h and y1 < (1-margin)*h and
            mean_pixel > 90 and std_pixel > 13
        ):
            candidates.append((area, x0, y0, x1, y1, aspect))
    # Ưu tiên chọn: 1 hình gần vuông (aspect gần 1), 1 hình chữ nhật (bảng biến thiên)
    if not candidates:
        return []
    # Sắp xếp theo diện tích giảm dần
    candidates = sorted(candidates, key=lambda x: -x[0])
    # Chọn 1 hình aspect ~1 (vuông) + 1-2 hình aspect >1.7 (bảng)
    shapes = [c for c in candidates if 0.75 < c[5] < 1.35]
    tables = [c for c in candidates if c[5] >= 1.4 or c[5] <= 0.7]
    chosen = []
    if shapes: chosen.append(shapes[0])
    if tables: chosen.append(tables[0])
    # Nếu thiếu, bổ sung các block lớn tiếp theo
    for c in candidates:
        if c not in chosen and len(chosen) < max_figures:
            chosen.append(c)
    results = []
    for idx, (area, x0, y0, x1, y1, _) in enumerate(chosen[:max_figures]):
        crop = color_img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results
