import time
import numpy as np
from typing import Dict, Any

from config import MAX_AMP


class VoiceActivityDetector:
    """Phát hiện hoạt động giọng nói (Voice Activity Detection)"""

    def __init__(self, sample_rate: int = 48000, silence_threshold: float = 0.02,
                 silence_duration: float = 5.0, min_speech_duration: float = 0.5,
                 pre_buffer_duration: float = 0.2, post_buffer_duration: float = 0.2):
        """
        Args:
            sample_rate: Tần số lấy mẫu
            silence_threshold: Ngưỡng âm lượng để coi là im lặng (0.0-1.0)
            silence_duration: Thời gian im lặng để kết thúc thu âm (giây)
            min_speech_duration: Thời gian nói tối thiểu để bắt đầu thu âm (giây)
            pre_buffer_duration: Thời gian giữ âm thanh trước khi phát hiện giọng nói (giây)
            post_buffer_duration: Thời gian giữ âm thanh sau khi im lặng (giây)
        """
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.min_speech_duration = min_speech_duration
        self.pre_buffer_duration = pre_buffer_duration
        self.post_buffer_duration = post_buffer_duration

        # Trạng thái
        self.is_speaking = False
        self.speech_start_time = None
        self.silence_start_time = None
        self.audio_buffer = []
        self.pre_buffer = []  # Buffer để giữ âm thanh trước khi phát hiện giọng nói
        self.post_buffer = []  # Buffer để giữ âm thanh sau khi im lặng

    def process_audio_chunk(self, audio_chunk: np.ndarray) -> Dict[str, Any]:
        """
        Xử lý chunk âm thanh để phát hiện giọng nói

        Args:
            audio_chunk: Chunk âm thanh (numpy array)

        Returns:
            Dict với thông tin trạng thái
        """
        # Tính RMS (Root Mean Square) để đo âm lượng
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))

        current_time = time.time()

        # Phát hiện giọng nói
        if rms > self.silence_threshold:
            if not self.is_speaking:
                # Bắt đầu nói - thêm pre_buffer vào đầu
                self.is_speaking = True
                self.speech_start_time = current_time
                self.silence_start_time = None
                # Bắt đầu với pre_buffer (âm thanh trước khi phát hiện) + chunk hiện tại
                self.audio_buffer = self.pre_buffer.copy() + [audio_chunk]
                self.post_buffer = []  # Reset post buffer
                print(f"🗣️ Bắt đầu phát hiện giọng nói (RMS: {rms:.4f}) - Pre-buffer: {len(self.pre_buffer)} chunks")
            else:
                # Đang nói - thêm vào buffer
                self.audio_buffer.append(audio_chunk)
                self.silence_start_time = None
                self.post_buffer = []  # Reset post buffer khi còn đang nói
        else:
            # Im lặng
            if self.is_speaking:
                # Thêm vào post_buffer trong thời gian im lặng
                self.post_buffer.append(audio_chunk)
                
                if self.silence_start_time is None:
                    self.silence_start_time = current_time
                elif current_time - self.silence_start_time >= self.silence_duration:
                    # Kết thúc nói - thêm post_buffer vào cuối
                    speech_duration = current_time - self.speech_start_time
                    if speech_duration >= self.min_speech_duration:
                        # Có đủ thời gian nói
                        # Thêm post_buffer vào cuối (nhưng chỉ lấy post_buffer_duration)
                        all_audio = self.audio_buffer + self.post_buffer
                        
                        # Chuẩn hóa biên độ âm thanh trước khi nối
                        normalized_buffers = []
                        for chunk in all_audio:
                            normalized_buffers.append(chunk)

                        audio_data = np.concatenate(normalized_buffers)

                        # Đảm bảo audio_data là mảng 1 chiều
                        if len(audio_data.shape) > 1:
                            audio_data = audio_data.flatten()

                        self.is_speaking = False
                        self.speech_start_time = None
                        self.silence_start_time = None
                        self.audio_buffer = []
                        self.post_buffer = []

                        print(f"✅ Hoàn tất thu âm ({speech_duration:.1f}s) - Tổng chunks: {len(all_audio)}")
                        return {
                            'action': 'speech_complete',
                            'audio_data': audio_data,
                            'duration': speech_duration,
                            'rms': rms
                        }
                    else:
                        # Thời gian nói quá ngắn - bỏ qua
                        print(
                            f"⚠️ Thời gian nói quá ngắn ({speech_duration:.1f}s) - bỏ qua")
                        self.is_speaking = False
                        self.speech_start_time = None
                        self.silence_start_time = None
                        self.audio_buffer = []
                        self.post_buffer = []
            else:
                # Đang im lặng và chưa phát hiện giọng nói - giữ trong pre_buffer
                # Tính số chunks cần giữ dựa trên pre_buffer_duration
                # Tính thời gian của mỗi chunk (giây)
                chunk_duration = len(audio_chunk) / self.sample_rate
                # Tính số chunks cần giữ (làm tròn lên để đảm bảo đủ thời gian)
                import math
                max_pre_chunks = max(1, math.ceil(self.pre_buffer_duration / chunk_duration))
                self.pre_buffer.append(audio_chunk)
                # Giữ pre_buffer trong giới hạn
                if len(self.pre_buffer) > max_pre_chunks:
                    self.pre_buffer = self.pre_buffer[-max_pre_chunks:]

        return {
            'action': 'listening' if not self.is_speaking else 'speaking',
            'is_speaking': self.is_speaking,
            'rms': rms,
            'speech_duration': current_time - self.speech_start_time if self.is_speaking else 0
        }
