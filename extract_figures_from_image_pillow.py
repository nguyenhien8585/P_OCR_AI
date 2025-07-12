from PIL import Image, ImageFilter
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def extract_figures_from_image(
    img_bytes,
    min_area=1800,
    blur_radius=1,
    max_figures=10,
    min_aspect=0.20,
    max_aspect=5.0,
    min_area_ratio=0.004,
    max_area_ratio=0.7,
    min_mean_pixel=160,
    min_std_pixel=12
):
    """
    Tách tất cả các vùng nghi là hình minh hoạ – để user tick chọn lại cho chính xác.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    arr = np.array(img)
    h, w = arr.shape
    img_blur = img.filter(ImageFilter.GaussianBlur(blur_radius))
    arr_blur = np.array(img_blur)
    edge = np.abs(arr.astype(np.int16) - arr_blur.astype(np.int16))
    edge = (edge > 10).astype(np.uint8)
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
        aspect = (x1-x0)/(y1-y0+1e-5)
        area_ratio = area/(h*w)
        crop_arr = arr[y0:y1, x0:x1]
        mean_pixel = crop_arr.mean()
        std_pixel = crop_arr.std()
        if (
            area > min_area and
            min_aspect < aspect < max_aspect and
            min_area_ratio < area_ratio < max_area_ratio and
            x0 > 0.005*w and x1 < 0.995*w and y0 > 0.005*h and y1 < 0.995*h and
            mean_pixel > min_mean_pixel and
            std_pixel > min_std_pixel
        ):
            candidates.append((area, x0, y0, x1, y1))
    candidates = sorted(candidates, key=lambda x: -x[0])[:max_figures]
    for idx, (area, x0, y0, x1, y1) in enumerate(candidates):
        crop = color_img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results
