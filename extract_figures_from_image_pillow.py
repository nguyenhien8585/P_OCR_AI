from PIL import Image
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def extract_figures_from_image(img_bytes, min_area=2000):
    """
    Tự động tách các vùng hình vẽ trong ảnh (block đậm, sát mép).
    - min_area: diện tích tối thiểu của 1 hình để tách (pixel).
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")  # Gray
    arr = np.array(img)
    # Threshold: các pixel tối hơn ngưỡng là vùng hình vẽ
    mask = arr < 180  # Ngưỡng có thể chỉnh
    # Label các vùng connected (liên thông)
    labeled, num = label(mask)
    objects = find_objects(labeled)
    results = []
    idx = 0
    color_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    for obj in objects:
        if obj is None: continue
        y0, y1 = obj[0].start, obj[0].stop
        x0, x1 = obj[1].start, obj[1].stop
        # Lọc vùng đủ lớn (tránh cắt ký tự, gạch chân, ...)
        if (x1-x0)*(y1-y0) > min_area:
            crop = color_img.crop((x0, y0, x1, y1))
            buf = io.BytesIO()
            crop.save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            results.append({"name": f"img-{idx}.jpeg", "base64": b64})
            idx += 1
    return results
