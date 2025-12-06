#!/usr/bin/env python3
"""Check audio devices để tìm đúng microphone index"""

import pyaudio

pa = pyaudio.PyAudio()

print("\n=== Audio Devices ===\n")

for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    name = info.get('name', 'Unknown')
    max_in = info.get('maxInputChannels', 0)
    max_out = info.get('maxOutputChannels', 0)
    default_rate = info.get('defaultSampleRate', 0)
    
    device_type = []
    if max_in > 0:
        device_type.append(f"INPUT({max_in}ch)")
    if max_out > 0:
        device_type.append(f"OUTPUT({max_out}ch)")
    
    if max_in > 0:  # Chỉ hiển thị devices có input
        print(f"Index {i}: {name}")
        print(f"  Channels: {' & '.join(device_type)}")
        print(f"  Sample Rate: {int(default_rate)} Hz")
        print()

pa.terminate()

print("✅ Done! Use the index of your USB microphone in config.py")
