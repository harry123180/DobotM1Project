from pymodbus.client import ModbusTcpClient  # 匯入模組
import time
# Modbus TCP 伺服器設定
IP = "192.188.2.88"  # 伺服器 IP
PORT = 1000  # 伺服器 Port
UNIT_ID = 10  # Slave ID

# 目標寄存器與要寫入的值
REGISTER_ADDRESS = 58 # 目標寄存器 (單一寫入)
WRITE_VALUE =1  # 要寫入的數值 (可自行更改)

# 創建 Modbus TCP 客戶端
client = ModbusTcpClient(host=IP, port=PORT)

def write_single_register(client, address, value):
    """
    單獨寫入 Modbus TCP 保持寄存器 (Holding Register)
    :param client: ModbusTcpClient 物件
    :param address: 目標寄存器地址
    :param value: 要寫入的數值
    """
    try:
        response = client.write_register(address=address, value=value, slave=UNIT_ID)  # ✅ 單一寄存器寫入
        if response.isError():
            print(f"⚠️  寫入地址 {address} 失敗: {response}")
        else:
            print(f"✅ 成功寫入: 寄存器 {address} 設定為 {value}")
    except Exception as e:
        print(f"❌ Modbus 寫入錯誤: {e}")

# 主程式
if client.connect():
    print("✅ 已成功連接到 Modbus TCP 伺服器！")
    for i in range(10):
        # 單獨寫入 4 號寄存器
        write_single_register(client, REGISTER_ADDRESS, i)
        time.sleep(1)


    # 關閉連線
    write_single_register(client, REGISTER_ADDRESS, 0)
    client.close()
    print("🔌 已關閉 Modbus TCP 連線。")
else:
    print("❌ 無法連接到 Modbus TCP 伺服器")
