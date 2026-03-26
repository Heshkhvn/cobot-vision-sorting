"""
HMI Operator Dashboard — Streamlit-based Cobot Sorting Interface

Production-floor style HMI with:
- Live vision camera feed with detection overlays
- Real-time sort counts, cycle times, reject rates
- Start / Stop / Pause controls
- Part history log

Usage:
    streamlit run dashboard.py

Author: Hesham Asim Khan
"""

import os
import sys
import time
import json

import streamlit as st
import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vision import VisionSystem
from generate_test_images import generate_conveyor_image

# ── Page Config ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="Cobot Vision Sorting — HMI",
    page_icon="🤖",
    layout="wide",
)

# ── Custom CSS for HMI look ──────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background-color: #1a1a2e; }
    .metric-card {
        background: #16213e;
        border: 1px solid #0f3460;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        margin: 4px;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #e94560;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #a0a0b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .status-online { color: #00ff88; font-weight: 700; }
    .status-paused { color: #ffaa00; font-weight: 700; }
    .status-offline { color: #ff4444; font-weight: 700; }
    .log-entry { font-family: monospace; font-size: 0.8rem; color: #c0c0d0; }
</style>
""", unsafe_allow_html=True)


# ── Session State Init ───────────────────────────────────────────────

if "vision" not in st.session_state:
    st.session_state.vision = VisionSystem(min_area=400, max_area=50000)
if "running" not in st.session_state:
    st.session_state.running = False
if "paused" not in st.session_state:
    st.session_state.paused = False
if "frame_idx" not in st.session_state:
    st.session_state.frame_idx = 0
if "total_sorted" not in st.session_state:
    st.session_state.total_sorted = 0
if "total_accepted" not in st.session_state:
    st.session_state.total_accepted = 0
if "total_rejected" not in st.session_state:
    st.session_state.total_rejected = 0
if "cycle_times" not in st.session_state:
    st.session_state.cycle_times = []
if "log" not in st.session_state:
    st.session_state.log = []
if "start_time" not in st.session_state:
    st.session_state.start_time = None


# ── Helper Functions ─────────────────────────────────────────────────

def metric_card(label, value, color="#e94560"):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:{color}">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def process_next_frame():
    """Generate and process one conveyor frame."""
    s = st.session_state
    s.frame_idx += 1

    frame, _ = generate_conveyor_image(num_parts=6, seed=200 + s.frame_idx)
    t0 = time.time()
    parts = s.vision.process_frame(frame)
    detect_ms = (time.time() - t0) * 1000

    for part in parts:
        import math
        bin_y = 100 if part.accepted else 400
        dist = math.sqrt((700 - part.center_x)**2 + (bin_y - part.center_y)**2)
        cycle_ms = (dist / 500) * 1000

        s.total_sorted += 1
        if part.accepted:
            s.total_accepted += 1
        else:
            s.total_rejected += 1
        s.cycle_times.append(cycle_ms)

        status = "PICK" if part.accepted else "REJECT"
        log_entry = (
            f"[{time.strftime('%H:%M:%S')}] Part #{part.part_id}: "
            f"{part.color} {part.shape} → {status} "
            f"({part.center_x},{part.center_y}) | {cycle_ms:.0f}ms"
        )
        s.log.insert(0, log_entry)

    # Keep log to last 50 entries
    s.log = s.log[:50]

    annotated = s.vision.draw_detections(frame, parts)
    return annotated, parts, detect_ms


# ── Layout ───────────────────────────────────────────────────────────

st.markdown("## 🤖 Cobot Vision Sorting Cell — HMI Dashboard")

# Controls row
col_start, col_pause, col_stop, col_reset, col_status = st.columns([1, 1, 1, 1, 2])

with col_start:
    if st.button("▶ START", use_container_width=True, type="primary"):
        st.session_state.running = True
        st.session_state.paused = False
        if st.session_state.start_time is None:
            st.session_state.start_time = time.time()

with col_pause:
    if st.button("⏸ PAUSE", use_container_width=True):
        st.session_state.paused = not st.session_state.paused

with col_stop:
    if st.button("⏹ STOP", use_container_width=True):
        st.session_state.running = False
        st.session_state.paused = False

with col_reset:
    if st.button("🔄 RESET", use_container_width=True):
        st.session_state.running = False
        st.session_state.paused = False
        st.session_state.frame_idx = 0
        st.session_state.total_sorted = 0
        st.session_state.total_accepted = 0
        st.session_state.total_rejected = 0
        st.session_state.cycle_times = []
        st.session_state.log = []
        st.session_state.start_time = None
        st.session_state.vision.reset_counter()

with col_status:
    s = st.session_state
    if s.running and not s.paused:
        st.markdown('<p class="status-online">● SYSTEM RUNNING</p>', unsafe_allow_html=True)
    elif s.running and s.paused:
        st.markdown('<p class="status-paused">● PAUSED</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-offline">● STOPPED</p>', unsafe_allow_html=True)

st.markdown("---")

# Main content: camera feed + metrics
cam_col, stats_col = st.columns([2, 1])

with cam_col:
    st.markdown("### Vision Camera Feed")
    camera_placeholder = st.empty()

    if st.session_state.running and not st.session_state.paused:
        annotated, parts, detect_ms = process_next_frame()
        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        camera_placeholder.image(rgb, use_container_width=True,
                                 caption=f"Frame #{st.session_state.frame_idx} | "
                                         f"{len(parts)} parts detected | "
                                         f"{detect_ms:.1f}ms detection time")
    else:
        # Show a blank conveyor
        blank, _ = generate_conveyor_image(num_parts=0, seed=0)
        rgb = cv2.cvtColor(blank, cv2.COLOR_BGR2RGB)
        camera_placeholder.image(rgb, use_container_width=True,
                                 caption="Camera feed — press START to begin sorting")

with stats_col:
    st.markdown("### Sorting Metrics")
    s = st.session_state

    reject_rate = (s.total_rejected / s.total_sorted * 100) if s.total_sorted > 0 else 0
    avg_cycle = sum(s.cycle_times) / len(s.cycle_times) if s.cycle_times else 0
    uptime = time.time() - s.start_time if s.start_time else 0

    metric_card("Total Sorted", s.total_sorted, "#00d4ff")
    metric_card("Accepted", s.total_accepted, "#00ff88")
    metric_card("Rejected", s.total_rejected, "#ff4444")
    metric_card("Reject Rate", f"{reject_rate:.1f}%", "#ffaa00")
    metric_card("Avg Cycle Time", f"{avg_cycle:.0f}ms", "#e94560")
    metric_card("Uptime", f"{uptime:.0f}s", "#a0a0ff")

# Event log
st.markdown("---")
st.markdown("### Event Log")
log_container = st.container(height=250)
with log_container:
    if st.session_state.log:
        for entry in st.session_state.log[:20]:
            st.markdown(f'<p class="log-entry">{entry}</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="log-entry">No events yet — press START to begin.</p>',
                    unsafe_allow_html=True)

# Auto-refresh when running
if st.session_state.running and not st.session_state.paused:
    time.sleep(0.5)
    st.rerun()
