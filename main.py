"""
Main MQTT Application
=====================
"""
import multiprocessing as mp

from module.camera.camera_direct import CameraDirect
from mqtt import MQTTClient, VoiceMQTT, GPSMQTT
from log import setup_logger
from module.voice_speaker import VoiceSpeaker
from mcp_server.server import mcp
from config import TOPICS
from module.gps_manager import GPSManager
from module.gps import GPSService
logger = setup_logger(__name__)
from module.obstacle_detection import ObstacleDetectionSystem
from module.lane_segmentation import LaneSegmentation

def main():
    """Main application loop"""
    # Initialize MQTT client
    
    mqtt_client = MQTTClient()
    mqtt_client.connect()
    
    # # # # # # --- Chạy hệ thống phát hiện vật cản ---
    obstacle_system = ObstacleDetectionSystem()
    obstacle_system.run()
    
    speaker = VoiceSpeaker("USB Audio Device")

    # Initialize services
    voice = VoiceMQTT(mqtt_client)
    voice.start_continuous_listening()
    mqtt_client.handler.set_voice_mqtt(voice)
    
    logger.info("✅ VoiceMQTT linked to WebRTC - will pause during calls")
    
    camera = CameraDirect()
    
    # Lane Segmentation - Mặc định TẮT, bật qua MCP
    lane_segmentation = LaneSegmentation()
    # lane_segmentation.run()  # Không tự động chạy, dùng MCP để bật
    logger.info("📌 Lane Segmentation: TẮT (dùng MCP để bật)")
    
    # Obstacle Detection - Worker chạy (sensors sẵn sàng), nhưng detection TẮT
    # Để bật detection, dùng MCP tool start_obstacle_detection
    logger.info("📌 Obstacle Detection: sensors sẵn sàng, detection TẮT (dùng MCP để bật)")
    

    # # MQTT GPS publisher
    # gps = GPSMQTT(mqtt_client)
    # gps.publish_gps(qos=1)
    
    mcp.run(transport='sse')
    
    try:
        pass
        
    except KeyboardInterrupt as e:
        logger.error(f"Lỗi: {e}", exc_info=True)
        logger.info("Dừng hệ thống...")
    finally:
        obstacle_system.stop()
        camera.stop()
        voice.stop()
        mqtt_client.disconnect()
        lane_segmentation.stop()

if __name__ == "__main__":
    main()
