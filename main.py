import schedule
import time
from config import load_config
from playwright.sync_api import sync_playwright

# load config
config = load_config("config.yaml")
interval = config["interval"]

def job(browser_context, session):
    try:
        from app import app
        app(session, config, browser_context)
    except Exception as e:
        print(f"Error in job: {e}")

if __name__ == "__main__":
    with sync_playwright() as p:
        print("Starting Playwright Headless Browser...")
        browser = p.chromium.launch(headless=True)
        context = p.chromium.launch_persistent_context(
            user_data_dir="./playwright_data",
            headless=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Navigate to homepage once to fetch Incapsula Javascript challenge cookies
        print("Navigating to BBDC Homepage to solve initial Incapsula JS challenge...")
        page = context.new_page()
        page.goto("https://booking.bbdc.sg/")
        time.sleep(5)
        page.close() # Clean up page, we just need the context cookies

        # Import Session here to avoid premature initialization before Playwright is ready if needed, 
        # but it's fine above since it's just a class.
        from app import Session
        session = Session()

        job(context, session)  # test
    
        # Run the job every interval seconds, with a randomized jitter
        # so we don't hit the server on exactly the same cadence.
        start_interval = max(1, interval - 5)
        end_interval = interval + 5
        schedule.every(start_interval).to(end_interval).seconds.do(job, browser_context=context, session=session)
        
        while True:
            # Check if there's a pending job
            schedule.run_pending()
            time.sleep(1)
