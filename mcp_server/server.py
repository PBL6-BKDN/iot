import asyncio
import datetime
import cv2
import numpy as np
from config import SERVER_HTTP_BASE
from container import container
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from typing import List, Dict

import httpx
from log import setup_logger
from module.camera.camera_base import Camera
from module.llm.open_ai import OpenAIAgent
from module.lane_segmentation import LaneSegmentation
from module.obstacle_detection import ObstacleDetectionSystem

mcp = FastMCP(name="PBL6_MCP_IOT")

# Cho phép domain bên ngoài (vd: mcp.phuocnguyn.id.vn) truy cập SSE
# và bỏ chặn Invalid Host header
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "mcp.phuocnguyn.id.vn",
        "mcp.phuocnguyn.id.vn:3000",
        "localhost",
        "127.0.0.1",
        "::1",
    ],
    allowed_origins=[
        "https://mcp.phuocnguyn.id.vn",
        "http://mcp.phuocnguyn.id.vn",
    ],
)
logger = setup_logger(__name__)

# ============ CAMERA TOOLS ============

@mcp.tool()
async def start_camera() -> str:
    """
    Bật camera. Camera sẽ bắt đầu capture frames và lưu vào shared memory.
    """
    try:
        camera = container.get("camera")
        if camera is None:
            return "Lỗi: Camera chưa được khởi tạo"
        
        if camera.is_running():
            return "⚠️ Camera đã đang chạy rồi!"
        
        camera.run()
        return "✅ Đã bật camera thành công"
    except Exception as e:
        logger.error(f"Lỗi khi bật camera: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def stop_camera() -> str:
    """
    Tắt camera và giải phóng tài nguyên.
    Lưu ý: Các module phụ thuộc vào camera (Lane Segmentation) cũng sẽ ngừng hoạt động.
    """
    try:
        camera = container.get("camera")
        if camera is None:
            return "Lỗi: Camera chưa được khởi tạo"
        
        if not camera.is_running():
            return "⚠️ Camera chưa chạy!"
        
        camera.stop()
        return "✅ Đã tắt camera thành công"
    except Exception as e:
        logger.error(f"Lỗi khi tắt camera: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def get_camera_status() -> str:
    """
    Kiểm tra trạng thái của camera.
    """
    try:
        camera = container.get("camera")
        if camera is None:
            return "Camera chưa được khởi tạo"
        
        is_running = camera.is_running()
        stats = camera.get_stats()
        status = "🟢 Đang chạy" if is_running else "🔴 Đã dừng"
        
        return f"""📷 **Trạng thái Camera**
- Trạng thái: {status}
- Target FPS: {stats.get('target_fps', 'N/A')}
- Camera ID: {stats.get('camera_id', 'N/A')}
"""
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra camera status: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

# ============ LANE SEGMENTATION TOOLS ============

@mcp.tool()
async def start_lane_segmentation() -> str:
    """
    Bật chức năng phân đoạn làn đường (Lane Segmentation).
    Hệ thống sẽ tự động phát hiện và phân tích làn đường từ camera.
    """
    try:
        lane_seg: LaneSegmentation = container.get("lane_segmentation")
        if lane_seg is None:
            return "Lỗi: Module phân đoạn làn đường chưa được khởi tạo"
        
        if lane_seg.is_running():
            return "⚠️ Phân đoạn làn đường đã đang chạy rồi!"
        
        success = lane_seg.run()
        if success:
            return "Đã bật phân đoạn làn đường thành công"
        else:
            return "Không thể bật phân đoạn làn đường"
    except Exception as e:
        logger.error(f"Lỗi khi bật lane segmentation: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def stop_lane_segmentation() -> str:
    """
    Tắt chức năng phân đoạn làn đường (Lane Segmentation).
    """
    try:
        lane_seg: LaneSegmentation = container.get("lane_segmentation")
        if lane_seg is None:
            return "Lỗi: Module phân đoạn làn đường chưa được khởi tạo"
        
        if not lane_seg.is_running():
            return "⚠️ Phân đoạn làn đường chưa chạy!"
        
        success = lane_seg.stop()
        if success:
            return "Đã tắt phân đoạn làn đường thành công"
        else:
            return "Không thể tắt phân đoạn làn đường"
    except Exception as e:
        logger.error(f"Lỗi khi tắt lane segmentation: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def get_lane_segmentation_status() -> str:
    """
    Kiểm tra trạng thái của chức năng phân đoạn làn đường.
    Trả về: đang chạy hay đã dừng.
    """
    try:
        lane_seg: LaneSegmentation = container.get("lane_segmentation")
        if lane_seg is None:
            return "Module phân đoạn làn đường chưa được khởi tạo"
        
        is_running = lane_seg.is_running()
        status = "Đang chạy" if is_running else "Đã dừng"
        interval = lane_seg.adaptive_interval if is_running else 0
        
        return f"""📊 **Trạng thái Phân đoạn Làn đường**
- Trạng thái: {status}
- Interval hiện tại: {interval:.1f}s
"""
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra lane segmentation status: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

# ============ OBSTACLE DETECTION TOOLS ============

@mcp.tool()
async def start_obstacle_detection() -> str:
    """
    Bật chức năng phát hiện vật cản (Obstacle Detection).
    Hệ thống sẽ sử dụng cảm biến ToF để phát hiện vật cản và cảnh báo.
    Lưu ý: Worker process phải đang chạy (sensors đã sẵn sàng).
    """
    try:
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        if obstacle_sys is None:
            return "Lỗi: Module phát hiện vật cản chưa được khởi tạo"
        
        # Kiểm tra worker process có đang chạy không
        if not obstacle_sys.is_running():
            return "⚠️ Worker process chưa chạy! Sensors chưa sẵn sàng."
        
        if obstacle_sys.is_detection_enabled():
            return "⚠️ Phát hiện vật cản đã đang bật rồi!"
        
        obstacle_sys.enable_detection()
        return "✅ Đã BẬT phát hiện vật cản"
    except Exception as e:
        logger.error(f"Lỗi khi bật obstacle detection: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def stop_obstacle_detection() -> str:
    """
    Tắt chức năng phát hiện vật cản (Obstacle Detection).
    Sensors vẫn hoạt động và sẵn sàng để bật lại.
    """
    try:
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        if obstacle_sys is None:
            return "Lỗi: Module phát hiện vật cản chưa được khởi tạo"
        
        if not obstacle_sys.is_detection_enabled():
            return "⚠️ Phát hiện vật cản đã tắt rồi!"
        
        obstacle_sys.disable_detection()
        return "✅ Đã TẮT phát hiện vật cản (sensors vẫn sẵn sàng)"
    except Exception as e:
        logger.error(f"Lỗi khi tắt obstacle detection: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def get_obstacle_detection_status() -> str:
    """
    Kiểm tra trạng thái của chức năng phát hiện vật cản.
    Trả về: trạng thái worker, detection enabled, số lượng cảm biến.
    """
    try:
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        if obstacle_sys is None:
            return "Module phát hiện vật cản chưa được khởi tạo"
        
        worker_running = obstacle_sys.is_running()
        detection_enabled = obstacle_sys.is_detection_enabled() if worker_running else False
        worker_status = "🟢 Đang chạy" if worker_running else "🔴 Đã dừng"
        detection_status = "🟢 BẬT" if detection_enabled else "🔴 TẮT"
        
        return f"""📊 **Trạng thái Phát hiện Vật cản**
- Worker Process: {worker_status}
- Detection: {detection_status}
- Alert interval: {obstacle_sys.alert_interval}s
"""
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra obstacle detection status: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

# ============ SYSTEM STATUS TOOL ============

@mcp.tool()
async def get_all_system_status() -> str:
    """
    Lấy trạng thái tổng quan của tất cả các hệ thống
    """
    try:
        status_parts = []
        
        # Camera status
        camera: Camera = container.get("camera")
        cam_status = "Đang chạy" if (camera and camera.is_running()) else "Đã dừng"
        status_parts.append(f"📷 Camera: {cam_status}")
        
        # Lane Segmentation status
        lane_seg: LaneSegmentation = container.get("lane_segmentation")
        lane_status = "Đang chạy" if (lane_seg and lane_seg.is_running()) else "Đã dừng"
        status_parts.append(f"Phân đoạn làn đường: {lane_status}")
        
        # Obstacle Detection status
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        obs_status = "Đang chạy" if (obstacle_sys and obstacle_sys.is_running()) else "Đã dừng"
        status_parts.append(f"Phát hiện vật cản: {obs_status}")
        
        return "**Trạng thái Hệ thống**\n" + "\n".join(status_parts)
    except Exception as e:
        logger.error(f"Lỗi khi lấy system status: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def initiate_sos_call() -> str:
    """
    Khởi tạo cuộc gọi từ thiết bị đến người thân không cần số điện thoại
    """
    try:
        # Lấy MessageHandler từ container
        from mqtt.handlers import MessageHandler
        message_handler: MessageHandler = container.get("message_handler")
        
        if message_handler is None:
            logger.error("MessageHandler chưa được khởi tạo")
            return "Lỗi: MessageHandler chưa được khởi tạo"
        
        # Gọi hàm initiate_sos_call thông qua WebRTC event loop
        # Vì hàm này là async và cần chạy trong WebRTC event loop
        future = message_handler.webrtc.run_async(
            message_handler.initiate_sos_call()
        )
        logger.info(f"Future: {future}")
        if future:
            try:
                result = future.result(timeout=30)  # Timeout 30 giây (tăng từ 10s để đủ thời gian cho ICE gathering)
                logger.info("Đã lấy kết quả cuộc gọi")
                if result:
                    return "Đã khởi tạo cuộc gọi từ thiết bị đến người thân thành công"
                else:
                    return "Không thể khởi tạo cuộc gọi. Vui lòng thử lại."
            except Exception as e:
                logger.error(f"Lỗi khi chờ kết quả SOS call: {e}", exc_info=True)
                return f"Đã khởi tạo cuộc gọi nhưng có lỗi: {str(e)}"
        else:
            return "Không thể khởi tạo event loop cho cuộc gọi"
    except ValueError as e:
        logger.error(f"MessageHandler chưa được đăng ký trong container: {e}", exc_info=True)
        return "Lỗi: MessageHandler chưa được khởi tạo. Vui lòng đảm bảo MQTT client đã được khởi động."
    except Exception as e:
        logger.error(f"Lỗi khi khởi tạo SOS call: {e}", exc_info=True)
        return f"Lỗi khi khởi tạo cuộc gọi từ thiết bị đến người thân: {str(e)}"
        
@mcp.tool()
async def image_captioning() -> str:
    """Mô tả hình ảnh trước mặt của người dùng bằng ngôn ngữ tự nhiên"""
    try:
        camera: Camera = container.get("camera")
        if camera is None:
            return "Lỗi: Camera chưa được khởi tạo"
        
        frame = camera.get_latest_frame()
        if frame is None:
            return "Lỗi: Không có frame nào từ camera"
        
        # Encode numpy array (BGR) thành JPEG bytes
        success, encoded_image = cv2.imencode('.jpg', frame)
        if not success:
            return "Lỗi: Không thể encode hình ảnh"
        
        image_bytes = encoded_image.tobytes()
        
        # Gửi request đến API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{SERVER_HTTP_BASE}/image-captioning",
                files={
                    "image": (f"image_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg", image_bytes, "image/jpeg")
                }
            )
            response.raise_for_status()  # Ném exception nếu status code không phải 2xx
            result = response.json()
            
            if "error" in result:
                return f"Lỗi từ API: {result['error']}"
            
            return result.get("caption", "Không có mô tả")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"Lỗi HTTP khi gọi API image-captioning: {e}", exc_info=True)
        return f"Lỗi HTTP {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e:
        logger.error(f"Lỗi kết nối đến API image-captioning: {e}", exc_info=True)
        return f"Lỗi kết nối: {str(e)}"
    except Exception as e:
        logger.error(f"Lỗi khi xử lý image captioning: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"
    
if __name__ == "__main__":
    mcp.run(transport='sse')
