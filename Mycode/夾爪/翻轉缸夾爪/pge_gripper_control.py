from pymodbus.client import ModbusSerialClient
from pymodbus import __version__
print(__version__)

class PGE_Gripper:
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
            raise ConnectionError("❌ Could not connect to PGE gripper")

    def write_register(self, address, value):
        result = self.client.write_register(address=address, value=value, slave=self.unit_id)
        if result.isError():
            print(f"⚠️ Failed to write {value} to register {address} (unit {self.unit_id})")
        else:
            print(f"✅ Wrote {value} to register {address} (unit {self.unit_id})")

    def read_register(self, address, count=1):
        """讀取寄存器值"""
        result = self.client.read_holding_registers(address=address, count=count, slave=self.unit_id)
        if result.isError():
            print(f"⚠️ Failed to read register {address} (unit {self.unit_id})")
            return None
        else:
            print(f"✅ Read register {address}: {result.registers[0]} (unit {self.unit_id})")
            return result.registers[0]

    def initialize(self, mode=0x01):
        """初始化夾爪，mode=0x01為回零，mode=0xA5為完全初始化"""
        self.write_register(0x0100, mode)

    def stop(self):
        """停止當前動作"""
        self.write_register(0x0100, 0)
        print("🛑 動作已停止")

    def set_position(self, value):
        """設定夾爪位置（0~1000，千分比）"""
        if not 0 <= value <= 1000:
            print(f"⚠️ Position value {value} out of range (0-1000)")
            return
        self.write_register(0x0103, value)

    def set_force(self, value):
        """設定夾爪力道（20~100，百分比）"""
        if not 20 <= value <= 100:
            print(f"⚠️ Force value {value} out of range (20-100)")
            return
        self.write_register(0x0101, value)

    def set_speed(self, value):
        """設定夾爪速度（1~100，百分比）"""
        if not 1 <= value <= 100:
            print(f"⚠️ Speed value {value} out of range (1-100)")
            return
        self.write_register(0x0104, value)

    def open(self):
        """張開夾爪（位置1000）"""
        self.set_position(1000)

    def close(self):
        """閉合夾爪（位置0）"""
        self.set_position(0)

    def get_initialization_status(self):
        """獲取初始化狀態反饋"""
        status = self.read_register(0x0200)
        if status is not None:
            status_dict = {0: "未初始化", 1: "初始化成功", 2: "初始化中"}
            print(f"🔍 初始化狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_grip_status(self):
        """獲取夾持狀態反饋"""
        status = self.read_register(0x0201)
        if status is not None:
            status_dict = {0: "運動中", 1: "到達位置", 2: "夾住物體", 3: "物體掉落"}
            print(f"🔍 夾持狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_position_feedback(self):
        """獲取位置反饋"""
        position = self.read_register(0x0202)
        if position is not None:
            print(f"🔍 當前位置: {position}")
        return position

    def get_current_settings(self):
        """獲取當前設定值"""
        print("📊 當前設定值:")
        force = self.read_register(0x0101)
        position = self.read_register(0x0103) 
        speed = self.read_register(0x0104)
        
        if force is not None:
            print(f"   力道: {force}%")
        if position is not None:
            print(f"   位置: {position}")
        if speed is not None:
            print(f"   速度: {speed}%")

    def save_settings(self):
        """保存設定到Flash"""
        print("💾 保存設定到Flash...")
        self.write_register(0x0300, 1)
        print("⚠️ 保存操作需要1-2秒，期間請勿發送其他命令")

    def disconnect(self):
        self.client.close()
        print("🔌 Serial connection closed.")