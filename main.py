"""
Main MQTT Application
=====================
"""

import time
from mqtt import MQTTClient, VoiceMQTT, CameraCapture, ObstacleDetector, DeviceStatus
from log import setup_logger

logger = setup_logger(__name__)


def main():
    """Main application loop"""
    # Initialize MQTT client
    mqtt_client = MQTTClient()

    # Initialize services
    voice = VoiceMQTT(mqtt_client)
    voice.start_continuous_listening()
    camera = CameraCapture()
    obstacle = ObstacleDetector(mqtt_client)
    status = DeviceStatus(mqtt_client)

    # Connect to MQTT broker
    mqtt_client.connect()

    # Publish initial device info
    print("Device started. Press Ctrl+C to exit.")
    try:
        pass
    except KeyboardInterrupt:
        print("\nShutting down device...")
        voice.stop_continuous_listening()
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()
