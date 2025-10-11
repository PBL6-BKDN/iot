sudo systemctl restart nvargus-daemon
pkill -f camera_server.py || true
sleep 2
env -u DISPLAY python3 camera_server.py &
SERVER_PID=$!
sleep 4
python3 camera_client.py
kill $SERVER_PID