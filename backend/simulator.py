import argparse
import json
import random
import time
import urllib.request


def post(url, path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def boat_reading(waste=False):
    if waste:
        return {"station_id": "aqua-boat-1", "segment": "S3", "ph": round(random.uniform(9.0, 9.8), 2),
                "turbidity": round(random.uniform(380, 450), 1), "tds": round(random.uniform(1350, 1550)),
                "temp_c": round(random.uniform(29.5, 31.0), 1)}
    return {"station_id": "aqua-boat-1", "segment": "S3", "ph": round(random.uniform(7.1, 7.8), 2),
            "turbidity": round(random.uniform(60, 140), 1), "tds": round(random.uniform(380, 480)),
            "temp_c": round(random.uniform(27.5, 29.5), 1)}


def level_reading(rising=False, last=1.2, tick=0):
    if rising and tick > 18:
        return round(last + 0.14, 3)
    return round(1.2 + random.uniform(-0.02, 0.02), 3)


def device_fields(tick):
    return {
        "battery_v": round(max(3.2, 4.05 - tick * 0.0006), 2),
        "rssi": random.randint(-78, -52),
        "gps_fix": False,
    }


DETECTION_LABELS = [
    ("Plastic bag", 3), ("Plastic bottle", 3), ("Metal can", 2), ("Water hyacinth", 2),
    ("Thermocol", 2), ("Textile waste", 2), ("Foam / discoloured water", 2),
]


def random_detection():
    labels = [l for l, w in DETECTION_LABELS for _ in range(w)]
    seg = random.choice(["S1", "S2", "S3", "S4", "S5"])
    conf = round(random.triangular(72, 95, 84), 1)
    return {"label": random.choice(labels), "confidence": conf, "segment": seg, "source": "sim"}


def main():
    p = argparse.ArgumentParser(description="Simulate the ESP32 sensor boat / flow station over HTTP.")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--interval", type=float, default=2.0)
    p.add_argument("--event", choices=["none", "wastewater", "surge", "breach"], default="none")
    p.add_argument("--detections", action="store_true", help="also post random YOLO-style detections")
    p.add_argument("--wastewater", action="store_true", help="keep posting polluted water quality")
    args = p.parse_args()

    print(f"Simulator -> {args.url} (Ctrl+C to stop)")
    if args.event != "none":
        time.sleep(2)
        if post(args.url, f"/api/events/{args.event}", {}):
            print(f"fired event: {args.event}")
        if args.event == "surge":
            print("surge simulation now driven by the backend tick loop")

    tick = 0
    last = 1.2
    while True:
        tick += 1
        post(args.url, "/api/readings", boat_reading(args.wastewater) | device_fields(tick))
        rising = args.event == "surge"
        last = level_reading(rising, last, tick)
        post(args.url, "/api/readings", {"station_id": "flow-station-1", "segment": "S2",
                                         "level_a_m": round(last + random.uniform(-0.01, 0.01), 3),
                                         "level_b_m": round(last + random.uniform(-0.01, 0.01), 3),
                                         **device_fields(tick)})
        if args.detections and tick % 10 == 0:
            post(args.url, "/api/detections", random_detection())
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
