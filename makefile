.PHONY: start_mic_playback stop_mic_playback

stop_mic_playback:
	amixer -c 3 cset numid=3 off && amixer -c 3 cset numid=4 0 && echo "✅ Đã tắt Mic Playback!"