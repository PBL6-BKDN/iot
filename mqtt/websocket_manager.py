"""
WebSocket Manager for Video/Audio Streaming
============================================
Manages WebSocket connections and streams video/audio to mobile app
"""

import asyncio
import json
import base64
import time
import cv2
import numpy as np
from typing import Optional, Set
import websockets
from websockets.server import WebSocketServerProtocol
import pyaudio
import queue
import threading

from log import setup_logger
from container import container

logger = setup_logger(__name__)


class WebSocketManager:
    """Manage WebSocket connections for video/audio streaming"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """
        Initialize WebSocket Manager
        
        Args:
            host: Host to bind WebSocket server
            port: Port to bind WebSocket server
        """
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.is_streaming = False
        self.server = None
        
        # Video settings
        self.video_fps = 20  # Lower FPS to reduce bandwidth
        self.video_quality = 80  # JPEG quality (0-100)
        self.video_width = 640
        self.video_height = 480
        
        # Audio settings
        self.audio_rate = 48000
        self.audio_channels = 1
        self.audio_chunk = 960  # 20ms at 48kHz
        
        # Audio playback (for incoming audio from mobile)
        self._pyaudio = None
        self._audio_output_stream = None
        self._audio_input_queue = queue.Queue(maxsize=100)
        
        # Streaming tasks
        self._video_task = None
        self._audio_task = None
        
        logger.info(f"✅ WebSocketManager initialized (host={host}, port={port})")
    
    async def start_server(self):
        """Start WebSocket server"""
        try:
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info(f"🚀 WebSocket server started on ws://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Failed to start WebSocket server: {e}", exc_info=True)
            raise
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket client connection"""
        client_addr = websocket.remote_address
        logger.info(f"📱 New client connected: {client_addr}")
        
        self.clients.add(websocket)
        
        try:
            # Start streaming when first client connects
            if len(self.clients) == 1:
                await self.start_streaming()
            
            # Handle incoming messages from client
            async for message in websocket:
                await self.handle_message(websocket, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"📴 Client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"❌ Error handling client {client_addr}: {e}", exc_info=True)
        finally:
            self.clients.discard(websocket)
            
            # Stop streaming when no clients
            if len(self.clients) == 0:
                await self.stop_streaming()
    
    async def handle_message(self, websocket: WebSocketServerProtocol, message):
        """Handle incoming message from client"""
        try:
            # Parse message
            if isinstance(message, bytes):
                # Binary message (audio data)
                await self.handle_audio_data(message)
            else:
                # Text message (JSON control)
                data = json.loads(message)
                msg_type = data.get("type")
                
                if msg_type == "audio":
                    # Audio data in JSON format
                    audio_b64 = data.get("data")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await self.handle_audio_data(audio_bytes)
                elif msg_type == "ping":
                    # Respond to ping
                    await websocket.send(json.dumps({"type": "pong"}))
                else:
                    logger.warning(f"Unknown message type: {msg_type}")
                    
        except Exception as e:
            logger.error(f"❌ Error handling message: {e}", exc_info=True)
    
    async def handle_audio_data(self, audio_bytes: bytes):
        """Handle incoming audio data from mobile and play through speaker"""
        try:
            # Initialize PyAudio if needed
            if self._pyaudio is None:
                self._pyaudio = pyaudio.PyAudio()
            
            # Open output stream if needed
            if self._audio_output_stream is None:
                # Find USB Audio Device for output
                output_device_index = None
                try:
                    info = self._pyaudio.get_host_api_info_by_index(0)
                    numdevices = info.get('deviceCount', 0)
                    for i in range(numdevices):
                        try:
                            device_info = self._pyaudio.get_device_info_by_host_api_device_index(0, i)
                            name = device_info.get('name', '')
                            max_out = device_info.get('maxOutputChannels', 0)
                            
                            if max_out > 0 and ('USB Audio Device' in name or 'hw:3,0' in name):
                                output_device_index = i
                                logger.info(f"🔊 Found USB speaker: {name} (index={i})")
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.warning(f"Could not enumerate audio devices: {e}")
                
                # Open stream
                stream_kwargs = {
                    'format': pyaudio.paInt16,
                    'channels': self.audio_channels,
                    'rate': self.audio_rate,
                    'output': True,
                    'frames_per_buffer': self.audio_chunk,
                }
                if output_device_index is not None:
                    stream_kwargs['output_device_index'] = output_device_index
                
                self._audio_output_stream = self._pyaudio.open(**stream_kwargs)
                logger.info(f"🔊 Audio output stream opened (rate={self.audio_rate}, device={output_device_index})")
            
            # Play audio
            self._audio_output_stream.write(audio_bytes)
            
        except Exception as e:
            logger.error(f"❌ Error playing audio: {e}", exc_info=True)
    
    async def start_streaming(self):
        """Start video and audio streaming"""
        if self.is_streaming:
            logger.warning("⚠️ Already streaming")
            return
        
        logger.info("🎬 Starting video/audio streaming...")
        self.is_streaming = True
        
        # Start video streaming task
        self._video_task = asyncio.create_task(self._stream_video())
        
        # Start audio streaming task
        self._audio_task = asyncio.create_task(self._stream_audio())
        
        logger.info("✅ Streaming started")
    
    async def stop_streaming(self):
        """Stop video and audio streaming"""
        if not self.is_streaming:
            return
        
        logger.info("🛑 Stopping streaming...")
        self.is_streaming = False
        
        # Cancel tasks
        if self._video_task:
            self._video_task.cancel()
            try:
                await self._video_task
            except asyncio.CancelledError:
                pass
            self._video_task = None
        
        if self._audio_task:
            self._audio_task.cancel()
            try:
                await self._audio_task
            except asyncio.CancelledError:
                pass
            self._audio_task = None
        
        # Close audio streams
        if self._audio_output_stream:
            try:
                self._audio_output_stream.stop_stream()
                self._audio_output_stream.close()
                self._audio_output_stream = None
            except Exception:
                pass
        
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
                self._pyaudio = None
            except Exception:
                pass
        
        logger.info("✅ Streaming stopped")
    
    async def _stream_video(self):
        """Stream video frames to all connected clients"""
        try:
            camera = container.get("camera")
            if not camera:
                logger.error("❌ No camera available for streaming")
                return
            
            frame_interval = 1.0 / self.video_fps
            frame_count = 0
            
            logger.info(f"📹 Video streaming started (fps={self.video_fps}, quality={self.video_quality})")
            
            while self.is_streaming:
                start_time = time.time()
                
                # Get frame from camera
                frame_bgr = camera.get_latest_frame()
                if frame_bgr is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Resize if needed
                height, width = frame_bgr.shape[:2]
                if width != self.video_width or height != self.video_height:
                    frame_bgr = cv2.resize(frame_bgr, (self.video_width, self.video_height))
                
                # Encode as JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.video_quality]
                _, buffer = cv2.imencode('.jpg', frame_bgr, encode_param)
                jpg_bytes = buffer.tobytes()
                
                # Create message
                message = {
                    "type": "video",
                    "data": base64.b64encode(jpg_bytes).decode('utf-8'),
                    "timestamp": int(time.time() * 1000),
                    "width": self.video_width,
                    "height": self.video_height,
                    "frame": frame_count
                }
                
                # Send to all clients
                if self.clients:
                    message_json = json.dumps(message)
                    await asyncio.gather(
                        *[client.send(message_json) for client in self.clients],
                        return_exceptions=True
                    )
                
                frame_count += 1
                
                # Log every 30 frames (1.5 seconds at 20fps)
                if frame_count % 30 == 0:
                    logger.debug(f"📹 Sent frame {frame_count}, size={len(jpg_bytes)} bytes to {len(self.clients)} clients")
                
                # Maintain FPS
                elapsed = time.time() - start_time
                if elapsed < frame_interval:
                    await asyncio.sleep(frame_interval - elapsed)
                    
        except asyncio.CancelledError:
            logger.info("📹 Video streaming cancelled")
        except Exception as e:
            logger.error(f"❌ Error in video streaming: {e}", exc_info=True)
    
    async def _stream_audio(self):
        """Stream audio from microphone to all connected clients"""
        try:
            # Initialize PyAudio for input
            pa = pyaudio.PyAudio()
            
            # Find USB Audio Device for input
            input_device_index = None
            try:
                info = pa.get_host_api_info_by_index(0)
                numdevices = info.get('deviceCount', 0)
                for i in range(numdevices):
                    try:
                        device_info = pa.get_device_info_by_host_api_device_index(0, i)
                        name = device_info.get('name', '')
                        max_in = device_info.get('maxInputChannels', 0)
                        
                        if max_in > 0 and ('USB Audio Device' in name or 'hw:3,0' in name):
                            input_device_index = i
                            logger.info(f"🎤 Found USB microphone: {name} (index={i})")
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Could not enumerate audio devices: {e}")
            
            # Audio queue for callback
            audio_queue = queue.Queue(maxsize=100)
            
            def audio_callback(in_data, frame_count, time_info, status):
                try:
                    audio_queue.put_nowait(in_data)
                except queue.Full:
                    # Drop oldest
                    try:
                        audio_queue.get_nowait()
                        audio_queue.put_nowait(in_data)
                    except Exception:
                        pass
                return (None, pyaudio.paContinue)
            
            # Open input stream
            stream_kwargs = {
                'format': pyaudio.paInt16,
                'channels': self.audio_channels,
                'rate': self.audio_rate,
                'input': True,
                'frames_per_buffer': self.audio_chunk,
                'stream_callback': audio_callback,
            }
            if input_device_index is not None:
                stream_kwargs['input_device_index'] = input_device_index
            
            stream = pa.open(**stream_kwargs)
            stream.start_stream()
            
            logger.info(f"🎤 Audio streaming started (rate={self.audio_rate}, device={input_device_index})")
            
            chunk_count = 0
            
            while self.is_streaming:
                # Get audio chunk from queue
                try:
                    audio_data = await asyncio.get_event_loop().run_in_executor(
                        None, audio_queue.get, True, 1.0
                    )
                except queue.Empty:
                    continue
                
                # Create message
                message = {
                    "type": "audio",
                    "data": base64.b64encode(audio_data).decode('utf-8'),
                    "timestamp": int(time.time() * 1000),
                    "sampleRate": self.audio_rate,
                    "channels": self.audio_channels
                }
                
                # Send to all clients
                if self.clients:
                    message_json = json.dumps(message)
                    await asyncio.gather(
                        *[client.send(message_json) for client in self.clients],
                        return_exceptions=True
                    )
                
                chunk_count += 1
                
                # Log every 100 chunks (~2 seconds)
                if chunk_count % 100 == 0:
                    logger.debug(f"🎤 Sent audio chunk {chunk_count} to {len(self.clients)} clients")
            
            # Cleanup
            stream.stop_stream()
            stream.close()
            pa.terminate()
            
        except asyncio.CancelledError:
            logger.info("🎤 Audio streaming cancelled")
        except Exception as e:
            logger.error(f"❌ Error in audio streaming: {e}", exc_info=True)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.clients:
            return
        
        message_json = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_json) for client in self.clients],
            return_exceptions=True
        )
    
    def run(self):
        """Run WebSocket server (blocking)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.start_server())
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("🛑 WebSocket server stopped by user")
        finally:
            loop.close()
