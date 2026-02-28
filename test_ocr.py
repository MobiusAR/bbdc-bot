import base64
import sys
from captcha_decoder import solve_captcha

def test_ocr(file_path):
    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    
    print(f"Testing {file_path} against OCR.space...")
    text, conf = solve_captcha(encoded_string)
    print(f"Result: {text} | Confidence: {conf}%")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_ocr(sys.argv[1])
    else:
        test_ocr("test_captcha.png")
