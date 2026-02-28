import cv2
import numpy as np

img = cv2.flip(cv2.imread('test_captcha.png'), 1) # Not actually flipping, just reading
img = cv2.imread('test_captcha.png')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# BBDC noise has small dots, let's blur then threshold
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# Dilate to connect characters broken by lines
kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
dilated = cv2.dilate(thresh, kernel, iterations=1)

contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

valid_contours = []
for c in contours:
    x, y, w, h = cv2.boundingRect(c)
    # Filter out tiny noise blobs and huge lines, BBDC letters are usually a specific size
    if 5 < w < 40 and 10 < h < 45: 
        valid_contours.append(cv2.boundingRect(c))

valid_contours = sorted(valid_contours, key=lambda b: b[0])
print(f"Found {len(valid_contours)} valid characters.")

for i, (x, y, w, h) in enumerate(valid_contours):
    roi = img[y:y+h, x:x+w]
    cv2.imwrite(f"char_{i}.png", roi)
print("Saved separated characters")
