# pix2tex_wrapper.py
import base64
from pix2tex.cli import LatexOCR
from PIL import Image
import io

model = LatexOCR()

def recognize_latex_from_images(images):
    results = []
    for fig in images:
        try:
            img_data = base64.b64decode(fig["base64"])
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            latex = model(img)
            results.append({"name": fig["name"], "latex": latex})
        except Exception as e:
            results.append({"name": fig["name"], "latex": f"ERROR: {e}"})
    return results
