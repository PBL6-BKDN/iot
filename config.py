import os
from pprint import pprint
import dotenv

dotenv.load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cấu hình GPS
GPS_PORT = "/dev/ttyTHS1"
BAUD_RATE = 9600

# Cấu hình phân đoạn làn đường
SEND_INTERVAL = 12  # Giây, chỉ gửi ảnh mỗi 2 giây (giới hạn tần suất)
DIFF_THRESHOLD = 25  # Ngưỡng khác biệt, có thể điều chỉnh
SEND_INTERVAL_MIN = 5
SEND_INTERVAL_MAX = 10

# Cấu hình MQTT
# Địa chỉ IP của máy chủ MQTT
BROKER_HOST = os.getenv("BROKER_HOST", "192.168.1.11")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1885"))
BROKER_TRANSPORT = os.getenv("BROKER_TRANSPORT", "websockets")
BROKER_USE_TLS = os.getenv("BROKER_USE_TLS", "False").lower() == "true"
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin")
# DEVICE_ID = os.getenv("DEVICE_ID", "device001")  # ID của thiết bị
DEVICE_ID = "device001"

BROKER_WS_PATH = os.getenv("BROKER_WS_PATH", "/")

# # mic khong co day
# MIC_INDEX = 12
# AUDIO_SAMPLE_RATE = 48000  

# mic co day
MIC_INDEX = 11
AUDIO_SAMPLE_RATE = 44100  

AUDIO_CHUNK_MS = 1000     # Giảm latency
SILENCE_THRESHOLD = 0.2
SILENCE_DURATION = 3.0
MIN_SPEECH_DURATION = 2.0
MAX_AMP = 0.8

SERVER_HTTP_BASE = os.getenv("SERVER_HTTP_BASE", "http://192.168.1.11:3000")

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
MOBILE_ID = 'mobile001'

TOPICS = {
    'device_stt': f"device/{DEVICE_ID}/stt/audio",
    'device_obstacle': f"device/{DEVICE_ID}/obstacle",
    'device_info': f"device/{DEVICE_ID}/info",
    'device_status': f"device/{DEVICE_ID}/status",
    'device_ping': f"device/{DEVICE_ID}/ping",
    'server_tts': f"server/{DEVICE_ID}/audio",
    'server_command': f"server/{DEVICE_ID}/command",
    'server_pong': f"server/{DEVICE_ID}/pong",
    'device_gps': f"device/{DEVICE_ID}/gps",
    'mobile_offer': f"mobile/{MOBILE_ID}/webrtc/offer",
    'mobile_answer': f"mobile/{MOBILE_ID}/webrtc/answer",
    'mobile_candidate': f"mobile/{MOBILE_ID}/webrtc/candidate",
}
pprint({
    "BROKER_HOST": BROKER_HOST,
    "BROKER_PORT": BROKER_PORT,
    "BROKER_TRANSPORT": BROKER_TRANSPORT,
    "BROKER_USE_TLS": BROKER_USE_TLS,
    "MQTT_USER": MQTT_USER,
    "MQTT_PASS": MQTT_PASS,
    "DEVICE_ID": DEVICE_ID,
    "BROKER_WS_PATH": BROKER_WS_PATH,
    "AUDIO_SAMPLE_RATE": AUDIO_SAMPLE_RATE,
    "AUDIO_CHUNK_MS": AUDIO_CHUNK_MS,
    "SERVER_HTTP_BASE": SERVER_HTTP_BASE,
    "TOPICS": TOPICS,
    "SILENCE_THRESHOLD": SILENCE_THRESHOLD,
    "SILENCE_DURATION": SILENCE_DURATION,
    "MIN_SPEECH_DURATION": MIN_SPEECH_DURATION,
    "MAX_AMP": MAX_AMP,
    "MIC_INDEX": MIC_INDEX
})
