from pymodbus.client import ModbusTcpClient
import struct

# Modbus伺服器設定
modbus_ip = "192.168.1.6"
modbus_port = 502
register_address = 242  # 脚本地址 (GetInRegs)

def read_float32_register(client, address):
    try:
        # 從指定地址讀取1個寄存器 (32位元需要2個寄存器)
        response = client.read_input_registers(address, count=2, slave=1)
        if not response.isError():  # 驗證是否成功
            # 拼接寄存器值
            registers = response.registers
            # 手動處理字節順序 (Little Endian word order)
            raw_data = struct.pack(">HH", registers[1], registers[0])
            # 將二進制數據轉為浮點數
            value = struct.unpack(">f", raw_data)[0]
            return value
        else:
            print(f"讀取寄存器失敗: {response}")
            return None
    except Exception as e:
        print(f"發生錯誤: {e}")
        return None

if __name__ == "__main__":
    # 建立Modbus TCP連接
    client = ModbusTcpClient(host=modbus_ip, port=modbus_port)
    try:
        if client.connect():
            print("成功連接到Modbus伺服器")

            # 讀取寄存器
            value = read_float32_register(client, register_address)
            if value is not None:
                print(f"寄存器地址 {register_address} 的值為: {value}")
            else:
                print("無法獲取值")
        else:
            print("無法連接到Modbus伺服器")
    finally:
        client.close()
