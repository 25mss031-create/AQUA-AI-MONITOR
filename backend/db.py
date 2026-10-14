import sqlite3

from . import config


def _conn():
    c = sqlite3.connect(config.DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS readings(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, station_id TEXT, segment TEXT,
                lat REAL, lon REAL, ph REAL, turbidity REAL,
                tds REAL, temp_c REAL, level_m REAL
            );
            CREATE TABLE IF NOT EXISTS detections(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, segment TEXT, label TEXT,
                confidence REAL, lat REAL, lon REAL, source TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, channel TEXT, severity TEXT, message TEXT, segment TEXT
            );
            """
        )


def add_reading(r):
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO readings(ts,station_id,segment,lat,lon,ph,turbidity,tds,temp_c,level_m)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    r.get("ts"), r.get("station_id"), r.get("segment"),
                    r.get("lat"), r.get("lon"), r.get("ph"), r.get("turbidity"),
                    r.get("tds"), r.get("temp_c"), r.get("level_m"),
                ),
            )
    except Exception:
        pass


def add_detection(d):
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO detections(ts,segment,label,confidence,lat,lon,source)"
                " VALUES(?,?,?,?,?,?,?)",
                (
                    d.get("ts"), d.get("segment"), d.get("label"),
                    d.get("confidence"), d.get("lat"), d.get("lon"), d.get("source"),
                ),
            )
    except Exception:
        pass


def add_alert(a):
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO alerts(ts,channel,severity,message,segment) VALUES(?,?,?,?,?)",
                (a.get("ts"), a.get("channel"), a.get("severity"), a.get("message"), a.get("segment")),
            )
    except Exception:
        pass


def counts():
    try:
        with _conn() as c:
            return {
                "readings": c.execute("SELECT COUNT(*) FROM readings").fetchone()[0],
                "detections": c.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
                "alerts": c.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
            }
    except Exception:
        return {"readings": 0, "detections": 0, "alerts": 0}
