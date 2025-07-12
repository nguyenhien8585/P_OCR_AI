def extract_figures_from_image(
    img_bytes,
    max_figures=3,
    min_area=900,
    min_aspect=0.18,
    max_aspect=6.0,
    min_area_ratio=0.004,
    max_area_ratio=0.50,
    margin=0.01
):
    from PIL import Image, ImageEnhance, ImageFilter
    import numpy as np
    import base64
    import io
    from scipy.ndimage import label, find_objects

    orig_img = Image.open(io.BytesIO(img_bytes))
    img = orig_img.convert("L")
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.7)
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.08)
    img = img.filter(ImageFilter.MedianFilter(3))
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150))
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
        percent_white = np.mean(crop_arr > 200)
        # Loại tiêu đề, mã đề (nằm sát trên cùng)
        # Chỉ lấy block có y0 cách trên >12% chiều cao và không sát dưới
        if (
            area > min_area and
            min_aspect < aspect < max_aspect and
            min_area_ratio < area_ratio < max_area_ratio and
            x0 > margin*w and x1 < (1-margin)*w and
            y0 > int(0.12*h) and y1 < int(0.93*h) and
            mean_pixel > 90 and std_pixel > 15 and percent_white > 0.18
        ):
            candidates.append((area, x0, y0, x1, y1, aspect, std_pixel, percent_white))
    # Sắp xếp theo diện tích lớn nhất
    candidates = sorted(candidates, key=lambda x: -x[0])
    results = []
    for idx, (area, x0, y0, x1, y1, *_ ) in enumerate(candidates[:max_figures]):
        crop = color_img.crop((x0, y0, x1, y1))
        buf = io.BytesIO()
        crop.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append({"name": f"img-{idx+1}.jpeg", "base64": b64})
    return results
