
from navigation.speech.voice_speaker import VoiceSpeaker


speaker_service = VoiceSpeaker(speaker_name="USB Audio Device")
speaker_service.play_file(
    "/home/jetson/AI/debug/audio_response_from_server.wav")
