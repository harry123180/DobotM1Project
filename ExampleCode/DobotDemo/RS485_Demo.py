import time
from dobot_api import DobotApiDashboard

def connect_robot(ip="192.168.1.6"):
    print("🔌 正在連接機械臂...")
    dashboard = DobotApiDashboard(ip, 29999)
    print("✅ 機械臂連線成功！")
    return dashboard

def parse_response(response):
    if not response or response.startswith("-1"):
        return None, "❌ 無回應或 Modbus 失敗"
    try:
        data_str = response.split(",")[1].strip("{}")
        reg_str = data_str.split(":")[1]
        return int(reg_str), None
    except Exception as e:
        return None, f"⚠️ 回應格式解析錯誤: {e}"

if __name__ == '__main__':
    dashboard = connect_robot()

    print("🛠️ 建立 RS485 (Modbus RTU) 主站...")
    result = dashboard.ModbusCreate("127.0.0.1", 60000, 1, 1)  # ✅ 正確參數
    print("ModbusCreate 回應:", result)

    print("📤 開始每秒讀取夾爪位置 (暫存器 0x0202)... 按 Ctrl+C 停止")
    try:
        while True:
            resp = dashboard.GetHoldRegs(1, 0x0202, 1, "U16")
            value, error = parse_response(resp)
            if error:
                print(f"⛔ [{time.strftime('%H:%M:%S')}] 無效回應: {error}")
            else:
                print(f"🔍 [{time.strftime('%H:%M:%S')}] 夾爪位置（0~100%）: {value}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🧹 停止讀取，關閉 Modbus 通道...")
        dashboard.ModbusClose(1)
