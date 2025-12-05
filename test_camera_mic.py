#!/usr/bin/env python3
"""
Test Camera và Microphone
=========================
Kiểm tra xem camera và mic có hoạt động đúng không
"""

import cv2
import numpy as np
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from container import container
from config import MIC_INDEX, AUDIO_SAMPLE_RATE
from module.camera.camera_direct import CameraDirect

def test_camera():
    """Test camera"""
    print("\n" + "="*60)
    print("🎥 TESTING CAMERA")
    print("="*60)
    
    try:
        # Test 1: Kiểm tra camera có tồn tại không
        print("\n1️⃣ Checking camera devices...")
        import glob
        video_devices = glob.glob('/dev/video*')
        print(f"   Found video devices: {video_devices}")
        
        if not video_devices:
            print("   ❌ No video devices found!")
            return False
        
        # Test 2: Mở camera bằng OpenCV
        print("\n2️⃣ Opening camera with OpenCV...")
        camera = CameraDirect(camera_id=0, width=640, height=480, fps=30)
        
        if not camera.is_running():
            print("   ❌ Camera thread not running!")
            return False
        
        print("   ✅ Camera opened successfully")
        
        # Test 3: Đọc frames
        print("\n3️⃣ Reading frames from camera...")
        frame_count = 0
        start_time = time.time()
        timeout = 5  # 5 seconds
        
        while time.time() - start_time < timeout:
            frame = camera.get_latest_frame()
            if frame is not None:
                frame_count += 1
                height, width = frame.shape[:2]
                print(f"   ✅ Frame {frame_count}: {width}x{height}, dtype={frame.dtype}")
                
                if frame_count >= 10:  # Đọc 10 frames là đủ
                    break
            else:
                print("   ⏳ Waiting for frame...")
                time.sleep(0.5)
        
        camera.stop()
        
        if frame_count == 0:
            print("   ❌ No frames received from camera!")
            return False
        
        print(f"   ✅ Successfully read {frame_count} frames")
        
        # Test 4: Kiểm tra container
        print("\n4️⃣ Checking camera in container...")
        try:
            cam_from_container = container.get("camera")
            if cam_from_container:
                print("   ✅ Camera found in container")
                test_frame = cam_from_container.get_latest_frame()
                if test_frame is not None:
                    print(f"   ✅ Can read frame from container camera: {test_frame.shape}")
                else:
                    print("   ⚠️ Container camera exists but no frame available")
            else:
                print("   ⚠️ Camera not found in container (may need to initialize)")
        except Exception as e:
            print(f"   ⚠️ Container check failed: {e}")
        
        print("\n✅ CAMERA TEST PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ CAMERA TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_microphone():
    """Test microphone"""
    print("\n" + "="*60)
    print("🎤 TESTING MICROPHONE")
    print("="*60)
    
    try:
        # Test 1: Kiểm tra sounddevice
        print("\n1️⃣ Checking sounddevice...")
        try:
            import sounddevice as sd
            print("   ✅ sounddevice imported successfully")
        except ImportError:
            print("   ❌ sounddevice not installed! Run: pip install sounddevice")
            return False
        
        # Test 2: Liệt kê audio devices
        print("\n2️⃣ Listing audio devices...")
        devices = sd.query_devices()
        print(f"   Found {len(devices)} audio devices:")
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                print(f"      [{i}] {device['name']} - Input: {device['max_input_channels']}ch, Rate: {device['default_samplerate']}Hz")
        
        # Test 3: Kiểm tra device index
        print(f"\n3️⃣ Checking microphone index {MIC_INDEX}...")
        try:
            device_info = sd.query_devices(MIC_INDEX)
            print(f"   Device: {device_info['name']}")
            print(f"   Input channels: {device_info['max_input_channels']}")
            print(f"   Default sample rate: {device_info['default_samplerate']}Hz")
            
            if device_info['max_input_channels'] == 0:
                print("   ❌ Device has no input channels!")
                return False
        except Exception as e:
            print(f"   ❌ Cannot access device {MIC_INDEX}: {e}")
            return False
        
        # Test 4: Test recording
        print(f"\n4️⃣ Testing microphone recording (sample_rate={AUDIO_SAMPLE_RATE})...")
        duration = 2  # 2 seconds
        print(f"   Recording for {duration} seconds... (speak into mic)")
        
        try:
            recording = sd.rec(
                int(AUDIO_SAMPLE_RATE * duration),
                samplerate=AUDIO_SAMPLE_RATE,
                channels=1,
                dtype='int16',
                device=MIC_INDEX
            )
            sd.wait()  # Wait until recording is finished
            
            # Analyze audio
            audio_data = recording.reshape(-1)
            max_amplitude = np.max(np.abs(audio_data))
            rms = np.sqrt(np.mean(audio_data.astype(np.float32) ** 2))
            
            print(f"   ✅ Recording completed")
            print(f"   Max amplitude: {max_amplitude}")
            print(f"   RMS level: {rms:.0f}")
            
            if max_amplitude < 100:
                print("   ⚠️ Very low audio level - mic may not be working or too quiet")
            elif max_amplitude > 30000:
                print("   ⚠️ Very high audio level - may be clipping")
            else:
                print("   ✅ Audio levels look good")
                
        except Exception as e:
            print(f"   ❌ Recording failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 5: Test stream (như trong WebRTC)
        print(f"\n5️⃣ Testing microphone stream (like WebRTC)...")
        try:
            samples_per_frame = int(AUDIO_SAMPLE_RATE * 0.02)  # 20ms
            
            def audio_callback(indata, frames, time_info, status):
                if status:
                    print(f"   ⚠️ Audio callback status: {status}")
                max_amp = np.max(np.abs(indata))
                if max_amp > 1000:  # Only log if there's significant audio
                    print(f"   🔊 Audio received: max={max_amp:.0f}, frames={frames}")
            
            print(f"   Opening stream (blocksize={samples_per_frame})...")
            with sd.InputStream(
                device=MIC_INDEX,
                channels=1,
                samplerate=AUDIO_SAMPLE_RATE,
                dtype='int16',
                blocksize=samples_per_frame,
                callback=audio_callback
            ) as stream:
                print("   ✅ Stream opened successfully")
                print("   Listening for 3 seconds... (speak into mic)")
                time.sleep(3)
                print("   ✅ Stream test completed")
                
        except Exception as e:
            print(f"   ❌ Stream test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n✅ MICROPHONE TEST PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ MICROPHONE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_concurrent_access():
    """Test xem camera/mic có bị conflict không"""
    print("\n" + "="*60)
    print("🔍 TESTING CONCURRENT ACCESS")
    print("="*60)
    
    try:
        import subprocess
        
        # Check if camera is being used by another process
        print("\n1️⃣ Checking camera usage...")
        result = subprocess.run(
            ['lsof', '/dev/video0'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout:
            print("   ⚠️ Camera is being used by:")
            print(result.stdout)
        else:
            print("   ✅ Camera is not being used by other processes")
        
        # Check audio devices
        print("\n2️⃣ Checking audio device usage...")
        try:
            import sounddevice as sd
            # Try to open device exclusively
            test_stream = sd.InputStream(
                device=MIC_INDEX,
                channels=1,
                samplerate=44100,
                dtype='int16',
                blocksize=960
            )
            test_stream.close()
            print("   ✅ Microphone is available")
        except Exception as e:
            print(f"   ⚠️ Microphone may be in use: {e}")
        
        return True
        
    except Exception as e:
        print(f"   ⚠️ Concurrent access check failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 CAMERA & MICROPHONE DIAGNOSTIC TEST")
    print("="*60)
    
    results = {
        'camera': False,
        'microphone': False,
        'concurrent': False
    }
    
    # Test camera
    results['camera'] = test_camera()
    
    # Test microphone
    results['microphone'] = test_microphone()
    
    # Test concurrent access
    results['concurrent'] = test_concurrent_access()
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Camera:        {'✅ PASS' if results['camera'] else '❌ FAIL'}")
    print(f"Microphone:    {'✅ PASS' if results['microphone'] else '❌ FAIL'}")
    print(f"Concurrent:    {'✅ PASS' if results['concurrent'] else '⚠️ WARN'}")
    
    if results['camera'] and results['microphone']:
        print("\n✅ All critical tests passed!")
        print("💡 Camera and microphone are working correctly.")
        print("   If WebRTC still fails, the issue is likely in network/ICE configuration.")
    else:
        print("\n❌ Some tests failed!")
        print("💡 Fix camera/microphone issues before testing WebRTC.")
    
    return results['camera'] and results['microphone']


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

