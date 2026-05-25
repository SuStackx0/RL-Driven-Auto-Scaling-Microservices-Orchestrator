"""
RL Agent service.

On startup:
  1. If models/scaling_policy.zip exists, load it.
  2. Otherwise, train a new PPO model (takes ~2–3 min on CPU).
  3. Start the inference loop (polls metrics every POLL_INTERVAL seconds).

Exposes:
  GET /decisions  – last 100 scaling decisions
  GET /health
"""

import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import numpy as np
import requests
from fastapi import FastAPI

from env import N_SERVICES, SERVICES, TARGET_LATENCY

METRICS_URL   = os.getenv("METRICS_URL",   "http://metrics_collector:8060")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))
MODEL_PATH    = "models/scaling_policy"

decisions_log: deque = deque(maxlen=100)
_model        = None
_model_ready  = threading.Event()

ACTION_NAMES = {0: "scale_down", 1: "keep", 2: "scale_up"}


# ---------------------------------------------------------------------------
# Model loading / training
# ---------------------------------------------------------------------------

def _load_or_train():
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env
    from env import ScalingEnv

    global _model
    if os.path.exists(f"{MODEL_PATH}.zip"):
        print("[agent] Loading existing model...")
        _model = PPO.load(MODEL_PATH)
    else:
        print("[agent] No model found — training from scratch (50 k steps)...")
        env = make_vec_env(ScalingEnv, n_envs=4)
        _model = PPO(
            "MlpPolicy", env,
            learning_rate=3e-4, n_steps=512, batch_size=64,
            n_epochs=10, gamma=0.99, verbose=1,
        )
        _model.learn(total_timesteps=50_000, progress_bar=True)
        os.makedirs("models", exist_ok=True)
        _model.save(MODEL_PATH)
        print(f"[agent] Model saved → {MODEL_PATH}.zip")

    _model_ready.set()
    print("[agent] Model ready. Starting inference loop.")


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

_DEFAULT_LATENCY = [50.0, 30.0, 150.0, 80.0]


def _state_to_obs(raw: dict) -> np.ndarray:
    obs = []
    for i, svc in enumerate(SERVICES):
        d       = raw.get(svc, {})
        avg_lat = d.get("avg_latency_ms", _DEFAULT_LATENCY[i])
        p95_lat = d.get("p95_latency_ms", avg_lat * 1.3)
        err     = d.get("error_rate",     0.0)
        rps     = d.get("rps",            1.0)
        inst    = d.get("instances",      1)
        obs += [
            min(avg_lat / (TARGET_LATENCY[i] * 3), 1.0),
            min(p95_lat / (TARGET_LATENCY[i] * 3), 1.0),
            min(err,   1.0),
            min(rps / 30.0, 1.0),
            (inst - 1) / 4.0,
        ]
    return np.array(obs, dtype=np.float32)


# ---------------------------------------------------------------------------
# Inference loop
# ---------------------------------------------------------------------------

def _run_loop():
    _model_ready.wait()
    print("[agent] Inference loop started.")

    while True:
        try:
            resp = requests.get(f"{METRICS_URL}/state", timeout=3)
            raw  = resp.json()
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue

        if not raw:
            time.sleep(POLL_INTERVAL)
            continue

        obs         = _state_to_obs(raw)
        action, _   = _model.predict(obs, deterministic=True)

        scaled = {}
        for i, svc in enumerate(SERVICES):
            a        = int(action[i])
            cur_inst = raw.get(svc, {}).get("instances", 1)

            if a == 0:
                new_inst = max(1, cur_inst - 1)
            elif a == 2:
                new_inst = min(5, cur_inst + 1)
            else:
                continue

            if new_inst != cur_inst:
                try:
                    requests.post(
                        f"{METRICS_URL}/metrics/instances",
                        json={"service": svc, "instance_count": new_inst},
                        timeout=2,
                    )
                    scaled[svc] = {
                        "action":           ACTION_NAMES[a],
                        "instances_before": cur_inst,
                        "instances_after":  new_inst,
                    }
                except Exception:
                    pass

        if scaled:
            decisions_log.appendleft({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decisions": scaled,
            })

        time.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_load_or_train,  daemon=True).start()
    threading.Thread(target=_run_loop,        daemon=True).start()
    yield


app = FastAPI(title="RL Scaling Agent", lifespan=lifespan)


@app.get("/decisions")
def get_decisions():
    return list(decisions_log)


@app.get("/health")
def health():
    return {"status": "rl-agent-running", "model_ready": _model_ready.is_set()}
