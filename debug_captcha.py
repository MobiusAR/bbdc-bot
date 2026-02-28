import io
import base64
import time
from PIL import Image
from playwright.sync_api import sync_playwright

url = "https://booking.bbdc.sg/bbdc-back-service/api/"
LoginCaptcha_url = "auth/getLoginCaptchaImage"

def main():
    print("Launching Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_data",
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("Navigating to BBDC Homepage to solve Incapsula JS challenge...")
        # This initial navigation triggers Incapsula. Playwright will naturally execute the JS and accept the cookies.
        page.goto("https://booking.bbdc.sg/")
        
        # Give it a few seconds to let any Javascript redirects/cookie-settings finish
        print("Waiting 5 seconds for background JS...")
        time.sleep(5)
        
        print("Cookies captured. Fetching API endpoint...")
        # Now use the context's request interceptor which shares the Incapsula session cookies
        response = context.request.post(
            url + LoginCaptcha_url,
            headers={"Content-Type": "application/json", "Accept": "application/json, text/plain, */*", "Origin": "https://booking.bbdc.sg", "Referer": "https://booking.bbdc.sg/"},
            data={}
        )
        
        print("Status Code:", response.status)
        try:
            data = response.json()
            encoded_data = data["data"]["image"].split(",")[1]

            # Save to disk to preview
            img_data = base64.b64decode(encoded_data)
            img = Image.open(io.BytesIO(img_data)).convert("RGB")
            img.save("test_captcha.png")
            print("Successfully extracted Captcha image! Saved test_captcha.png! Open it to see the raw image.")
        except Exception as e:
            print("Failed to decode JSON. Server response:")
            print(response.text())
        
        context.close()
        browser.close()

if __name__ == "__main__":
    main()
