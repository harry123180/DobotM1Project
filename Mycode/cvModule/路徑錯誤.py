from pathlib import Path
import cv2
img_path = Path(r"D:\AWORKSPACE\Github\DobotM1Project\parameter\CASE\BD-00009260-CASE-back")

print("✅ 測試路徑：", img_path)

for i in range(1, 21):
    image_path = img_path / f"{i}.bmp"
    print(f"🟡 嘗試讀取：{image_path}")
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"❌ 無法讀取：{image_path}")
    else:
        print(f"✅ 成功讀取第 {i} 張圖，大小：{img.shape}")