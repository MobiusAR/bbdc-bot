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
            return "", 0
            
        slices = self.slice_captcha(img)
        
        # BBDC captchas are always 5-6 valid readable characters. 
        # If it's too overlapping to slice cleanly, ABORT instantly.
        if not (5 <= len(slices) <= 6):
            return "", 0 
            
        # Re-run connected components to find tiny dots for J/j detection
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
            
            # If the best match has a confidence below 65%, it is either a tiny dot 
            # of noise or an unknown, garbled font variation. We discard the slice safely.
            if conf < 0.65:
                continue
                
            if char.endswith('_LOWER'):
                final_char = char[0].lower()
            elif char.endswith('_UPPER'):
                final_char = char[0].upper()
            else:
                final_char = char
                
            # Dynamic dot detection for J
            if final_char.upper() == 'J':
                has_dot = False
                if i < len(char_boxes):
                    cx, cy, cw, ch = char_boxes[i]
                    pad = 3
                    for dx, dy, dw, dh, darea in all_components:
                        # check if dot is above the hook, horizontally within bounds, and h < 25
                        if dh < 25 and dy + dh < cy and dx + dw > cx - pad and dx < cx + cw + pad:
                            if cy - (dy + dh) < 25: 
                                has_dot = True
                                break
                final_char = 'j' if has_dot else 'J'
                
            result += final_char
            total_conf += conf
            
        avg_conf = total_conf / len(slices) if slices else 0
        return result, int(avg_conf * 100)

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
