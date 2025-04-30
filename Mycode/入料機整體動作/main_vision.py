# main.py
from Vision import initialize_all_cameras, shutdown_all, GetObjectPosition
import time
from vibration_plate import Vibration_plate
# 初始化相機
initialize_all_cameras()
time.sleep(2)
VP = Vibration_plate("192.188.2.88", 1000, 10)
VP.backlight(1)
try:
    # 取得合法圓心座標
    positions = GetObjectPosition()
    print(positions[0][0],positions[0][1])
    print(positions)
    # 輸出每個圓心位置
    print(positions[0][0],positions[0][1])
    for i, (x, y) in enumerate(positions):
        print(f"第 {i} 個圓心座標: x = {x:.2f}, y = {y:.2f}")
        #print(x,y)
    if not positions:
        print("⚠️ 沒有找到合法圓形")

finally:
    # 關閉相機
    shutdown_all()
    print("✅ 已關閉相機")
VP.backlight(1)