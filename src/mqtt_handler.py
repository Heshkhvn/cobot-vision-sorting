"""
MQTT Handler — Publish/Subscribe Wrapper for Cobot Sorting Cell

Wraps paho-mqtt with reconnection logic, QoS handling, and message buffering.
Falls back gracefully if MQTT broker is unavailable.

Author: Hesham Asim Khan
"""

import json
import time
import logging
from typing import Callable, Optional
from collections import deque

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

logger = logging.getLogger("MQTTHandler")


class MQTTHandler:
    """
    MQTT publish/subscribe handler with automatic reconnection
    and message buffering for reliability.
    """

    def __init__(self, broker: str = "localhost", port: int = 1883,
                 client_id: str = "cobot_sorting", buffer_size: int = 100):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.client: Optional[mqtt.Client] = None
        self._message_buffer = deque(maxlen=buffer_size)
        self._callbacks: dict = {}

        if not MQTT_AVAILABLE:
            logger.warning("paho-mqtt not installed. MQTT features disabled.")
            return

    def connect(self) -> bool:
        """Connect to MQTT broker. Returns True on success."""
        if not MQTT_AVAILABLE:
            return False

        try:
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            time.sleep(1)
            return self.connected
        except Exception as e:
            logger.error(f"Failed to connect to {self.broker}:{self.port}: {e}")
            return False

    def publish(self, topic: str, payload: dict, qos: int = 1) -> bool:
        """
        Publish a JSON message. Buffers if disconnected.
        """
        msg = json.dumps(payload, default=str)

        if self.client and self.connected:
            result = self.client.publish(topic, msg, qos=qos)
            return result.rc == 0
        else:
            self._message_buffer.append((topic, msg, qos))
            return False

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic with a callback function."""
        self._callbacks[topic] = callback
        if self.client and self.connected:
            self.client.subscribe(topic, qos=1)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker {self.broker}:{self.port}")
            # Resubscribe to all topics
            for topic in self._callbacks:
                client.subscribe(topic, qos=1)
            # Flush buffered messages
            self._flush_buffer()
        else:
            logger.warning(f"Connection failed: rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnect (rc={rc}). Will auto-reconnect.")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            payload = msg.payload.decode()

        if topic in self._callbacks:
            self._callbacks[topic](topic, payload)

    def _flush_buffer(self):
        """Publish any buffered messages."""
        flushed = 0
        while self._message_buffer and self.connected:
            topic, msg, qos = self._message_buffer.popleft()
            self.client.publish(topic, msg, qos=qos)
            flushed += 1
        if flushed > 0:
            logger.info(f"Flushed {flushed} buffered messages")

    def disconnect(self):
        """Clean disconnect."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self.connected = False
