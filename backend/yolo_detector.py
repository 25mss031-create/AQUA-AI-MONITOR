import argparse
import json
import time
import urllib.request
from pathlib import Path

COCO_TO_RIVER = {
    "bottle": "Plastic bottle",
    "wine glass": "Plastic bottle",
    "cup": "Plastic waste",
    "vase": "Plastic waste",
    "bowl": "Metal can",
    "fork": "Metal can",
    "knife": "Metal can",
    "spoon": "Metal can",
    "potted plant": "Water hyacinth",
    "banana": "Plastic waste",
    "boat": "Plastic waste",
}

PROXY_CLASSES = {"wine glass", "vase", "bowl", "fork", "knife", "spoon", "potted plant", "banana", "boat"}

MODEL_NOTE = (
    "Current weights are COCO-pretrained yolov8n.pt: it detects everyday COCO objects, "
    "which are remapped to river classes (bottle/cup directly, the rest approximately). "
    "Textile waste, foam, oil slick and dead fish need a TACO/Noyyal fine-tuned best.pt."
)


def post(url, path, payload):
    from . import http_util
    try:
        return http_util.post_json(url + path, payload, timeout=5)
    except Exception:
        return False


def main():
    p = argparse.ArgumentParser(description="Run YOLO on river photos/webcam and stream detections to the backend.")
    p.add_argument("--source", default="samples", help="image, folder, glob, or 0 for webcam")
    p.add_argument("--model", default="yolov8n.pt", help="weights file (e.g. best.pt) or model name")
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--segment", default="", help="force a stretch id (S1..S5); empty = auto by GPS")
    p.add_argument("--conf", type=float, default=0.35)
    p.add_argument("--loop", action="store_true", help="keep re-running (webcam / video)")
    p.add_argument("--save", default="data/annotated", help="folder for annotated output")
    p.add_argument("--no-post", action="store_true")
    args = p.parse_args()

    try:
        from ultralytics import YOLO
    except Exception as e:
        print("ultralytics is not installed. Run:  pip install -r requirements.txt")
        print(e)
        return

    print(f"loading model: {args.model}")
    model = YOLO(args.model)
    print(MODEL_NOTE)
    print(f"classes in weights: {len(model.names)}; accepted for river monitoring: "
          + ", ".join(sorted(COCO_TO_RIVER)))
    Path(args.save).mkdir(parents=True, exist_ok=True)

    source = args.source
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    def run_once(tag):
        results = model.predict(source, conf=args.conf, verbose=False, stream=False)
        total = 0
        for r in results:
            names = r.names
            boxes = []
            for box in r.boxes:
                raw = names[int(box.cls[0])]
                if raw not in COCO_TO_RIVER:
                    continue
                label = COCO_TO_RIVER[raw]
                conf = round(float(box.conf[0]) * 100, 1)
                boxes.append((label, conf))
                total += 1
                if not args.no_post:
                    payload = {"label": label, "confidence": conf, "source": "yolo",
                               "raw_class": raw, "proxy": raw in PROXY_CLASSES}
                    if args.segment:
                        payload["segment"] = args.segment
                    post(args.url, "/api/detections", payload)
            if len(boxes):
                print(f"[{tag}] {len(boxes)} detections: " + ", ".join(f"{l}({c}%)" for l, c in boxes))
            else:
                print(f"[{tag}] no detections")
            try:
                out = r.plot()
                import cv2
                fn = Path(args.save) / f"det_{tag}.jpg"
                cv2.imwrite(str(fn), out)
            except Exception:
                pass
        return total

    if args.loop or (isinstance(source, int)):
        i = 0
        while True:
            i += 1
            run_once(f"{i:05d}")
            time.sleep(1)
    else:
        run_once("out")
        print(f"annotated images saved to {Path(args.save).resolve()}")


if __name__ == "__main__":
    main()
