import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# ===== 路徑設定 =====
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
image_path = root_dir / "parameter" / "CASE" / "BD-00009260-CASE-back" / "12.bmp"
threshold_roundness = 0.85  # 圓度門檻

# ===== 讀圖與前處理 =====
img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
if img_gray is None:
    print(f"❌ 無法讀取圖片：{image_path}")
    exit()

equalized = cv2.equalizeHist(img_gray)
blurred = cv2.GaussianBlur(img_gray, (3, 3), 0)
ret,thresh1 = cv2.threshold(blurred,127,255,cv2.THRESH_BINARY)
edges = cv2.Canny(thresh1, 10, 350)
kernel = np.ones((3, 3), np.uint8)

#
morphed = cv2.dilate(edges, kernel, iterations=1)
morphed = cv2.erode(morphed, kernel, iterations=1)

# ===== 輪廓分析與繪製 =====
contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
output_img = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

for i, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, True)
    if perimeter == 0 or area < 30:
        continue

    roundness = (4 * np.pi * area) / (perimeter ** 2)

    # 計算中心點
    M = cv2.moments(cnt)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        cx, cy = 0, 0

    label_pos = (cx - 10, cy - 10)
    cv2.putText(output_img, str(i), label_pos, cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2, cv2.LINE_AA)

    if roundness > threshold_roundness:
        (x, y), radius = cv2.minEnclosingCircle(cnt)
        center = (int(x), int(y))
        radius = int(radius)
        cv2.circle(output_img, center, radius, (0, 255, 0), 2)
        cv2.circle(output_img, center, 2, (255, 0, 0), -1)  # 紅點
        print(f"✅ [{i}] 真圓：中心={center}, 半徑={radius}, 圓度={roundness:.3f}")
    else:
        cv2.drawContours(output_img, [cnt], -1, (255, 0, 255), 2)  # 紫色輪廓
        cv2.circle(output_img, (cx, cy), 2, (0, 0, 255), -1)  # 紅點也畫出
        print(f"❌ [{i}] 非圓：中心=({cx},{cy}) 圓度={roundness:.3f}, 面積={area:.1f}, 周長={perimeter:.1f}")

# ===== 使用 matplotlib 顯示 =====
# ===== 並排顯示所有處理階段 =====
# ===== 並排顯示處理結果（2 圖）=====
fig, axs = plt.subplots(1, 2, figsize=(14, 6))

axs[0].imshow(morphed, cmap='gray')
axs[0].set_title("Canny + Dilate/Erode")
axs[0].axis('off')

axs[1].imshow(cv2.cvtColor(output_img, cv2.COLOR_BGR2RGB))
axs[1].set_title("Final Result")
axs[1].axis('off')

plt.tight_layout()
plt.show()
