import cv2
import numpy as np
from pathlib import Path



# 取得當前路徑
current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent.parent

# 圖片路徑
back_path = root_dir / "parameter" / "CASE" / "BD-00009260-CASE-back" / "1.bmp"
front_path = root_dir / "parameter" / "CASE" / "BD-00009260-CASE-front" / "1.bmp"

# 讀取並灰階處理
back_img_raw = cv2.imread(str(back_path), cv2.IMREAD_GRAYSCALE)
front_img_raw = cv2.imread(str(front_path), cv2.IMREAD_GRAYSCALE)

# 確認成功讀入
if back_img_raw is None:
    print(f"❌ 無法讀取背面圖片：{back_path}")
if front_img_raw is None:
    print(f"❌ 無法讀取正面圖片：{front_path}")

if back_img_raw is not None and front_img_raw is not None:
    # 縮放成相同高度
    height = min(back_img_raw.shape[0], front_img_raw.shape[0])
    back_img = cv2.resize(back_img_raw, (int(back_img_raw.shape[1] * height / back_img_raw.shape[0]), height))
    front_img = cv2.resize(front_img_raw, (int(front_img_raw.shape[1] * height / front_img_raw.shape[0]), height))


    # 拼接
    combined = np.hstack((back_img, front_img))
    edges = cv2.Canny(combined, 110, 150)
    # 顯示
    cv2.namedWindow("Contour Classification: Back vs Front", cv2.WINDOW_NORMAL)
    cv2.imshow("Contour Classification: Back vs Front", edges)
    
    print(f"✅ 拼接後尺寸：{edges.shape[1]}x{edges.shape[0]}")

    cv2.waitKey(0)
    cv2.destroyAllWindows()
