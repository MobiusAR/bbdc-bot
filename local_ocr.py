import cv2
import numpy as np
import os
import glob
import time
from concurrent.futures import ThreadPoolExecutor

class LocalCaptchaMatcher:
    def __init__(self, templates_dir="templates"):
        self.templates = {}
        self.load_templates(templates_dir)

    def load_templates(self, templates_dir):
        # Load all categorized templates into memory
        loaded = 0
        for char_dir in glob.glob(f"{templates_dir}/*"):
            if not os.path.isdir(char_dir):
                continue
            char = os.path.basename(char_dir)
            self.templates[char] = []
            
            for img_path in glob.glob(f"{char_dir}/*.png"):
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # Invert so text is white on black for matching
                    img = cv2.bitwise_not(img)
                    self.templates[char].append(img)
                    loaded += 1
        print(f"Loaded {loaded} templates for {len(self.templates)} unique characters.")

    def slice_captcha(self, img):
        """Slice the captcha using the exact same logic used for training data."""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
            
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
            
            if area > 40 and w > 5 and h > 10:
                char_boxes.append((x, y, w, h))
                
        char_boxes = sorted(char_boxes, key=lambda b: b[0])
        
        slices = []
        for x, y, w, h in char_boxes:
            pad = 2
            top = max(0, y - pad)
            bottom = min(thresh.shape[0], y + h + pad)
            left = max(0, x - pad)
            right = min(thresh.shape[1], x + w + pad)
            
            # Extract white-on-black slice for matching
            char_img = thresh[top:bottom, left:right]
            slices.append(char_img)
            
        return slices

    def match_slice(self, slice_img):
        """Find the best matching template for a single slice."""
        best_match_char = "?"
        best_match_score = -1.0
        
        slice_h, slice_w = slice_img.shape
        
        for char, t_imgs in self.templates.items():
            for t_img in t_imgs:
                t_h, t_w = t_img.shape
                
                # We need the images to be exactly the same size to use cv2.matchTemplate
                # Resize the template to match the slice size EXACTLY
                if slice_h != t_h or slice_w != t_w:
                    scaled_t_img = cv2.resize(t_img, (slice_w, slice_h), interpolation=cv2.INTER_AREA)
                else:
                    scaled_t_img = t_img
                    
                # Use Template Matching (Normalized Cross Correlation)
                res = cv2.matchTemplate(slice_img, scaled_t_img, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                
                if max_val > best_match_score:
                    best_match_score = max_val
                    best_match_char = char
                    
                # Early exit if we find a perfect match (saves time)
                if best_match_score > 0.98:
                    return best_match_char, best_match_score
                    
        return best_match_char, best_match_score

    def solve(self, image_input):
        if isinstance(image_input, str):
            img = cv2.imread(image_input)
        else:
            img = image_input # It's already a decoded OpenCV numpy array
            
        if img is None:
            return "", 0.0
            
        slices = self.slice_captcha(img)
        if not (5 <= len(slices) <= 6):
            return "", 0.0 # BBDC captchas are always 5-6 valid readable characters
            
        result = ""
        total_conf = 0.0
        
        for s in slices:
            char, conf = self.match_slice(s)
            
            if conf < 0.65:
                continue
                
            if char.endswith('_LOWER'):
                final_char = char[0].lower()
            elif char.endswith('_UPPER'):
                final_char = char[0].upper()
            else:
                case_map = {
                    'B': 'b', 'G': 'g', 'H': 'h', 'J': 'j', 'Q': 'Q', 'R': 'r'
                }
                final_char = case_map.get(char, char)
                
            result += final_char
            total_conf += conf
            
        avg_conf = total_conf / len(slices) if slices else 0
        return result, avg_conf

if __name__ == "__main__":
    print("Testing Local Matcher against farmed captchas...")
    matcher = LocalCaptchaMatcher()
    
    captchas = glob.glob("captchas/*.png")
    print(f"\nBenchmarking {len(captchas)} captchas...")
    
    start_time = time.time()
    
    valid_count = 0
    total_conf = 0
    
    for i, path in enumerate(captchas):
        text, conf = matcher.solve(path)
        
        if 5 <= len(text) <= 6:
            valid_count += 1
            total_conf += conf
            
        print(f"[{i+1}/{len(captchas)}] {os.path.basename(path):30s} => '{text:6s}' (Conf: {conf:.1%})")
        
    elapsed = time.time() - start_time
    print(f"\n--- BENCHMARK RESULTS ---")
    print(f"Total Processed: {len(captchas)} images")
    print(f"Time Taken: {elapsed:.2f} seconds ({elapsed/len(captchas):.3f}s per image)")
    print(f"Valid Guesses (5-6 chars): {valid_count}/{len(captchas)} ({valid_count/len(captchas):.1%})")
    if valid_count > 0:
        print(f"Average Confidence of Valid Guesses: {total_conf/valid_count:.1%}")
