import asyncio
import datetime
from container import container
from mcp.server.fastmcp import FastMCP
from typing import List, Dict


from log import setup_logger
from module.camera.camera_base import Camera
from module.llm.open_ai import OpenAIAgent
from module.lane_segmentation import LaneSegmentation
from module.obstacle_detection import ObstacleDetectionSystem

mcp = FastMCP(name="PBL6_MCP_IOT")
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

if __name__ == "__main__":
    mcp.run(transport='sse')
