# RS485_Demo.py
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove
from time import sleep

def connect_robot(ip="192.168.1.6"):
    print("🔌 正在連接機械臂...")
    dashboard = DobotApiDashboard(ip, 29999)
    move = DobotApiMove(ip, 30003)
    feed = DobotApi(ip, 30004)
    print("✅ 機械臂連線成功！")
    return dashboard, move, feed

def read_gripper_position(dashboard, slave_id=1):
    # 建立 Modbus RTU 主站（isRTU=1）
    print("🛠️ 建立 RS485 (Modbus RTU) 主站...")
    result = dashboard.ModbusCreate("127.0.0.1", 0, slave_id, 1)
    print("ModbusCreate 回應:", result)
    sleep(0.2)

    # 讀取寄存器 0x0202（十進位 514）: PGC 夾爪位置，資料格式 U16
    print("📤 嘗試讀取 PGC 電爪位置 (register 0x0202)...")
    result = dashboard.GetHoldRegs(slave_id, 514, 1, "U16")
    print("GetHoldRegs 回應:", result)

    try:
        # 嘗試解析回傳格式：例如 "value = 680"
        value_str = result.split("=")[-1].strip()
        value = int(value_str)
        print(f"➡️ 夾爪目前位置：{value} ‰（約為 {value / 1000.0 * 100:.1f}% 開口）")
    except Exception as e:
        print("⚠️ 無法解析位置回傳：", e)

    print("🧹 關閉 Modbus 通道")
    dashboard.ModbusClose(slave_id)

if __name__ == '__main__':
    dashboard, move, feed = connect_robot()
    read_gripper_position(dashboard)
