import cv2
import pytesseract
from PIL import Image
import numpy as np

def test_tesseract(image_path):
    print(f"Testing local Tesseract OCR on {image_path}...")
    
    # 1. Read the image
    img = cv2.imread(image_path)
    
    # 2. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 3. Resize (upscale) to improve OCR accuracy for small text
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # 4. Apply thresholding to get clear black text on white background
    # BBDC captchas might need different thresholding, let's try Otsu's
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 5. Denoise (optional, depends on how dirty the captcha is)
    # blurred = cv2.medianBlur(thresh, 3)
    
    # 6. Run Tesseract with specific config
    # --psm 8: Treat the image as a single word
    # -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 (optional whitelist)
    custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    
    text = pytesseract.image_to_string(thresh, config=custom_config)
    print(f"Raw Tesseract output: '{text}'")
    
    cleaned_text = ''.join(e for e in text if e.isalnum())
    print(f"Cleaned Tesseract Output: '{cleaned_text}'")
    
    # Save the processed image to see what tesseract is "seeing"
    cv2.imwrite("processed_test_captcha.png", thresh)
    print("Saved pre-processed image to processed_test_captcha.png")

if __name__ == "__main__":
    test_tesseract("test_captcha.png")
