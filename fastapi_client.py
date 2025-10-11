import os
import asyncio
import contextlib
import zmq
import zmq.asyncio
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn

app = FastAPI()
app.state.latest_jpeg = None
app.state.subscriber_task = None
app.state.zmq_socket = None

BOUNDARY = "frame"

async def zmq_subscriber(zmq_url: str):
    ctx = zmq.asyncio.Context.instance()
    sock = ctx.socket(zmq.SUB)
    try:
        sock.setsockopt(zmq.CONFLATE, 1)
    except Exception:
        pass
    sock.setsockopt(zmq.RCVHWM, 1)
    sock.setsockopt(zmq.LINGER, 0)
    sock.connect(zmq_url)
    sock.setsockopt(zmq.SUBSCRIBE, b"")
    app.state.zmq_socket = sock

    while True:
        data = await sock.recv()
        app.state.latest_jpeg = data

@app.on_event("startup")
async def on_startup():
    zmq_url = os.getenv("ZMQ_URL", "tcp://localhost:5555")
    app.state.subscriber_task = asyncio.create_task(zmq_subscriber(zmq_url))

@app.on_event("shutdown")
async def on_shutdown():
    if app.state.subscriber_task:
        app.state.subscriber_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.subscriber_task
    if app.state.zmq_socket:
        app.state.zmq_socket.close(0)

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html>
<html>
  <head><meta charset=\"utf-8\"><title>ZeroMQ MJPEG</title></head>
  <body style=\"margin:0;background:#000;display:flex;justify-content:center;align-items:center;height:100vh\">
    <img src=\"/mjpeg\" style=\"max-width:100%;height:auto;\" />
  </body>
</html>"""

async def mjpeg_generator():
    boundary = BOUNDARY.encode()
    while True:
        frame = app.state.latest_jpeg
        if frame is not None:
            headers = (
                b"--" + boundary +
                b"\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() +
                b"\r\n\r\n"
            )
            yield headers + frame + b"\r\n"
        await asyncio.sleep(0.005)

@app.get("/mjpeg")
async def mjpeg():
    return StreamingResponse(
        mjpeg_generator(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
    )

@app.get("/snapshot.jpg")
def snapshot():
    frame = app.state.latest_jpeg
    if frame is None:
        return Response(status_code=503)
    return Response(content=frame, media_type="image/jpeg")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--zmq", default="tcp://localhost:5555", help="ZeroMQ server URL (e.g. tcp://<JETSON_IP>:5555)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.environ["ZMQ_URL"] = args.zmq
    uvicorn.run("fastapi_client:app", host=args.host, port=args.port, reload=False)
