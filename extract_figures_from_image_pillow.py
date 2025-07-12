from PIL import Image, ImageFilter
import numpy as np
import base64
import io
from scipy.ndimage import label, find_objects

def extract_figures_from_image(
    img_bytes,
    min_area=4000,        # Diện tích tối thiểu 1 block (pixel)
    blur_radius=2,        # Độ làm mờ biên khi detect block
    max_figures=4,        # Số hình tối đa trả về
    min_aspect=0.35,      # Tỉ lệ khung hình tối thiểu (chặn hình quá mỏng/dài)
    max_aspect=3.0,       # Tỉ lệ khung hình tối đa
    min_area_ratio=0.015, # Tỉ lệ diện tích nhỏ nhất trên toàn ảnh
    max_area_ratio=0.5,   # Tỉ lệ diện tích lớn nhất trên toàn ảnh
    min_mean_pixel=180,   # Độ trắng nền tối thiểu (tùy đề scan)
    min_std_pixel=28      # Độ lệch chuẩn pixel (phân biệt hình vẽ với text/công thức)
):
    """
    Tách các vùng hình minh hoạ thực sự, loại công thức/text/mép giấy.
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
        aspect = (x1-x0)/(y1-y0+1e-5)
        area_ratio = area/(h*w)
        crop_arr = arr[y0:y1, x0:x1]
        mean_pixel = crop_arr.mean()
        std_pixel = crop_arr.std()
        # Điều kiện lọc:
        if (
            area > min_area and
            min_aspect < aspect < max_aspect and
            min_area_ratio < area_ratio < max_area_ratio and
            x0 > 0.01*w and x1 < 0.99*w and y0 > 0.01*h and y1 < 0.99*h and
            mean_pixel > min_mean_pixel and
            std_pixel > min_std_pixel
        ):
            candidates.append((area, x0, y0, x1, y1))
    # Lấy các block lớn nhất (nếu có)
    candidates = sorted(candidates, key=lambda x: -x[0])[:max_figures]
    for idx, (area, x0, y0, x1, y1) in enumerate(candidates):
        crop = color_img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results
