"""
Message Handlers for WebSocket-based Calls
==========================================
"""

import base64
import json
import os
import time
import threading
import numpy as np
import soundfile as sf
from config import BASE_DIR
from module.voice_speaker import VoiceSpeaker

from log import setup_logger
logger = setup_logger(__name__)


# Audio stream buffers for STT audio
audio_stream_buffers = {}
STREAM_TIMEOUT = 15  # seconds


class MessageHandlerWebSocket:
    """Handle incoming MQTT messages for WebSocket-based calls"""

    def __init__(self, mqtt_client=None, websocket_manager=None):
        self.speaker = VoiceSpeaker("USB Audio Device")
        self.mqtt_client = mqtt_client
        self.websocket_manager = websocket_manager
        
        # VoiceMQTT reference (will be set from outside)
        self.voice_mqtt = None
        
        # Start cleanup thread for audio streams
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_streams, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("✅ MessageHandlerWebSocket initialized")
    
    def set_voice_mqtt(self, voice_mqtt):
        """Set VoiceMQTT instance to pause/resume during calls"""
        self.voice_mqtt = voice_mqtt
        logger.info("✅ VoiceMQTT linked to MessageHandlerWebSocket")
    
    def set_websocket_manager(self, websocket_manager):
        """Set WebSocket manager after initialization"""
        self.websocket_manager = websocket_manager
        logger.info("✅ WebSocket manager linked to MessageHandlerWebSocket")
    
    def handle_message(self, topic: str, payload: dict):
        """Route messages to appropriate handlers"""
        if not topic.endswith("/audio"):
            logger.info(f"Handling {topic}")

        if topic.endswith("/audio"):
            self.handle_stt_audio(payload)
        elif topic.endswith("/command"):
            self.handle_command(payload)
        elif topic.endswith("/call/start"):
            self.handle_call_start(payload)
        elif topic.endswith("/call/end"):
            self.handle_call_end(payload)
        else:
            logger.warning(f"No handler for {topic}")
    
    def handle_call_start(self, payload):
        """Handle call start request from mobile"""
        try:
            logger.info("📞 Call start request received from mobile")
            
            # Pause VAD and release audio devices
            if self.voice_mqtt:
                try:
                    logger.info("🔇 Releasing audio devices before call...")
                    self.voice_mqtt.pause_vad()
                    logger.info("✅ VAD paused")
                    
                    # Stop speaker stream
                    if hasattr(self, 'speaker') and self.speaker:
                        try:
                            self.speaker.stop_stream()
                            logger.info("✅ Speaker stream stopped")
                        except Exception as e:
                            logger.warning(f"Could not stop speaker: {e}")
                    
                    # Stop sounddevice globally
                    try:
                        import sounddevice as sd
                        sd.stop()
                        logger.info("✅ Sounddevice stopped globally")
                    except Exception as e:
                        logger.warning(f"Could not stop sounddevice: {e}")
                    
                    # Wait for device release
                    logger.info("⏳ Waiting 1s for device release...")
                    time.sleep(1.0)
                    logger.info("✅ Audio devices released")
                    
                except Exception as e:
                    logger.error(f"Error releasing audio devices: {e}")
            
            # WebSocket streaming will start automatically when client connects
            logger.info("✅ Call started - WebSocket streaming active")
            
        except Exception as e:
            logger.error(f"❌ Error handling call start: {e}", exc_info=True)
    
    def handle_call_end(self, payload):
        """Handle call end request"""
        try:
            logger.info("📴 Call end request received")
            
            # Resume VAD
            if self.voice_mqtt:
                try:
                    self.voice_mqtt.resume_vad()
                    logger.info("▶️ VAD resumed after call ended")
                except Exception as e:
                    logger.error(f"Error resuming VAD: {e}")
            
            logger.info("✅ Call ended")
            
        except Exception as e:
            logger.error(f"❌ Error handling call end: {e}", exc_info=True)
    
    def handle_stt_audio(self, payload):
        """
        Handle audio stream from server and convert to text when complete
        """
        try:
            stream_id = payload.get("serverStreamId")
            chunk_index = payload.get("chunkIndex", 0)
            total_chunks = payload.get("totalChunks", 1)
            is_last = payload.get("isLast", False)
            format_audio = payload.get("format", "pcm16le")
            sample_rate = payload.get("sampleRate", 44100)
            
            # Check audio data
            data_str = payload.get("data", "")
            if not data_str:
                logger.error(f"Empty audio data for chunk {chunk_index}")
                return
                
            logger.debug(f"Received audio chunk {chunk_index} with sample rate {sample_rate} from server (stream: {stream_id})")
            
            # Decode audio from base64
            try:
                audio_chunk = base64.b64decode(data_str)
            except Exception as e:
                logger.error(f"Error decoding base64 data: {e}")
                return

            # Create unique key for this stream
            stream_key = f"{stream_id}"
            
            # Initialize buffer for stream if not exists
            if stream_key not in audio_stream_buffers:
                audio_stream_buffers[stream_key] = {
                    "chunks": {},
                    "total_chunks": total_chunks,
                    "received_chunks": 0,
                    "format": format_audio,
                    "sample_rate": sample_rate,
                    "timestamp": time.time()
                }
            
            # Save chunk to buffer
            audio_stream_buffers[stream_key]["chunks"][chunk_index] = audio_chunk
            audio_stream_buffers[stream_key]["received_chunks"] += 1
            
            logger.debug(f"Received audio chunk {chunk_index+1}/{total_chunks} from server (stream: {stream_id})")
            
            # Check if all chunks received or last chunk received
            if is_last or audio_stream_buffers[stream_key]["received_chunks"] >= total_chunks:
                logger.info(f"Completed audio stream {stream_id} from server, processing...")
                
                # Combine chunks in order
                all_chunks = []
                for i in range(total_chunks):
                    if i in audio_stream_buffers[stream_key]["chunks"]:
                        all_chunks.append(audio_stream_buffers[stream_key]["chunks"][i])
                    else:
                        logger.warning(f"Missing chunk {i} in stream {stream_id} from server")
                
                # Combine all chunks
                combined_audio = b''.join(all_chunks)
                logger.info(f"Playing audio from server (stream: {stream_id})")
                
                # Save debug file
                file_path = os.path.join(BASE_DIR, "debug", f"audio_response_from_server.wav")
                try:
                    audio_np = np.frombuffer(combined_audio, dtype=np.int16)
                    sf.write(file_path, audio_np, audio_stream_buffers[stream_key]["sample_rate"], subtype='PCM_16')
                    logger.debug(f"💾 Saved audio file: {file_path}")
                except Exception as e:
                    logger.error(f"❌ Error saving audio file: {e}")
                
                # Play audio
                self.speaker.play_audio_data(combined_audio, audio_stream_buffers[stream_key]["sample_rate"])
                    
                # Delete buffer after processing
                del audio_stream_buffers[stream_key]
                
        except Exception as e:
            logger.error(f"Error processing audio from server: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _cleanup_old_streams(self):
        """Check and process audio streams that timed out"""
        while True:
            try:
                current_time = time.time()
                streams_to_process = []
                
                # Check streams that exceeded timeout
                for stream_key, stream_data in list(audio_stream_buffers.items()):
                    if current_time - stream_data["timestamp"] > STREAM_TIMEOUT:
                        if stream_data["received_chunks"] > 0:
                            logger.warning(f"Stream {stream_key} timed out with {stream_data['received_chunks']}/{stream_data['total_chunks']} chunks. Processing anyway.")
                            streams_to_process.append(stream_key)
                
                # Process timed out streams
                for stream_key in streams_to_process:
                    stream_data = audio_stream_buffers[stream_key]
                    
                    # Combine chunks in order
                    all_chunks = []
                    for i in range(stream_data["total_chunks"]):
                        if i in stream_data["chunks"]:
                            all_chunks.append(stream_data["chunks"][i])
                    
                    # Combine all chunks
                    if all_chunks:
                        combined_audio = b''.join(all_chunks)
                        logger.info(f"Playing timed out audio from server (stream: {stream_key}, {len(all_chunks)}/{stream_data['total_chunks']} chunks)")
                        self.speaker.play_audio_data(combined_audio, stream_data["sample_rate"])
                    
                    # Delete buffer after processing
                    del audio_stream_buffers[stream_key]
                
                # Sleep 1 second before checking again
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in cleanup thread: {e}")
                time.sleep(5)  # Sleep longer if error
    
    def handle_command(self, payload: dict):
        """Handle commands from server"""
        command = payload.get("command")
        if command == "send_sms":
            self.handle_send_sms(payload)

    def handle_send_sms(self, payload: dict):
        """
        Handle SMS send request from server.
        payload expected: { "command": "send_sms", "phoneNumber": "+84xxxxxxxxx", "message": "..." }
        """
        try:
            phone_number = payload.get("phone_number")
            message = payload.get("message")

            if not phone_number or not message:
                logger.error("Missing phoneNumber or message for send_sms command")
                return

            logger.info(f"Sending SMS to {phone_number}...")
            # Note: GPRS connection removed - implement if needed
            logger.warning("SMS functionality not implemented in WebSocket version")
        except Exception as e:
            logger.error(f"Error handling send_sms: {e}")
