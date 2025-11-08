"""
Main MQTT Application
=====================
"""

import time
from module.camera.camera_direct import CameraDirect
from module.lane_segmentation import LaneSegmentation
from mqtt import MQTTClient, VoiceMQTT, CameraCapture, ObstacleDetector, DeviceStatus
from log import setup_logger
from container import container
from module.voice_speaker import VoiceSpeaker
from module.obstacle_detection import ObstacleDetectionSystem
from mcp_server.server import mcp
from config import TOPICS
logger = setup_logger(__name__)


def main():
    """Main application loop"""
    # Initialize MQTT client
    mqtt_client = MQTTClient()
    mqtt_client.connect()
    
    # # --- Chạy hệ thống phát hiện vật cản ---
    obstacle_system = ObstacleDetectionSystem()
    obstacle_system.run()
    
    speaker = VoiceSpeaker("USB Audio Device")

    # Initialize services
    voice = VoiceMQTT(mqtt_client)
    voice.start_continuous_listening()
    
    camera = CameraDirect()
    # obstacle = ObstacleDetector(mqtt_client)
    lane_segmentation = LaneSegmentation()
    lane_segmentation.run()
    # status = DeviceStatus(mqtt_client)
    
    mcp.run(transport='sse')
    
    mqtt_client.publish(TOPICS['device_ping'], {"data": "PING"})
    
    # Publish initial device info
    print("Device started. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt as e:
        logger.error(f"Lỗi: {e}", exc_info=True)
        logger.info("Dừng hệ thống...")
        obstacle_system.stop()
        camera.stop()
        voice.stop()
        mqtt_client.disconnect()
        lane_segmentation.stop()

if __name__ == "__main__":
    main()
