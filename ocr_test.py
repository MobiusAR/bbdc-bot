import cv2
import pytesseract
import numpy as np

def test_ocr(image_path):
    print(f"--- Testing {image_path} ---")
    img = cv2.imread(image_path)
    
    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. Threshold: convert to pure black and white, and INVERT (white text, black bg)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # 3. Dilate the white text to connect broken pieces caused by the interference lines
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    
    # 4. Invert back to black text on white bg for tesseract
    final_img = cv2.bitwise_not(dilated)
    
    # 5. Resize to give more pixels to work with
    img_large = cv2.resize(final_img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 6. Run Tesseract 
    custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    text = pytesseract.image_to_string(img_large, config=custom_config)
    
    print(f"OCR Result: '{text.strip()}'")

test_ocr('/Users/aalhadrangnekar/bbdc-booking-bot/captchas/captcha_1772259361602.png')
test_ocr('/Users/aalhadrangnekar/bbdc-booking-bot/captchas/captcha_1772259330324.png')
