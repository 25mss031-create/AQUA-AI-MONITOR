"""Pre-demo self check: run `python -m backend.selfcheck` before going on stage.

Offline checks run always (river geometry, thresholds, bilingual strings, engine
rules). Online checks need the backend running on http://127.0.0.1:8000.
"""
import asyncio
import json
import math
import sys
import urllib.error
import urllib.request

from . import config, engine, i18n, risk, river

BASE = "http://127.0.0.1:8000"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def skip(name, detail):
    SKIP.append((name, detail))
    print(f"[SKIP] {name} — {detail}")


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return json.loads(r.read().decode())


def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def point_segment_m(p, a, b):
    lat0 = math.cos(math.radians(p[0])) * 111320.0
    lon0 = 110574.0
    P = ((p[1] - a[1]) * lat0, (p[0] - a[0]) * lon0)
    B = ((b[1] - a[1]) * lat0, (b[0] - a[0]) * lon0)
    L2 = B[0] ** 2 + B[1] ** 2
    t = 0 if L2 == 0 else max(0, min(1, (P[0] * B[0] + P[1] * B[1]) / L2))
    return math.hypot(P[0] - t * B[0], P[1] - t * B[1])


def offline():
    pts = river.polyline()
    check("river polyline has points", len(pts) >= 100, f"{len(pts)} points")
    check("river length realistic", river.TOTAL_KM > 100, f"{river.TOTAL_KM:.1f} km")
    airport = (11.0407, 77.0464)

    def dist_m(p):
        return math.hypot((p[0] - airport[0]) * 111320,
                          (p[1] - airport[1]) * 111320 * math.cos(math.radians(11.0)))

    markers = [(s["lat"], s["lon"]) for s in config.SEGMENTS]
    markers += [(v["lat"], v["lon"]) for v in config.VILLAGES]
    markers += [(config.GHAT["lat"], config.GHAT["lon"]),
                (config.SURGE_SENSOR["lat"], config.SURGE_SENSOR["lon"]),
                (config.DAM["lat"], config.DAM["lon"])]
    nearest = min(dist_m(p) for p in markers)
    check("all map markers away from the airport", nearest > 3000, f"nearest marker {nearest/1000:.1f} km away")

    check("surge sensor 5 km upstream of ghat",
          abs((config.GHAT_CHAIN - config.SENSOR_CHAIN) - 5.0) < 0.01,
          f"{config.GHAT_CHAIN - config.SENSOR_CHAIN:.1f} km")
    check("auto-alert threshold above review threshold",
          config.AUTO_ALERT_CONF > config.DETECTION_CONFIRM_CONF,
          f"{config.DETECTION_CONFIRM_CONF}% / {config.AUTO_ALERT_CONF}%")

    missing = [k for k, v in i18n.STRINGS.items() if not v.get("en") or not v.get("ta")]
    check("every alert string has EN + TA", not missing, ", ".join(missing))
    check("label levels resolve", all(isinstance(risk.label_level(x), int) for x in risk.CONCERN))

    async def _noop(msg):
        return None

    eng = engine.Engine(_noop)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(eng.add_detection({"label": "Textile waste", "confidence": 80.0, "segment": "S4", "source": "selfcheck"}))
        loop.run_until_complete(eng.add_detection({"label": "Foam / discoloured water", "confidence": 87.0, "segment": "S4", "source": "selfcheck"}))
        loop.run_until_complete(eng.add_detection({"label": "Plastic bottle", "confidence": 93.0, "segment": "S2", "source": "selfcheck"}))
    finally:
        loop.close()
    statuses = {d["confidence"]: d["status"] for d in eng.detections}
    check("80% high-concern waits for officer", statuses.get(80.0) == "pending", statuses.get(80.0))
    check("87% high-concern is logged, not auto-sent", statuses.get(87.0) == "logged", statuses.get(87.0))
    check("93% bottle is logged (low concern)", statuses.get(93.0) == "logged", statuses.get(93.0))
    check("review queue has the 80% item", len(eng.pending) == 1, f"{len(eng.pending)} items")

    snapped = [d for d in eng.detections if d.get("lat") is not None]
    worst = max(min(point_segment_m((d["lat"], d["lon"]), pts[i], pts[i + 1])
                    for i in range(len(pts) - 1)) for d in snapped)
    check("detections sit on the real river", worst < 100, f"worst {worst:.0f} m off-river")

    ch = __import__("backend.alerts", fromlist=["channel_status"]).channel_status()
    check("channels list is honest",
          "SMS" in ch["planned"] and "Telegram Bot API" in ch["implemented"],
          "planned/implemented split present")

    from . import telegram_bot

    old_chat = config.TELEGRAM_CHAT_ID
    config.TELEGRAM_CHAT_ID = "5551234"
    bot = telegram_bot.TelegramBot(eng)
    loop2 = asyncio.new_event_loop()
    try:
        r_help = loop2.run_until_complete(bot.handle("5551234", "/help"))
        r_foreign = loop2.run_until_complete(bot.handle("999", "/status"))
        r_pend = loop2.run_until_complete(bot.handle("5551234", "/pending"))
        r_appr = loop2.run_until_complete(bot.handle("5551234", "/approve 1"))
        r_stat = loop2.run_until_complete(bot.handle("5551234", "/status"))
        r_pin_bad = loop2.run_until_complete(bot.handle("5551234", "/breach 0000"))
        breach_after_bad = eng.breach["confirmed"]
        r_pin_ok = loop2.run_until_complete(bot.handle("5551234", f"/breach {config.OFFICER_PIN}"))
    finally:
        loop2.close()
        config.TELEGRAM_CHAT_ID = old_chat
    check("bot help lists the commands", "/approve" in r_help and "/breach" in r_help)
    check("bot ignores other chats", r_foreign is None)
    check("bot lists the review queue", "Textile waste" in r_pend)
    check("bot approve resolves the item", "confirmed" in r_appr and len(eng.pending) == 0)
    check("bot status shows risk", "Below dam" in r_stat)
    check("bot rejects a wrong PIN", "REJECTED" in r_pin_bad and not breach_after_bad)
    check("bot accepts the real PIN", eng.breach["confirmed"] and "confirmed" in r_pin_ok.lower())


def online():
    try:
        h = get("/api/health")
    except Exception as e:
        skip("backend online", f"not reachable at {BASE} ({e}); start with: python run.py")
        return
    check("backend health", bool(h.get("ok")))

    s = get("/api/state")
    for key in ("river", "segments", "devices", "channels", "detections", "alerts", "villages", "map"):
        check(f"state has '{key}'", key in s)
    check("at least two map segments", len(s.get("segments", [])) >= 5, f"{len(s.get('segments', []))} segments")
    check("channels show planned channels", bool(s.get("channels", {}).get("planned")))

    code, _ = post("/api/events/breach", {"pin": "0000"})
    check("wrong officer PIN is rejected", code == 403, f"HTTP {code}")

    cap = get("/api/cap")
    check("CAP export has identifier", "alert" in cap and cap["alert"].get("identifier"), cap["alert"].get("identifier", ""))

    siren = get("/api/device/siren")
    check("siren endpoint shape", "siren" in siren and "beacon" in siren)

    if config.TELEGRAM_BOT_TOKEN:
        from . import telegram_bot

        try:
            me = telegram_bot.api_call("getMe")
            username = (me.get("result") or {}).get("username", "")
            check("telegram bot token valid", bool(me.get("ok") and username), username)
        except Exception as e:
            check("telegram bot token valid", False, str(e))
    else:
        skip("telegram officer bot",
             "set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, restart the backend to enable it")


def main():
    print("AQUA AI self check\n" + "=" * 40)
    offline()
    print("-" * 40)
    online()
    print("=" * 40)
    print(f"passed {len(PASS)}  failed {len(FAIL)}  skipped {len(SKIP)}")
    if FAIL:
        print("fix the failures before the demo.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
