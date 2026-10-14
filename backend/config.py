import os
from pathlib import Path

from . import river

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DASHBOARD_DIR = BASE_DIR / "dashboard"


def _load_dotenv(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv(BASE_DIR / ".env")

DB_PATH = os.getenv("AQUA_DB", str(DATA_DIR / "aqua.db"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
INGEST_TOKEN = os.getenv("INGEST_TOKEN", "aqua-demo-key")
OFFICER_PIN = os.getenv("OFFICER_PIN", "2026")

PH_MIN = 6.5
PH_MAX = 8.5
TURB_LIMIT = 300.0
TDS_LIMIT = 1000.0

SURGE_RATE_LIMIT = 5.0
SURGE_SENSOR_DISTANCE_M = 5000.0
SURGE_WAVE_SPEED = 2.0
SURGE_HISTORY = 60
SURGE_DEMO_STEP_MIN = 2

BREACH_DEMO_STEP_MIN = 1
WAVE_SPEED_DEFAULT = 5.0

DETECTION_CONFIRM_CONF = 85.0
AUTO_ALERT_CONF = 90.0

BATTERY_LOW_V = 3.35

CHAIN_S1 = 35.7
CHAIN_S2 = 47.0
CHAIN_S3 = 58.0
CHAIN_S4 = 70.0
CHAIN_S5 = 82.0

GHAT_CHAIN = CHAIN_S3
SENSOR_CHAIN = GHAT_CHAIN - SURGE_SENSOR_DISTANCE_M / 1000.0

VILLAGE_OFFSET_KM = [10, 20, 32, 45]

_SEG_DEFS = [
    ("S1", "Below dam", CHAIN_S1, CHAIN_S2),
    ("S2", "Flow station", CHAIN_S2, CHAIN_S3),
    ("S3", "Bathing ghat", CHAIN_S3, CHAIN_S4),
    ("S4", "Town", CHAIN_S4, CHAIN_S5),
    ("S5", "Tail", CHAIN_S5, CHAIN_S5 + 12.0),
]

SEGMENTS = [
    {"id": sid, "name": name, "chain_from": a, "chain_to": b,
     "lat": river.at_km(a)[0], "lon": river.at_km(a)[1]}
    for sid, name, a, b in _SEG_DEFS
]
SEGMENT_BY_ID = {s["id"]: s for s in SEGMENTS}

SEGMENT_SPANS = {
    sid: [river.span_index(a), river.span_index(b) + 1]
    for sid, _n, a, b in _SEG_DEFS
}

GHAT = {"name": "Ghat siren", "lat": river.at_km(GHAT_CHAIN)[0], "lon": river.at_km(GHAT_CHAIN)[1]}
SURGE_SENSOR = {"name": "Upstream level sensor", "lat": river.at_km(SENSOR_CHAIN)[0],
                "lon": river.at_km(SENSOR_CHAIN)[1]}
DAM = {"name": "Head works / dam", "lat": river.at_km(CHAIN_S1)[0], "lon": river.at_km(CHAIN_S1)[1]}

VILLAGES = []
for _i, _off in enumerate(VILLAGE_OFFSET_KM):
    _chain = CHAIN_S1 + _off
    _lat, _lon = river.at_km(_chain)
    VILLAGES.append({"name": f"Village {chr(65 + _i)}", "distance_km": _off,
                     "chain_km": round(_chain, 1), "lat": _lat, "lon": _lon})

STATIONS = {
    "aqua-boat-1": {"kind": "water", "segment": "S3"},
    "flow-station-1": {"kind": "level", "segment": "S2"},
}

RIVER_POLYLINE = river.polyline()

_DEMO_PTS = [(s["lat"], s["lon"]) for s in SEGMENTS] + \
            [(v["lat"], v["lon"]) for v in VILLAGES] + \
            [(GHAT["lat"], GHAT["lon"]), (SURGE_SENSOR["lat"], SURGE_SENSOR["lon"])]
DEMO_BOUNDS = {
    "south": min(p[0] for p in _DEMO_PTS),
    "north": max(p[0] for p in _DEMO_PTS),
    "west": min(p[1] for p in _DEMO_PTS),
    "east": max(p[1] for p in _DEMO_PTS),
}
