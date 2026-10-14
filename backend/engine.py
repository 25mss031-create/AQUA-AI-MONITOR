import asyncio
import json
import math
import random
from datetime import datetime, timezone

from . import alerts, config, db, i18n, risk, river


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _age(ts):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds()
    except Exception:
        return None


class Engine:
    def __init__(self, broadcast):
        self.broadcast = broadcast
        self._reset_state()

    def _reset_state(self):
        self.water = {"ph": 7.4, "turbidity": 85.0, "tds": 420.0, "temp_c": 28.5, "segment": "S3"}
        self.anomalies = []
        self.risk_src = {s["id"]: {"water": 0, "det": 0, "surge": 0} for s in config.SEGMENTS}
        self.detections = []
        self.pending = []
        self.alert_log = []
        self.det_count = 0
        self.surge = self._new_surge()
        self.breach = {"confirmed": False, "elapsed_min": 0, "by": None}
        self.wave_speed = config.WAVE_SPEED_DEFAULT
        self.last_boat_segment = "S3"
        self.devices = {}

    def _new_surge(self):
        return {
            "active": False, "alert": False, "siren": False, "beacon": False, "rate": 0.0,
            "level": 1.2, "level_a": 1.2, "level_b": 1.2, "countdown_min": None,
            "arrived": False, "history": [1.2] * config.SURGE_HISTORY, "ticks": 0,
        }

    def _new_device(self, station):
        return {
            "station": station, "battery_v": None, "rssi": None,
            "sensor_ok": True, "lat": None, "lon": None, "gps_fix": False,
            "last_seen": None, "low_alerted": False, "fault_alerted": False,
        }

    def _device(self, station=None):
        sid = station or "flow-station-1"
        if sid not in self.devices:
            self.devices[sid] = self._new_device(sid)
        return self.devices[sid]

    def _seg_risk(self, sid):
        return max(self.risk_src.get(sid, {"water": 0, "det": 0, "surge": 0}).values())

    def _nearest_segment(self, lat, lon):
        if lat is None or lon is None:
            return None
        best, bd = None, 1e18
        for s in config.SEGMENTS:
            dd = (s["lat"] - lat) ** 2 + (s["lon"] - lon) ** 2
            if dd < bd:
                bd, best = dd, s["id"]
        return best

    def _eta(self, i):
        km = config.VILLAGES[i]["distance_km"]
        return km * 1000.0 / self.wave_speed / 60.0

    def _alert(self, channel, severity, key, params=None, segment=None):
        params = params or {}
        en, ta = i18n.pair(key, **params)
        entry = {"ts": now_iso(), "channel": channel, "severity": severity,
                 "segment": segment, "en": en, "ta": ta, "key": key}
        self.alert_log.insert(0, entry)
        self.alert_log = self.alert_log[:200]
        db.add_alert({**entry, "message": en})
        if alerts.channel_status()["telegram"]:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(asyncio.to_thread(
                    alerts.send_telegram, f"[AQUA AI][{severity.upper()}]\n{en}\n{ta}"))
            except RuntimeError:
                pass

    async def _emit(self):
        await self.broadcast(json.dumps(self.snapshot()))

    def _update_level(self, level, a=None, b=None):
        h = self.surge["history"]
        h.append(level)
        del h[0]
        self.surge["level"] = level
        self.surge["level_a"] = a if a is not None else level
        self.surge["level_b"] = b if b is not None else level
        if len(h) >= 7:
            rate = (h[-1] - h[-7]) / 6.0 * 60.0
            self.surge["rate"] = round(rate, 1)
            if rate > config.SURGE_RATE_LIMIT and not self.surge["alert"]:
                self._trigger_surge(rate)

    def _trigger_surge(self, rate):
        s = self.surge
        s["alert"] = True
        s["siren"] = True
        s["beacon"] = True
        s["countdown_min"] = math.ceil(config.SURGE_SENSOR_DISTANCE_M / config.SURGE_WAVE_SPEED / 60.0)
        self.risk_src["S3"]["surge"] = 2
        self._alert("Dashboard + Telegram + ghat siren + beacon", "high", "surge",
                    {"rate": rate, "min": s["countdown_min"]}, "S3")

    def _check_device(self, r):
        d = self._device(r.get("station_id"))
        d["last_seen"] = r.get("ts")
        d["station"] = r.get("station_id") or d["station"]
        if r.get("battery_v") is not None:
            d["battery_v"] = round(float(r["battery_v"]), 2)
        if r.get("rssi") is not None:
            d["rssi"] = int(r["rssi"])
        if r.get("sensor_ok") is not None:
            d["sensor_ok"] = bool(r["sensor_ok"])
        if r.get("lat") is not None:
            d["lat"] = r.get("lat")
        if r.get("lon") is not None:
            d["lon"] = r.get("lon")
        if r.get("gps_fix") is not None:
            d["gps_fix"] = bool(r["gps_fix"])
        v = d.get("battery_v")
        if v is not None and v < config.BATTERY_LOW_V and not d["low_alerted"]:
            d["low_alerted"] = True
            self._alert("Dashboard + Telegram", "medium", "low_battery",
                        {"station": d["station"], "v": v})
        if v is not None and v >= config.BATTERY_LOW_V:
            d["low_alerted"] = False
        if not d["sensor_ok"] and not d["fault_alerted"]:
            d["fault_alerted"] = True
            self._alert("Dashboard", "medium", "sensor_fault",
                        {"station": d["station"], "a": self.surge["level_a"], "b": self.surge["level_b"]})
        if d["sensor_ok"]:
            d["fault_alerted"] = False

    async def reset(self):
        self._reset_state()
        await self._emit()

    async def add_reading(self, r):
        r = dict(r)
        r.setdefault("ts", now_iso())
        sid = r.get("station_id")
        station = config.STATIONS.get(sid, {})
        seg = r.get("segment") or station.get("segment")
        r["segment"] = seg
        if r.get("lat") is None and seg in config.SEGMENT_BY_ID:
            r["lat"] = config.SEGMENT_BY_ID[seg]["lat"]
            r["lon"] = config.SEGMENT_BY_ID[seg]["lon"]
        db.add_reading(r)

        a = r.get("level_a_m")
        b = r.get("level_b_m")
        lvl = r.get("level_m")
        if a is not None and b is not None:
            a, b = float(a), float(b)
            lvl = (a + b) / 2.0
            r["level_m"] = lvl
            if abs(a - b) > 0.3:
                self._device(sid)["sensor_ok"] = False
            else:
                self._device(sid)["sensor_ok"] = True
        if lvl is not None and not (self.surge["active"] and not self.surge["arrived"]):
            self._update_level(float(lvl), a, b)
        self._check_device(r)

        if any(r.get(k) is not None for k in ("ph", "turbidity", "tds")):
            if seg:
                self.last_boat_segment = seg
            self.water = {
                "ph": r.get("ph", self.water["ph"]),
                "turbidity": r.get("turbidity", self.water["turbidity"]),
                "tds": r.get("tds", self.water["tds"]),
                "temp_c": r.get("temp_c", self.water["temp_c"]),
                "segment": seg,
            }
            lvlv, flags = risk.water_level(self.water["ph"], self.water["turbidity"], self.water["tds"])
            self.anomalies = flags
            if seg:
                self.risk_src[seg]["water"] = lvlv
        await self._emit()

    async def add_detection(self, d):
        d = dict(d)
        d.setdefault("ts", now_iso())
        seg = d.get("segment") or self._nearest_segment(d.get("lat"), d.get("lon")) or self.last_boat_segment
        d["segment"] = seg
        if d.get("lat") is None:
            segd = config.SEGMENT_BY_ID.get(seg) or {}
            a = float(segd.get("chain_from", config.GHAT_CHAIN - 4))
            b = float(segd.get("chain_to", config.GHAT_CHAIN + 4))
            chain = random.uniform(min(a, b), max(a, b))
            la, lo = river.at_km(chain)
            d["lat"] = round(la + random.uniform(-0.0004, 0.0004), 6)
            d["lon"] = round(lo + random.uniform(-0.0004, 0.0004), 6)
            d["chain_km"] = round(chain, 1)
        elif d.get("chain_km") is None:
            d["chain_km"] = config.SEGMENT_BY_ID.get(seg, {}).get("chain_from")
        db.add_detection(d)

        label = d.get("label")
        conf = float(d.get("confidence") or 0)
        level = risk.label_level(label)
        segname = config.SEGMENT_BY_ID.get(seg, {}).get("name", seg)

        item = {
            "ts": d["ts"], "segment": seg, "segment_name": segname,
            "label": label, "confidence": conf, "lat": d.get("lat"),
            "lon": d.get("lon"), "source": d.get("source"), "level": level,
            "chain_km": d.get("chain_km"), "status": "logged",
            "coco": d.get("raw_class"), "proxy": bool(d.get("proxy")),
        }
        if level >= 2 and conf < config.DETECTION_CONFIRM_CONF:
            item["status"] = "pending"
            self.pending.insert(0, item)
            self.pending = self.pending[:40]
            self._alert("Dashboard (review queue)", "medium", "review",
                        {"label": label, "segment": segname, "conf": conf}, seg)
        elif level >= 2 and conf >= config.AUTO_ALERT_CONF:
            item["status"] = "notified"
            self._alert("Dashboard + Telegram to TNPCB", "high", "tnpcb",
                        {"label": label, "segment": segname, "conf": conf}, seg)
            if seg in self.risk_src:
                self.risk_src[seg]["det"] = max(self.risk_src[seg]["det"], level)

        self.detections.insert(0, item)
        self.detections = self.detections[:200]
        self.det_count += 1
        await self._emit()

    async def resolve_review(self, ts, action):
        item = next((x for x in self.pending if x["ts"] == ts), None)
        if item is None:
            return False
        self.pending = [x for x in self.pending if x["ts"] != ts]
        seg = item["segment"]
        segname = item["segment_name"]
        label = item["label"]
        conf = item["confidence"]
        if action == "approve":
            item["status"] = "approved"
            if seg in self.risk_src:
                self.risk_src[seg]["det"] = max(self.risk_src[seg]["det"], item["level"])
            self._alert("Dashboard + Telegram to TNPCB (officer-approved)", "high", "approved",
                        {"label": label, "segment": segname}, seg)
        else:
            item["status"] = "dismissed"
            self._alert("Dashboard", "low", "dismissed",
                        {"label": label, "segment": segname}, seg)
        for x in self.detections:
            if x["ts"] == ts:
                x["status"] = item["status"]
        await self._emit()
        return True

    async def trigger_wastewater(self):
        self.water = {"ph": 9.4, "turbidity": 410.0, "tds": 1450.0, "temp_c": 30.2, "segment": "S3"}
        lvlv, flags = risk.water_level(9.4, 410.0, 1450.0)
        self.anomalies = flags
        self.risk_src["S3"]["water"] = lvlv
        segname = config.SEGMENT_BY_ID["S3"]["name"]
        self._alert("Dashboard + Telegram to TNPCB", "high", "wastewater",
                    {"ph": 9.4, "tds": 1450, "segment": segname}, "S3")
        for label, conf in [("Foam / discoloured water", 79.0), ("Textile waste", 84.0)]:
            await self.add_detection({"label": label, "confidence": conf, "segment": "S3", "source": "sim"})
        await self._emit()

    async def trigger_surge(self):
        if self.surge["active"] and not self.surge["arrived"]:
            return
        self.surge = self._new_surge()
        self.surge["active"] = True
        await self._emit()

    async def confirm_breach(self):
        if self.breach["confirmed"]:
            return
        self.breach = {"confirmed": True, "elapsed_min": 0, "by": "officer"}
        self._alert("Officer-confirmed: dashboard + Telegram + ghat siren + beacon + CAP export", "high", "breach",
                    {"village": config.VILLAGES[0]["name"], "min": round(self._eta(0))}, None)
        await self._emit()

    async def breach_request(self, pin, source):
        if str(pin) != config.OFFICER_PIN:
            self._alert(f"{source} (security log)", "high", "pin_rejected", {}, None)
            await self._emit()
            return False
        await self.confirm_breach()
        return True

    async def tick(self):
        s = self.surge
        if s["active"] and not s["arrived"]:
            s["ticks"] += 1
            if s["ticks"] < 18:
                level = 1.2 + random.uniform(-0.02, 0.02)
            else:
                level = s["history"][-1] + 0.14
            self._update_level(level, level + random.uniform(-0.02, 0.02), level + random.uniform(-0.02, 0.02))
            if s["alert"] and s["countdown_min"] is not None:
                s["countdown_min"] = max(0, s["countdown_min"] - config.SURGE_DEMO_STEP_MIN)
                if s["countdown_min"] == 0:
                    s["arrived"] = True
                    s["siren"] = False
                    s["beacon"] = False
                    self._alert("Dashboard + ghat siren/beacon", "high", "arrived", {}, "S3")
        if self.breach["confirmed"]:
            if self.breach["elapsed_min"] <= self._eta(len(config.VILLAGES) - 1) + 2:
                self.breach["elapsed_min"] += config.BREACH_DEMO_STEP_MIN

    def snapshot(self):
        segs = [{
            "id": s["id"], "name": s["name"], "lat": s["lat"], "lon": s["lon"],
            "chain_from": s["chain_from"], "risk": self._seg_risk(s["id"]),
        } for s in config.SEGMENTS]
        villages = []
        for i, v in enumerate(config.VILLAGES):
            eta = self._eta(i)
            rem = max(0.0, eta - self.breach["elapsed_min"]) if self.breach["confirmed"] else eta
            if not self.breach["confirmed"]:
                status = "standby"
            elif rem <= 0:
                status = "water"
            elif rem <= 10:
                status = "evacuate"
            else:
                status = "warned"
            villages.append({
                "name": v["name"], "distance_km": v["distance_km"], "chain_km": v["chain_km"],
                "lat": v["lat"], "lon": v["lon"], "eta_min": round(eta),
                "remaining_min": round(rem), "status": status,
            })
        high = sum(1 for s in config.SEGMENTS if self._seg_risk(s["id"]) == 2)
        level_status = "SURGE" if (self.surge["alert"] and not self.surge["arrived"]) else "Normal"
        devs = []
        for d in self.devices.values():
            x = dict(d)
            x["age_s"] = _age(d.get("last_seen")) if d.get("last_seen") else None
            devs.append(x)
        devs.sort(key=lambda x: x["station"])
        dev = next((x for x in devs if x["station"] == "flow-station-1"), devs[0] if devs else {})
        return {
            "ts": now_iso(),
            "kpis": {"detections": self.det_count, "high_risk": high,
                     "level_status": level_status, "alerts": len(self.alert_log),
                     "pending": len(self.pending)},
            "water": {**self.water, "anomalies": self.anomalies,
                      "limits": {"ph_min": config.PH_MIN, "ph_max": config.PH_MAX,
                                 "turb": config.TURB_LIMIT, "tds": config.TDS_LIMIT}},
            "segments": segs,
            "segment_spans": config.SEGMENT_SPANS,
            "river": config.RIVER_POLYLINE,
            "detections": self.detections[:40],
            "pending": self.pending,
            "surge": {
                "active": self.surge["active"], "alert": self.surge["alert"],
                "siren": self.surge["siren"], "beacon": self.surge["beacon"],
                "rate": self.surge["rate"], "level": round(self.surge["level"], 2),
                "level_a": round(self.surge["level_a"], 2),
                "level_b": round(self.surge["level_b"], 2),
                "countdown_min": self.surge["countdown_min"],
                "arrived": self.surge["arrived"],
                "history": [round(x, 2) for x in self.surge["history"]],
            },
            "device": dev,
            "devices": devs,
            "breach": self.breach,
            "villages": villages,
            "alerts": self.alert_log[:60],
            "wave_speed": self.wave_speed,
            "map": {"ghat": config.GHAT, "sensor": config.SURGE_SENSOR, "dam": config.DAM,
                    "bounds": config.DEMO_BOUNDS},
            "channels": alerts.channel_status(),
        }

    def siren_on(self):
        return bool(self.surge["siren"])

    def beacon_on(self):
        return bool(self.surge["beacon"])

    async def set_wave_speed(self, v):
        try:
            self.wave_speed = max(1.0, min(12.0, float(v)))
        except Exception:
            pass
        await self._emit()

    def cap_alert(self):
        return {
            "alert": {
                "identifier": "AQUA-DEMO-001",
                "sender": "aqua-monitor@demo",
                "sent": now_iso(),
                "status": "Exercise",
                "msgType": "Alert",
                "scope": "Restricted",
                "info": {
                    "category": "Geo",
                    "event": "Dam breach",
                    "urgency": "Immediate",
                    "severity": "Extreme",
                    "certainty": "Observed",
                    "language": ["en-IN", "ta-IN"],
                    "headline": "Dam breach: move to high ground",
                    "description": "AQUA AI Monitor has confirmed a dam breach. Riverbank and low-lying "
                                   "villages must move to high ground immediately. "
                                   "அணை உடைப்பு உறுதி. உயரமான இடத்திற்கு செல்லுங்கள்.",
                    "area": [
                        {"areaDesc": v["name"], "chain_km": v["chain_km"], "eta_min": round(self._eta(i))}
                        for i, v in enumerate(config.VILLAGES)
                    ],
                },
            }
        }
