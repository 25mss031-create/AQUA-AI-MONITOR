"""Telegram officer bot: long-polling command bot on top of the Bot API.

Enabled only when TELEGRAM_BOT_TOKEN (and TELEGRAM_CHAT_ID) are set. Only the
configured officer chat is answered; the dam-breach command still needs the
officer PIN.
"""
import asyncio
import json

from . import alerts, config, http_util

HELP = (
    "AQUA AI officer bot (Noyyal pilot)\n"
    "/status — risk by stretch, river level, siren/beacon, devices\n"
    "/alerts — last 3 alerts\n"
    "/pending — detections waiting for your decision\n"
    "/approve N — confirm a real discharge at item N (notifies TNPCB)\n"
    "/dismiss N — item N is a false detection\n"
    "/cap — CAP alert JSON\n"
    "/breach PIN — confirm dam breach (officer PIN required)\n"
    "/reset — reset the demo\n"
    "/help — this text\n\n"
    "Only this chat is answered. Wrong PIN is rejected and logged.\n"
    "இது அதிகாரி உதவியாளர் பாட். /status, /pending, /approve, /dismiss, "
    "/breach <PIN> பயன்படுத்தலாம்."
)


def api_call(method, **params):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}"
    timeout = max(60, int(params.get("timeout", 0)) + 10)
    status, body = http_util.get_json(url, params, timeout=timeout)
    if status != 200 or not body.get("ok"):
        raise RuntimeError(f"telegram {method} failed: HTTP {status} {body.get('description', '')}")
    return body


class TelegramBot:
    def __init__(self, engine):
        self.engine = engine
        self.offset = 0

    def _risk_word(self, level):
        return ["Low", "Medium", "High"][int(level)] if level in (0, 1, 2) else str(level)

    async def _status(self):
        s = self.engine.snapshot()
        su = s["surge"]
        lines = ["AQUA AI — live status", ""]
        lvl = f"level {su['level']} m (A {su['level_a']} / B {su['level_b']})"
        lines.append(f"River: {lvl} — {s['kpis']['level_status']}")
        lines.append(f"Siren: {'ON' if su['siren'] else 'off'}, beacon: {'ON' if su['beacon'] else 'off'}")
        if su["alert"] and not su["arrived"] and su["countdown_min"] is not None:
            lines.append(f"SURGE: wave at the ghat in about {su['countdown_min']} minutes")
        lines.append("")
        lines.append("Stretches:")
        for seg in s["segments"]:
            lines.append(f"  {seg['id']} {seg['name']}: {self._risk_word(seg['risk'])}")
        lines.append("")
        for d in s.get("devices", []):
            v = d.get("battery_v")
            pos = "GPS fix" if d.get("gps_fix") else ("configured coords" if d.get("lat") is not None else "no position")
            lines.append(f"{d['station']}: {v if v is not None else '—'} V, "
                         f"{d.get('rssi', '—')} dBm, probes {'OK' if d.get('sensor_ok') else 'FAULT'}, {pos}")
        lines.append("")
        lines.append(f"Needs your decision: {len(s.get('pending', []))} item(s). Use /pending")
        return "\n".join(lines)

    async def _alerts(self):
        s = self.engine.snapshot()
        rows = s.get("alerts", [])[:3]
        if not rows:
            return "No alerts. Everything is quiet."
        out = ["Last alerts:"]
        for a in rows:
            out.append(f"[{a['severity']}] {a['en']}")
            out.append(f"  {a['ta']}")
        return "\n".join(out)

    async def _pending(self):
        items = self.engine.pending
        if not items:
            return "Nothing waiting. No discharge decisions needed."
        out = ["Waiting for your decision (is this a real dye/effluent discharge?):"]
        for i, p in enumerate(items, 1):
            out.append(f"{i}. {p['label']} {p['confidence']}% at {p['segment_name'] or p['segment']}"
                       f" — /approve {i} or /dismiss {i}")
        return "\n".join(out)

    async def _resolve(self, arg, action):
        try:
            n = int(arg)
        except (TypeError, ValueError):
            return "Give the item number, e.g. /approve 1 (see /pending)."
        items = self.engine.pending
        if not 1 <= n <= len(items):
            return f"No item {n}. Send /pending to see the list."
        ok = await self.engine.resolve_review(items[n - 1]["ts"], action)
        if not ok:
            return "That item is no longer in the queue."
        return (f"Item {n} confirmed as a real discharge. TNPCB notified via Telegram."
                if action == "approve" else
                f"Item {n} dismissed as a false detection. Nothing sent to TNPCB.")

    async def handle(self, chat_id, text):
        if str(chat_id) != str(config.TELEGRAM_CHAT_ID):
            return None
        parts = (text or "").strip().split()
        if not parts:
            return None
        cmd = parts[0].split("@")[0].lower().lstrip("/")
        arg = parts[1] if len(parts) > 1 else ""
        if cmd in ("start", "help"):
            return HELP
        if cmd == "status":
            return await self._status()
        if cmd == "alerts":
            return await self._alerts()
        if cmd == "pending":
            return await self._pending()
        if cmd == "approve":
            return await self._resolve(arg, "approve")
        if cmd == "dismiss":
            return await self._resolve(arg, "dismiss")
        if cmd == "cap":
            return "CAP export:\n" + json.dumps(self.engine.cap_alert(), indent=1)
        if cmd == "breach":
            ok = await self.engine.breach_request(arg, "Telegram bot")
            return ("Dam breach confirmed. Countdown is running on the dashboard; "
                    "ghat siren and beacon ON."
                    if ok else
                    "REJECTED: wrong officer PIN. No alert was sent. The attempt was logged.")
        if cmd == "reset":
            await self.engine.reset()
            return "Demo state reset."
        return "Unknown command. Send /help"

    async def run(self):
        while True:
            try:
                upd = await asyncio.to_thread(
                    api_call, "getUpdates", offset=self.offset, timeout=50,
                    allowed_updates=["message"])
            except Exception:
                await asyncio.sleep(5)
                continue
            for u in upd.get("result", []):
                self.offset = u["update_id"] + 1
                msg = u.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                if chat is None:
                    continue
                try:
                    reply = await self.handle(chat, msg.get("text") or "")
                except Exception:
                    reply = "Command failed. Check the backend logs."
                if reply:
                    await asyncio.to_thread(alerts.send_telegram, reply, chat)


def start(engine):
    if not config.TELEGRAM_BOT_TOKEN:
        print("telegram bot: disabled (TELEGRAM_BOT_TOKEN not set)")
        return None
    print(f"telegram bot: polling, officer chat {config.TELEGRAM_CHAT_ID or 'NOT SET'}")
    return asyncio.create_task(TelegramBot(engine).run())
