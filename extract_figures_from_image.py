import cv2
import numpy as np
import base64
from PIL import Image
import io

def extract_figures_from_image(img_bytes):
    img_array = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    edged = cv2.Canny(blur, 30, 150)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    figures = []
    idx = 0
    h, w = img.shape[:2]
    for c in contours:
        x, y, w_box, h_box = cv2.boundingRect(c)
        if w_box * h_box > 3000 and w_box < 0.85 * w and h_box < 0.85 * h:
            crop = img[y:y+h_box, x:x+w_box]
            pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
            buf = io.BytesIO()
            pil_img.save(buf, format="JPEG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            figures.append({"name": f"figure-{idx}.jpeg", "base64": b64})
            idx += 1
    return figures
