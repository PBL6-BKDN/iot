"""
MQTT Client
===========
"""

import json
import time
import paho.mqtt.client as mqtt
from config import DEVICE_ID, BROKER_TRANSPORT, BROKER_HOST, BROKER_PORT, BROKER_USE_TLS, BROKER_WS_PATH, MQTT_USER, MQTT_PASS, TOPICS
from .handlers import MessageHandler
from container import container
from log import setup_logger
logger = setup_logger(__name__)


class MQTTClient:
    """MQTT Client wrapper with connection management"""

    def __init__(self):
        self.client = None
        self.handler = MessageHandler()
        self._setup_client()
        container.register("mqtt_client", self)

    def _setup_client(self):
        """Setup MQTT client with configuration"""
        self.client = mqtt.Client(
            client_id=f"device-{DEVICE_ID}",
            clean_session=False,
            protocol=mqtt.MQTTv311,
            transport=BROKER_TRANSPORT
        )
        
        # Tăng giới hạn kích thước tin nhắn và buffer
        self.client._max_inflight_messages = 100  # Tăng số lượng tin nhắn đang chờ xử lý
        self.client._max_queued_messages = 0      # Không giới hạn hàng đợi
        self.client.max_inflight_messages_set(100)  # Tăng giới hạn tin nhắn đang bay

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        # Authentication
        if MQTT_USER and MQTT_PASS:
            self.client.username_pw_set(MQTT_USER, MQTT_PASS)

        # TLS/WebSocket options
        if BROKER_TRANSPORT == "websockets":
            self.client.ws_set_options(path=BROKER_WS_PATH)
        if BROKER_USE_TLS:
            self.client.tls_set()

        # Last will message
        self.client.will_set(
            TOPICS['device_status'],
            json.dumps({
                "deviceId": DEVICE_ID,
                "status": "offline",
                "ts": int(time.time() * 1000)
            }),
            qos=0,
            retain=True
        )

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback when MQTT connection is established"""
        print(f"Connected to MQTT broker with result code: {rc}")

        # Subscribe to server topics
        client.subscribe(TOPICS['server_tts'], qos=1)
        client.subscribe(TOPICS['server_command'], qos=1)
        client.subscribe(TOPICS['server_pong'], qos=2)

    def _on_message(self, client, userdata, msg):
        """Callback when MQTT message is received"""
        try:
            # Xử lý an toàn khi giải mã payload
            try:
                payload_str = msg.payload.decode('utf-8')
                payload = json.loads(payload_str)
                if msg.topic.endswith("/audio"):
                    logger.info(f"Received message on {msg.topic}")
                else:
                    logger.info(f"Received message on {msg.topic}: {payload}")
            except UnicodeDecodeError:
                # Xử lý trường hợp dữ liệu nhị phân không phải UTF-8
                print(f"Warning: Received binary data on topic {msg.topic}, skipping JSON parsing")
                return
            except json.JSONDecodeError as je:
                # Xử lý trường hợp chuỗi không phải JSON hợp lệ
                print(f"Error decoding JSON: {je}, payload length: {len(msg.payload)}")
                print(f"Payload: {msg.payload}")
                
            # Xử lý message
            self.handler.handle_message(msg.topic, payload)
        except Exception as e:
            import traceback
            print(f"Error processing message: {e}")
            traceback.print_exc()

    def connect(self):
        """Connect to MQTT broker"""
        self.client.connect(BROKER_HOST, BROKER_PORT, keepalive=120)
        self.client.loop_start()

    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: dict, qos: int = 0, retain: bool = False):
        """Publish message to MQTT topic"""
        self.client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    def loop(self, timeout: float = 0.1):
        """Process MQTT messages"""
        self.client.loop(timeout=timeout)
