"""
Traffic load simulator.

POST /simulate/start  {"mode": "normal"|"burst", "rps": <int>}
POST /simulate/stop
GET  /simulate/status
GET  /health
"""

import asyncio
import os
import random

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:8040")

app = FastAPI(title="Load Simulator")

_state: dict = {"running": False, "mode": "normal", "rps": 5}
_task:  asyncio.Task | None = None

REQUESTS = [
    ("GET",  "/search",       {"query": "laptop"}),
    ("GET",  "/search",       {"query": "wireless headphones"}),
    ("GET",  "/search",       {"query": "running shoes"}),
    ("GET",  "/recommend",    {"user_id": 1}),
    ("GET",  "/recommend",    {"user_id": 42}),
    ("GET",  "/pay",          {"user_id": 7,  "amount": 49.99}),
    ("GET",  "/pay",          {"user_id": 99, "amount": 199.00}),
    ("POST", "/auth/login",   {"username": "alice", "password": "password123"}),
    ("POST", "/auth/login",   {"username": "bob",   "password": "mypassword"}),
]


async def _send_one(client: httpx.AsyncClient):
    method, path, params = random.choice(REQUESTS)
    try:
        if method == "POST":
            await client.post(path, params=params, timeout=5.0)
        else:
            await client.get(path,  params=params, timeout=5.0)
    except Exception:
        pass


async def _loop():
    async with httpx.AsyncClient(base_url=GATEWAY_URL) as client:
        while _state["running"]:
            delay = 1.0 / max(_state["rps"], 0.1)

            # Burst mode: occasionally fire several requests in quick succession
            if _state["mode"] == "burst" and random.random() < 0.12:
                tasks = [asyncio.create_task(_send_one(client)) for _ in range(5)]
                await asyncio.gather(*tasks, return_exceptions=True)
                delay *= 0.3

            else:
                await _send_one(client)

            await asyncio.sleep(delay)


class SimConfig(BaseModel):
    mode: str = "normal"
    rps:  int = 5


@app.post("/simulate/start")
async def start(cfg: SimConfig):
    global _task
    _state["running"] = True
    _state["mode"]    = cfg.mode
    _state["rps"]     = cfg.rps

    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())

    return {"status": "started", "mode": cfg.mode, "rps": cfg.rps}


@app.post("/simulate/stop")
async def stop():
    _state["running"] = False
    return {"status": "stopped"}


@app.get("/simulate/status")
def status():
    return _state


@app.get("/health")
def health():
    return {"status": "load-simulator-running"}
