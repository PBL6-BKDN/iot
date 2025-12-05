# Phân tích lỗi WebRTC SOS Call

## Tóm tắt các lỗi chính

### 1. 🔴 PyAudio Device Unavailable (Lỗi nghiêm trọng)

**Vị trí**: Dòng 722-792, 850-972 trong log

**Lỗi**: 
```
OSError: [Errno -9985] Device unavailable
Expression 'AlsaOpen' failed in 'src/hostapi/alsa/pa_linux_alsa.c'
```

**Nguyên nhân**:
- Audio device (USB mic) đang bị chiếm bởi VAD (Voice Activity Detection)
- Mặc dù đã pause VAD và đợi 0.5s, device chưa được release hoàn toàn
- Có thể cần thời gian lâu hơn hoặc cần force close stream

**Ảnh hưởng**:
- ❌ Không thể tạo audio track cho WebRTC
- ❌ Cuộc gọi thiếu audio input
- ⚠️ Retry 3 lần nhưng vẫn fail

**Giải pháp đề xuất**:
1. Tăng thời gian đợi sau khi pause VAD (từ 0.5s → 1-2s)
2. Thêm logic kiểm tra device availability trước khi tạo track
3. Force close và release device trước khi pause VAD
4. Thêm fallback: nếu không có audio, vẫn cho phép cuộc gọi với video only

---

### 2. ⏱️ TimeoutError trong MCP Server (Lỗi nghiêm trọng)

**Vị trí**: Dòng 762-768, 942-948

**Lỗi**:
```python
concurrent.futures._base.TimeoutError
File "/home/jetson/iot/mcp_server/server.py", line 226
    result = future.result(timeout=10)  # Timeout 10 giây
```

**Nguyên nhân**:
- Hàm `initiate_sos_call()` không hoàn thành trong 10 giây
- Có thể do:
  - Chờ ICE gathering (có thể mất >10s trong mạng phức tạp)
  - Retry audio track (3 lần × 0.5s = 1.5s)
  - Xử lý async bị block hoặc chờ đợi lâu

**Ảnh hưởng**:
- ❌ MCP tool trả về lỗi timeout
- ⚠️ Cuộc gọi có thể đã được khởi tạo nhưng không biết kết quả

**Giải pháp đề xuất**:
1. Tăng timeout từ 10s → 30s (ICE gathering có thể mất lâu)
2. Không chờ kết quả, chỉ trigger và return ngay (fire-and-forget)
3. Sử dụng callback để báo kết quả sau
4. Thêm polling mechanism để check status

---

### 3. ⚠️ Local Description không được set (Lỗi logic)

**Vị trí**: Dòng 798, 996

**Cảnh báo**:
```
⚠️ No local description after ICE gathering complete
```

**Nguyên nhân**:
- Race condition: ICE gathering hoàn thành TRƯỚC khi `setLocalDescription` hoàn tất
- Hoặc `setLocalDescription` bị fail im lặng
- Trong code: `setLocalDescription` được gọi ở dòng 715, nhưng có thể chưa complete

**Ảnh hưởng**:
- ⚠️ Local description có thể là None khi cần dùng
- ❌ Dẫn đến lỗi khi handle answer (lỗi #4)

**Giải pháp đề xuất**:
1. Đợi `setLocalDescription` hoàn thành trước khi tiếp tục
2. Kiểm tra `self.pc.localDescription` sau khi set
3. Thêm event handler cho `signalingstatechange` để đảm bảo state đúng

---

### 4. ❌ Lỗi khi xử lý Answer (Lỗi nghiêm trọng)

**Vị trí**: Dòng 976-984

**Lỗi**:
```python
AttributeError: 'NoneType' object has no attribute 'media'
File "/home/jetson/miniconda3/envs/iot/lib/python3.10/site-packages/aiortc/rtcpeerconnection.py", line 1392
    offer_media = [(media.kind, media.rtp.muxId) for media in offer.media]
```

**Nguyên nhân**:
- `self.pc.localDescription` là `None` khi validate answer
- Do lỗi #3: local description chưa được set đúng cách
- Code trong `handle_answer` (dòng 920) cố gắng set remote description nhưng validation fail

**Ảnh hưởng**:
- ❌ Không thể complete WebRTC negotiation
- ❌ Cuộc gọi không thể kết nối

**Giải pháp đề xuất**:
1. Kiểm tra `self.pc.localDescription` trước khi handle answer
2. Nếu None, re-initiate call hoặc log error rõ ràng
3. Fix lỗi #3 trước (đảm bảo local description được set)

---

### 5. ⏱️ ICE Candidate Timeout (Lỗi phụ)

**Vị trí**: Dòng 882-937

**Lỗi**:
```python
concurrent.futures._base.TimeoutError
File "/home/jetson/iot/mqtt/handlers.py", line 218
    future.result(timeout=5)  # Timeout 5 giây
```

**Nguyên nhân**:
- `handle_ice_candidate` timeout 5s
- Do peer connection chưa sẵn sàng (chưa có remote description)
- Candidates được buffer nhưng xử lý chậm

**Ảnh hưởng**:
- ⚠️ Có thể làm chậm quá trình kết nối
- ⚠️ Nhiều candidates bị timeout

**Giải pháp đề xuất**:
1. Tăng timeout từ 5s → 10s
2. Không chờ kết quả, chỉ trigger async task
3. Cải thiện buffering mechanism

---

## Thứ tự ưu tiên sửa lỗi

### Priority 1 (Critical - Phải sửa ngay):
1. **Lỗi #3**: Fix local description không được set
2. **Lỗi #4**: Fix lỗi handle answer (phụ thuộc vào #3)
3. **Lỗi #1**: Fix audio device unavailable

### Priority 2 (Important):
4. **Lỗi #2**: Fix timeout trong MCP server
5. **Lỗi #5**: Fix ICE candidate timeout

---

## Giải pháp cụ thể

### Fix 1: Đảm bảo Local Description được set

```python
# Trong webrtc_manager.py, hàm initiate_sos_call()
# 3. Set local description
logger.info("🔒 Setting local description...")
await self.pc.setLocalDescription(offer)

# ✅ THÊM: Đợi và kiểm tra local description
import asyncio
max_wait = 5  # 5 giây
waited = 0
while not self.pc.localDescription and waited < max_wait:
    await asyncio.sleep(0.1)
    waited += 0.1

if not self.pc.localDescription:
    logger.error("❌ Failed to set local description after 5s")
    return False

logger.info(f"✅ Local description set: {len(self.pc.localDescription.sdp)} chars")
```

### Fix 2: Tăng timeout trong MCP server

```python
# Trong mcp_server/server.py
result = future.result(timeout=30)  # Tăng từ 10s → 30s
```

### Fix 3: Tăng thời gian đợi sau pause VAD

```python
# Trong handlers.py, hàm initiate_sos_call()
await asyncio.sleep(1.5)  # Tăng từ 0.5s → 1.5s
```

### Fix 4: Kiểm tra local description trước khi handle answer

```python
# Trong webrtc_manager.py, hàm handle_answer()
if not self.pc.localDescription:
    logger.error("❌ Cannot handle answer: no local description")
    return False
```

---

## Testing Checklist

Sau khi fix, kiểm tra:
- [ ] Audio device được release đúng cách sau pause VAD
- [ ] Local description được set trước khi publish offer
- [ ] MCP server không timeout trong 30s
- [ ] Answer được handle thành công
- [ ] WebRTC connection established
- [ ] Audio và video hoạt động trong cuộc gọi

