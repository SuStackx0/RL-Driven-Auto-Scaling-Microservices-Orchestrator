from fastapi import FastAPI, Query, HTTPException
import time
import random
import bcrypt
import jwt
import datetime

app = FastAPI(title="auth-service")

SECRET = "SUPER_SECRET_KEY_SHOULD_BE_IN_ENV"

# Simulated user DB
FAKE_USER_DB = {
    "alice": bcrypt.hashpw(b"password123", bcrypt.gensalt()),
    "bob": bcrypt.hashpw(b"mypassword", bcrypt.gensalt())
}

@app.post("/login")
def login(username: str = Query(...), password: str = Query(...)):
    # 5% chance of throttling
    if random.random() < 0.05:
        raise HTTPException(status_code=429, detail="Too many requests")

    # 2–4% internal error
    if random.random() < 0.04:
        raise HTTPException(status_code=500, detail="auth internal error")

    # Simulate password hashing verify (CPU heavy)
    stored = FAKE_USER_DB.get(username)
    if not stored or not bcrypt.checkpw(password.encode(), stored):
        raise HTTPException(status_code=401, detail="invalid credentials")

    # Make a JWT
    payload = {
        "user": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")

    return {"token": token, "status": "success"}

@app.get("/verify")
def verify(token: str = Query(...)):
    try:
        decoded = jwt.decode(token, SECRET, algorithms=["HS256"])
        return {"valid": True, "user": decoded["user"]}
    except Exception:
        return {"valid": False}
