import cv2
import numpy as np
import os

os.makedirs('extracted_letters', exist_ok=True)

img = cv2.imread('test_captcha.png')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Better processing for BBDC noise
# 1. Blur to remove pepper noise
blurred = cv2.medianBlur(gray, 3)

# 2. Adaptive thresholding handles varying background colors better
thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

# 3. Find contours
contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

letter_image_regions = []

for contour in contours:
    (x, y, w, h) = cv2.boundingRect(contour)
    # Check if the contour is roughly the size of a letter
    # BBDC captchas are usually about 15-30 pixels wide and 15-35 tall
    if w >= 8 and w <= 35 and h >= 15 and h <= 40:
        letter_image_regions.append((x, y, w, h))

# Sort from left to right
letter_image_regions = sorted(letter_image_regions, key=lambda x: x[0])

print(f"Found {len(letter_image_regions)} letters.")

for i, (x, y, w, h) in enumerate(letter_image_regions):
    # Extract the letter with a 1 pixel padding
    roi = img[max(0, y-1):y+h+1, max(0, x-1):x+w+1]
    cv2.imwrite(f"extracted_letters/letter_{i+1}.png", roi)

print("Saved letters to extracted_letters/ folder.")
