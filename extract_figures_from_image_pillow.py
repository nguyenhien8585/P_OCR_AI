from PIL import Image, ImageFilter
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def extract_figures_from_image(img_bytes, min_area=1500, blur_radius=2):
    """
    Tách các vùng hình minh hoạ khỏi ảnh lớn hoặc từng trang PDF.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    arr = np.array(img)
    img_blur = img.filter(ImageFilter.GaussianBlur(blur_radius))
    arr_blur = np.array(img_blur)
    edge = np.abs(arr.astype(np.int16) - arr_blur.astype(np.int16))
    edge = (edge > 12).astype(np.uint8)
    labeled, num = label(edge)
    objects = find_objects(labeled)
    color_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    results = []
    idx = 0
    for obj in objects:
        if obj is None: continue
        y0, y1 = obj[0].start, obj[0].stop
        x0, x1 = obj[1].start, obj[1].stop
        if (x1-x0)*(y1-y0) > min_area and (y1-y0)>30 and (x1-x0)>30:
            crop = color_img.crop((x0, y0, x1, y1))
            if (x1-x0)<0.95*color_img.width and (y1-y0)<0.95*color_img.height:
                buf = io.BytesIO()
                crop.save(buf, format="JPEG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                results.append({"name": f"img-{idx}.jpeg", "base64": b64})
                idx += 1
    return results
