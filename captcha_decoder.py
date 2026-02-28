#!/usr/bin/python3
# coding: utf-8

import requests
import time
import argparse
import logging
import io
import base64
import re
from PIL import Image, ImageOps

# setup logging
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

def solve_captcha(base64_string, api_key="K82590680388957"):
    """
    Sends the captcha image to OCR.space API for highly accurate 
    Alphanumeric character decoding, with pre-processing for better results.
    Arguments:
        base64_string (str): The base64 encoded string from BBDC
        api_key (str): Free tier API key from ocr.space
            
    Return:
        Tuple[str, int]: 'textualized' OCR string and confidence level
    """
    try:
        # PRE-PROCESSING
        # Decode base64 to image
        img_data = base64.b64decode(base64_string)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        
        # Upscale and add contrast since BBDC captchas are small and noisy
        img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
        img = ImageOps.autocontrast(img)
        img = img.convert("L") # Grayscale
        
        # Save back to base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        processed_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # OCR.space API expects a payload
        payload = {
            'isOverlayRequired': False,
            'apikey': api_key,
            'language': 'eng',
            'OCREngine': '2', # Engine 2 is best for standard alphanumeric
            'scale': 'true',
            'base64Image': f"data:image/png;base64,{processed_base64}"
        }
        
        # Retry loop for OCR.space API calls
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    'https://api.ocr.space/parse/image',
                    data=payload,
                    timeout=30 # Increased timeout for free tier stability
                )
                response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                logging.warning(f"OCR.space API attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return ("", 0)
                time.sleep(2 * (attempt + 1))
        
        if not response:
            return ("", 0)
            
        result_json = response.json()
        
        if result_json.get('IsErroredOnProcessing'):
            logging.error(f"OCR API Error: {result_json.get('ErrorMessage')}")
            return ("", 0)
            
        parsed_results = result_json.get('ParsedResults')
        if not parsed_results:
            return ("", 0)
            
        text = parsed_results[0].get('ParsedText', '').strip()
        
        # Strip all whitespace and non-alphanumeric characters
        cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', text)

        # STRICT VALIDATION: BBDC Captchas are always 5-6 characters.
        conf = 99 if 5 <= len(cleaned_text) <= 6 else 0
        logging.info(f"External OCR result: '{cleaned_text}' | Confidence (implied): {conf}%")
        return (cleaned_text, conf)
        
    except Exception as e:
        logging.error(f"Failed to submit captcha to OCR.space: {e}")
        return ("", 0)

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "-i", "--image", required=True, help="path to input image to be OCR'd"
    )
    args = vars(argparser.parse_args())
    path = args["image"]
    with open(path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    print("-- Resolving")
    captcha_text = solve_captcha(encoded_string)[0]
    print("-- Result: {}".format(captcha_text))
