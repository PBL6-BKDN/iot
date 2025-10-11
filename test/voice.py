from pprint import pprint
import time
import numpy as np
from config import AUDIO_SAMPLE_RATE, MIC_INDEX
from navigation.speech.voice_mic import VoiceStreamer
from navigation.speech.voice_speaker import VoiceSpeaker

import sounddevice as sd

print('Audio devices:')
pprint([f'{i}: {device}' for i, device in enumerate(sd.query_devices())])

def demo_continuous_listening():
    devices = sd.query_devices()
    print(devices)
    """Demo lắng nghe liên tục"""
    print("=== Demo Continuous Voice Listening ===")
    speaker_service = VoiceSpeaker(speaker_name="USB Audio Device")
    print(MIC_INDEX)
    streamer = VoiceStreamer(
        MIC_INDEX, sample_rate=AUDIO_SAMPLE_RATE, chunk_duration_ms=100)

    def on_speech_start():
        print("🎤 Bắt đầu phát hiện giọng nói!")

    def on_speech_complete(audio_data, duration):
        print(f"✅ Hoàn tất thu âm: {duration:.1f}s, {len(audio_data)} bytes")

        # Phát lại âm thanh vừa thu
        print("🔊 Phát lại...")
        speaker_service.play_audio_data(
            audio_data, sample_rate=AUDIO_SAMPLE_RATE)

        # Có thể gửi qua MQTT ở đây
        # mqtt_sender.send_audio_file(audio_data)

    def on_speech_data(audio_chunk, timestamp, status):
        if status['action'] == 'speaking':
            print(
                f"🎤 Đang nói... (RMS: {status['rms']:.4f}, Duration: {status['speech_duration']:.1f}s)")

    # Thiết lập callbacks
    streamer.set_callbacks(
        on_speech_start=on_speech_start,
        on_speech_complete=on_speech_complete,
        on_speech_data=on_speech_data
    )

    try:
        # Bắt đầu lắng nghe
        streamer.start_listening()

        print("🔊 Hệ thống đang lắng nghe...")
        print("💡 Nói gì đó để bắt đầu thu âm")
        print("💡 Im lặng 5 giây để hoàn tất thu âm")
        print("💡 Nhấn Ctrl+C để dừng")

        # Giữ chương trình chạy
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n⏹️ Dừng hệ thống...")
        streamer.stop_listening()


# demo_continuous_listening()
