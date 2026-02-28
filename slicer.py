import cv2
import numpy as np
import os
import glob

def slice_captcha_cc(image_path, output_dir="slices"):
    os.makedirs(output_dir, exist_ok=True)
    img = cv2.imread(image_path)
    if img is None: return
    
    # Pre-processing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Median blur to remove thin line noise creating false connections
    thresh = cv2.medianBlur(thresh, 3)
    
    # Find connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh, connectivity=8)
    
    # Filter out background (label 0) and small noise
    char_boxes = []
    
    for i in range(1, num_labels):
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        w = stats[i, cv2.CC_STAT_WIDTH]
        h = stats[i, cv2.CC_STAT_HEIGHT]
        area = stats[i, cv2.CC_STAT_AREA]
        
        # BBDC characters are usually at least 10x10. Ignore lines/dots.
        if area > 40 and w > 5 and h > 10:
            char_boxes.append((x, y, w, h))
            
    # Sort left-to-right
    char_boxes = sorted(char_boxes, key=lambda b: b[0])
    
    base_name = os.path.basename(image_path).replace('.png', '')
    
    # We expect 5 or 6 characters
    if not (5 <= len(char_boxes) <= 6):
        print(f"{base_name}: Found {len(char_boxes)} characters (SKIPPING - noise or severe overlap)")
        return
        
    print(f"{base_name}: Sliced into {len(char_boxes)} exact characters")
    
    for count, (x, y, w, h) in enumerate(char_boxes):
        pad = 2
        top = max(0, y - pad)
        bottom = min(thresh.shape[0], y + h + pad)
        left = max(0, x - pad)
        right = min(thresh.shape[1], x + w + pad)
        
        char_img = thresh[top:bottom, left:right]
        clean_slice = cv2.bitwise_not(char_img) # black text, white background
        cv2.imwrite(f"{output_dir}/{base_name}_slice_{count}.png", clean_slice)

for p in glob.glob("captchas/*.png"):
    slice_captcha_cc(p)
