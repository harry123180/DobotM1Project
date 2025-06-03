import os
import time
import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
from pathlib import Path
import matplotlib.pyplot as plt

# === 強制使用 CPU 避免 NCCL 錯誤 ===
os.environ["CUDA_VISIBLE_DEVICES"] = ""

# === 載入模型結構 ===
class SimpleCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.fc = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 16 * 16, 128), nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, x): return self.fc(self.conv(x))

# === 模型與預處理設定 ===
device = torch.device("cpu")
model_path = Path(__file__).resolve().parent / "trained_model.pth"
model = SimpleCNN().to(device)
model.load_state_dict(torch.load(model_path, map_location=device))
model.eval()

transform = transforms.Compose([
    transforms.Resize((128, 128)),
    transforms.ToTensor(),
])

# === 圖片來源 ===
total_start_time = time.perf_counter()
root_dir = Path(__file__).resolve().parent.parent.parent
image_path = root_dir / "parameter" / "CASE" / "BD-00009260-CASE-back" / "9.bmp"
img_gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
if img_gray is None:
    print(f"❌ 無法讀取圖片：{image_path}")
    exit()

# === 前處理與邊緣檢測 ===
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
morphed_mask = cv2.dilate(inverted_mask, kernel_dilate, iterations=1)
morphed_mask = cv2.erode(morphed_mask, kernel_erode, iterations=1)

edges_final = cv2.Canny(morphed_mask, 10, 350)
contours_final, _ = cv2.findContours(edges_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
output_img = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)

# === 判斷與標記圓形 ===
threshold_roundness = 0.85
radius_scale = 1.3
label_map = ["A", "B"]
inference_times = []
circle_results = []

for i, cnt in enumerate(contours_final):
    area = cv2.contourArea(cnt)
    perimeter = cv2.arcLength(cnt, True)
    if perimeter == 0 or area < 30:
        continue

    roundness = (4 * np.pi * area) / (perimeter ** 2)
    M = cv2.moments(cnt)
    cx, cy = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])) if M["m00"] != 0 else (0, 0)
    label_pos = (cx - 20, cy - 20)

    if roundness > threshold_roundness:
        (x, y), radius = cv2.minEnclosingCircle(cnt)
        cx_crop, cy_crop = int(x), int(y)
        box_half = int(radius * radius_scale)

        x1 = max(cx_crop - box_half, 0)
        y1 = max(cy_crop - box_half, 0)
        x2 = min(cx_crop + box_half, img_gray.shape[1])
        y2 = min(cy_crop + box_half, img_gray.shape[0])
        crop = img_gray[y1:y2, x1:x2]

        # 推論
        pil_img = Image.fromarray(crop).convert("L")
        input_tensor = transform(pil_img).unsqueeze(0).to(device)

        start_time = time.perf_counter()
        with torch.no_grad():
            output = model(input_tensor)
            pred = torch.argmax(output, dim=1).item()
        end_time = time.perf_counter()
        elapsed_ms = (end_time - start_time) * 1000
        inference_times.append(elapsed_ms)

        # 畫圖與文字
        cv2.circle(output_img, (cx_crop, cy_crop), int(radius), (0, 255, 0), 2)
        cv2.circle(output_img, (cx_crop, cy_crop), 2, (255, 0, 0), -1)
        cv2.putText(output_img, f"{i} {label_map[pred]}", label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

        circle_results.append((i, crop, label_map[pred]))

        print(f"✅ [{i}] 真圓 | 類別: {label_map[pred]} | 圓度={roundness:.3f} | 半徑={radius:.1f} | 面積={area:.1f} | 周長={perimeter:.1f} | 時間={elapsed_ms:.2f}ms")
    else:
        cv2.drawContours(output_img, [cnt], -1, (255, 0, 255), 2)
        cv2.circle(output_img, (cx, cy), 2, (0, 0, 255), -1)
        print(f"❌ [{i}] 非圓 | 圓度={roundness:.3f} | 面積={area:.1f} | 周長={perimeter:.1f}")

# === 平均推論時間與總耗時 ===
if inference_times:
    avg_time = sum(inference_times) / len(inference_times)
    print(f"\n⏱ 平均每個圓的模型推論時間：{avg_time:.2f}ms")

total_end_time = time.perf_counter()
total_elapsed_ms = (total_end_time - total_start_time) * 1000
print(f"\n🚀 整體總耗時：{total_elapsed_ms:.2f}ms（從圖片載入到完成推論）")

# === 顯示原圖結果 ===
plt.figure(figsize=(12, 6))
plt.imshow(cv2.cvtColor(output_img, cv2.COLOR_BGR2RGB))
plt.title("CNN Inference + Circle Detection Result")
plt.axis('off')
plt.tight_layout()
plt.show()

# === 顯示每個裁切圓形結果圖像 ===
cols = 5
rows = (len(circle_results) + cols - 1) // cols
fig, axs = plt.subplots(rows, cols, figsize=(3 * cols, 3 * rows))

for idx, (circle_idx, img_arr, label) in enumerate(circle_results):
    r, c = divmod(idx, cols)
    ax = axs[r][c] if rows > 1 else axs[c]
    ax.imshow(img_arr, cmap='gray')
    ax.set_title(f"Circle {circle_idx}\nPred: {label}")
    ax.axis('off')

# 清除空白子圖
for j in range(len(circle_results), rows * cols):
    r, c = divmod(j, cols)
    ax = axs[r][c] if rows > 1 else axs[c]
    ax.axis('off')

plt.suptitle("Circle Patch Prediction", fontsize=16)
plt.tight_layout()
plt.show()
