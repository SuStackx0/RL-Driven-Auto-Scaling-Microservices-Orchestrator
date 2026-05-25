import time

import plotly.graph_objects as go
import requests
import streamlit as st

METRICS_URL = "http://metrics_collector:8060"
AGENT_URL   = "http://rl_agent:8070"
LOAD_URL    = "http://load_simulator:8080"

SERVICES = ["search", "recommendation", "payment", "auth"]
COLORS   = {"search": "#636EFA", "recommendation": "#EF553B",
            "payment": "#00CC96",  "auth": "#AB63FA"}

st.set_page_config(
    page_title="RL Auto-Scaler",
    page_icon="robot",
    layout="wide",
)

st.title("RL-Driven Auto-Scaling Orchestrator")
st.caption("Live view — refreshes every 3 seconds")

# ── Session state ──────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # list of {time, search:{...}, ...}


# ── Data fetchers ──────────────────────────────────────────────────────────
def fetch_state():
    try:
        return requests.get(f"{METRICS_URL}/state", timeout=2).json()
    except Exception:
        return {}


def fetch_decisions():
    try:
        return requests.get(f"{AGENT_URL}/decisions", timeout=2).json()
    except Exception:
        return []


def agent_ready():
    try:
        return requests.get(f"{AGENT_URL}/health", timeout=1).json().get("model_ready", False)
    except Exception:
        return False


# ── Fetch current data ─────────────────────────────────────────────────────
state     = fetch_state()
decisions = fetch_decisions()

if state:
    entry = {"time": time.strftime("%H:%M:%S")}
    entry.update(state)
    st.session_state.history.append(entry)
    if len(st.session_state.history) > 60:
        st.session_state.history = st.session_state.history[-60:]

history = st.session_state.history

# ── Agent status banner ────────────────────────────────────────────────────
if agent_ready():
    st.success("RL agent is active and making scaling decisions.")
else:
    st.warning("RL agent is training or unavailable — decisions will appear shortly.")

st.divider()

# ── Service cards ──────────────────────────────────────────────────────────
st.subheader("Service Status")
cols = st.columns(4)
for col, svc in zip(cols, SERVICES):
    d        = state.get(svc, {})
    replicas = d.get("instances", 1)
    avg_lat  = d.get("avg_latency_ms", 0.0)
    err      = d.get("error_rate",    0.0)
    rps      = d.get("rps",          0.0)
    with col:
        st.metric(label=f"**{svc.upper()}**",
                  value=f"{replicas} replica{'s' if replicas != 1 else ''}",
                  delta=f"{avg_lat:.0f} ms avg lat")
        st.caption(f"RPS: {rps:.1f}  |  Errors: {err:.1%}")

st.divider()

# ── Charts ─────────────────────────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    st.subheader("Avg Latency (ms)")
    fig = go.Figure()
    for svc in SERVICES:
        y = [h.get(svc, {}).get("avg_latency_ms", 0) for h in history]
        x = [h["time"] for h in history]
        fig.add_trace(go.Scatter(x=x, y=y, name=svc, mode="lines",
                                 line=dict(color=COLORS[svc], width=2)))
    fig.update_layout(height=280, margin=dict(t=10, b=30, l=40, r=10),
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, use_container_width=True)

with c2:
    st.subheader("Replica Count")
    fig = go.Figure()
    for svc in SERVICES:
        y = [h.get(svc, {}).get("instances", 1) for h in history]
        x = [h["time"] for h in history]
        fig.add_trace(go.Scatter(x=x, y=y, name=svc, mode="lines+markers",
                                 line=dict(color=COLORS[svc], width=2),
                                 marker=dict(size=4)))
    fig.update_layout(height=280, margin=dict(t=10, b=30, l=40, r=10),
                      yaxis=dict(dtick=1, range=[0, 6]),
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, use_container_width=True)

c3, c4 = st.columns(2)

with c3:
    st.subheader("RPS")
    fig = go.Figure()
    for svc in SERVICES:
        y = [h.get(svc, {}).get("rps", 0) for h in history]
        x = [h["time"] for h in history]
        fig.add_trace(go.Scatter(x=x, y=y, name=svc, mode="lines",
                                 line=dict(color=COLORS[svc], width=2)))
    fig.update_layout(height=250, margin=dict(t=10, b=30, l=40, r=10),
                      legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, use_container_width=True)

with c4:
    st.subheader("Error Rate")
    fig = go.Figure()
    for svc in SERVICES:
        y = [h.get(svc, {}).get("error_rate", 0) * 100 for h in history]
        x = [h["time"] for h in history]
        fig.add_trace(go.Scatter(x=x, y=y, name=svc, mode="lines",
                                 line=dict(color=COLORS[svc], width=2)))
    fig.update_layout(height=250, margin=dict(t=10, b=30, l=40, r=10),
                      yaxis_ticksuffix="%",
                      legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── RL Decisions log ───────────────────────────────────────────────────────
st.subheader("RL Agent Decisions")
if decisions:
    for d in decisions[:15]:
        ts   = d.get("timestamp", "")[:19].replace("T", " ")
        acts = d.get("decisions", {})
        parts = []
        for svc, info in acts.items():
            a    = info.get("action", "")
            bef  = info.get("instances_before", "?")
            aft  = info.get("instances_after",  "?")
            icon = "⬆" if a == "scale_up" else "⬇"
            parts.append(f"{icon} **{svc}** {bef}→{aft}")
        st.markdown(f"`{ts}` &nbsp; " + "  &nbsp;|&nbsp;  ".join(parts))
else:
    st.info("No scaling decisions yet. Start the load simulator to trigger activity.")

st.divider()

# ── Load simulator controls ────────────────────────────────────────────────
st.subheader("Load Simulator")
b1, b2, b3 = st.columns(3)

with b1:
    if st.button("▶  Normal load (5 RPS)", use_container_width=True):
        try:
            requests.post(f"{LOAD_URL}/simulate/start",
                          json={"mode": "normal", "rps": 5}, timeout=2)
            st.success("Normal load started.")
        except Exception:
            st.error("Load simulator unavailable.")

with b2:
    if st.button("💥  Burst load (20 RPS)", use_container_width=True):
        try:
            requests.post(f"{LOAD_URL}/simulate/start",
                          json={"mode": "burst", "rps": 20}, timeout=2)
            st.success("Burst load started!")
        except Exception:
            st.error("Load simulator unavailable.")

with b3:
    if st.button("⏹  Stop load", use_container_width=True):
        try:
            requests.post(f"{LOAD_URL}/simulate/stop", timeout=2)
            st.success("Load stopped.")
        except Exception:
            st.error("Load simulator unavailable.")

# ── Auto-refresh ───────────────────────────────────────────────────────────
time.sleep(3)
st.rerun()
