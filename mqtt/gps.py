import sys
import json
from pathlib import Path
import time
import threading

from mqtt.client import MQTTClient

# Import config từ root
sys.path.append(str(Path(__file__).parent.parent))
from config import TOPICS
from log import setup_logger
from module.gps import GPSService

logger = setup_logger(__name__)

class GPSMQTT:
    def __init__(self, mqtt_client : MQTTClient):
        """
        :param mqtt_client: Instance của class MQTTClient
        """
        self.mqtt = mqtt_client
        self.gps_service = GPSService()
        self.gps_service.run()
        
        # Thread control
        self.running = False
        self.publish_thread = None
        self.qos = 1

    def publish_gps(self, qos=1): 
        """
        Bắt đầu publish GPS trong thread riêng (không block main thread)
        :param qos: Quality of Service level (0, 1, hoặc 2)
        """
        if self.running:
            logger.warning("GPS publishing đã đang chạy")
            return
            
        self.qos = qos
        self.running = True
        self.publish_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.publish_thread.start()
        logger.info("✅ GPS publishing started in background thread")

    def _publish_loop(self):
        """Vòng lặp publish GPS trong thread riêng"""
        topic = TOPICS.get("device_gps")
        
        try:
            while self.running:
                lat, lng = self.gps_service.get_location()
                if lat and lng:
                    payload = {
                        "latitude": lat,
                        "longitude": lng
                    }
                    self.mqtt.publish(topic, payload, qos=self.qos, retain=True)
                    logger.info(f"📍 GPS published: {lat:.6f}, {lng:.6f}")
                else:
                    logger.debug("⏳ Waiting for GPS fix...")
                
                time.sleep(2)  # Publish mỗi 2 giây
        except Exception as e:
            logger.error(f"❌ Lỗi trong GPS publish loop: {e}", exc_info=True)
        finally:
            logger.info("🛑 GPS publishing stopped")

    def stop(self):
        """Dừng GPS publishing và cleanup"""
        if not self.running:
            return
            
        self.running = False
        if self.publish_thread:
            self.publish_thread.join(timeout=2.0)
        
        if self.gps_service:
            self.gps_service.cleanup()
        
        logger.info("✅ GPSMQTT stopped")
    
        