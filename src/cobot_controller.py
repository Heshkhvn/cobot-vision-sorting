"""
Cobot Controller Module — Trajectory Planning & MQTT Command Publishing

Receives detected parts from the vision system, computes pick/place
trajectory waypoints, and publishes sorting commands over MQTT.

When MQTT is not available, falls back to local logging mode.

Author: Hesham Asim Khan
"""

import json
import time
import math
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional

# Try importing paho-mqtt; fall back to local mode if not installed
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

from vision import DetectedPart

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CobotController")


# ── Cobot Configuration ──────────────────────────────────────────────

# Simulated cobot workspace (mm) — maps to pixel coordinates
WORKSPACE = {
    "x_min": 0, "x_max": 800,
    "y_min": 0, "y_max": 500,
    "z_safe": 150,      # safe travel height (mm)
    "z_pick": 5,         # pick height (mm)
    "z_place": 5,        # place height (mm)
}

# Place bins (where sorted parts go)
PLACE_BINS = {
    "accept": {"x": 700, "y": 100, "z": 5},
    "reject": {"x": 700, "y": 400, "z": 5},
}

# MQTT topics
TOPICS = {
    "command":   "cobot/sorting/command",
    "status":    "cobot/sorting/status",
    "telemetry": "cobot/sorting/telemetry",
    "vision":    "cobot/sorting/vision",
}


@dataclass
class Waypoint:
    """A single point in the cobot trajectory."""
    x: float
    y: float
    z: float
    speed: float = 100.0    # mm/s
    action: str = "move"    # "move", "pick", "place", "home"


@dataclass
class SortCommand:
    """Complete sorting command for one part."""
    part_id: int
    shape: str
    color: str
    accepted: bool
    pick_x: float
    pick_y: float
    place_bin: str
    waypoints: List[dict]
    cycle_time_ms: float
    timestamp: float


class CobotController:
    """
    Controls the cobot sorting cell.
    
    Pipeline:
    1. Receive detected parts from vision system
    2. Plan pick-and-place trajectory for each part
    3. Publish sorting commands over MQTT (or log locally)
    4. Track cycle times and sort statistics
    """

    def __init__(self, mqtt_broker: str = "localhost", mqtt_port: int = 1883):
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_client: Optional[mqtt.Client] = None
        self.connected = False

        # Statistics
        self.total_sorted = 0
        self.total_accepted = 0
        self.total_rejected = 0
        self.cycle_times: List[float] = []
        self.start_time = time.time()

        self._connect_mqtt()

    def _connect_mqtt(self):
        """Try to connect to MQTT broker. Fall back to local mode."""
        if not MQTT_AVAILABLE:
            logger.info("paho-mqtt not installed — running in local logging mode")
            return

        try:
            self.mqtt_client = mqtt.Client(client_id="cobot_controller")
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            time.sleep(1)
        except Exception as e:
            logger.warning(f"MQTT connection failed: {e} — running in local logging mode")
            self.mqtt_client = None

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            self._publish_status("online")
        else:
            logger.warning(f"MQTT connection failed with code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning("Disconnected from MQTT broker")

    def process_parts(self, parts: List[DetectedPart]) -> List[SortCommand]:
        """
        Process a list of detected parts: plan trajectories and publish commands.
        
        Args:
            parts: list of DetectedPart objects from vision system
            
        Returns:
            list of SortCommand objects (one per part)
        """
        commands = []

        # Publish vision detection results
        vision_msg = {
            "timestamp": time.time(),
            "parts_detected": len(parts),
            "parts": [
                {
                    "id": p.part_id,
                    "shape": p.shape,
                    "color": p.color,
                    "center": [p.center_x, p.center_y],
                    "confidence": round(p.confidence, 2),
                }
                for p in parts
            ],
        }
        self._publish(TOPICS["vision"], vision_msg)

        for part in parts:
            cycle_start = time.time()

            # Plan trajectory
            waypoints = self._plan_trajectory(part)

            # Simulate execution time based on trajectory distance
            exec_time = self._simulate_execution(waypoints)
            time.sleep(min(exec_time, 0.1))  # cap sleep for demo speed

            cycle_time = (time.time() - cycle_start) * 1000  # ms
            self.cycle_times.append(cycle_time)

            # Build sort command
            place_bin = "accept" if part.accepted else "reject"
            cmd = SortCommand(
                part_id=part.part_id,
                shape=part.shape,
                color=part.color,
                accepted=part.accepted,
                pick_x=float(part.center_x),
                pick_y=float(part.center_y),
                place_bin=place_bin,
                waypoints=[asdict(wp) for wp in waypoints],
                cycle_time_ms=round(cycle_time, 1),
                timestamp=time.time(),
            )
            commands.append(cmd)

            # Update stats
            self.total_sorted += 1
            if part.accepted:
                self.total_accepted += 1
            else:
                self.total_rejected += 1

            # Publish command
            self._publish(TOPICS["command"], asdict(cmd))

            status = "PICK → ACCEPT" if part.accepted else "PICK → REJECT"
            logger.info(
                f"Part #{part.part_id}: {part.color} {part.shape} → {status} "
                f"| pick=({part.center_x},{part.center_y}) | cycle={cycle_time:.0f}ms"
            )

        # Publish telemetry after processing batch
        self._publish_telemetry()
        return commands

    def _plan_trajectory(self, part: DetectedPart) -> List[Waypoint]:
        """
        Plan a pick-and-place trajectory for a single part.
        
        Trajectory: Home → Above Pick → Pick → Lift → Above Place → Place → Lift → Home
        """
        pick_x = float(part.center_x)
        pick_y = float(part.center_y)
        
        bin_name = "accept" if part.accepted else "reject"
        place = PLACE_BINS[bin_name]

        waypoints = [
            Waypoint(x=pick_x, y=pick_y, z=WORKSPACE["z_safe"],
                     speed=200, action="move"),
            Waypoint(x=pick_x, y=pick_y, z=WORKSPACE["z_pick"],
                     speed=50, action="move"),
            Waypoint(x=pick_x, y=pick_y, z=WORKSPACE["z_pick"],
                     speed=0, action="pick"),
            Waypoint(x=pick_x, y=pick_y, z=WORKSPACE["z_safe"],
                     speed=100, action="move"),
            Waypoint(x=place["x"], y=place["y"], z=WORKSPACE["z_safe"],
                     speed=200, action="move"),
            Waypoint(x=place["x"], y=place["y"], z=place["z"],
                     speed=50, action="move"),
            Waypoint(x=place["x"], y=place["y"], z=place["z"],
                     speed=0, action="place"),
            Waypoint(x=place["x"], y=place["y"], z=WORKSPACE["z_safe"],
                     speed=100, action="move"),
        ]
        return waypoints

    def _simulate_execution(self, waypoints: List[Waypoint]) -> float:
        """Calculate simulated execution time based on total travel distance."""
        total_dist = 0.0
        for i in range(1, len(waypoints)):
            dx = waypoints[i].x - waypoints[i-1].x
            dy = waypoints[i].y - waypoints[i-1].y
            dz = waypoints[i].z - waypoints[i-1].z
            total_dist += math.sqrt(dx*dx + dy*dy + dz*dz)

        avg_speed = 150.0  # mm/s
        return total_dist / avg_speed if avg_speed > 0 else 0

    def _publish(self, topic: str, payload: dict):
        """Publish a message to MQTT or log locally."""
        msg = json.dumps(payload, default=str)

        if self.mqtt_client and self.connected:
            self.mqtt_client.publish(topic, msg, qos=1)
        else:
            logger.debug(f"[LOCAL] {topic}: {msg[:120]}...")

    def _publish_status(self, status: str):
        """Publish cobot status."""
        self._publish(TOPICS["status"], {
            "status": status,
            "timestamp": time.time(),
        })

    def _publish_telemetry(self):
        """Publish current statistics as telemetry."""
        avg_cycle = sum(self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0
        uptime = time.time() - self.start_time
        reject_rate = (self.total_rejected / self.total_sorted * 100) if self.total_sorted > 0 else 0

        telemetry = {
            "timestamp": time.time(),
            "total_sorted": self.total_sorted,
            "total_accepted": self.total_accepted,
            "total_rejected": self.total_rejected,
            "reject_rate_pct": round(reject_rate, 1),
            "avg_cycle_time_ms": round(avg_cycle, 1),
            "last_cycle_time_ms": round(self.cycle_times[-1], 1) if self.cycle_times else 0,
            "uptime_seconds": round(uptime, 1),
        }
        self._publish(TOPICS["telemetry"], telemetry)

    def get_stats(self) -> dict:
        """Return current sorting statistics."""
        avg_cycle = sum(self.cycle_times) / len(self.cycle_times) if self.cycle_times else 0
        reject_rate = (self.total_rejected / self.total_sorted * 100) if self.total_sorted > 0 else 0

        return {
            "total_sorted": self.total_sorted,
            "accepted": self.total_accepted,
            "rejected": self.total_rejected,
            "reject_rate": round(reject_rate, 1),
            "avg_cycle_time_ms": round(avg_cycle, 1),
            "uptime_s": round(time.time() - self.start_time, 1),
        }

    def shutdown(self):
        """Clean shutdown."""
        self._publish_status("offline")
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info("Cobot controller shut down.")
