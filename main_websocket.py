"""
Main WebSocket Application
===========================
Entry point for WebSocket-based video/audio streaming
"""

import threading
import asyncio
from module.camera.camera_direct import CameraDirect
from mqtt import MQTTClient, VoiceMQTT, GPSMQTT
from mqtt.handlers_websocket import MessageHandlerWebSocket
from mqtt.websocket_manager import WebSocketManager
from log import setup_logger
from module.voice_speaker import VoiceSpeaker
from mcp_server.server import mcp
from config import TOPICS, DEVICE_ID
from module.gps_manager import GPSManager
from module.gps import GPSService
from container import container

logger = setup_logger(__name__)


def run_websocket_server(ws_manager):
    """Run WebSocket server in separate thread"""
    try:
        logger.info("🚀 Starting WebSocket server thread...")
        ws_manager.run()
    except Exception as e:
        logger.error(f"❌ WebSocket server error: {e}", exc_info=True)


def main():
    """Main application loop"""
    # Initialize camera
    camera = CameraDirect()
    logger.info("✅ Camera initialized")
    
    # Initialize speaker
    speaker = VoiceSpeaker("USB Audio Device")
    logger.info("✅ Speaker initialized")
    
    # Initialize WebSocket manager
    ws_manager = WebSocketManager(host="0.0.0.0", port=8765)
    logger.info("✅ WebSocket manager initialized")
    
    # Initialize MQTT client with WebSocket handlers
    mqtt_client = MQTTClient()
    
    # Create message handler with WebSocket manager
    handler = MessageHandlerWebSocket(mqtt_client, ws_manager)
    mqtt_client.handler = handler
    
    # Connect MQTT
    mqtt_client.connect()
    logger.info("✅ MQTT connected")
    
    # Initialize VoiceMQTT
    voice = VoiceMQTT(mqtt_client)
    voice.start_continuous_listening()
    logger.info("✅ VoiceMQTT started")
    
    # Link VoiceMQTT with handler to pause/resume during calls
    handler.set_voice_mqtt(voice)
    logger.info("✅ VoiceMQTT linked to handler - will pause during calls")
    
    # Start WebSocket server in separate thread
    ws_thread = threading.Thread(
        target=run_websocket_server,
        args=(ws_manager,),
        daemon=True
    )
    ws_thread.start()
    logger.info("✅ WebSocket server thread started")
    
    # Start MCP server (optional)
    # mcp.run(transport='sse')
    
    # GPS service (optional)
    # gps_service = GPSService()
    # gps_service.run()
    
    # MQTT GPS publisher (optional)
    # gps = GPSMQTT(mqtt_client)
    # gps.publish_gps(qos=1)
    
    # Publish device ping
    mqtt_client.publish(TOPICS['device_ping'], {"data": "PING"})
    
    logger.info("=" * 60)
    logger.info("✅ WebSocket-based system started successfully!")
    logger.info(f"📡 WebSocket server: ws://0.0.0.0:8765")
    logger.info(f"📱 Device ID: {DEVICE_ID}")
    logger.info("=" * 60)
    
    try:
        # Keep main thread alive
        while True:
            import time
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping system...")
    finally:
        # Cleanup
        camera.stop()
        voice.stop()
        mqtt_client.disconnect()
        logger.info("✅ System stopped")


if __name__ == "__main__":
    main()
