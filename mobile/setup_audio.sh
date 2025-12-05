#!/bin/bash
# Setup audio devices for Jetson Nano WebRTC

echo "🔊 Setting up USB Audio Device (card 3)..."

# Unmute and set volume to 100% for Speaker
amixer -c 3 set Speaker 100% unmute 2>/dev/null
echo "✅ Speaker volume set to 100%"

# Unmute and set volume to 100% for Mic
amixer -c 3 set Mic 100% unmute 2>/dev/null
echo "✅ Microphone volume set to 100%"

# Enable Auto Gain Control to reduce noise and normalize levels
amixer -c 3 set 'Auto Gain Control' on 2>/dev/null && echo "✅ Auto Gain Control enabled"

echo ""
echo "🎵 Audio setup complete!"
echo "   Device: USB Audio Device (card 3)"
echo "   Speaker: hw:3,0"
echo "   Microphone: hw:3,0"
echo ""
echo "💡 Note: Card 3 is used for both input and output"
