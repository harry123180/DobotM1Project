import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# ===== 路徑設定 =====
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
image_path = root_dir / "parameter" / "CASE" / "BD-00009260-CASE-back" / "17.bmp"
threshold_roundness = 0.85  # 圓度門檻

# ===== 讀圖與前處理 =====
img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
if img_gray is None:
    print(f"❌ 無法讀取圖片：{image_path}")
    exit()

# 直方圖均衡與模糊
equalized = cv2.equalizeHist(img_gray)
blurred = cv2.GaussianBlur(equalized, (3, 3), 0)

# 門檻二值化
_, binary_thresh = cv2.threshold(blurred, 170, 255, cv2.THRESH_BINARY)

# 初始邊緣偵測
edges_initial = cv2.Canny(binary_thresh, 10, 350)

# 建立形態學用的 kernel
kernel_dilate = np.ones((13, 13), np.uint8)
kernel_erode = np.ones((11, 11), np.uint8)

# 輪廓填滿處理
contours_initial, _ = cv2.findContours(edges_initial, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
filled_mask = np.zeros_like(cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR))
cv2.drawContours(filled_mask, contours_initial, -1, (255, 255, 255), thickness=cv2.FILLED)

# 反轉並進行形態學處理
inverted_mask = cv2.bitwise_not(filled_mask)
morphed_mask = cv2.dilate(inverted_mask, kernel_dilate, iterations=1)
morphed_mask = cv2.erode(morphed_mask, kernel_erode, iterations=1)

# 再次邊緣偵測
edges_final = cv2.Canny(morphed_mask, 10, 350)
contours_final, _ = cv2.findContours(edges_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# 初始化輸出圖
output_img = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

# ===== 輪廓分析與繪製 =====
for i, cnt in enumerate(contours_final):
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, True)
    if perimeter == 0 or area < 30:
        continue

    roundness = (4 * np.pi * area) / (perimeter ** 2)

    M = cv2.moments(cnt)
    cx, cy = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])) if M["m00"] != 0 else (0, 0)

    label_pos = (cx - 10, cy - 10)
    cv2.putText(output_img, str(i), label_pos, cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 0), 2, cv2.LINE_AA)

    if roundness > threshold_roundness:
        (x, y), radius = cv2.minEnclosingCircle(cnt)
        center = (int(x), int(y))
        radius = int(radius)
        cv2.circle(output_img, center, radius, (0, 255, 0), 2)
        cv2.circle(output_img, center, 2, (255, 0, 0), -1)  # 藍色中心點
        print(f"✅ [{i}] 真圓：中心={center}, 半徑={radius}, 圓度={roundness:.3f}")
    else:
        cv2.drawContours(output_img, [cnt], -1, (255, 0, 255), 2)
        cv2.circle(output_img, (cx, cy), 2, (0, 0, 255), -1)
        print(f"❌ [{i}] 非圓：中心=({cx},{cy}) 圓度={roundness:.3f}, 面積={area:.1f}, 周長={perimeter:.1f}")

# ===== 使用 matplotlib 顯示處理結果 =====
fig, axs = plt.subplots(2, 2, figsize=(14, 6))

axs[0][0].imshow(morphed_mask, cmap='gray')
axs[0][0].set_title("Canny + Dilate/Erode")
axs[0][0].axis('off')

axs[1][0].imshow(output_img[..., ::-1])  # BGR to RGB
axs[1][0].set_title("Final Result")
axs[1][0].axis('off')
axs[0][1].imshow(edges_initial[..., ::-1])  # BGR to RGB
axs[0][1].set_title("edges_initialq")
axs[0][1].axis('off')
axs[1][1].imshow(filled_mask[..., ::-1])  # BGR to RGB
axs[1][1].set_title("edges_final")
axs[1][1].axis('off')

plt.tight_layout()
plt.show()
