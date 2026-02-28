import time
from playwright.sync_api import sync_playwright

def test_otp():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_data",
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        page.goto("https://booking.bbdc.sg/")
        time.sleep(5)
        
        # First test checkIdAndPass
        print("Testing checkIdAndPass...")
        resp1 = context.request.post(
            "https://booking.bbdc.sg/bbdc-back-service/api/auth/checkIdAndPass",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Referer": "https://booking.bbdc.sg/",
                "Origin": "https://booking.bbdc.sg"
            },
            data={"userId": "657D04111998", "userPass": "529942"},
            timeout=30000
        )
        print("checkIdAndPass Status:", resp1.status)
        token = ""
        try:
            print("checkIdAndPass Response:", resp1.json())
            token = resp1.json().get("data", {}).get("tokenContent", "")
        except Exception as e:
            pass

        # Text the sendOtp endpoint
        print("Testing sendOtp with token...")
        response = context.request.post(
            "https://booking.bbdc.sg/bbdc-back-service/api/auth/sendOtp",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Referer": "https://booking.bbdc.sg/",
                "Origin": "https://booking.bbdc.sg",
                "Authorization": token
            },
            data={"userId": "657D04111998", "userPass": "529942"},
            timeout=30000
        )
        print("Status:", response.status)
        try:
            print("Response:", response.json())
        except Exception as e:
            print("Error parsing json:", e)
            print("Text:", response.text()[:200])

if __name__ == "__main__":
    test_otp()
