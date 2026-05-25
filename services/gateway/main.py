import asyncio
import time

import httpx
from fastapi import FastAPI, HTTPException, Request

SERVICES = {
    "search":         "http://search:8050",
    "recommendation": "http://recommendation:8051",
    "payment":        "http://payment:8052",
    "auth":           "http://auth:8053",
}
METRICS_URL = "http://metrics_collector:8060"

app = FastAPI(title="API Gateway")


async def _report(service: str, latency_ms: float, status_code: int):
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{METRICS_URL}/metrics/request",
                json={
                    "service": service,
                    "latency_ms": latency_ms,
                    "status_code": status_code,
                    "timestamp": time.time(),
                },
                timeout=1.0,
            )
        except Exception:
            pass


async def _proxy(service: str, path: str, request: Request, method: str = "GET", timeout: float = 5.0):
    params = dict(request.query_params)
    start = time.time()
    async with httpx.AsyncClient() as client:
        try:
            if method == "POST":
                r = await client.post(f"{SERVICES[service]}{path}", params=params, timeout=timeout)
            else:
                r = await client.get(f"{SERVICES[service]}{path}", params=params, timeout=timeout)
            latency = (time.time() - start) * 1000
            asyncio.create_task(_report(service, latency, r.status_code))
            return r.json()
        except httpx.TimeoutException:
            asyncio.create_task(_report(service, timeout * 1000, 504))
            raise HTTPException(504, "upstream timeout")
        except Exception as e:
            asyncio.create_task(_report(service, 5000, 503))
            raise HTTPException(503, str(e))


@app.get("/health")
async def health():
    return {"status": "gateway-running"}


@app.get("/search")
async def fwd_search(request: Request):
    return await _proxy("search", "/search", request)


@app.get("/recommend")
async def fwd_recommend(request: Request):
    return await _proxy("recommendation", "/recommend", request)


@app.get("/pay")
async def fwd_pay(request: Request):
    return await _proxy("payment", "/pay", request, timeout=10.0)


@app.post("/auth/login")
async def fwd_login(request: Request):
    return await _proxy("auth", "/login", request, method="POST")


@app.get("/auth/verify")
async def fwd_verify(request: Request):
    return await _proxy("auth", "/verify", request)
