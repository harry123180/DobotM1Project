import cv2
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# 設定 matplotlib 字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus'] = False

# ===== 使用者可調整的參數 =====
dist_thresh_ratio = 0.7  # ← 距離轉換的閾值比例，0.7 表示只取最中心的高距離區

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

# ===== Otsu 二值化 + 開運算清除雜訊 + 關運算補圓 =====
_, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
kernel = np.ones((3, 3), np.uint8)
opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel, iterations=2)
working_img = closing.copy()

# ===== 膨脹找背景 =====
sure_bg = cv2.dilate(working_img, kernel, iterations=3)

# ===== 距離轉換找前景（圓心）=====
dist_transform = cv2.distanceTransform(working_img, cv2.DIST_L2, 5)
_, sure_fg = cv2.threshold(dist_transform, dist_thresh_ratio * dist_transform.max(), 255, 0)
sure_fg = np.uint8(sure_fg)

# ===== 計算未知區域（背景 - 前景）=====
unknown = cv2.subtract(sure_bg, sure_fg)

# ===== connectedComponents 前景標記 =====
_, markers = cv2.connectedComponents(sure_fg)
markers = markers + 1
markers[unknown == 255] = 0
markers = np.int32(markers)

# ===== 執行分水嶺 =====
cv2.watershed(img_color, markers)
img_color[markers == -1] = [0, 0, 255]  # 邊界紅線

# ===== 顯示圖像結果 =====
fig, axs = plt.subplots(1, 3, figsize=(18, 5))

axs[0].imshow(gray, cmap='gray')
axs[0].set_title("A - 原始灰階圖")
axs[0].axis('off')

axs[1].imshow(dist_transform, cmap='jet')
axs[1].set_title(f"B - 距離轉換圖\n(門檻比例: {dist_thresh_ratio:.2f})")
axs[1].axis('off')

axs[2].imshow(cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB))
axs[2].set_title("C - 分水嶺分割結果")
axs[2].axis('off')

plt.tight_layout()
plt.show()
