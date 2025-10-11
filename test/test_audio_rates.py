#!/usr/bin/env python3
"""
Test Audio Sample Rates
=======================
Kiểm tra sample rates được hỗ trợ bởi audio device
"""

import sounddevice as sd
import numpy as np


def test_sample_rates():
    """Test các sample rates khác nhau"""
    device_id = 12  # USB Composite Device
    test_rates = [8000, 16000, 22050, 44100, 48000, 96000]

    print("=== Testing Audio Sample Rates ===")
    print(f"Device: {device_id}")
    print()

    for rate in test_rates:
        try:
            # Test input
            with sd.InputStream(
                device=device_id,
                channels=1,
                samplerate=rate,
                dtype='int16',
                blocksize=1024
            ) as stream:
                print(f"✅ {rate}Hz - Input OK")

        except Exception as e:
            print(f"❌ {rate}Hz - Input Error: {e}")

        try:
            # Test output
            with sd.OutputStream(
                device=11,  # USB Audio Device
                channels=1,
                samplerate=rate,
                dtype='int16',
                blocksize=1024
            ) as stream:
                print(f"✅ {rate}Hz - Output OK")

        except Exception as e:
            print(f"❌ {rate}Hz - Output Error: {e}")

        print()


def get_supported_rates():
    """Lấy danh sách sample rates được hỗ trợ"""
    device_id = 12
    device_info = sd.query_devices(device_id)

    print(f"Device {device_id} info:")
    print(f"  Name: {device_info['name']}")
    print(f"  Max input channels: {device_info['max_input_channels']}")
    print(f"  Default sample rate: {device_info['default_samplerate']}")
    print(f"  Default low latency: {device_info['default_low_input_latency']}")
    print(
        f"  Default high latency: {device_info['default_high_input_latency']}")


if __name__ == "__main__":
    get_supported_rates()
    print()
    test_sample_rates()
