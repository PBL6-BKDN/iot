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

# ============ CAMERA & AI TOOLS ============

@mcp.tool()
async def describe_image() -> str:
    """
    Mô tả hình ảnh, trả về mô tả của hình ảnh
    """
    camera: Camera = container.get("camera")
    frame = camera.get_latest_frame()
    agent: OpenAIAgent = container.get("agent")
    answer = await agent.get_answer(
        question="Mô tả hình ảnh",
        image=frame
    )
    return answer

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
    """
    try:
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        if obstacle_sys is None:
            return "Lỗi: Module phát hiện vật cản chưa được khởi tạo"
        
        if obstacle_sys.is_running():
            return "⚠️ Phát hiện vật cản đã đang chạy rồi!"
        
        success = obstacle_sys.run()
        if success:
            return "Đã bật phát hiện vật cản thành công"
        else:
            return "Không thể bật phát hiện vật cản"
    except Exception as e:
        logger.error(f"Lỗi khi bật obstacle detection: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def stop_obstacle_detection() -> str:
    """
    Tắt chức năng phát hiện vật cản (Obstacle Detection).
    """
    try:
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        if obstacle_sys is None:
            return "Lỗi: Module phát hiện vật cản chưa được khởi tạo"
        
        if not obstacle_sys.is_running():
            return "⚠️ Phát hiện vật cản chưa chạy!"
        
        success = obstacle_sys.stop()
        if success:
            return "Đã tắt phát hiện vật cản thành công"
        else:
            return "Không thể tắt phát hiện vật cản"
    except Exception as e:
        logger.error(f"Lỗi khi tắt obstacle detection: {e}", exc_info=True)
        return f"Lỗi: {str(e)}"

@mcp.tool()
async def get_obstacle_detection_status() -> str:
    """
    Kiểm tra trạng thái của chức năng phát hiện vật cản.
    Trả về: đang chạy hay đã dừng, số lượng cảm biến.
    """
    try:
        obstacle_sys: ObstacleDetectionSystem = container.get("obstacle_detection_system")
        if obstacle_sys is None:
            return "Module phát hiện vật cản chưa được khởi tạo"
        
        is_running = obstacle_sys.is_running()
        status = "Đang chạy" if is_running else "Đã dừng"
        num_sensors = len(obstacle_sys.sensors) if is_running else 0
        
        return f"""📊 **Trạng thái Phát hiện Vật cản**
- Trạng thái: {status}
- Số cảm biến: {num_sensors}
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
