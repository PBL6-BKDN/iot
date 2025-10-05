import soundfile as sf
import os
import sounddevice as sd
import numpy as np
import tempfile
from scipy import signal
from log import setup_logger

logger = setup_logger(__name__)


def find_device_index_by_name(keyword, kind='output'):
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if keyword.lower() in dev['name'].lower():
            if kind == 'output' and dev['max_output_channels'] > 0:
                return i
    return None


class VoiceSpeaker:
    def __init__(self, speaker_name):
        self.speaker_index = find_device_index_by_name(
            speaker_name, kind='output')
        if self.speaker_index is None:
            raise ValueError(f"Không tìm thấy loa nào chứa '{speaker_name}'!")
        logger.info(f"🔊 Speaker index (PulseAudio): {self.speaker_index}")

    def play_file(self, file_path: str):
        """Phát âm thanh từ file (wav, flac, ogg, mp3 nếu có soundfile hỗ trợ)."""
        if not os.path.exists(file_path):
            logger.error(f"❌ File không tồn tại: {file_path}", exc_info=True)
            return

        try:
            data, samplerate = sf.read(file_path, dtype='float32')
            # Đảm bảo samplerate phù hợp với thiết bị
            if samplerate != 44100:
                logger.info(f"Chuyển đổi sample rate từ {samplerate} sang 44100Hz")
                # Nếu sample rate khác 44100, thực hiện resampling
                samples = len(data)
                new_samples = int(samples * 44100 / samplerate)
                data = signal.resample(data, new_samples)
                samplerate = 44100
                
            sd.play(data, device=self.speaker_index)
            sd.wait()  # Chờ phát xong
        except Exception as e:
            logger.error(f"⚠️ Lỗi khi phát file: {e}", exc_info=True)

    def play_audio_data(self, audio_data: bytes, sample_rate: int = 44100):
        """
        Phát âm thanh từ dữ liệu raw
        """
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Tạo file WAV tạm với soundfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                # Lưu với soundfile để có header WAV đúng
                sf.write(temp_file.name, audio_array,
                        sample_rate, subtype='PCM_16')
                temp_file.flush()

                self.play_file(temp_file.name)

                # Cleanup
                os.unlink(temp_file.name)

            logger.info(
                f"🔊 Phát âm thanh thành công - {len(audio_data)} bytes với sample rate {sample_rate}")
        except Exception as e:
            logger.error(f"❌ Lỗi phát âm thanh: {e}", exc_info=True)
