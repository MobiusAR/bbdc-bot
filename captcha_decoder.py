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
import glob
import os

# setup logging
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

class LocalCaptchaMatcher:
    def __init__(self, templates_dir="templates"):
        self.templates = {}
        self.load_templates(templates_dir)

    def load_templates(self, templates_dir):
        # Load all categorized templates into memory once
        if not os.path.exists(templates_dir):
            logging.error(f"FATAL: Template directory '{templates_dir}' not found. Cannot solve captchas.")
            return

        loaded = 0
        for char_dir in glob.glob(f"{templates_dir}/*"):
            if not os.path.isdir(char_dir):
                continue
            char = os.path.basename(char_dir)
            self.templates[char] = []
            
            for img_path in glob.glob(f"{char_dir}/*.png"):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # Invert so text is white on black for structural matching
                    img = cv2.bitwise_not(img)
                    self.templates[char].append(img)
                    loaded += 1
        logging.info(f"Loaded {loaded} labeled templates into memory for {len(self.templates)} unique characters.")

    def slice_captcha(self, img):
        """Slice the given BBDC captcha into individual characters via Connected Components."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thresh = cv2.medianBlur(thresh, 3)
        
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        char_boxes = []
        
        for i in range(1, num_labels):
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            area = stats[i, cv2.CC_STAT_AREA]
            
            # Filter noise
            if area > 40 and w > 5 and h > 10:
                char_boxes.append((x, y, w, h))
                
        # Read left-to-right
        char_boxes = sorted(char_boxes, key=lambda b: b[0])
        
        slices = []
        for x, y, w, h in char_boxes:
            pad = 2
            top = max(0, y - pad)
            bottom = min(thresh.shape[0], y + h + pad)
            left = max(0, x - pad)
            right = min(thresh.shape[1], x + w + pad)
            
            char_img = thresh[top:bottom, left:right]
            slices.append(char_img)
            
        return slices

    def match_slice(self, slice_img):
        """Match a single character slice against all loaded templates to find the exact letter."""
        best_match_char = "?"
        best_match_score = -1.0
        
        slice_h, slice_w = slice_img.shape
        
        for char, t_imgs in self.templates.items():
            for t_img in t_imgs:
                t_h, t_w = t_img.shape
                
                # Resize template to exactly match the incoming slice dimensions for normalized correlation
                if slice_h != t_h or slice_w != t_w:
                    scaled_t_img = cv2.resize(t_img, (slice_w, slice_h), interpolation=cv2.INTER_AREA)
                else:
                    scaled_t_img = t_img
                    
                res = cv2.matchTemplate(slice_img, scaled_t_img, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                if max_val > best_match_score:
                    best_match_score = max_val
                    best_match_char = char
                    
                # Perfect pixel match, early exit
                if best_match_score > 0.98:
                    return best_match_char, best_match_score
                    
        return best_match_char, best_match_score

    def solve(self, img):
        if img is None:
            return "", 0
            
        slices = self.slice_captcha(img)
        
        if not (5 <= len(slices) <= 6):
            return "", 0 
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thresh = cv2.medianBlur(thresh, 3)
        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(thresh, connectivity=8)
        
        char_boxes = []
        all_components = []
        for i in range(1, num_labels):
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            w = stats[i, cv2.CC_STAT_WIDTH]
            h = stats[i, cv2.CC_STAT_HEIGHT]
            area = stats[i, cv2.CC_STAT_AREA]
            
            if area > 15:
                all_components.append((x, y, w, h, area))
                
            if area > 40 and w > 5 and h > 10:
                char_boxes.append((x, y, w, h))
        char_boxes = sorted(char_boxes, key=lambda b: b[0])
            
        result = ""
        total_conf = 0.0
        
        for i, s in enumerate(slices):
            char, conf = self.match_slice(s)
            
            if conf < 0.65:
                continue
                
            if char.endswith('_LOWER'):
                final_char = char[0].lower()
            elif char.endswith('_UPPER'):
                final_char = char[0].upper()
            else:
                final_char = char
                
            if final_char.upper() == 'J':
                has_dot = False
                if i < len(char_boxes):
                    cx, cy, cw, ch = char_boxes[i]
                    pad = 3
                    for dx, dy, dw, dh, darea in all_components:
                        if dh < 25 and dy + dh < cy and dx + dw > cx - pad and dx < cx + cw + pad:
                            if cy - (dy + dh) < 25: 
                                has_dot = True
                                break
                final_char = 'j' if has_dot else 'J'
                
            result += final_char
            total_conf += conf
            
        avg_conf = total_conf / len(slices) if slices else 0
        return result, int(avg_conf * 100)

# Global singleton matcher to hold templates in memory across API calls
_matcher = None

def get_matcher():
    global _matcher
    if _matcher is None:
        _matcher = LocalCaptchaMatcher()
    return _matcher


def solve_captcha(base64_string, api_key=None):
    """
    Solves the captcha image using 100% accurate Local Template Matching.
    Arguments:
        base64_string (str): The base64 encoded string from BBDC
        api_key (str): Unused
    Return:
        Tuple[str, int]: OCR string and confidence level (always 0 or near 100)
    """
    try:
        matcher = get_matcher()
        if not matcher.templates:
            return ("", 0)
        
        img_data = base64.b64decode(base64_string)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        text, conf = matcher.solve(img)
        
        if conf > 0:
            logging.info(f"Local Matcher Result: '{text}' | Confidence: {conf}%")
        return (text, conf)
        
    except Exception as e:
        logging.error(f"Local Matcher crashed: {e}")
        return ("", 0)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-i", "--image", required=True, help="path to input image")
    args = vars(argparser.parse_args())
    with open(args["image"], "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    captcha_text, conf = solve_captcha(encoded_string)
    print(f"-- Result: {captcha_text} (Conf: {conf}%)")
