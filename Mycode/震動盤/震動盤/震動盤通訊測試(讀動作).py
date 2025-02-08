from pymodbus.client import ModbusTcpClient  # 匯入模組

# 定義地址與描述的對應字典
address_map = {
    20: "動作-上-強度",
    21: "動作-下-強度",
    22: "動作-左-強度",
    23: "動作-右-強度",
    24: "動作-左上-強度",
    25: "動作-左下-強度",
    26: "動作-右上-強度",
    27: "動作-右下-強度",
    28: "動作-橫-強度",
    29: "動作-縱-強度",
    30: "動作-散開-強度",
    60: "動作-上-頻率",
    61: "動作-下-頻率",
    62: "動作-左-頻率",
    63: "動作-右-頻率",
    64: "動作-左上-頻率",
    65: "動作-左下-頻率",
    66: "動作-右上-頻率",
    67: "動作-右下-頻率",
    68: "動作-橫-頻率",
    69: "動作-縱-頻率",
    70: "動作-散開-頻率",
}

# Modbus TCP 通訊設定
IP = "192.188.2.88"
PORT = 1000

# 創建 Modbus TCP 客戶端
client = ModbusTcpClient(host=IP, port=PORT)

def read_registers(client, start_address, count):
    """讀取保持寄存器的數據"""
    try:
        # **只傳遞 2 個參數，移除 unit/slave**
        response = client.read_holding_registers(address=start_address, count=count,slave=10)  # ✅ 必須使用關鍵字參數
        
        if response.isError():
            print(f"讀取地址範圍 {start_address} - {start_address + count - 1} 失敗: {response}")
            return None
        return response.registers
    except Exception as e:
        print(f"Modbus 讀取錯誤: {e}")
        return None

# 主程式
if client.connect():
    results = {}
    # 讀取地址範圍 20~30 和 60~70
    for start_address, count in [(20, 11), (60, 11)]:
        registers = read_registers(client, start_address, count)
        if registers:
            for i, value in enumerate(registers):
                address = start_address + i
                if address in address_map:
                    results[address_map[address]] = value

    # 格式化輸出結果
    for key, value in results.items():
        print(f"{key}: {value}")
    
    client.close()
else:
    print("無法連接到 Modbus TCP 伺服器")
