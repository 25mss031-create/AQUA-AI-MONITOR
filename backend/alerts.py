from . import config, http_util


def send_telegram(text, chat_id=None):
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    cid = chat_id or config.TELEGRAM_CHAT_ID
    if not cid:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        status, body = http_util.post_form(
            url, {"chat_id": cid, "text": text, "disable_web_page_preview": "true"})
        return status == 200 and bool(body.get("ok"))
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
