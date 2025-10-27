import asyncio
import json
import logging
import platform
import sys
import threading
from collections import deque

import aioice.stun
import paho.mqtt.client as mqtt
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer

try:
    from aiortc.sdp import candidate_from_sdp
except Exception:
    candidate_from_sdp = None

# Fix STUN private address check
def is_private_address(addr):
    if addr.startswith("10.") or addr.startswith("192.168."):
        return True
    if addr.startswith("172."):
        try:
            second_octet = int(addr.split(".")[1])
            return 16 <= second_octet <= 31
        except:
            return False
    return False

aioice.stun.is_private_address = is_private_address

# --- Cấu hình logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc_simulator")

# --- Biến toàn cục ---
client = None
pc = None
player = None
DEVICE_ID = "jetson"
MAIN_LOOP: asyncio.AbstractEventLoop | None = None
pending_ice_candidates = deque()

def on_connect(client, userdata, flags, reason_code, properties):
    if getattr(reason_code, "is_failure", False):
        logger.error(f"Failed to connect to MQTT: {reason_code}")
        return
    logger.info(f"MQTT Connected with reason code {reason_code}")
    topics = [
        f"mobile/{DEVICE_ID}/webrtc/offer",
        f"mobile/{DEVICE_ID}/webrtc/answer",
        f"mobile/{DEVICE_ID}/webrtc/candidate",
    ]
    for topic in topics:
        client.subscribe(topic)
        logger.info(f"Subscribed to {topic}")

async def process_pending_candidates():
    """Xử lý tất cả ICE candidates đang chờ"""
    global pc, pending_ice_candidates
    
    if not pc or not pc.remoteDescription:
        return
    
    processed = 0
    while pending_ice_candidates:
        data = pending_ice_candidates.popleft()
        try:
            await add_ice_candidate(data)
            processed += 1
        except Exception as e:
            logger.error(f"Error processing pending candidate: {e}")
    
    if processed > 0:
        logger.info(f"✅ Processed {processed} pending ICE candidates")

async def add_ice_candidate(data):
    """Thêm ICE candidate vào peer connection"""
    global pc
    
    if not data or not data.get("candidate"):
        logger.debug("Received empty ICE candidate (end-of-candidates)")
        return
    
    try:
        candidate_str = data.get("candidate")
        sdp_mid = data.get("sdpMid")
        sdp_mline_index = data.get("sdpMLineIndex")

        if candidate_str and candidate_from_sdp:
            parsed = candidate_from_sdp(candidate_str)
            parsed.sdpMid = sdp_mid
            parsed.sdpMLineIndex = sdp_mline_index
            await pc.addIceCandidate(parsed)
            
            # Log chi tiết loại candidate
            if "typ relay" in candidate_str:
                logger.info(f"🔄 RELAY candidate added: {candidate_str[:80]}...")
            elif "typ srflx" in candidate_str:
                logger.info(f"🌐 SRFLX candidate added: {candidate_str[:80]}...")
            elif "typ host" in candidate_str:
                logger.info(f"🏠 HOST candidate added: {candidate_str[:80]}...")
            else:
                logger.info(f"✅ ICE candidate added: {candidate_str[:60]}...")
        else:
            logger.warning(f"Cannot parse ICE candidate: {candidate_str[:50]}...")
    except Exception as e:
        logger.error(f"Failed to add ICE candidate: {e}")

async def handle_message_async(topic, payload):
    global pc, pending_ice_candidates
    logger.info(f"📨 Received on {topic}")
    
    try:
        data = json.loads(payload)

        if topic.endswith("/webrtc/offer"):
            logger.info("📞 Received offer from mobile, preparing answer...")
            pending_ice_candidates.clear()
            
            await initialize_peer_connection()
            if pc:
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                )
                logger.info("✅ Remote description set successfully.")
                
                await process_pending_candidates()
                await answer_call()

        elif topic.endswith("/webrtc/answer"):
            if pc:
                logger.info("📞 Received answer from mobile.")
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                )
                logger.info("✅ Remote description set successfully.")
                await process_pending_candidates()

        elif topic.endswith("/webrtc/candidate"):
            if not pc:
                logger.warning("⚠️ ICE candidate received but PeerConnection not ready.")
                return
            
            if not pc.remoteDescription:
                logger.warning("⚠️ ICE candidate buffered (waiting for remote description)")
                pending_ice_candidates.append(data)
                return
            
            await add_ice_candidate(data)

    except Exception as e:
        logger.error(f"❌ Error handling message on {topic}: {e}", exc_info=True)

def on_message(client, userdata, msg):
    if MAIN_LOOP and MAIN_LOOP.is_running():
        asyncio.run_coroutine_threadsafe(
            handle_message_async(msg.topic, msg.payload.decode()),
            MAIN_LOOP,
        )
    else:
        logger.error("Main asyncio loop is not available. Dropping MQTT message.")

async def initialize_peer_connection():
    global pc, player
    
    if pc and pc.connectionState != "closed":
        await pc.close()
    if player:
        try:
            player.stop()
        except Exception:
            pass

    # Configure camera
    options = {"framerate": "30", "video_size": "640x480"}
    if platform.system() == "Windows":
        try:
            player = MediaPlayer("video=Integrated Webcam", format="dshow", options=options)
        except Exception as e:
            logger.warning(f"Could not open 'Integrated Webcam' ({e}). Please check your camera name.")
            return
    elif platform.system() == "Darwin":
        player = MediaPlayer("default:none", format="avfoundation", options=options)
    else:
        # Linux (Jetson Nano)
        camera_devices = ["/dev/video0", "/dev/video1"]
        player = None
        
        for device in camera_devices:
            try:
                player = MediaPlayer(device, format="v4l2", options=options)
                logger.info(f"📹 Using camera at {device}")
                break
            except Exception as e:
                logger.warning(f"Could not open {device}: {e}")
        
        if not player:
            logger.error("❌ Could not open any camera device!")
            return

    # Create peer connection with UPDATED ICE servers
    try:
        from aiortc import RTCConfiguration, RTCIceServer
        
        # Sử dụng nhiều TURN servers khác nhau để tăng khả năng kết nối
        ice_servers = [
            # Google STUN (luôn reliable)
            RTCIceServer(urls=[
                "stun:stun.l.google.com:19302",
                "stun:stun1.l.google.com:19302",
            ]),
            # ExpressTurn TURN Server (Your credentials) - UDP + TCP + TLS
            RTCIceServer(
                urls=[
                    "turn:relay1.expressturn.com:3478",
                    "turn:relay1.expressturn.com:3478?transport=tcp",
                    "turns:relay1.expressturn.com:5349",
                ],
                username="000000002076506456",
                credential="bK8A/K+WGDw/tYcuvM9/5xCnEZs=",
            ),
            # Twilio STUN/TURN (public free tier)
            RTCIceServer(
                urls=[
                    "turn:global.turn.twilio.com:3478?transport=udp",
                    "turn:global.turn.twilio.com:3478?transport=tcp",
                    "turn:global.turn.twilio.com:443?transport=tcp",
                ],
                username="f4b4035eaa76f4a55de5f4351567653ee4ff6fa97b50b6b334fcc1be9c27212d",
                credential="w1uxM55V9yVoqyVFjt+mxDBV0F87AUCemaYVQGxsPLw=",
            ),
        ]
        
        pc = RTCPeerConnection(
            configuration=RTCConfiguration(iceServers=ice_servers)
        )
        logger.info("✅ RTCPeerConnection created with ICE servers")
        logger.info(f"   - {len(ice_servers)} ICE servers configured")
        logger.info("   Note: aiortc does not support iceTransportPolicy, will try all candidates")
        
    except Exception as e:
        logger.error(f"❌ Failed to create PC with ICE config: {e}")
        pc = RTCPeerConnection()

    # Add video track
    if player and player.video:
        logger.info("✅ Webcam opened successfully.")
        pc.addTrack(player.video)
    else:
        logger.error("❌ COULD NOT OPEN WEBCAM.")
        return

    # Event handlers with detailed logging
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        state = pc.connectionState
        emoji = {"new": "🆕", "connecting": "🔄", "connected": "✅", "disconnected": "⚠️", "failed": "❌", "closed": "🔒"}
        logger.info(f"{emoji.get(state, '❓')} Connection state: {state}")
        
        if state == "failed":
            logger.error("❌ WebRTC connection FAILED!")
            logger.error("💡 Troubleshooting tips:")
            logger.error("   1. Check if mobile app has internet connection")
            logger.error("   2. Try using mobile data instead of WiFi (or vice versa)")
            logger.error("   3. Check firewall settings on both devices")
            logger.error("   4. Ensure both devices can reach TURN servers")
        elif state == "connected":
            logger.info("🎉 WebRTC connection ESTABLISHED!")

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        state = pc.iceConnectionState
        emoji = {"new": "🆕", "checking": "🔍", "connected": "✅", "completed": "🏁", "failed": "❌", "disconnected": "⚠️", "closed": "🔒"}
        logger.info(f"{emoji.get(state, '❓')} ICE connection state: {state}")

    @pc.on("icegatheringstatechange")
    async def on_icegatheringstatechange():
        state = pc.iceGatheringState
        logger.info(f"📡 ICE gathering state: {state}")

    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            cand_str = candidate.candidate
            
            # Log với emoji tùy loại
            if "typ relay" in cand_str:
                logger.info(f"🔄 RELAY candidate (TURN): {cand_str[:80]}...")
            elif "typ srflx" in cand_str:
                logger.info(f"🌐 SRFLX candidate (STUN): {cand_str[:80]}...")
            elif "typ host" in cand_str:
                logger.info(f"🏠 HOST candidate (Local): {cand_str[:80]}...")
            else:
                logger.info(f"🎯 ICE candidate: {cand_str[:80]}...")
            
            payload = json.dumps({
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex,
            })
            topic = f"device/{DEVICE_ID}/webrtc/candidate"
            client.publish(topic, payload)
            logger.info(f"📤 Published ICE candidate to {topic}")
        else:
            logger.info("🏁 ICE candidate gathering complete (end-of-candidates)")

async def start_sos_call():
    """Khởi tạo cuộc gọi từ device"""
    global pc, pending_ice_candidates
    
    if pc and pc.connectionState != "closed":
        logger.warning("⚠️ Connection already exists, skipping...")
        return

    logger.info("🆘 Starting SOS call...")
    pending_ice_candidates.clear()
    await initialize_peer_connection()
    
    if pc:
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        payload = json.dumps({"sdp": offer.sdp, "type": offer.type})
        client.publish(f"device/{DEVICE_ID}/webrtc/offer", payload)
        logger.info("📤 Offer published to MQTT")

async def answer_call():
    """Trả lời cuộc gọi từ mobile"""
    global pc
    
    if pc:
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        payload = json.dumps({"sdp": answer.sdp, "type": answer.type})
        client.publish(f"device/{DEVICE_ID}/webrtc/answer", payload)
        logger.info("📤 Answer published to MQTT")

async def main():
    global client, MAIN_LOOP
    
    # Setup MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
    try:
        client.ws_set_options(path="/mqtt")
    except Exception:
        pass
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    logger.info("🔌 Connecting to MQTT broker...")
    client.connect("broker.hivemq.com", 8000, 60)

    MAIN_LOOP = asyncio.get_running_loop()
    client.loop_start()

    # Setup user input handler
    sos_requested = asyncio.Event()

    def user_input_handler():
        while True:
            try:
                sys.stdin.readline()
                MAIN_LOOP.call_soon_threadsafe(sos_requested.set)
            except (KeyboardInterrupt, EOFError):
                break

    input_thread = threading.Thread(target=user_input_handler, daemon=True)
    input_thread.start()

    print("\n" + "="*60)
    print("🚀 WebRTC Video Call Simulator (Jetson Nano)")
    print("="*60)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"🌐 MQTT Broker: broker.hivemq.com:8000")
    print("📹 Press Enter to START SOS call (Device -> Mobile)")
    print("📞 Also listening for incoming calls from Mobile...")
    print("="*60 + "\n")

    try:
        while True:
            if sos_requested.is_set():
                await start_sos_call()
                sos_requested.clear()

            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("🛑 Shutting down...")
        if player:
            try:
                player.stop()
            except Exception:
                pass
        if pc:
            await pc.close()
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Simulator stopped by user.")