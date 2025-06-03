import cv2
import numpy as np
from pathlib import Path

# ===== 參數設定 =====
threshold_roundness = 0.85
radius_scale = 1.6
mask_radius_scale = 1.65  # 遮罩用的半徑比例
save_path = Path(r"D:\AWORKSPACE\Github\DobotM1Project\output_circles_Front")
save_path.mkdir(parents=True, exist_ok=True)

# ===== 圖片來源設定 =====
input_path = Path(r"D:\AWORKSPACE\Github\DobotM1Project\parameter\CASE\BD-0040419-2-CASE_front")

# ===== 主處理流程（基於等化、形態學、二次邊緣判斷） =====
for img_index in range(1, 21):
    image_path = input_path / f"{img_index}.bmp"
    img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img_gray is None:
        print(f"❌ 無法讀取圖片：{image_path}")
        continue

    equalized = cv2.equalizeHist(img_gray)
    blurred = cv2.GaussianBlur(equalized, (3, 3), 0)
    _, binary_thresh = cv2.threshold(blurred, 170, 255, cv2.THRESH_BINARY)
    edges_initial = cv2.Canny(binary_thresh, 10, 350)

    kernel_dilate = np.ones((13, 13), np.uint8)
    kernel_erode = np.ones((11, 11), np.uint8)

    contours_initial, _ = cv2.findContours(edges_initial, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled_mask = np.zeros_like(cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR))
    cv2.drawContours(filled_mask, contours_initial, -1, (255, 255, 255), thickness=cv2.FILLED)

    inverted_mask = cv2.bitwise_not(filled_mask)
    morphed_mask = cv2.dilate(inverted_mask, kernel_dilate, iterations=4)
    morphed_mask = cv2.erode(morphed_mask, kernel_erode, iterations=1)

    edges_final = cv2.Canny(morphed_mask, 10, 350)
    contours_final, _ = cv2.findContours(edges_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    circle_count = 1
    for cnt in contours_final:
        area = cv2.contourArea(cnt)
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0 or area < 30:
            continue

        roundness = (4 * np.pi * area) / (perimeter ** 2)
        if roundness > threshold_roundness:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            cx, cy = int(x), int(y)
            box_half = int(radius * radius_scale)

            x1 = max(cx - box_half, 0)
            y1 = max(cy - box_half, 0)
            x2 = min(cx + box_half, img_gray.shape[1])
            y2 = min(cy + box_half, img_gray.shape[0])

            # 裁切圖像
            cropped = img_gray[y1:y2, x1:x2].copy()

            # 建立黑底白圓遮罩（保留圓形，遮掉其餘）
            mask = np.zeros_like(cropped, dtype=np.uint8)
            center_x = cx - x1
            center_y = cy - y1
            mask_radius = int(radius * mask_radius_scale)
            cv2.circle(mask, (center_x, center_y), mask_radius, 255, -1)

            # 套用遮罩：只保留圓形區域，其他區域補白色
            masked = cropped.copy()
            masked[mask == 0] = 255  # 外圍補白


            # 儲存
            filename = f"{image_path.stem}_img{img_index:02d}_c{circle_count:02d}.bmp"
            cv2.imwrite(str(save_path / filename), masked)

            print(f"✅ [{img_index}] 圓 {circle_count} 儲存為 {filename}（中心=({cx},{cy}) 半徑={radius:.1f} 圓度={roundness:.3f}）")
            circle_count += 1
