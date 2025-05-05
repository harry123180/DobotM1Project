import cv2
import numpy as np
import time
from camera_manager import initialize_all_cameras, get_image, shutdown_all

# === 相機參數 ===
K = np.array([
    [5527.91522, 0.0, 1249.56097],
    [0.0, 5523.37409, 997.41524],
    [0.0, 0.0, 1.0]
])

D = np.array([
    -0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681
])

# 使用上一步 PnP 計算出的 rvec 與 tvec
rvec = np.array([[-2.17796294], [-2.24565035], [0.02621215]])  # shape (3,1)
tvec = np.array([[330.20053861], [48.63793437], [533.5402696]])  # shape (3,1)

# === 像素點轉世界座標 ===
def pixel_to_world(u, v, K, D, rvec, tvec, Z_plane=0):
    undistorted = cv2.undistortPoints(np.array([[[u, v]]], dtype=np.float32), K, D, P=K)
    uv_hom = np.array([undistorted[0, 0, 0], undistorted[0, 0, 1], 1.0], dtype=np.float64)
    R, _ = cv2.Rodrigues(rvec)
    cam_coords = np.linalg.inv(K) @ uv_hom
    tz = float(tvec.flatten()[2])
    s = (Z_plane - tz) / (R[2, :] @ cam_coords)
    XYZ_cam = s * cam_coords
    world_coords = np.linalg.inv(R) @ (XYZ_cam - tvec.flatten())
    return tuple(world_coords.flatten().astype(float))  # ✅ 回傳 float tuple

# === 判斷是否為圓形 ===
def is_circle(contour, tolerance=0.2):
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False
    circularity = 4 * np.pi * area / (perimeter * perimeter)
    return 1 - tolerance < circularity < 1 + tolerance

# === 主功能：擷取圓形物件的世界座標位置 ===
def GetObjectPosition():
    positions = []
    try:
        raw_bytes = get_image("cam_3")
        img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((1944, 2592))
        blurred = cv2.GaussianBlur(img, (9, 9), 2)
        edges = cv2.Canny(blurred, 20, 60)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if is_circle(contour) and area > 30000:
                (x, y), _ = cv2.minEnclosingCircle(contour)
                Xw, Yw, _ = pixel_to_world(int(x), int(y), K, D, rvec, tvec)
                print(Xw,Yw)
                # ✅ 安全區域過濾條件
                if -80 <= Xw <= 16 and -373 <= Yw <= -244:
                    positions.append([round(Xw, 2), round(Yw, 2)])
                else:
                    print("No Object detecte")
    except Exception as e:
        print(f"❌ 擷取或分析失敗: {e}")

    return positions

# （需要時啟用初始化或關閉）
# initialize_all_cameras()
# time.sleep(2)
# shutdown_all()
