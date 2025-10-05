import asyncio
import base64
import json
import tempfile
import time
import threading
from typing import Optional, Callable, Dict, Any
import sounddevice as sd
import paho.mqtt.client as mqtt
from pydub import AudioSegment
import os
import soundfile as sf
import numpy as np

from module.vad import VoiceActivityDetector
from navigation.speech.voice_speaker import VoiceSpeaker
from config import SILENCE_THRESHOLD, SILENCE_DURATION, MIN_SPEECH_DURATION
from log import setup_logger
from config import BASE_DIR, MAX_AMP
logger = setup_logger(__name__)


class VoiceStreamer:
    """Class để ghi âm và gửi âm thanh qua MQTT hoặc HTTP"""

    def __init__(self, mic_index: int, sample_rate: int = 48000, chunk_duration_ms: int = 100):
        """
        Args:
            mic_name: Tên microphone để tìm device
            sample_rate: Tần số lấy mẫu âm thanh
            chunk_duration_ms: Thời gian mỗi chunk (ms) cho real-time streaming
        """
        self.mic_index = mic_index
        self.sample_rate = sample_rate
        self.chunk_duration_ms = chunk_duration_ms
        self.chunk_samples = int(sample_rate * chunk_duration_ms / 1000.0)
        self.is_listening = False
        self.listening_thread = None

        # Voice Activity Detector
        self.vad = VoiceActivityDetector(
            sample_rate=sample_rate,
            silence_threshold=SILENCE_THRESHOLD,  # Điều chỉnh theo môi trường
            silence_duration=SILENCE_DURATION,
            min_speech_duration=MIN_SPEECH_DURATION
        )

        # Callback functions
        self.on_speech_start = None
        self.on_speech_complete = None
        self.on_speech_data = None

        print(f"🎤 VoiceStreamer initialized - Mic index: {self.mic_index}")

    def set_callbacks(self, on_speech_start: Callable = None,
                      on_speech_complete: Callable = None,
                      on_speech_data: Callable = None):
        """
        Thiết lập callback functions

        Args:
            on_speech_start: Gọi khi bắt đầu phát hiện giọng nói
            on_speech_complete: Gọi khi hoàn tất thu âm (audio_data, duration)
            on_speech_data: Gọi mỗi chunk âm thanh (audio_chunk, timestamp, status)
        """
        self.on_speech_start = on_speech_start
        self.on_speech_complete = on_speech_complete
        self.on_speech_data = on_speech_data

    def start_listening(self):
        """Bắt đầu lắng nghe liên tục"""
        if self.is_listening:
            print("⚠️ Đang lắng nghe rồi!")
            return

        self.is_listening = True
        self.listening_thread = threading.Thread(target=self._listening_loop)
        self.listening_thread.start()
        print("👂 Bắt đầu lắng nghe liên tục...")

    def stop_listening(self):
        """Dừng lắng nghe"""
        self.is_listening = False
        if self.listening_thread:
            self.listening_thread.join()
        print("⏹️ Dừng lắng nghe")

    def _listening_loop(self):
        """Vòng lặp lắng nghe liên tục"""
        try:
            with sd.InputStream(
                device=self.mic_index,
                channels=1,
                samplerate=self.sample_rate,
                dtype='int16',
                blocksize=self.chunk_samples
            ) as stream:
                print("🎧 Đang lắng nghe... (nói gì đó để bắt đầu thu âm)")

                while self.is_listening:
                    audio_chunk, overflowed = stream.read(self.chunk_samples)
                    if overflowed:
                        print("⚠️ Audio buffer overflow!")

                    if len(audio_chunk) > 0:
                        # Chuyển đổi sang float32 cho VAD và áp dụng chuẩn hóa biên độ
                        audio_float = audio_chunk.astype(np.float32) / 32768.0

                        # # Áp dụng giới hạn biên độ để tránh tiếng rè
                        # max_amp = np.max(np.abs(audio_float))
                        # if max_amp > MAX_AMP:  # Nếu biên độ quá lớn
                        #     audio_float = audio_float * (MAX_AMP/ max_amp)

                        # Xử lý VAD
                        vad_result = self.vad.process_audio_chunk(audio_float)

                        # Gọi callbacks
                        if self.on_speech_data:
                            self.on_speech_data(audio_chunk, int(
                                time.time() * 1000), vad_result)

                        if vad_result['action'] == 'speech_complete':
                            if self.on_speech_complete:
                                # Chuyển đổi từ float32 về int16 để đảm bảo định dạng nhất quán với record_audio
                                audio_data = vad_result['audio_data']
                                int16_audio = (
                                    audio_data * 32768.0).astype(np.int16).tobytes()
                                self.on_speech_complete(
                                    int16_audio, vad_result['duration'])
                                # Tạo thư mục lưu nếu chưa có
                                save_dir = "debug"
                                os.makedirs(save_dir, exist_ok=True)
                                file_path = os.path.join(
                                    BASE_DIR, save_dir, f"audio_mic.wav")
                                try:
                                    sf.write(
                                        file_path, vad_result['audio_data'], self.sample_rate, subtype='PCM_16')
                                    logger.debug(
                                        f"💾 Đã lưu file âm thanh: {file_path}")
                                except Exception as e:
                                    logger.error(
                                        f"❌ Lỗi khi lưu file âm thanh: {e}")
                        elif vad_result['action'] == 'speaking' and not self.vad.is_speaking:
                            if self.on_speech_start:
                                self.on_speech_start()

        except Exception as e:
            print(f"❌ Lỗi lắng nghe: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_listening = False

    def __del__(self):
        self.stop_listening()

    def record_audio(self, duration_sec: float) -> bytes:
        """
        Ghi âm trong thời gian xác định và trả về dữ liệu âm thanh

        Args:
            duration_sec: Thời gian ghi âm (giây)

        Returns:
            bytes: Dữ liệu âm thanh raw (PCM 16-bit)
        """
        print(f"🎙️ Đang ghi âm {duration_sec}s...")

        total_samples = int(self.sample_rate * duration_sec)
        recording = sd.rec(
            total_samples,
            samplerate=self.sample_rate,
            channels=1,
            dtype='int16',
            device=self.mic_index
        )
        sd.wait()

        audio_data = recording.reshape(-1).tobytes()
        print(f"✅ Ghi âm hoàn thành - {len(audio_data)} bytes")
        return audio_data


class MQTTVoiceSender:
    """Gửi âm thanh qua MQTT"""

    def __init__(self, mqtt_client: mqtt.Client, device_id: str):
        self.client = mqtt_client
        self.device_id = device_id
        self.topic_prefix = f"device/{device_id}/voice"

    def send_audio_file(self, audio_data: bytes, metadata: Dict[str, Any] = None):
        """
        Gửi file âm thanh hoàn chỉnh qua MQTT

        Args:
            audio_data: Dữ liệu âm thanh raw
            metadata: Thông tin bổ sung (format, sample_rate, etc.)
        """
        if metadata is None:
            metadata = {}

        # Chia thành chunks nhỏ để tránh vượt quá giới hạn MQTT
        chunk_size = 1024 * 8  # 8KB per chunk
        total_chunks = (len(audio_data) + chunk_size - 1) // chunk_size

        stream_id = f"voice_{int(time.time() * 1000)}"

        for i in range(total_chunks):
            start = i * chunk_size
            end = min(start + chunk_size, len(audio_data))
            chunk_data = audio_data[start:end]

            payload = {
                "deviceId": self.device_id,
                "streamId": stream_id,
                "chunkIndex": i,
                "totalChunks": total_chunks,
                "isLast": (i == total_chunks - 1),
                "timestamp": int(time.time() * 1000),
                "format": metadata.get("format", "pcm16le"),
                "sampleRate": metadata.get("sampleRate", 48000),
                "data": base64.b64encode(chunk_data).decode()
            }

            topic = f"{self.topic_prefix}/file"
            self.client.publish(topic, json.dumps(payload), qos=1)

        print(f"📤 Gửi file âm thanh qua MQTT - {total_chunks} chunks")

    def send_audio_stream(self, audio_chunk: bytes, timestamp: int, stream_id: str = None):
        """
        Gửi chunk âm thanh real-time qua MQTT

        Args:
            audio_chunk: Chunk âm thanh
            timestamp: Timestamp của chunk
            stream_id: ID của stream (tự tạo nếu None)
        """
        if stream_id is None:
            stream_id = f"stream_{int(time.time() * 1000)}"

        payload = {
            "deviceId": self.device_id,
            "streamId": stream_id,
            "timestamp": timestamp,
            "format": "pcm16le",
            "sampleRate": 48000,
            "data": base64.b64encode(audio_chunk).decode()
        }

        topic = f"{self.topic_prefix}/stream"
        self.client.publish(topic, json.dumps(payload), qos=0)


# ========== DEMO FUNCTIONS ==========


def demo_mqtt_streaming():
    """Demo gửi âm thanh qua MQTT"""
    print("=== Demo MQTT Voice Streaming ===")

    # Setup MQTT
    client = mqtt.Client()
    client.connect("localhost", 1883, 60)
    client.loop_start()

    mqtt_sender = MQTTVoiceSender(client, "jetson_001")
    streamer = VoiceStreamer("USB", sample_rate=48000)

    def on_speech_complete(audio_data, duration):
        print(f"�� Gửi âm thanh qua MQTT: {duration:.1f}s")
        mqtt_sender.send_audio_file(audio_data, {
            "format": "pcm16le",
            "sampleRate": 48000,
            "duration": duration
        })

    streamer.set_callbacks(on_speech_complete=on_speech_complete)

    try:
        streamer.start_listening()
        print("🎧 Đang lắng nghe và gửi qua MQTT...")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⏹️ Dừng hệ thống...")
        streamer.stop_listening()
        client.loop_stop()
        client.disconnect()
