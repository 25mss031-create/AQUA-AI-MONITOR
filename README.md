# AQUA AI Monitor: River Edition (working prototype)

An end-to-end river pollution and life-safety monitoring prototype:
sensor boats and a flow station feed a Python backend that scores risk,
detects riverbank surges, prepares dam-breach countdowns, raises alerts
(dashboard + Telegram), and shows everything on a live OpenStreetMap dashboard.

## Languages and what each part does

| Part | Language / tool | File |
|---|---|---|
| AI detection | Python + YOLO (Ultralytics) | `backend/yolo_detector.py` |
| Sensor boat + flow station + siren | C++ (Arduino) for ESP32 | `esp32/aqua_boat/aqua_boat.ino` |
| Backend (data, risk, countdown, alerts) | Python + FastAPI | `backend/app.py`, `backend/engine.py` |
| Risk rules | Python | `backend/risk.py` |
| Dashboard + map | HTML/CSS/JS + Leaflet + OpenStreetMap | `dashboard/index.html` |
| Database | SQLite | `data/aqua.db` |
| ESP32 data path | HTTP over WiFi (GSM/LoRa for remote sites: planned) | firmware + `backend/simulator.py` |
| Telegram alerts | Python (HTTP) | `backend/alerts.py` |

## Actual implementation stack

This is what the code in this repository really uses.

| Component | Choice |
|---|---|
| AI detection | Python, Ultralytics YOLOv8, `yolov8n.pt` (COCO weights) |
| Backend API | Python 3.13, FastAPI, Uvicorn |
| Real-time updates | WebSocket |
| Risk analysis | Plain Python rules and surge calculations |
| Database | SQLite |
| Frontend | HTML, CSS, vanilla JavaScript |
| River map | OpenStreetMap + Leaflet 1.9.4 |
| Hardware controller | ESP32 |
| Water sensors | pH, turbidity, TDS and DS18B20 temperature |
| Surge monitoring | 2 × JSN-SR04T waterproof ultrasonic (dual probes, cross-checked) |
| Location | NEO-6M GPS on the boat; fixed stations use configured coordinates |
| Local warning | Relay, siren and flashing beacon |
| Notifications | Telegram Bot API; dashboard + WebSocket; CAP export (file) |
| Demo mode | Python HTTP simulator |

### Planned, not implemented

Do not present these as working features:

| Item | Status |
|---|---|
| SMS, email, Firebase push notifications | planned |
| LoRa / GSM field link, solar panel + battery | planned for remote river sites (demo uses WiFi + mains/USB) |
| Fine-tuned river-litter detector (`best.pt`, TACO / Noyyal photos) | planned |
| Panchayat / district authority app integration | planned |

Alert channels that actually run today: **dashboard + WebSocket, Telegram
Bot API, ghat siren + beacon relay, CAP export as a JSON file.**

## Quick start

```
start.bat
```

Then open http://localhost:8000

For a one-shot stage demo (backend + simulator + browser):

```
demo.bat
```

## Manual run

```
pip install -r requirements.txt
python run.py
```

In a second terminal, start the ESP32 simulator (no hardware needed):

```
python -m backend.simulator --detections
```

Fire the scripted events from the dashboard buttons, or from the API:

```
curl -X POST http://localhost:8000/api/events/wastewater
curl -X POST http://localhost:8000/api/events/surge
curl -X POST http://localhost:8000/api/events/breach
curl -X POST http://localhost:8000/api/events/reset
```

## Self check (run before every demo)

With the backend running:

```
python -m backend.selfcheck
```

It verifies river geometry, the 85%/90% detection thresholds, bilingual
alert strings, the officer PIN gate, the channels list and the live API, and
prints `passed N  failed 0`. If anything fails, fix it before going on stage.
Use `python -m backend.selfcheck` in a terminal where the backend is already
up; offline checks still run if it is not, and the online ones are skipped.

## Stage run-of-show (~8 minutes)

| Time | Do this | What the judges see |
|---|---|---|
| 0:00 | Run `demo.bat`, open the browser at http://localhost:8000 | Live map of the real Noyyal, 5 stretches, KPIs updating from the sensor simulator |
| 0:45 | Point at **Field device health** | Boat + flow station: battery, RSSI, dual probes, GPS "configured coords" (GPS fix when the boat has one) |
| 1:30 | Click **Simulate wastewater event** | S3 turns red, pH/TDS/TDS tiles flag ANOMALY, two detections appear in the review queue |
| 2:30 | Scroll to **Did a dyeing/textile unit discharge here?** | Approve one item → bilingual "Officer confirmed… TNPCB notified" alert; dismiss the other → "false detection" |
| 3:30 | Run `python -m backend.yolo_detector --source samples --conf 0.35` | Real YOLO detections stream in, each tagged with its COCO class, sitting on the river by chainage |
| 4:30 | Click **Simulate surge at riverbank** | Level chart rises, siren + beacon lights flash, 42-minute countdown, bilingual surge alert (CAP export button) |
| 6:00 | Dam-breach card: wrong PIN first, then `2026` | Wrong PIN → rejected and logged; correct PIN → per-village countdown table, villages change colour |
| 7:15 | **Reset all**, open **Alert channels** card | Shows what is implemented (dashboard, Telegram, siren/beacon, CAP file) vs what is only planned (SMS, email, Firebase, LoRa/GSM) |

## The demo workflow (what the judges see)

1. **Normal monitoring.** The simulator posts pH, turbidity, TDS, temperature
   (sensor boat) and water level (flow station). KPIs and the map are live.
2. **Wastewater event.** A stretch turns red, water quality shows ANOMALY,
   detections appear, and a TNPCB alert is logged.
3. **Riverbank surge.** The upstream ultrasonic sensor shows a rapid rate of
   rise. The ghat siren and beacon turn ON, a countdown appears, and a
   dashboard + Telegram alert is raised (CAP export available). When the wave
   arrives the siren stands down.
4. **Dam breach (officer only).** A per-village countdown is computed from
   distance / wave speed, village markers change colour, and a CAP alert can be
   exported for SACHET / Cell Broadcast.
5. **AI detections.** Run the YOLO runner on river photos or the webcam and watch
   boxes + detections stream into the dashboard.

## Real YOLO detection

Put 3-6 river photos in `samples/` and run:

```
python -m backend.yolo_detector --source samples --conf 0.35
```

Webcam / live video:

```
python -m backend.yolo_detector --source 0 --loop
```

### What the current model actually detects

`yolov8n.pt` ships with **COCO weights (80 everyday classes)**, not river
litter classes. `backend/yolo_detector.py` therefore:

- accepts only a fixed set of COCO classes (`bottle`, `cup`, `bowl`, `cutlery`,
  `potted plant`, `banana`, `boat`, `vase`, `wine glass`) and drops everything
  else (person, car, animal, ...);
- remaps them to river labels — `bottle`/`cup` directly, the rest as
  **approximate proxies** (marked `~` in the dashboard, e.g. `potted plant` →
  Water hyacinth);
- tags each detection with the original COCO class (`raw_class`) so the mapping
  stays visible.

Classes such as **Textile waste, Foam / discoloured water, Oil slick and Dead
fish are not produced by these weights.** They need a fine-tuned `best.pt`
(TACO dataset or your own labelled Noyyal photos) — listed as planned work in
the project PDF.

Annotated images are written to `data/annotated/`.

## Connect a real ESP32

`esp32/aqua_boat/aqua_boat.ino` reads:

- pH (analog), turbidity (analog), TDS (analog), DS18B20 temperature;
- **2 × JSN-SR04T** waterproof ultrasonic level probes (probe A + probe B,
  cross-checked by the backend — a disagreement raises a sensor-fault alert);
- **NEO-6M GPS** (Serial2, 9600 baud) so readings and detections are tagged
  with the boat's real position; with no fix the backend falls back to the
  configured stretch coordinates;
- battery voltage through a 2:1 divider and the WiFi RSSI, both shown in
  device health;
- drives the **siren relay** and a separate **beacon** output from
  `/api/device/siren`.

Set `WIFI_SSID`, `WIFI_PASS` and `SERVER` (the IP of the laptop running the
backend, use your phone hotspot for the demo) and upload with Arduino IDE or
PlatformIO. It POSTs to `/api/readings` and polls `/api/device/siren` so the
backend can switch the siren and beacon. Libraries: `OneWire`,
`DallasTemperature`, `TinyGPSPlus`.

### Field deployment (remote river sites)

The prototype uses WiFi + HTTP because it is demonstrated where a network
exists. Real remote sites need a **GSM or LoRa link** in place of WiFi and a
**solar panel + battery** instead of mains/USB. Neither is implemented in this
repository — see the planned table above.

## Telegram alerts (free)

Set these environment variables before starting the backend:

```
set TELEGRAM_BOT_TOKEN=123456:ABC...
set TELEGRAM_CHAT_ID=987654321
python run.py
```

When set, every alert is also pushed to Telegram. The dashboard shows
`Telegram: live`.

## API summary

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/readings` | ESP32 / simulator sensor readings |
| POST | `/api/detections` | YOLO detections |
| POST | `/api/events/wastewater` | scripted pollution event |
| POST | `/api/events/surge` | scripted riverbank surge |
| POST | `/api/events/breach` | officer-confirmed dam breach |
| POST | `/api/events/reset` | reset the demo |
| POST | `/api/wave-speed` | set wave speed (m/s) |
| GET | `/api/state` | full live snapshot |
| GET | `/api/cap` | CAP alert JSON export |
| GET | `/api/device/siren` | siren state for the ESP32 |
| WS | `/ws` | live dashboard stream |

## Notes

- Anomaly limits: pH outside 6.5-8.5, turbidity above 300 NTU, TDS above 1000 ppm.
- Surge limit: rate of rise above 5 m/hour. Sensor 5 km upstream, wave ~2 m/s.
- Dam-breach ETA uses distance / wave speed; the demo runs at 1 second = 1 minute.
- The map uses the real OpenStreetMap Noyyal course; every station, village and
  detection is placed on it by chainage (km from the head works). Locations come
  from the boat GPS when a fix is available, otherwise from those configured
  coordinates.
