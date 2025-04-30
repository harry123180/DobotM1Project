import cv2
import numpy as np
import time
from camera_manager import initialize_all_cameras, get_image, shutdown_all

# 初始化相機
initialize_all_cameras()
time.sleep(2)

target_cam = "cam_3"
cv2.namedWindow("Preview", cv2.WINDOW_NORMAL)
#cv2.namedWindow("Edges", cv2.WINDOW_NORMAL)
def is_circle(contour, tolerance=0.2):
    """用圓度指標判斷是否為圓形"""
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False
    circularity = 4 * np.pi * area / (perimeter * perimeter)
    return 1 - tolerance < circularity < 1 + tolerance

try:
    while True:
        try:
            raw_bytes = get_image(target_cam)
            img = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((1944, 2592))

            # 模糊處理
            blurred = cv2.GaussianBlur(img, (9, 9), 2)

            # Canny 邊緣
            edges = cv2.Canny(blurred, 20, 60)

            # 擷取輪廓
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 轉成彩色圖顯示用
            output = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            circle_count = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if is_circle(contour) and area >30000:
                    # 擬合最小外接圓取得圓心與半徑
                    (x, y), radius = cv2.minEnclosingCircle(contour)
                    center = (int(x), int(y))
                    radius = int(radius)
                    circle_count += 1

                    # 畫圓與標註
                    cv2.circle(output, center, radius, (0, 255, 0), 2)

                    # 計算面積
                    

                    # 標註文字資訊
                    label1 = f"{circle_count}: ({center[0]}, {center[1]})"
                    label2 = f"Area: {int(area)}"
                    cv2.putText(output, label1, (center[0] + 10, center[1] + 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 255, 0), 5)
                    #cv2.putText(output, label2, (center[0] + 10, center[1] + 40),
                    #            cv2.FONT_HERSHEY_SIMPLEX, 3.0, (0, 255, 0), 5)


            # 顯示畫面
            cv2.imshow("Preview", output)
            #ㄆcv2.imshow("Edges", edges)

        except Exception as e:
            print(f"⚠️ 擷取影像或處理失敗: {e}")
            blank = np.zeros((1944, 2592, 3), dtype=np.uint8)
            cv2.imshow("Preview", blank)

        # 按 q 鍵退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        time.sleep(1)

except KeyboardInterrupt:
    print("🛑 使用者中斷")

finally:
    cv2.destroyAllWindows()
    shutdown_all()
    print("✅ 已關閉相機與視窗")
