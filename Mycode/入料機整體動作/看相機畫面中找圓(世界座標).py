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

# === 轉換像素點到世界座標 ===
def pixel_to_world(u, v, K, D, rvec, tvec, Z_plane=0):
    undistorted = cv2.undistortPoints(np.array([[[u, v]]], dtype=np.float32), K, D, P=K)
    uv_hom = np.array([undistorted[0, 0, 0], undistorted[0, 0, 1], 1.0], dtype=np.float64)
    R, _ = cv2.Rodrigues(rvec)

    cam_coords = np.linalg.inv(K) @ uv_hom
    tz = float(tvec.flatten()[2])
    s = (Z_plane - tz) / (R[2, :] @ cam_coords)
    XYZ_cam = s * cam_coords

    world_coords = np.linalg.inv(R) @ (XYZ_cam - tvec.flatten())
    return tuple(world_coords.flatten().astype(float))  # 保證回傳 (float, float, float)

# === 初始化相機 ===
initialize_all_cameras()
time.sleep(2)

target_cam = "cam_3"
cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)

def is_circle(contour, tolerance=0.2):
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False
    circularity = 4 * np.pi * area / (perimeter * perimeter)
    return 1 - tolerance < circularity < 1 + tolerance

# === 主迴圈 ===
try:
    while True:
        try:
            raw_bytes = get_image(target_cam)
            if raw_bytes is None or len(raw_bytes) != 1944 * 2592:
                raise ValueError(f"影像資料錯誤，長度為 {len(raw_bytes) if raw_bytes else 'None'}，預期為 5038848。")

            img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((1944, 2592))
            blurred = cv2.GaussianBlur(img, (9, 9), 2)
            edges = cv2.Canny(blurred, 20, 60)
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            output = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            circle_count = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if is_circle(contour) and area > 30000:
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    center = (int(x), int(y))
                    radius = int(radius)
                    circle_count += 1

                    Xw, Yw, Zw = pixel_to_world(center[0], center[1], K, D, rvec, tvec)

                    cv2.circle(output, center, radius, (0, 255, 0), 2)
                    label1 = f"{circle_count}: ({center[0]}, {center[1]})"
                    label2 = f"Area: {int(area)}"
                    label3 = f"World: ({Xw:.1f}, {Yw:.1f})"

                    cv2.putText(output, label1, (center[0] + 10, center[1] + 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    cv2.putText(output, label2, (center[0] + 10, center[1] + 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    cv2.putText(output, label3, (center[0] + 10, center[1] + 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

            cv2.imshow("Preview", output)

        except Exception as e:
            print(f"⚠️ 擷取影像或處理失敗: {e}")
            blank = np.zeros((1944, 2592, 3), dtype=np.uint8)
            cv2.imshow("Preview", blank)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        time.sleep(1)

except KeyboardInterrupt:
    print("🛑 使用者中斷")

finally:
    cv2.destroyAllWindows()
    shutdown_all()
    print("✅ 已關閉相機與視窗")
