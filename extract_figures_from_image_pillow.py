from PIL import Image, ImageFilter
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def extract_figures_from_image(
    img_bytes,
    min_area=900,           # nhỏ hơn để bắt bảng nhỏ
    blur_radius=1,
    max_figures=4,          # lấy cả hình vẽ và bảng biến thiên
    min_aspect=0.3,         # nới cho bảng dài/ngang/dọc
    max_aspect=4.0,
    min_area_ratio=0.005,
    max_area_ratio=0.45,
    margin=0.01             # bỏ sát mép nhẹ thôi
):
    """
    Tách cả hình vẽ & bảng biến thiên (2-3 hình lớn nhất, nhiều hình chữ nhật).
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    arr = np.array(img)
    h, w = arr.shape
    img_blur = img.filter(ImageFilter.GaussianBlur(blur_radius))
    arr_blur = np.array(img_blur)
    edge = np.abs(arr.astype(np.int16) - arr_blur.astype(np.int16))
    edge = (edge > 8).astype(np.uint8)
    labeled, num = label(edge)
    objects = find_objects(labeled)
    color_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    candidates = []
    for obj in objects:
        if obj is None: continue
        y0, y1 = obj[0].start, obj[0].stop
        x0, x1 = obj[1].start, obj[1].stop
        area = (x1-x0)*(y1-y0)
        aspect = (x1-x0)/(y1-y0+1e-5)
        area_ratio = area/(h*w)
        if (x0 < margin*w or x1 > (1-margin)*w or y0 < margin*h or y1 > (1-margin)*h):
            continue
        if (area > min_area and
            min_aspect < aspect < max_aspect and
            min_area_ratio < area_ratio < max_area_ratio):
            candidates.append((area, x0, y0, x1, y1))
    candidates = sorted(candidates, key=lambda x: -x[0])[:max_figures]
    results = []
    for idx, (area, x0, y0, x1, y1) in enumerate(candidates):
        crop = color_img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results
