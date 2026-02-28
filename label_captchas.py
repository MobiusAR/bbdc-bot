import cv2
import os
import glob

def label_images():
    slices_dir = "slices"
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    images = glob.glob(f"{slices_dir}/*.png")
    print(f"Found {len(images)} images to label.")
    
    for img_path in images:
        img = cv2.imread(img_path)
        if img is None:
            continue
            
        # upscale for easier viewing
        img_show = cv2.resize(img, (150, 150), interpolation=cv2.INTER_NEAREST)
        
        window_name = "Label Captcha (Type Letter, SPACE to skip, ESC to exit)"
        cv2.imshow(window_name, img_show)
        
        # Bring window to front on Mac
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        
        # Wait indefinitely for a key press
        key = cv2.waitKey(0)
        
        if key == 27: # ESC
            print("Exiting labeling tool...")
            break
            
        if key == 32: # Spacebar
            print("Skipped image (Space pressed)")
            continue
            
        # Convert key to character
        try:
            char = chr(key).upper()
            if char.isalnum():
                char_dir = os.path.join(templates_dir, char)
                os.makedirs(char_dir, exist_ok=True)
                new_path = os.path.join(char_dir, os.path.basename(img_path))
                
                # Move the original image to its labeled folder
                os.rename(img_path, new_path)
                print(f"Labeled '{char}' -> {new_path}")
            else:
                print(f"Skipped image (Invalid character key: {key})")
        except ValueError:
            print(f"Skipped image (Invalid key pressed: {key})")
            
    cv2.destroyAllWindows()
    print("Labeling complete!")

if __name__ == "__main__":
    label_images()
