
from module.voice_speaker import VoiceSpeaker
from config import BASE_DIR
import os

speaker_service = VoiceSpeaker(speaker_name="USB Audio Device")
file_path = os.path.join(BASE_DIR, "audio", "stop.wav") 
speaker_service.play_file(file_path)
