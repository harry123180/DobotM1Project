from vibration_plate import Vibration_plate
import time
VP = Vibration_plate("192.188.2.88", 1000, 10)

# 開啟背光
VP.backlight(1)

# 觸發 "上" 的單一動作，強度60，頻率60
VP.up(60, 60)
time .sleep(3)
VP.stop()
VP.backlight(0)
# 關閉連線
VP.close()
