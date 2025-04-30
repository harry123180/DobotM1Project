# main.py
import cv2
import numpy as np
import time
from camera_manager import initialize_all_cameras, get_image, shutdown_all

# 初始化所有相機
initialize_all_cameras()

# 等待初始化完成
time.sleep(2)

# 指定要拍照的相機名稱
target_cam = "cam_3"

# 建立 OpenCV 可調整視窗
cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)

try:
    while True:
        # 嘗試取得影像並顯示
        try:
            raw_bytes = get_image(target_cam)
            img_array = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((1944, 2592))
            cv2.imshow("Preview", img_array)
        except Exception as e:
            print(f"⚠️ 擷取影像失敗: {e}")
            blank = np.zeros((1944, 2592), dtype=np.uint8)
            cv2.imshow("Preview", blank)

        # 按下 q 鍵退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # 每秒擷取一次
        time.sleep(1)

except KeyboardInterrupt:
    print("🛑 中斷操作")

finally:
    # 關閉視窗與相機
    cv2.destroyAllWindows()
    shutdown_all()
    print("✅ 已關閉相機與視窗")
