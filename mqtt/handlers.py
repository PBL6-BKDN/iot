"""
Message Handlers
================
"""

import base64
import json
import os
import numpy as np
import time
import threading
import soundfile as sf
from config import BASE_DIR
from module.voice_speaker import VoiceSpeaker
from .camera import CameraCapture
from .voice import VoiceMQTT
from .gprs_connection import GPRSConnection

from log import setup_logger
logger = setup_logger(__name__)
audio_stream_buffers = {}
# Thời gian tối đa (giây) để chờ đợi tất cả các chunks
STREAM_TIMEOUT = 15  # Tăng thời gian timeout lên 15 giây
class MessageHandler:
    """Handle incoming MQTT messages"""

    def __init__(self):
        self.camera = CameraCapture()
        self.speaker = VoiceSpeaker("USB Audio Device")
        self.gprs = GPRSConnection()
        self._gprs_ready = False
        # Khởi tạo luồng kiểm tra timeout cho audio streams
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_streams, daemon=True)
        self.cleanup_thread.start()

    def handle_message(self, topic: str, payload: dict):
        """Route messages to appropriate handlers"""
        
        if topic.endswith("/audio"):
            logger.info(f"Received message on {topic}")
        else:
            logger.info(f"Received message on {topic}: {payload}")

        if topic.endswith("/audio"):
            self.handle_stt_audio(payload)
        elif topic.endswith("/command"):
            self.handle_command(payload)
        else:
            logger.warning(f"Not handler {topic}")
            
    def handle_stt_audio(self, payload):
        """
        Xử lý luồng âm thanh từ thiết bị và chuyển đổi thành văn bản khi nhận đủ
        """
        try:
            stream_id = payload.get("serverStreamId")
            chunk_index = payload.get("chunkIndex", 0)
            total_chunks = payload.get("totalChunks", 1)
            is_last = payload.get("isLast", False)
            format_audio = payload.get("format", "pcm16le")
            sample_rate = payload.get("sampleRate", 44100)
            
            # Kiểm tra dữ liệu âm thanh
            data_str = payload.get("data", "")
            if not data_str:
                logger.error(f"Empty audio data for chunk {chunk_index}")
                return
                
            logger.debug(f"Received audio chunk {chunk_index} with sample rate {sample_rate} from server (stream: {stream_id})")
            
            # Giải mã âm thanh từ base64 an toàn
            try:
                audio_chunk = base64.b64decode(data_str)
            except Exception as e:
                logger.error(f"Error decoding base64 data: {e}")
                return

            
            # Tạo key duy nhất cho stream này
            stream_key = f"{stream_id}"
            
            # Khởi tạo buffer cho stream nếu chưa tồn tại
            if stream_key not in audio_stream_buffers:
                audio_stream_buffers[stream_key] = {
                    "chunks": {},
                    "total_chunks": total_chunks,
                    "received_chunks": 0,
                    "format": format_audio,
                    "sample_rate": sample_rate,
                    "timestamp": time.time()
                }
            
            # Lưu chunk vào buffer
            audio_stream_buffers[stream_key]["chunks"][chunk_index] = audio_chunk
            audio_stream_buffers[stream_key]["received_chunks"] += 1
            
            logger.debug(f"Received audio chunk {chunk_index+1}/{total_chunks} from server (stream: {stream_id})")
            
            # Kiểm tra xem đã nhận đủ chunks chưa hoặc đã nhận chunk cuối cùng
            if is_last or audio_stream_buffers[stream_key]["received_chunks"] >= total_chunks:
                # Xử lý ngay cả khi chưa nhận đủ tất cả các chunks
                logger.info(f"Completed audio stream {stream_id} from server, processing...")
                
                # Kết hợp các chunks theo thứ tự
                all_chunks = []
                for i in range(total_chunks):
                    if i in audio_stream_buffers[stream_key]["chunks"]:
                        all_chunks.append(audio_stream_buffers[stream_key]["chunks"][i])
                    else:
                        logger.warning(f"Missing chunk {i} in stream {stream_id} from server")
                
                # Kết hợp tất cả chunks
                combined_audio = b''.join(all_chunks)
                logger.info(f"Playing audio from server (stream: {stream_id})")
                file_path = os.path.join(
                                    BASE_DIR, "debug", f"audio_response_from_server.wav")
                try:
                    audio_np = np.frombuffer(combined_audio, dtype=np.int16)
                    sf.write(
                        file_path, audio_np, audio_stream_buffers[stream_key]["sample_rate"], subtype='PCM_16')
                    logger.debug(
                        f"💾 Đã lưu file âm thanh: {file_path}")
                except Exception as e:
                    logger.error(
                        f"❌ Lỗi khi lưu file âm thanh: {e}")
                self.speaker.play_audio_data(combined_audio, audio_stream_buffers[stream_key]["sample_rate"])
                # self.speaker.play_file(file_path)
                    
                # Xóa buffer sau khi xử lý xong
                del audio_stream_buffers[stream_key]
                
        except Exception as e:
            logger.error(f"Error processing audio from server: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _cleanup_old_streams(self):
        """Kiểm tra và xử lý các audio streams bị timeout"""
        while True:
            try:
                current_time = time.time()
                streams_to_process = []
                
                # Kiểm tra các streams đã quá thời gian chờ
                for stream_key, stream_data in list(audio_stream_buffers.items()):
                    if current_time - stream_data["timestamp"] > STREAM_TIMEOUT:
                        if stream_data["received_chunks"] > 0:
                            logger.warning(f"Stream {stream_key} timed out with {stream_data['received_chunks']}/{stream_data['total_chunks']} chunks. Processing anyway.")
                            streams_to_process.append(stream_key)
                
                # Xử lý các streams bị timeout
                for stream_key in streams_to_process:
                    stream_data = audio_stream_buffers[stream_key]
                    
                    # Kết hợp các chunks theo thứ tự
                    all_chunks = []
                    for i in range(stream_data["total_chunks"]):
                        if i in stream_data["chunks"]:
                            all_chunks.append(stream_data["chunks"][i])
                    
                    # Kết hợp tất cả chunks
                    if all_chunks:
                        combined_audio = b''.join(all_chunks)
                        logger.info(f"Playing timed out audio from server (stream: {stream_key}, {len(all_chunks)}/{stream_data['total_chunks']} chunks)")
                        self.speaker.play_audio_data(combined_audio, stream_data["sample_rate"])
                    
                    # Xóa buffer sau khi xử lý
                    del audio_stream_buffers[stream_key]
                
                # Ngủ 1 giây trước khi kiểm tra lại
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                time.sleep(5)  # Ngủ dài hơn nếu có lỗi
    
    def handle_command(self, payload: dict):
        """Handle commands from server"""
        command = payload.get("command")
        if command == "capture":
            print("Received command: capture image")
            self.camera.capture_and_upload()
        elif command == "send_sms":
            self.handle_send_sms(payload)

    def handle_send_sms(self, payload: dict):
        """
        Xử lý yêu cầu gửi SMS từ server.
        payload expected: { "command": "send_sms", "phoneNumber": "+84xxxxxxxxx", "message": "..." }
        """
        try:
            phone_number = payload.get("phone_number")
            message = payload.get("message")

            if not phone_number or not message:
                logger.error("Missing phoneNumber or message for send_sms command")
                return

            logger.info(f"Sending SMS to {phone_number}...")
            ok = self.gprs.send_test_sms(phone_number, message)
            if ok:
                logger.info("SMS sent successfully")
            else:
                logger.error("SMS sending failed")
        except Exception as e:
            logger.error(f"Error handling send_sms: {e}")
