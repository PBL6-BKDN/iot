import asyncio
import json
import os
import uuid
import paho.mqtt.client as mqtt
from config import (
    logger, DEVICE_ID, state,
    BROKER_TRANSPORT, BROKER_WS_PATH, BROKER_USE_TLS,
    BROKER_HOST, BROKER_PORT, MQTT_USER, MQTT_PASS
)
import ssl
from webrtc_handler import initialize_peer_connection, add_ice_candidate, process_pending_candidates, answer_call

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback khi kết nối MQTT thành công.

    Compatible with paho callbacks that call either:
      on_connect(client, userdata, flags, rc)
    or (MQTT v5):
      on_connect(client, userdata, flags, rc, properties)
    """
    # `rc` is the CONNACK return code (0 = success)
    try:
        code = int(rc)
    except Exception:
        code = rc

    if code != 0:
        logger.error(f"Failed to connect to MQTT: rc={code}")
        return
    logger.info(f"MQTT Connected with reason code {code}")
    # Device should listen for signaling messages published by mobiles.
    # Subscribe to any mobile id (mobile/+/webrtc/...) so device can accept offers
    # from one or more mobile clients. QoS: offer/answer = 1, candidate = 0.
    # Avoid duplicate subscribe churn by tracking a subscribe flag on state.
    if getattr(state, 'mqtt_subscribed', False):
        logger.debug('Already subscribed to mobile topics; skipping subscribe')
        return

    topics = [
        ("mobile/+/webrtc/offer", 1),
        ("mobile/+/webrtc/answer", 1),
        ("mobile/+/webrtc/candidate", 0),
    ]
    for topic, qos in topics:
        try:
            client.subscribe(topic, qos=qos)
            logger.info(f"Subscribed to {topic} (QoS={qos})")
        except Exception as e:
            logger.error(f"Failed to subscribe to {topic}: {e}")

    state.mqtt_subscribed = True

async def handle_message_async(topic, payload):
    """Process MQTT messages asynchronously."""
    logger.info(f"Received on {topic}")
    
    # Parse JSON
    try:
        data = json.loads(payload)
        msg_type = data.get("type", "unknown")
        logger.info(f"   Message type: {msg_type}")
    except Exception as e:
        logger.warning(f"   Failed to parse JSON: {e}")
        return
    
    try:
        # Normalize topic suffix for signaling
        if topic.endswith('/webrtc/offer'):
            logger.info("Offer received (mobile -> device); preparing answer")
            # Clear any previous pending candidates
            state.pending_ice_candidates.clear()

            # Initialize PC and set remote description (the mobile's offer)
            await initialize_peer_connection()
            if state.pc:
                from aiortc import RTCSessionDescription
                try:
                    await state.pc.setRemoteDescription(
                        RTCSessionDescription(sdp=data["sdp"], type=data.get("type", "offer"))
                    )
                    logger.info("Remote description (offer) set")
                except Exception as e:
                    logger.error(f"Failed to set remote offer: {e}")
                    return

                # Process any buffered ICE candidates from mobile
                await process_pending_candidates()

                # Create and publish answer
                await answer_call()

        elif topic.endswith('/webrtc/answer'):
            logger.info("Answer received (mobile -> device)")
            if not state.pc:
                logger.warning("Received answer but no peer connection exists")
                return
            try:
                if state.pc.signalingState != 'have-local-offer':
                    if state.pc.signalingState == 'stable':
                        logger.info('Already stable; ignoring answer')
                        return
                    logger.warning(f'Ignoring answer in signalingState={state.pc.signalingState}')
                    return

                sdp = data.get('sdp')
                if state.last_remote_answer_sdp == sdp:
                    logger.info('Duplicate answer SDP; ignoring')
                    return
                from aiortc import RTCSessionDescription
                await state.pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type=data.get('type', 'answer')))
                state.last_remote_answer_sdp = sdp
                logger.info('Remote answer applied')
                await process_pending_candidates()
            except Exception as e:
                logger.error(f'Failed to apply answer: {e}')

        elif topic.endswith('/webrtc/candidate'):
            logger.info('ICE candidate received (mobile -> device)')
            # Buffer if PC not ready
            if not state.pc:
                state.pending_ice_candidates.append(data)
                logger.info(f'Buffered candidate (no PC). total={len(state.pending_ice_candidates)}')
                return

            if not state.pc.remoteDescription:
                state.pending_ice_candidates.append(data)
                logger.info(f'Buffered candidate (no remoteDescription). total={len(state.pending_ice_candidates)}')
                return

            await add_ice_candidate(data)

        else:
            logger.warning(f'Unhandled topic: {topic}')

    except Exception as e:
        logger.error(f"❌ Error handling message on {topic}: {e}", exc_info=True)

def on_message(client, userdata, msg):
    """Callback khi nhận message MQTT"""
    if state.main_loop and state.main_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            handle_message_async(msg.topic, msg.payload.decode()),
            state.main_loop,
        )
    else:
        logger.error("Main asyncio loop is not available. Dropping MQTT message.")

def asetup_mqtt_client():
    """Thiết lập MQTT client"""
    # Use hardcoded values from config.py (already set there)
    transport = BROKER_TRANSPORT
    # Allow overriding client id via env var `MQTT_CLIENT_ID`.
    # By default use the fixed `DEVICE_ID` so you can input a predictable id for testing.
    env_client_id = os.getenv("MQTT_CLIENT_ID")
    if env_client_id:
        chosen_client_id = env_client_id
    else:
        chosen_client_id = DEVICE_ID

    # Create client using the chosen client id
    try:
        # Request a persistent session on the device side as well (clean_session=False)
        client = mqtt.Client(client_id=chosen_client_id, clean_session=False, transport=transport)
    except TypeError:
        # Older paho versions may have different signature; fall back and try to force non-clean session
        client = mqtt.Client(chosen_client_id, mqtt.CallbackAPIVersion.VERSION2, transport=transport)
        try:
            # attempt to set internal flag for older clients
            setattr(client, '_clean_session', False)
        except Exception:
            pass
    # Ensure websocket path is set to the configured value
    if transport == "websockets":
        try:
            client.ws_set_options(path=BROKER_WS_PATH)
            logger.info(f"MQTT websocket path set to '{BROKER_WS_PATH}'")
        except Exception as e:
            logger.warning(f"Failed to set websocket path options: {e}")
    # Auth
    if MQTT_USER:
        try:
            client.username_pw_set(MQTT_USER, MQTT_PASS)
        except Exception:
            logger.warning("Could not apply MQTT username/password")
    # TLS: enforce based on config
    if BROKER_USE_TLS:
        try:
            client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            client.tls_insecure_set(True)
            logger.info("MQTT TLS enabled (insecure allowed)")
        except Exception as e:
            logger.warning(f"Failed to enable TLS: {e}")
    
    client.on_connect = on_connect
    client.on_message = on_message
    # Lightweight logging hooks for disconnect/subscribe
    def _on_disconnect(c, u, rc):
        logger.warning(f"MQTT disconnected with rc={rc}")
        try:
            state.mqtt_connected = False
        except Exception:
            pass

    def _on_subscribe(c, u, mid, granted_qos):
        logger.info(f"MQTT on_subscribe: mid={mid} granted_qos={granted_qos}")

    client.on_disconnect = _on_disconnect
    client.on_subscribe = _on_subscribe

    # Reconnect/backoff tuning
    try:
        client.reconnect_delay_set(min_delay=1, max_delay=120)
        logger.info("Configured client reconnect delay (min=1s max=120s)")
    except Exception:
        logger.debug("reconnect_delay_set not available in this paho-mqtt version")
    logger.info(f"MQTT client configured: client_id={chosen_client_id}, host={BROKER_HOST}, port={BROKER_PORT}, transport={transport}, ws_path={BROKER_WS_PATH}, tls={BROKER_USE_TLS}, user={MQTT_USER}")
    
    return client


def publish_device_alert(client: mqtt.Client, alert: dict):
    """Publish an alert from device to topic `device/<DEVICE_ID>/alert`"""
    try:
        topic = f"device/{DEVICE_ID}/alert"
        payload = json.dumps(alert)
        client.publish(topic, payload, qos=1)
        logger.info(f"📤 Published alert to {topic}")
    except Exception as e:
        logger.error(f"Failed to publish alert: {e}")


def publish_device_gps(client: mqtt.Client, gps: dict):
    """Publish GPS payload to `device/<DEVICE_ID>/gps`"""
    try:
        topic = f"device/{DEVICE_ID}/gps"
        payload = json.dumps(gps)
        client.publish(topic, payload, qos=1)
        logger.info(f"📤 Published GPS to {topic}")
    except Exception as e:
        logger.error(f"Failed to publish GPS: {e}")


def publish_device_log(client: mqtt.Client, record: dict):
    """Publish arbitrary log messages to `device/<DEVICE_ID>/log`"""
    try:
        topic = f"device/{DEVICE_ID}/log"
        payload = json.dumps(record)
        client.publish(topic, payload, qos=0)
        logger.info(f"📤 Published log to {topic}")
    except Exception as e:
        logger.error(f"Failed to publish log: {e}")


def publish_device_mic(client: mqtt.Client, mic_payload: bytes, seq: int = 0):
    """Publish raw/encoded mic chunks. Use QoS 0 to minimize latency.
    `mic_payload` should be bytes or base64-encoded string depending on pipeline.
    """
    try:
        topic = f"device/{DEVICE_ID}/mic"
        # If bytes, convert to base64 string
        if isinstance(mic_payload, (bytes, bytearray)):
            import base64
            payload = base64.b64encode(mic_payload).decode()
            payload_obj = {"seq": seq, "data_b64": payload}
            client.publish(topic, json.dumps(payload_obj), qos=0)
        else:
            client.publish(topic, json.dumps(mic_payload), qos=0)
        logger.info(f"📤 Published mic chunk to {topic} (seq={seq})")
    except Exception as e:
        logger.error(f"Failed to publish mic chunk: {e}")
