# BBDC Auto-Booking Bot 🚗
A high-performance, fully automated Python bot designed to monitor and instantly secure driving practical slots at the Bukit Batok Driving Centre (BBDC) in Singapore. 

This repository is a heavily modernized enhancement of the original BBDC checkers, featuring a custom Playwright network stack, intelligent Captcha bypassing, and 24/7 cloud deployment support.

## 🚀 Key Features
* **Smart Captcha Solver:** Automatically bypasses BOTH the Login and Booking captchas using the `OCR.space` API, completely eliminating the need for user intervention.
* **Server-Lag Resilient:** BBDC's servers are notorious for lagging and timing out during slot confirmation. This bot utilizes custom API payload timeouts and a 15-tier retry system to guarantee the slot is locked in.
* **Instant Notifications:** Get pinged instantly on Telegram or Discord the millisecond a slot is successfully booked.
* **Smart Routing:** Seamlessly maps through empty months, cleanly skips un-preferred weekend/weekday sessions, and correctly drops erroneous Captcha reads to prevent account lockouts.

---

## 🛠️ Requirements
* Python 3.9+
* Playwright

---

## 💻 Local Setup (Mac / Windows)

### 1. Clone the repo
```sh
git clone https://github.com/MobiusAR/bbdc-bot.git
cd bbdc-bot
```

### 2. Create the Virtual Environment
```sh
# Create virtual environment
python3 -m venv env

# Activate the environment (Mac/Linux)
source env/bin/activate

# Windows equivalent:
# env\Scripts\activate
```

### 3. Install Dependencies
```sh
pip install -r requirements.txt
playwright install
playwright install-deps
```

### 4. Configuration
Rename `new_config.yaml` to `config.yaml` and fill in your details:
* `username` / `password`: Your BBDC login credentials.
* `months`: A list of the specific months you want to scan for (e.g., `["202604", "202605"]`).
* `sessions`: A dictionary allowing you to designate different target sessions for weekdays vs weekends.
* Make sure `save_captchas` is `True` if you wish to help build a local OCR dictionary.

### 5. Run the Bot
```sh
python main.py
```

---

## ☁️ 24/7 Cloud Deployment (DigitalOcean)

If you want the bot to run continuously while you sleep, setting it up on a $6/mo DigitalOcean Droplet is the best approach.

1. **Create an Ubuntu Droplet:** Choose the Singapore SG region for the lowest latency to BBDC servers.
2. **Connect via SSH:** `ssh root@<YOUR_DROPLET_IP>`
3. **Install Python & Git:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install python3 python3-venv python3-pip git -y
    ```
4. **Clone your code and setup:**
    ```bash
    git clone https://github.com/MobiusAR/bbdc-bot.git
    cd bbdc-bot
    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt
    playwright install
    playwright install-deps
    ```
5. **Run in the Background:**
    Use `nohup` so the bot continues running even after you close your terminal connection:
    ```bash
    nohup ./env/bin/python main.py > bot.log 2>&1 &
    ```
    *(You can view live updates anytime by running `tail -f bot.log`)*

---

## ⚠️ Anti-Suspension Protections
BBDC automatically suspends accounts for 48 hours if too many invalid captchas are submitted. To prevent this, the bot has built-in safety nets:
1. It validates the length of the OCR string before blindly submitting it.
2. It tracks consecutive login failures. If the API fails 3 times in a row, the bot will gracefully shut itself down and send a Critical Alert to your Telegram/Discord to prevent the system from banning your account.

---
*Disclaimer: Use at your own risk. This project is not affiliated with Bukit Batok Driving Centre.*