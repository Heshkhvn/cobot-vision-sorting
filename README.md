# Cobot Vision Sorting Simulator

**[▶ Live Demo on Streamlit Cloud](https://cobot-vision-sorting.streamlit.app)**

# Cobot Vision Sorting Simulator

A Python-based cobot pick-and-place simulator with OpenCV vision processing, MQTT command publishing, and a Streamlit HMI-style operator dashboard.

## What This Does

Simulates a real production-floor cobot sorting cell:

1. **Vision System** — OpenCV processes a camera feed (or test images) to detect and classify parts by shape and color
2. **Cobot Controller** — Computes pick/place coordinates and trajectory waypoints for each detected part, then publishes sorting commands over MQTT
3. **HMI Dashboard** — Streamlit-based operator interface showing real-time sort counts, cycle times, reject rates, and vision camera status with start/stop/pause controls

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│  Vision       │────▶│  Cobot Controller │────▶│  MQTT Broker   │
│  (OpenCV)     │     │  (Trajectory Plan) │     │  (Mosquitto)   │
└──────────────┘     └──────────────────┘     └───────┬───────┘
                                                       │
                                                       ▼
                                              ┌───────────────┐
                                              │  HMI Dashboard │
                                              │  (Streamlit)   │
                                              └───────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate test images (colored shapes on a conveyor background)
python src/generate_test_images.py

# 3. Run standalone demo (no MQTT/Streamlit needed)
python src/demo.py

# 4. Run with MQTT (requires Mosquitto broker running)
mosquitto &
python src/cobot_controller.py

# 5. Run full system with HMI dashboard
mosquitto &
streamlit run src/dashboard.py
```

## Project Structure

```
cobot-vision-sorting/
├── README.md
├── requirements.txt
├── src/
│   ├── vision.py              # OpenCV part detection and classification
│   ├── cobot_controller.py    # Trajectory planning + MQTT command publishing
│   ├── mqtt_handler.py        # MQTT publish/subscribe wrapper
│   ├── dashboard.py           # Streamlit HMI operator dashboard
│   ├── generate_test_images.py # Creates test part images
│   └── demo.py                # Standalone demo (no external deps)
├── test_images/               # Generated test conveyor images
└── docs/
    └── system_design.md       # System design documentation
```

## Demo Results
<img width="800" height="500" alt="demo_result_01" src="https://github.com/user-attachments/assets/ad024f91-f633-4c0b-9f88-9b06ae3acda6" />
<img width="800" height="500" alt="demo_result_03" src="https://github.com/user-attachments/assets/3e644f93-8ca7-4349-be6a-c987e5a2f979" />


## Tech Stack

- **Python 3.10+**
- **OpenCV** — contour detection, HSV color masking, shape classification
- **paho-mqtt** — MQTT publish/subscribe for cobot commands
- **Streamlit** — HMI-style operator dashboard
- **Mosquitto** — MQTT broker (lightweight, local)

## Author
Hesham Asim Khan — [Portfolio](https://heshkhvn.github.io/hesham-khan.github.io/) · [LinkedIn](https://linkedin.com/in/hesham-khan) · [Live Demo](https://cobot-vision-sorting.streamlit.app)
