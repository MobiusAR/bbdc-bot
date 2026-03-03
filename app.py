import json
import json
import io
import base64
import logging
import time
from typing import Tuple
from datetime import datetime

from PIL import Image
from captcha_decoder import solve_captcha
from bot import send_message_tele, send_message_disc

url = "https://booking.bbdc.sg/bbdc-back-service/api/"
LoginCaptcha_url = "auth/getLoginCaptchaImage"
Login_url = "auth/login"
jsessionid_url = "account/listAccountCourseType"
AvailableSlots_url = "booking/c3practical/listC3PracticalSlotReleased"
BookingCaptcha_url = "booking/manage/getCaptchaImage"
Booking_url = "booking/c3practical/callBookC3PracticalSlot"

# setup logging
logging.basicConfig(format="%(asctime)s %(message)s", level=logging.INFO)

# Removed global requests object in favor of Playwright context


def PostUrl(context, url, headers, payload):
    # Set default headers to avoid being blocked by anti-bot systems
    request_headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": "https://booking.bbdc.sg/",
        "Origin": "https://booking.bbdc.sg"
    }
    if headers:
        request_headers.update(headers)
        
    try:
        response = context.request.post(
            url, 
            headers=request_headers, 
            data=json.dumps(payload) if payload else "{}", 
            timeout=30000
        )
        
        # Playwright responses don't raise automatically like requests, so check status
        if response.status >= 400:
            logging.error(f"HTTP Error {response.status} when hitting {url}. Body: {response.text()[:200]}")
            return {"success": False, "data": None}
            
        try:
            data = response.json()
            return data
        except Exception as e:
            logging.error(f"Failed to decode JSON from {url}. Server returned: {response.text()[:200]}")
            return {"success": False, "data": None}
    except Exception as e:
        logging.error(f"Network error when calling {url}: {e}")
        return {"success": False, "data": None}


def base64img(encoded_data):
    fh = io.BytesIO()
    fh.write(base64.b64decode(encoded_data))
    fh.flush()
    return fh


class Api:

    @staticmethod
    def get_captcha_image(context, extension: str, headers: dict):
        data = PostUrl(
            context,
            url + (LoginCaptcha_url if extension == "Login" else BookingCaptcha_url),
            headers,
            None,
        )
        if data and data.get("data"):
            data["data"].pop("accountIdNric", None)
        return data

    # get jsessionid
    @staticmethod
    def get_jsessionid(context, bearerToken: str) -> str:
        headers = {"authorization": bearerToken}
        data = PostUrl(context, url + jsessionid_url, headers, None)
        if data and data.get("success") and data.get("data") and data["data"].get("activeCourseList"):
            jsessionid = data["data"]["activeCourseList"][0]["authToken"]
            courseType = data["data"]["activeCourseList"][0]["courseType"]
            return jsessionid, courseType
        return None, None

    # get slots
    @staticmethod
    def get_slots(context, headers: dict, courseType: str, releasedSlotMonth: str) -> dict:
        AvailableSlotsPayload = {
            "courseType": courseType,
            "releasedSlotMonth": releasedSlotMonth,
            "stageSubDesc": "Practical Lesson",
            "subVehicleType": None,
            "subStageSubNo": None,
        }
        data = PostUrl(context, url + AvailableSlots_url, headers, AvailableSlotsPayload)
        if data and data.get("success"):
            slots = data["data"]["releasedSlotListGroupByDay"]
            return slots
        return None

    # get login bearer token
    @staticmethod
    def login(context, username: str, password: str, captcha: str, captchaResponse: dict) -> str:
        data = {
            "userId": username,
            "userPass": password,
            "verifyCodeValue": captcha,
        }
        data.update(captchaResponse["data"])
        # print(data)
        loginData = PostUrl(context, url + Login_url, None, data)
        return loginData

    # book slot
    @staticmethod
    def book(context, headers: dict, captcha: str, captchaResponse: dict, slotPayload: dict):
        data = {"verifyCodeValue": captcha}
        data.update(captchaResponse["data"])
        data.update(slotPayload)
        bookingData = PostUrl(context, url + Booking_url, headers, data)
        return bookingData


class Session:
    bearerToken: str = None
    jsessionid: str
    courseType: str
    slots: dict

    def __init__(self):
        pass

    def __get_auth_header(self):
        return {"authorization": self.bearerToken, "jsessionid": self.jsessionid}

    @staticmethod
    def __process_captcha_response(data, api_key: str, save_captcha: bool = False) -> Tuple[str, int]:
        if not data or not data.get("data") or "image" not in data["data"]:
            logging.error(f"Invalid captcha response format: {data}")
            return ("", 0)
        data = data["data"]
        encoded_data = data.pop("image").split(",")[1]
        
        if save_captcha:
            try:
                import os
                os.makedirs("captchas", exist_ok=True)
                timestamp = int(time.time() * 1000)
                filepath = f"captchas/captcha_{timestamp}.png"
                img = Image.open(base64img(encoded_data)).convert("RGB")
                img.save(filepath)
                logging.info(f"Saved captcha image to {filepath}")
            except Exception as e:
                logging.error(f"Failed to save captcha image: {e}")
                
        return solve_captcha(encoded_data, api_key=api_key)

    @staticmethod
    def __validate_captcha(Captcha: Tuple[str, int]) -> bool:
        (CaptchaData, CaptchaConfidence) = Captcha
        return 5 <= len(CaptchaData) <= 6 and CaptchaConfidence > 70

    # get best captcha
    def get_best_captcha(self, context, extension: str, api_key: str, headers: dict = None, save_captcha: bool = False):
        captchaResponse = None
        captcha = None
        while captcha is None or not Session.__validate_captcha(captcha):
            if captchaResponse is not None:
                time.sleep(0.5)
            try:
                captchaResponse = Api.get_captcha_image(context, extension, headers)
                captcha = Session.__process_captcha_response(captchaResponse, api_key=api_key, save_captcha=save_captcha)
            except Exception as e:
                logging.error(f"Error solving captcha: {e}")
                time.sleep(2)
        return (captcha[0], captchaResponse)

    def login(self, context, username: str, password: str, manual: bool, api_key: str, save_captchas: bool = False, enable_tele=False, enable_disc=False, bot_token="", chat_id="", webhook=""):
        # retry login flow until captcha guessed is correct
        max_retries = 3
        for attempt in range(max_retries):
            if manual:
                captchaResponse = Api.get_captcha_image(context, "Login", None)
                encoded_data = captchaResponse["data"].pop("image").split(",")[1]
                captchaImage = Image.open(base64img(encoded_data)).convert("RGB")
                captchaImage.show()
                captcha = input("Solve Login Captcha: ")
            else:
                (captcha, captchaResponse) = self.get_best_captcha(context, "Login", api_key, save_captcha=save_captchas)
            loginData = Api.login(context, username, password, captcha, captchaResponse)
            if loginData and loginData.get("success"):
                logging.info("Logged In")
                self.bearerToken = loginData["data"]["tokenContent"]
                jsess, crs = Api.get_jsessionid(context, self.bearerToken)
                if jsess and crs:
                    self.jsessionid = jsess
                    self.courseType = crs
                    break
                else:
                    logging.info("Login succeeded but failed to fetch jsessionid. Retrying...")
                    time.sleep(2)
            else:
                msg = loginData.get("message", "") if loginData else ""
                if "suspended" in msg.lower():
                    alert_msg = "🚨 **CRITICAL: ACCOUNT SUSPENDED!** 🚨\nBBDC has temporarily blocked this account for 48 hours due to too many failed login attempts. The bot has exited to prevent further lockouts."
                    if enable_tele: send_message_tele(alert_msg, bot_token, chat_id)
                    if enable_disc: send_message_disc(alert_msg, webhook)
                    
                    logging.critical("ACCOUNT SUSPENDED: BBDC has temporarily blocked this account for 48 hours due to too many failed login attempts. Exiting bot to prevent further lockouts.")
                    exit(1)
                
                delay = 30 # Increased delay to prevent suspension
                logging.warning(f"Login failed (captcha might be wrong or credentials invalid). Attempt {attempt + 1}/{max_retries}. Waiting {delay}s...")
                
                if attempt == max_retries - 1:
                    alert_msg = f"⚠️ **WARNING: Max Login Retries ({max_retries}) Reached** ⚠️\nThe bot is shutting down to prevent BBDC from suspending your account. Please check the logs."
                    if enable_tele: send_message_tele(alert_msg, bot_token, chat_id)
                    if enable_disc: send_message_disc(alert_msg, webhook)
                    
                    logging.critical(f"Max login retries ({max_retries}) reached. Exiting bot to prevent account suspension.")
                    exit(1)
                
                time.sleep(delay)

    def manual_login(self, context, bearerToken: str):
        self.bearerToken = bearerToken
        self.jsessionid, self.courseType = Api.get_jsessionid(context, self.bearerToken)

    def is_expired(self, context):
        jsess, crs = Api.get_jsessionid(context, self.bearerToken)
        return not bool(jsess)

    # Get all slots in specific month
    def get_slots(self, context, releasedSlotMonth: str) -> dict:
        self.slots = Api.get_slots(
            context, self.__get_auth_header(), self.courseType, releasedSlotMonth
        )

    def display_slot(self, slot):
        slotDate = (
            datetime.strptime(slot["slotRefDate"], "%Y-%m-%d %H:%M:%S")
        ).strftime("%d/%m/%Y")
        message = """
        Slot Available
        Date: {}
        Time: {} - {}
        Session: {}
        Total Fee: {}""".format(
            slotDate,
            slot["startTime"],
            slot["endTime"],
            slot["slotRefName"],
            slot["totalFee"],
        )
        return message

    # Get slot payload for booking
    def get_slot_payload(self, slot):
        if slot:
            slotDict = {}
            slotDict["slotIdEnc"] = slot["slotIdEnc"]
            slotDict["bookingProgressEnc"] = slot["bookingProgressEnc"]
            slotPayload = {
                "courseType": self.courseType,
                "slotIdList": [slot["slotId"]],
                "encryptSlotList": [slotDict],
                "insInstructorId": "",
                "subVehicleType": None,
                "instructorType": "",
            }
            return slotPayload
        else:
            logging.info("Month schedule is entirely empty.")

    # Get preferred slot in month if possible else get earliest date
    def choose_slot(self, want=None):
        if self.slots:
            # Sorting
            keylist = list(self.slots.keys())
            keylist.sort()
            
            # If no preferences, pick earliest
            if not want:
                return self.slots[keylist[0]][0]
                
            total_slots_seen = 0
            for date_key in keylist:
                for slot in self.slots[date_key]:
                    total_slots_seen += 1
                    session_num = int(slot["slotRefName"].split()[1])
                    if isinstance(want, dict):
                        slot_date_obj = datetime.strptime(slot["slotRefDate"], "%Y-%m-%d %H:%M:%S")
                        is_weekend = slot_date_obj.weekday() >= 5
                        
                        if is_weekend and session_num in want.get("weekend", []):
                            return slot
                        elif not is_weekend and session_num in want.get("weekday", []):
                            return slot
                    elif session_num in want:
                        return slot
            
            # If we get here, slots existed but none matched
            if total_slots_seen > 0:
                logging.info(f"Ignored {total_slots_seen} available slots due to preference mismatch.")
            return None

    # Book using slot payload
    def book(self, context, slotPayload: dict, manual: bool, api_key: str, save_captchas: bool = False, enable_tele=False, enable_disc=False, bot_token="", chat_id="", webhook=""):
        headers = self.__get_auth_header()
        if slotPayload:
            max_retries = 15
            for attempt in range(max_retries):
                if manual:
                    captchaResponse = Api.get_captcha_image(context, "Booking", headers)
                    encoded_data = captchaResponse["data"].pop("image").split(",")[1]
                    captchaImage = Image.open(base64img(encoded_data)).convert("RGB")
                    captchaImage.show()
                    captcha = input("Solve Booking Captcha: ")
                    if captcha == "n":
                        logging.info("Ignoring this slot...")
                        break
                else:
                    (captcha, captchaResponse) = self.get_best_captcha(
                        context, "Booking", api_key, headers, save_captcha=save_captchas
                    )
                bookingData = Api.book(context, headers, captcha, captchaResponse, slotPayload)
                if bookingData and bookingData.get("success"):
                    # BBDC may return success:True but the slot list is empty or fails
                    slot_list = bookingData.get("data", {}).get("bookedPracticalSlotList", [])
                    if not slot_list:
                        logging.warning("Booking failed: Slot scooped by someone else (empty list). Aborting.")
                        break
                        
                    bookedSlot = slot_list[0]
                    msg = bookedSlot.get('message', '').lower()
                    
                    if 'already' in msg or 'sorry' in msg or 'taken' in msg or 'fail' in msg or 'exceeded' in msg:
                        logging.warning(f"Booking failed: Slot scooped by another user. API Msg: {msg}")
                        break # Slot is gone, abort retry loop
                        
                    logging.info("Booking Confirmed !")
                    
                    success_msg = f"✅ BBDC Booking Confirmed!\n\n{bookedSlot.get('message')}"
                    if enable_tele:
                        send_message_tele(success_msg, bot_token, chat_id)
                    if enable_disc:
                        send_message_disc(success_msg, webhook)
                    break
                else:
                    delay = 5
                    err_msg = bookingData.get("msg", "") if bookingData else ""
                    logging.warning(f"Booking failed (captcha might be wrong). Attempt {attempt + 1}/{max_retries}. Waiting {delay}s. Msg: {err_msg}")
                    
                    if "already" in err_msg.lower() or "taken" in err_msg.lower() or "sorry" in err_msg.lower():
                         logging.warning(f"Slot scooped! Aborting early: {err_msg}")
                         break
                         
                    if attempt == max_retries - 1:
                        logging.error(f"Max booking retries ({max_retries}) reached. Aborting booking for this slot.")
                        break
                    time.sleep(delay)


def app(session, config, context):
    # Login
    userId = config["login"]["username"]
    userPass = config["login"]["password"]

    # Preferred Month and Slot
    months = config["pref"].get("months", [])
    if not months and config["pref"].get("month"):
        months = [config["pref"]["month"]]
    want = config["pref"]["sessions"]

    # Manually Solve Captchas
    manualL = config["captcha"]["login"]
    manualB = config["captcha"]["booking"]
    save_captchas = config["captcha"].get("save_captchas", False)
    
    # OCR API
    ocr_api_key = config.get("ocr", {}).get("api_key", "K82590680388957")

    # Telegram Bot
    bot_token = config["telegram"]["token"]
    chat_id = config["telegram"]["chat_id"]
    enable_tele = config["telegram"]["enabled"]

    # Discord Bot
    enable_disc = config["discord"]["enabled"]
    webhook = config["discord"]["webhook"]

    enable_booking = config["enable_booking"]

    # Attempt Login
    if session.is_expired(context):
        logging.info("Attempting to login...")
        session.login(
            context, 
            userId, 
            userPass, 
            manualL, 
            ocr_api_key, 
            save_captchas=save_captchas,
            enable_tele=enable_tele,
            enable_disc=enable_disc,
            bot_token=bot_token,
            chat_id=chat_id,
            webhook=webhook
        )
        # session.manual_login(context, bearerToken)

    # Get Slot
    for month in months:
        try:
            session.get_slots(context, month)
            chosenSlot = session.choose_slot(want)
            slotPayload = session.get_slot_payload(chosenSlot)

            # Attempt Booking
            if slotPayload:
                message = session.display_slot(chosenSlot)
                logging.info(message)
                if enable_tele:
                    send_message_tele(message, bot_token, chat_id)
                if enable_disc:
                    send_message_disc(message, webhook)
                if enable_booking:
                    logging.info("Attempting to book...")
                    session.book(
                        context, 
                        slotPayload, 
                        manualB, 
                        ocr_api_key, 
                        save_captchas=save_captchas,
                        enable_tele=enable_tele,
                        enable_disc=enable_disc,
                        bot_token=bot_token,
                        chat_id=chat_id,
                        webhook=webhook
                    )
                return  # Return after finding/booking a slot to avoid booking multiple in one job
        except Exception as e:
            logging.error(f"Error checking slots for {month}: {e}")

