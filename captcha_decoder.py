#!/usr/bin/python3
# coding: utf-8

import re
import time
import argparse
import logging
import io
import base64
import cv2
import numpy as np
import easyocr
from PIL import Image, ImageOps

# setup logging
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

# Initialize EasyOCR reader once (model loads on first call)
_reader = None

def _get_reader():
    global _reader
    if _reader is None:
        logging.info("Loading EasyOCR model (first run downloads ~100MB model)...")
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        logging.info("EasyOCR model loaded successfully.")
    return _reader

def solve_captcha(base64_string, api_key=None):
    """
    Solves the captcha image using EasyOCR (runs locally, no API calls).
    Arguments:
        base64_string (str): The base64 encoded string from BBDC
        api_key (str): Unused, kept for backward compatibility
            
    Return:
        Tuple[str, int]: 'textualized' OCR string and confidence level
    """
    try:
        reader = _get_reader()
        
        # Decode base64 to numpy array for OpenCV
        img_data = base64.b64decode(base64_string)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return ("", 0)
        
        # Light preprocessing: upscale + contrast enhancement
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Run EasyOCR with alphanumeric whitelist
        raw_results = reader.readtext(
            enhanced,
            detail=1,
            allowlist='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
            paragraph=False
        )
        
        # Combine all detected text fragments
        full_text = ''.join([r[1] for r in raw_results])
        cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', full_text)
        
        # Average confidence across all detected regions
        avg_conf = sum(r[2] for r in raw_results) / len(raw_results) if raw_results else 0
        
        # STRICT VALIDATION: BBDC Captchas are always 5-6 characters.
        conf = 99 if 5 <= len(cleaned_text) <= 6 else 0
        logging.info(f"EasyOCR result: '{cleaned_text}' | Length: {len(cleaned_text)} | Model conf: {avg_conf:.1%} | Valid: {conf}%")
        return (cleaned_text, conf)
        
    except Exception as e:
        logging.error(f"EasyOCR failed: {e}")
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
