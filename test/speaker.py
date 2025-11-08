
from module.voice_speaker import VoiceSpeaker

speaker_service = VoiceSpeaker(speaker_name="USB Audio Device")
speaker_service.play_file(
    "/home/jetson/Documents/iot/audio/stop.wav")
