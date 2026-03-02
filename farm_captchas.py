import time
from playwright.sync_api import sync_playwright
from app import Api, base64img
from PIL import Image
import os
import logging

logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

def farm_captchas(count=100):
    os.makedirs("captchas", exist_ok=True)
    
    with sync_playwright() as p:
        print("Starting Playwright Headless Browser...")
        context = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_data",
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        print("Bypassing Incapsula...")
        page = context.new_page()
        page.goto("https://booking.bbdc.sg/")
        time.sleep(5)
        page.close()
        
        print(f"Farming {count} captchas safely...")
        for i in range(count):
            try:
                response = Api.get_captcha_image(context, "Login", None)
                if response and response.get("data") and "image" in response["data"]:
                    encoded_data = response["data"]["image"].split(",")[1]
                    timestamp = int(time.time() * 1000)
                    filepath = f"captchas/captcha_{timestamp}.png"
                    img = Image.open(base64img(encoded_data)).convert("RGB")
                    img.save(filepath)
                    logging.info(f"[{i+1}/{count}] Saved -> {filepath}")
                time.sleep(1.5) # respectful delay to avoid IP blocks
            except Exception as e:
                logging.error(f"Failed to fetch: {e}")
                time.sleep(5)

if __name__ == "__main__":
    farm_captchas(100)
