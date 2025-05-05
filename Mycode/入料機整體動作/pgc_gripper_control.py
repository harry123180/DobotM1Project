from pymodbus.client import ModbusSerialClient
from pymodbus import __version__
print(__version__)
class PGC_Gripper:
    def __init__(self, port='COM3', baudrate=115200, parity='N', stopbits=1, unit_id=1):
        self.client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            stopbits=stopbits,
            parity=parity,
            timeout=1
        )
        self.unit_id = unit_id
        if self.client.connect():
            print(f"✅ Connected to {port} @ {baudrate}bps")
        else:
            raise ConnectionError("❌ Could not connect to PGC gripper")

    def write_register(self, address, value):
        result = self.client.write_register(address=address, value=value, slave=self.unit_id)
        if result.isError():
            print(f"⚠️ Failed to write {value} to register {address} (unit {self.unit_id})")
        else:
            print(f"✅ Wrote {value} to register {address} (unit {self.unit_id})")


    def initialize(self, mode=0x01):
        """初始化夹爪，mode=0x01为回零，mode=0xA5为完全初始化"""
        self.write_register(0x0100, mode)

    def stop(self):
        """断开当前动作"""
        self.write_register(0x0100, 0)
        print("🛑 動作已停止")

    def set_position(self, value):
        """设定夹爪位置（0~1000，千分比）"""
        self.write_register(0x0103, value)

    def set_force(self, value):
        """设定夹爪力道（20~100，百分比）"""
        self.write_register(0x0101, value)

    def set_speed(self, value):
        """设定夹爪速度（1~100，百分比）"""
        self.write_register(0x0104, value)

    def open(self):
        """张开夹爪（位置1000）"""
        self.set_position(1000)

    def close(self):
        """闭合夹爪（位置0）"""
        self.set_position(0)

    def disconnect(self):
        self.client.close()
        print("🔌 Serial connection closed.")