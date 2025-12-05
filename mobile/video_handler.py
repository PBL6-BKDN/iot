"""Video handling (Linux camera + synthetic fallback). Simplified comments."""
import asyncio
import time
import fractions
import av
import numpy as np
from aiortc.mediastreams import MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
from config import logger, state, VIDEO_FRAME_LOG_INTERVAL, VIDEO_FIRST_FRAME_TIMEOUT

class MonitoredVideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, source_track: MediaStreamTrack):
        super().__init__()
        self._source = source_track

    async def recv(self):
        frame = await self._source.recv()
        state.video_frame_count += 1
        if state.video_first_frame_ts is None:
            state.video_first_frame_ts = time.time()
            logger.info("First video frame captured (outgoing)")
        if state.video_frame_count % VIDEO_FRAME_LOG_INTERVAL == 0:
            logger.info(f"Video frames sent: {state.video_frame_count}")
        return frame

    def stop(self):
        try:
            self._source.stop()
        except Exception:
            pass
        super().stop()

class SyntheticVideo(MediaStreamTrack):
    kind = "video"
    
    def __init__(self):
        super().__init__()
        self._pts = 0
        self._time_base = fractions.Fraction(1, 30)
        self._hue = 0
    
    async def recv(self):
        await asyncio.sleep(1/30)
        frame = av.VideoFrame(width=640, height=480, format='rgb24')
        # Solid color changing over time
        self._hue = (self._hue + 3) % 360
        # Simple hue to RGB approximation
        r = abs((self._hue % 360) - 180) / 180
        g = abs(((self._hue + 120) % 360) - 180) / 180
        b = abs(((self._hue + 240) % 360) - 180) / 180
        arr = np.zeros((480, 640, 3), dtype=np.uint8)
        arr[..., 0] = int(r * 255)
        arr[..., 1] = int(g * 255)
        arr[..., 2] = int(b * 255)
        frame.pts = self._pts
        frame.time_base = self._time_base
        frame.planes[0].update(arr.tobytes())
        self._pts += 1
        if self._pts == 1:
            logger.info("Synthetic video track started")
        if self._pts % 120 == 0:
            logger.info(f"Synthetic frames sent: {self._pts}")
        return frame

async def replace_with_synthetic_video(pc):
    """Replace camera track with synthetic test track."""
    try:
        for sender in list(pc.getSenders()):
            if sender.track and sender.track.kind == 'video':
                await sender.replaceTrack(None)
        synthetic = SyntheticVideo()
        pc.addTrack(synthetic)
        logger.info("Replaced camera video with synthetic test track")
    except Exception as e:
        logger.warning(f"Could not replace video track: {e}")

async def monitor_video():
    """Monitor video frames and fallback if none appear."""
    await asyncio.sleep(VIDEO_FIRST_FRAME_TIMEOUT)
    if state.video_first_frame_ts is None or state.video_frame_count == 0:
        logger.warning(
            f"No video frame within {VIDEO_FIRST_FRAME_TIMEOUT}s after connection. Switching to synthetic track."
        )
        if state.pc:
            await replace_with_synthetic_video(state.pc)

def setup_video_player():
    """Setup V4L2 camera player (Linux)."""
    options = {"framerate": "30", "video_size": "640x480"}
    camera_devices = ["/dev/video0", "/dev/video1"]
    
    for device in camera_devices:
        try:
            player = MediaPlayer(device, format="v4l2", options=options)
            logger.info(f"Using camera: {device}")
            return player
        except Exception as e:
            logger.warning(f"Could not open {device}: {e}")
    
    logger.error("❌ Could not open any camera device!")
    return None
