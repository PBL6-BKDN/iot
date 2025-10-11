"""
Obstacle Detection
==================
"""

import time
from config import *


class ObstacleDetector:
    """Obstacle detection and MQTT publishing"""
    
    def __init__(self, mqtt_client=None):
        self.mqtt_client = mqtt_client
    
    def set_mqtt_client(self, mqtt_client):
        """Set MQTT client for publishing alerts"""
        self.mqtt_client = mqtt_client
    
    def publish_obstacle(self, distance_m: float, severity: str):
        """Publish obstacle detection alert to server"""
        if not self.mqtt_client:
            return
        
        payload = {
            "deviceId": DEVICE_ID,
            "ts": int(time.time() * 1000),
            "distance": round(distance_m, 2),
            "unit": "m",
            "class": "unknown",
            "detectedObjects": [],
            "severity": severity
        }
        
        self.mqtt_client.publish(TOPICS['device_obstacle'], payload, qos=1)
        print(f"Published obstacle alert: {distance_m}m ({severity})")