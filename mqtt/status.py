"""
Device Status
=============
"""

import time
from config import *
from container import container
from module.gps import GPSService


class DeviceStatus:
    """Device status and heartbeat management"""

    def __init__(self, mqtt_client=None):
        self.mqtt_client = mqtt_client

    def set_mqtt_client(self, mqtt_client):
        """Set MQTT client for publishing status"""
        self.mqtt_client = mqtt_client

    def publish_info(self):
        """Publish device information and status"""
        if not self.mqtt_client:
            return

        # Get GPS location
        gps_service: GPSService = container.get("gps")
        # lat, lng = self.gps_service.get_location()
        lat, lng = gps_service.mock_gps()

        info = {
            "deviceId": DEVICE_ID,
            "ts": int(time.time() * 1000),
            "battery": 0.85,  # Battery level (0.0-1.0)
            "gps": {
                "lat": lat,
                "lng": lng,
                "acc": 6  # GPS accuracy in meters
            },
        }

        self.mqtt_client.publish(
            TOPICS['device_info'], info, qos=1, retain=True)
        print("Published device info")

    def publish_ping(self):
        """Publish ping to server"""
        if not self.mqtt_client:
            return

        payload = {
            "deviceId": DEVICE_ID,
            "ts": int(time.time() * 1000),
            "data": "PING"
        }

        self.mqtt_client.publish(TOPICS['device_ping'], payload, qos=2)
        print("Published ping to server")
