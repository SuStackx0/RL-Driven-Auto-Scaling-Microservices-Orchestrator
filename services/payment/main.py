from fastapi import FastAPI, Query
import random
import time
import math

app = FastAPI(title="payment-service")

# CPU-heavy fraud check simulation
def fraud_check(amount: float):
    score = 0
    for i in range(int(amount) * 5000):
        score += (i % 7) * random.random()
    return score

@app.get("/pay")
def process_payment(
    user_id: int = Query(...),
    amount: float = Query(..., gt=0)
):
    # 10% chance of failure
    if random.random() < 0.10:
        return {"status": "failed", "reason": "payment_gateway_error"}

    # Simulated I/O latency (external API)
    external_latency = random.uniform(0.05, 0.25)
    time.sleep(external_latency)

    # Fraud score (CPU heavy)
    fraud_score = fraud_check(amount)
    risk_flag = fraud_score % 5 < 0.5  # random-ish rule

    # 5% chance of timeout-like delay
    if random.random() < 0.05:
        time.sleep(0.5)

    return {
        "user_id": user_id,
        "amount": amount,
        "fraud_risk": "high" if risk_flag else "low",
        "latency_ms": round(external_latency * 1000, 2),
        "status": "success"
    }
