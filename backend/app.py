import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .engine import Engine


class Hub:
    def __init__(self):
        self.clients = set()

    async def connect(self, ws):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws):
        self.clients.discard(ws)

    async def broadcast(self, message):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


hub = Hub()
engine = Engine(hub.broadcast)


async def tick_loop():
    while True:
        await asyncio.sleep(1)
        await engine.tick()
        await hub.broadcast(json.dumps(engine.snapshot()))


@asynccontextmanager
async def lifespan(app):
    db.init()
    task = asyncio.create_task(tick_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="AQUA AI Monitor: River Edition", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True, "counts": db.counts()}


@app.get("/api/state")
async def state():
    return engine.snapshot()


@app.post("/api/readings")
async def readings(payload: dict = Body(...)):
    await engine.add_reading(payload)
    return {"ok": True}


@app.post("/api/detections")
async def detections(payload: dict = Body(...)):
    await engine.add_detection(payload)
    return {"ok": True}


@app.post("/api/events/wastewater")
async def ev_wastewater():
    await engine.trigger_wastewater()
    return {"ok": True}


@app.post("/api/events/surge")
async def ev_surge():
    await engine.trigger_surge()
    return {"ok": True}


@app.post("/api/events/breach")
async def ev_breach(payload: dict = Body(default={})):
    pin = str(payload.get("pin", ""))
    if pin != config.OFFICER_PIN:
        engine._alert("Dashboard (security log)", "high", "pin_rejected", {}, None)
        raise HTTPException(status_code=403, detail="Wrong officer PIN")
    await engine.confirm_breach()
    return {"ok": True}


@app.post("/api/review")
async def review(payload: dict = Body(...)):
    ok = await engine.resolve_review(payload.get("ts"), payload.get("action", "dismiss"))
    return {"ok": ok}


@app.post("/api/events/reset")
async def ev_reset():
    await engine.reset()
    return {"ok": True}


@app.post("/api/wave-speed")
async def wave_speed(payload: dict = Body(...)):
    await engine.set_wave_speed(payload.get("wave_speed", config.WAVE_SPEED_DEFAULT))
    return {"ok": True, "wave_speed": engine.wave_speed}


@app.get("/api/cap")
async def cap():
    return JSONResponse(engine.cap_alert())


@app.get("/api/device/siren")
async def device_siren(station: str = "ghat"):
    return {"station": station, "siren": engine.siren_on(), "beacon": engine.beacon_on()}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        await ws.send_text(json.dumps(engine.snapshot()))
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)


app.mount("/", StaticFiles(directory=str(config.DASHBOARD_DIR), html=True), name="dashboard")
