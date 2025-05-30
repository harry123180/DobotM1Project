import serial
import struct
import time

# Modbus RTU CRC 計算
def modbus_crc(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

# 組裝 Modbus RTU 封包（功能碼 0x10）
def build_modbus_packet(slave_addr, func_code, start_addr, values):
    packet = bytearray()
    packet += struct.pack('>B', slave_addr)
    packet += struct.pack('>B', func_code)
    packet += struct.pack('>H', start_addr)
    packet += struct.pack('>H', len(values))
    packet += struct.pack('>B', len(values) * 2)
    for val in values:
        packet += struct.pack('>H', val)
    crc = modbus_crc(packet)
    packet += struct.pack('<H', crc)
    return packet

# 傳送資料
def write_registers(start_addr, values):
    pkt = build_modbus_packet(0x0A, 0x10, start_addr, values)
    ser.write(pkt)
    resp = ser.read(8)
    print(f"📤 Sent: {pkt.hex()}")
    print(f"📥 Resp: {resp.hex()}")
    if resp and resp[1] == 0x90:
        print("❌ Modbus Exception Code:", hex(resp[2]))

# 建立序列埠連線
ser = serial.Serial(
    port='COM3',
    baudrate=115200,
    bytesize=8,
    parity=serial.PARITY_NONE,
    stopbits=1,
    timeout=1
)

# ✅ 初始化設定（只做一次）
write_registers(0x0058, [0x0000])             # 運轉資料 No = 0
write_registers(0x005A, [0x0002])             # 運轉方式 = 絕對定位
write_registers(0x005E, [0x0000, 0x1388])     # 速度 = 5000 Hz
write_registers(0x0060, [0x000F, 0x4240])     # 起動變速斜率 = 1000000
write_registers(0x0062, [0x000F, 0x4240])     # 停止變速斜率 = 1000000
write_registers(0x0064, [0x0000, 0x03E8])     # 運轉電流 = 100%
write_registers(0x0066, [0x0000])             # 不反映變數

# 定義兩個絕對位置
positions = [1000, 10000]

# 🔁 無限來回運轉
i = 0
while True:
    pos = positions[i % 2]
    high = (pos >> 16) & 0xFFFF
    low = pos & 0xFFFF

    print(f"➡ 移動到絕對位置：{pos} step")

    write_registers(0x005C, [high, low])      # 設定目標位置
    write_registers(0x0068, [0x0001])         # ✅ 運轉觸發

    time.sleep(1)  # 等待 1 秒
    i += 1

# ser.close()  # 若有需要可在條件下關閉連線
