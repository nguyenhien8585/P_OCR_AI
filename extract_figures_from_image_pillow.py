from PIL import Image, ImageFilter
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def extract_figures_from_image(img_bytes, min_area=3000, blur_radius=2, max_figures=4):
    """
    Tách các vùng hình minh hoạ thực sự, loại đường viền/mép giấy/cạnh nhỏ.
    - Chỉ lấy vùng lớn, tỉ lệ khung hình hợp lý, không quá sát mép
    - max_figures: số hình tối đa trả về (mặc định 2-4)
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    arr = np.array(img)
    h, w = arr.shape
    img_blur = img.filter(ImageFilter.GaussianBlur(blur_radius))
    arr_blur = np.array(img_blur)
    edge = np.abs(arr.astype(np.int16) - arr_blur.astype(np.int16))
    edge = (edge > 12).astype(np.uint8)
    labeled, num = label(edge)
    objects = find_objects(labeled)
    color_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    results = []
    candidates = []
    for obj in objects:
        if obj is None: continue
        y0, y1 = obj[0].start, obj[0].stop
        x0, x1 = obj[1].start, obj[1].stop
        area = (x1-x0)*(y1-y0)
        # Lọc vùng lớn, không quá mỏng, tỉ lệ ảnh ~ hình chữ nhật
        aspect = (x1-x0)/(y1-y0+1e-5)
        area_ratio = area/(h*w)
        # Loại vùng nhỏ hoặc cực dài/mỏng
        if area > min_area and 0.25 < aspect < 4.0 and 0.015 < area_ratio < 0.5:
            # Không lấy vùng sát mép giấy (chừa 2% mép)
            if x0 < 0.02*w or x1 > 0.98*w or y0 < 0.02*h or y1 > 0.98*h:
                continue
            candidates.append((area, x0, y0, x1, y1))
    # Chỉ lấy các vùng lớn nhất
    candidates = sorted(candidates, key=lambda x: -x[0])[:max_figures]
    for idx, (area, x0, y0, x1, y1) in enumerate(candidates):
        crop = color_img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results
