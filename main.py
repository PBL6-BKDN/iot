"""
Main MQTT Application
=====================
"""
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
    
    # Link VoiceMQTT với WebRTC Manager để có thể pause/resume khi có cuộc gọi
    mqtt_client.handler.set_voice_mqtt(voice)
    logger.info("✅ VoiceMQTT linked to WebRTC - will pause during calls")
    
    camera = CameraDirect()
    lane_segmentation = LaneSegmentation()
    lane_segmentation.run()
    # status = DeviceStatus(mqtt_client)
    

    # MQTT GPS publisher
    gps = GPSMQTT(mqtt_client)
    gps.publish_gps(qos=1)
    
    mcp.run(transport='sse')
    # mqtt_client.publish(TOPICS['device_ping'], {"data": "PING"})
    
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
