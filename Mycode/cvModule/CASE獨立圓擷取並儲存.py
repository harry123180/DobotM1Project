import cv2
import numpy as np
from pathlib import Path

# ===== 參數設定 =====
threshold_roundness = 0.85
radius_scale = 1.3
save_path = Path(r"D:\AWORKSPACE\Github\DobotM1Project\output_circles_A")  # <=== 修改你要儲存的位置
save_path.mkdir(parents=True, exist_ok=True)

# ===== 圖片來源設定 =====
input_path = Path(r"D:\AWORKSPACE\Github\DobotM1Project\parameter\CASE\BD-00009260-CASE-back")

# ===== 主處理流程 =====
for img_index in range(1, 21):
    image_path = input_path / f"{img_index}.bmp"
    img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        print(f"❌ 無法讀取圖片：{image_path}")
        continue

    # --- 前處理 ---
    blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 1, 400)
    kernel = np.ones((3, 3), np.uint8)
    morphed = cv2.dilate(edges, kernel, iterations=1)
    morphed = cv2.erode(morphed, kernel, iterations=1)

    # --- 輪廓偵測 ---
    contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    circle_count = 1

    for cnt in contours:
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0 or area < 30:
            continue

        roundness = (4 * np.pi * area) / (perimeter ** 2)

        if roundness > threshold_roundness:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            cx, cy = int(x), int(y)
            box_half = int(radius * radius_scale)

            # 邊界檢查
            x1 = max(cx - box_half, 0)
            y1 = max(cy - box_half, 0)
            x2 = min(cx + box_half, img_gray.shape[1])
            y2 = min(cy + box_half, img_gray.shape[0])

            cropped = img_gray[y1:y2, x1:x2]
            filename = f"{img_index}_{circle_count}.bmp"
            cv2.imwrite(str(save_path / filename), cropped)

            print(f"✅ [{img_index}] 圓 {circle_count} 儲存為 {filename}（中心=({cx},{cy}) 半徑={radius:.1f} 圓度={roundness:.3f}）")
            circle_count += 1
