from pathlib import Path
import cv2
import numpy as np
import shutil

# ===== 設定根資料夾與輸出位置 =====
input_root = Path(r"D:\AWORKSPACE\Github\DobotM1Project\parameter\CASE")
output_root = Path(r"D:\AWORKSPACE\Github\DobotM1Project\output_circles_all")
output_root.mkdir(parents=True, exist_ok=True)

# ===== 處理參數 =====
threshold_roundness = 0.85
radius_scale = 1.6

# ===== 尋找所有 CASE-xxx 的資料夾 =====
case_folders = sorted(list(input_root.glob("*CASE*")))

# ===== 處理每個資料夾內的 1~20.bmp 圖片 =====
for folder in case_folders:
    case_name = folder.name.replace("-", "_")  # 確保檔名合法性
    for img_index in range(1, 21):
        image_path = folder / f"{img_index}.bmp"
        if not image_path.exists():
            continue

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

                cropped = img_gray[y1:y2, x1:x2]
                filename = f"{case_name}_img{img_index:02d}_c{circle_count:02d}.bmp"
                save_path = output_root / filename
                cv2.imwrite(str(save_path), cropped)

                print(f"✅ {filename} 儲存完成（中心=({cx},{cy}) 半徑={radius:.1f} 圓度={roundness:.3f}）")
                circle_count += 1

len(list(output_root.glob("*.bmp")))
