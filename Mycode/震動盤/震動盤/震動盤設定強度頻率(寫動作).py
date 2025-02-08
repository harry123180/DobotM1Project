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
UNIT_ID = 10  # Slave ID

# 創建 Modbus TCP 客戶端
client = ModbusTcpClient(host=IP, port=PORT)

def write_modbus_registers(client, values):
    """
    批量寫入 Modbus TCP 寄存器
    :param client: ModbusTcpClient 物件
    :param values: 需要寫入的數據，格式 {address: value}
    """
    try:
        for address, value in values.items():
            response = client.write_register(address=address, value=value, slave=UNIT_ID)  # ✅ 使用關鍵字參數
            if response.isError():
                print(f"寫入地址 {address} 失敗: {response}")
            else:
                print(f"寫入成功: {address_map.get(address, '未知地址')} ({address}) 設定為 {value}")
    except Exception as e:
        print(f"Modbus 寫入錯誤: {e}")

# 主程式
if client.connect():
    print("成功連接到 Modbus TCP 伺服器！")

    # 設定所有動作強度與頻率的數值（範例數值，可根據需求調整）
    write_values = {
        20: 100,  # 動作-上-強度
        21: 100,   # 動作-下-強度
        22: 100,   # 動作-左-強度
        23: 100,   # 動作-右-強度
        24: 100,   # 動作-左上-強度
        25: 100,   # 動作-左下-強度
        26: 100,   # 動作-右上-強度
        27: 100,   # 動作-右下-強度
        28: 100,   # 動作-橫-強度
        29: 100,   # 動作-縱-強度
        30: 85,    # 動作-散開-強度
        60: 109,  # 動作-上-頻率
        61: 109,  # 動作-下-頻率
        62: 109,  # 動作-左-頻率
        63: 109,  # 動作-右-頻率
        64: 109,  # 動作-左上-頻率
        65: 109,  # 動作-左下-頻率
        66: 109,  # 動作-右上-頻率
        67: 109,  # 動作-右下-頻率
        68: 109,  # 動作-橫-頻率
        69: 110,  # 動作-縱-頻率
        70: 100   # 動作-散開-頻率
    }

    # 寫入數據
    write_modbus_registers(client, write_values)

    # 關閉連接
    client.close()
    print("已關閉 Modbus TCP 連線。")
else:
    print("無法連接到 Modbus TCP 伺服器")
