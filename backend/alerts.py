import urllib.parse
import urllib.request

from . import config


def send_telegram(text):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status == 200
    except Exception:
        return False


def channel_status():
    return {
        "telegram": bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID),
        "dashboard": True,
        "siren_beacon": True,
        "cap_export": True,
        "implemented": ["Dashboard + WebSocket", "Telegram Bot API", "Ghat siren + beacon relay", "CAP export (file)"],
        "planned": ["SMS", "Email", "Firebase push notification", "LoRa / GSM field link", "Panchayat app"],
    }
