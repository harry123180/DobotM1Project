import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# 設定中文字體，避免 matplotlib 顯示錯亂
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# ===== 圖片路徑設定 =====
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent
image_path = root_dir / "parameter" / "CASE" / "BD-00009260-CASE-back" / "12.bmp"

# ===== 讀取灰階圖片 =====
gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
if gray is None:
    raise FileNotFoundError(f"❌ 無法讀取圖片：{image_path}")

# ===== 彩圖轉換 (必要給 watershed 用) =====
img_color = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

# ===== Otsu 二值化 =====
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

# ===== 開運算清除雜訊 =====
kernel = np.ones((3, 3), np.uint8)
opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)

# ===== 關運算補圓心（補洞）=====
closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel, iterations=2)

# ===== 輪廓填滿影像：更強的填圓方式 =====
filled_image = np.zeros_like(closing)
contours, _ = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
cv2.drawContours(filled_image, contours, -1, 255, thickness=cv2.FILLED)

# ===== 膨脹找背景 =====
sure_bg = cv2.dilate(filled_image, kernel, iterations=3)

# ===== 距離轉換找前景（圓心）=====
dist_transform = cv2.distanceTransform(filled_image, cv2.DIST_L2, 5)
_, sure_fg = cv2.threshold(dist_transform, 0.7 * dist_transform.max(), 255, 0)
sure_fg = np.uint8(sure_fg)

# ===== 計算未知區域（背景 - 前景）=====
unknown = cv2.subtract(sure_bg, sure_fg)

# ===== connectedComponents 標記前景區域 =====
_, markers = cv2.connectedComponents(sure_fg)
markers = markers + 1  # 背景設為 1，物體為 2+
markers[unknown == 255] = 0
markers = np.int32(markers)

# ===== 執行分水嶺 =====
cv2.watershed(img_color, markers)
img_color[markers == -1] = [0, 0, 255]  # 分水嶺邊界標紅

# ===== 建立 RGB mask 顯示前景、背景、未知區 =====
seg_color = np.zeros((gray.shape[0], gray.shape[1], 3), dtype=np.uint8)
seg_color[sure_bg == 255] = [0, 0, 255]      # 背景藍
seg_color[sure_fg == 255] = [0, 255, 0]      # 前景綠
seg_color[unknown == 255] = [255, 0, 0]      # 未知紅

# ===== 顯示四張圖 =====
fig, axs = plt.subplots(1, 4, figsize=(20, 5))

axs[0].imshow(gray, cmap='gray')
axs[0].set_title("A - 原始灰階圖")
axs[0].axis('off')

axs[1].imshow(filled_image, cmap='gray')
axs[1].set_title("B - 輪廓填滿後影像")
axs[1].axis('off')

axs[2].imshow(seg_color)
axs[2].set_title("C - 前景 / 背景 / 未知")
axs[2].axis('off')

axs[3].imshow(cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB))
axs[3].set_title("D - 分水嶺分割結果")
axs[3].axis('off')

plt.tight_layout()
plt.show()
