# main.py
from pgc_gripper_control import PGC_Gripper
import time

# 建立夾爪控制物件（根據你提供的參數）
gripper = PGC_Gripper(port='COM3', baudrate=115200, parity='N', stopbits=1, unit_id=1)

# 初始化（歸零）
gripper.initialize()
time.sleep(2)

# 設定力道與速度
gripper.set_force(50)
gripper.set_speed(40)

# 開合測試
gripper.set_position(400)
time.sleep(3)
gripper.set_position(500)
time.sleep(3)
gripper.set_position(0)
time.sleep(3)
# 停止當前動作
gripper.stop()

# 斷開連線
gripper.disconnect()
