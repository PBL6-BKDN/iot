import cv2
import numpy as np
import albumentations as A
from albumentations.pytorch import ToTensorV2
import time
import threading
import onnxruntime as ort
from navigation.speech.voice import VoiceService

# --- Load model ONNX ---
model_path = "model.onnx"
ort_session = ort.InferenceSession(
    model_path,
    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
)
print("Model ONNX đã được load.")

# --- Khởi tạo VoiceService ---
voice_service = VoiceService()

# --- Màu cho từng lớp ---
COLORS = [
    (255, 255, 0),     # lớp 0
    (0, 255, 0),       # lớp 1
    (255, 0, 0),       # lớp 2
    (0, 0, 255),       # lớp 3
    (0, 0, 0),         # lớp 4 - nền
]

# --- Hàm decode mask sang màu ---
def decode_segmap(mask, num_classes):
    h, w = mask.shape
    color_mask = np.zeros((h, w, 3), dtype=np.uint8)
    for cls in range(num_classes):
        color_mask[mask == cls] = COLORS[cls]
    return color_mask

# --- Phân tích vị trí người đứng dựa trên lớp ---
def analyze_position(pred):
    guidance = ""
    h, w = pred.shape
    bottom = pred[-h // 4:, :]
    unique_classes = np.unique(bottom)

    if 2 in unique_classes:
        guidance = "⚠️ Cảnh báo: Bạn đang đứng trên **đường xe chạy**!"
    elif 1 in unique_classes:
        guidance = "🚸 Bạn đang đứng trên **vạch kẻ đường cho người đi bộ**."
    elif 3 in unique_classes:
        guidance = "✅ Bạn đang đứng trên **vỉa hè**."
    else:
        guidance = "❓ Không xác định được vị trí đứng."

    left = pred[:, :w//3]
    center = pred[:, w//3:2*w//3]
    right = pred[:, 2*w//3:]

    def find_position(region, cls):
        return cls in np.unique(region)

    for cls, name in [(1, "vạch kẻ đường"), (3, "vỉa hè")]:
        pos = []
        if find_position(left, cls):
            pos.append("bên trái")
        if find_position(center, cls):
            pos.append("phía trước")
        if find_position(right, cls):
            pos.append("bên phải")

        if pos:
            guidance += f" 📍 ({name}) xuất hiện ở: {', '.join(pos)}."
        else:
            guidance += f" 📍 ({name}) không xuất hiện trong ảnh."
    return guidance

# --- Phát giọng nói ---
def speak_guidance(guidance):
    try:
        if guidance:
            voice_service.speak(guidance)
            print(f"Played guidance: {guidance}")
    except Exception as e:
        print(f"Failed to play audio: {e}")

# --- Hàm chính xử lý camera ---
def predict_camera(frame, frame_skip=2):
    num_classes = 5
    try:
        last_guidance = ""
        last_speak_time = 0
        frame_count = 0

        print("Đang phán đoán làn đường...")


        if frame_count % frame_skip != 0:
            frame_count += 1

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        transform = A.Compose([
            A.Resize(384, 512),
            A.Normalize(mean=(0.485, 0.456, 0.406),
                        std=(0.229, 0.224, 0.225)),
            ToTensorV2()
        ])
        aug = transform(image=frame_rgb)
        input_tensor = aug['image'].unsqueeze(0).cpu().numpy().astype(np.float32)  # (1, 3, 384, 512)

        # Inference ONNX Runtime
        start = time.time()
        ort_inputs = {ort_session.get_inputs()[0].name: input_tensor}
        ort_outs = ort_session.run(None, ort_inputs)
        output = ort_outs[0]  # (1, num_classes, H, W)
        pred = np.argmax(output, axis=1).squeeze()  # (H, W)
        end = time.time()
        print(f"⏱ Thời gian suy luận (ONNX Runtime): {(end - start)*1000:.2f} ms")

        guidance = analyze_position(pred)

        pred_color = decode_segmap(pred, num_classes)
        pred_color_bgr = cv2.cvtColor(pred_color, cv2.COLOR_RGB2BGR)

        img_resized = cv2.resize(frame, (512, 384))
        overlay = cv2.addWeighted(img_resized, 0.5, pred_color_bgr, 0.5, 0)

        if guidance != last_guidance and (time.time() - last_speak_time > 10):
            speak_guidance(guidance)
            last_guidance = guidance
            last_speak_time = time.time()



        frame_count += 1
        return overlay


    except Exception as e:
        print(f"Camera processing failed: {e}")
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        raise