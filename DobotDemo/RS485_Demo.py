# RS485_Demo.py
from dobot_api import DobotApiDashboard
import time

def read_gripper_position(dobot_ip="192.168.1.6", slave_id=1):
    dashboard_port = 29999

    # 連線到 Dobot Dashboard 端口
    dashboard = DobotApiDashboard(dobot_ip, dashboard_port)

    # 建立 Modbus RTU 主站（假設已正確接到 M1Pro 末端485口）
    print("[1] 建立 Modbus RTU 連線...")
    modbus_result = dashboard.ModbusCreate("127.0.0.1", 0, slave_id, 1)
    print("ModbusCreate 回應:", modbus_result)

    # 等一下，讓設備穩定
    time.sleep(0.5)

    # 讀取位置寄存器 0x0202（十進位 514），讀 1 筆 U16 資料
    print("[2] 讀取 PGC 夾爪位置 (register 0x0202)...")
    result = dashboard.GetHoldRegs(slave_id, 514, 1, "U16")
    print("GetHoldRegs 回應:", result)

    # 嘗試解析回傳格式，例如："value = 630"
    try:
        value_str = result.split("=")[-1].strip()
        value = int(value_str)
        print(f"➡️ 目前夾爪位置：{value} ‰（約為 {value / 1000.0 * 100:.1f}% 開口）")
    except Exception as e:
        print("⚠️ 解析失敗:", e)

    # 結束後關閉 Modbus 通道
    print("[3] 關閉 Modbus 通道")
    dashboard.ModbusClose(slave_id)

if __name__ == '__main__':
    read_gripper_position()
