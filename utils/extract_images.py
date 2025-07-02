import cv2

def extract_diagrams(image_path, save_prefix):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 15, -2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    idx = 1
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h > 10_000:
            roi = img[y:y + h, x:x + w]
            cv2.imwrite(f"{save_prefix}_{idx}.png", roi)
            idx += 1
