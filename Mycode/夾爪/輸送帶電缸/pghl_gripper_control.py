from pymodbus.client import ModbusSerialClient
from pymodbus import __version__
print(__version__)

class PGHL_Gripper:
    def __init__(self, port='COM4', baudrate=115200, parity='N', stopbits=1, unit_id=5):
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
            raise ConnectionError("❌ Could not connect to PGHL gripper")

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

    def home(self):
        """夾爪回零"""
        self.write_register(0x0100, 1)

    def stop(self):
        """停止當前動作"""
        self.write_register(0x0100, 0)
        print("🛑 動作已停止")

    def set_push_force(self, value):
        """設定推壓力值（20~100，百分比）"""
        if not 20 <= value <= 100:
            print(f"⚠️ Push force value {value} out of range (20-100)")
            return
        self.write_register(0x0101, value)

    def set_push_length(self, value):
        """設定推壓段長度（0~65535，單位0.01mm）"""
        if not 0 <= value <= 65535:
            print(f"⚠️ Push length value {value} out of range (0-65535)")
            return
        self.write_register(0x0102, value)

    def set_target_position(self, value):
        """設定目標位置（0~65535，單位0.01mm）"""
        if not 0 <= value <= 65535:
            print(f"⚠️ Target position value {value} out of range (0-65535)")
            return
        self.write_register(0x0103, value)

    def set_max_speed(self, value):
        """設定最大速度（50~100，百分比）"""
        if not 50 <= value <= 100:
            print(f"⚠️ Max speed value {value} out of range (50-100)")
            return
        self.write_register(0x0104, value)

    def set_acceleration(self, value):
        """設定加/減速度（1~100，百分比）"""
        if not 1 <= value <= 100:
            print(f"⚠️ Acceleration value {value} out of range (1-100)")
            return
        self.write_register(0x0105, value)

    def set_relative_position(self, value):
        """設定相對位置（-32767~32767，單位0.01mm）"""
        if not -32767 <= value <= 32767:
            print(f"⚠️ Relative position value {value} out of range (-32767-32767)")
            return
        self.write_register(0x0106, value)

    def jog_control(self, direction):
        """點動控制（-1閉合，0停止，1張開）"""
        if direction not in [-1, 0, 1]:
            print(f"⚠️ Jog direction must be -1, 0, or 1")
            return
        self.write_register(0x0107, direction)

    def open_gripper(self, distance_mm=50):
        """張開夾爪到指定距離（單位：mm）"""
        distance_0_01mm = distance_mm * 100  # 轉換為0.01mm單位
        self.set_target_position(distance_0_01mm)

    def close_gripper(self):
        """閉合夾爪到0位置"""
        self.set_target_position(0)

    def get_home_status(self):
        """獲取回零狀態反饋"""
        status = self.read_register(0x0200)
        if status is not None:
            status_dict = {0: "未初始化", 1: "初始化成功", 2: "初始化中"}
            print(f"🔍 回零狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_running_status(self):
        """獲取運行狀態反饋"""
        status = self.read_register(0x0201)
        if status is not None:
            status_dict = {
                0: "運動中", 
                1: "到達位置", 
                2: "堵轉", 
                3: "掉落",
                -1: "非推壓段碰撞物體"
            }
            print(f"🔍 運行狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_position_feedback(self):
        """獲取位置反饋"""
        position = self.read_register(0x0202)
        if position is not None:
            position_mm = position / 100.0  # 轉換為mm
            print(f"🔍 當前位置: {position} (0.01mm) = {position_mm:.2f}mm")
        return position

    def get_current_feedback(self):
        """獲取電流反饋"""
        current = self.read_register(0x0204)
        if current is not None:
            print(f"🔍 當前電流: {current}")
        return current

    def get_current_settings(self):
        """獲取當前設定值"""
        print("📊 當前設定值:")
        
        push_force = self.read_register(0x0101)
        push_length = self.read_register(0x0102)
        target_pos = self.read_register(0x0103)
        max_speed = self.read_register(0x0104)
        acceleration = self.read_register(0x0105)
        
        if push_force is not None:
            print(f"   推壓力值: {push_force}%")
        if push_length is not None:
            print(f"   推壓段長度: {push_length} (0.01mm) = {push_length/100:.2f}mm")
        if target_pos is not None:
            print(f"   目標位置: {target_pos} (0.01mm) = {target_pos/100:.2f}mm")
        if max_speed is not None:
            print(f"   最大速度: {max_speed}%")
        if acceleration is not None:
            print(f"   加速度: {acceleration}%")

    def set_push_speed(self, value):
        """設定推壓速度（10~40，百分比）"""
        if not 10 <= value <= 40:
            print(f"⚠️ Push speed value {value} out of range (10-40)")
            return
        self.write_register(0x0309, value)

    def set_push_direction(self, direction):
        """設定推壓方向（0張開，1閉合，2雙向）"""
        if direction not in [0, 1, 2]:
            print(f"⚠️ Push direction must be 0, 1, or 2")
            return
        self.write_register(0x030A, direction)

    def set_home_direction(self, direction):
        """設定回零方向（0張開歸零，1閉合歸零）"""
        if direction not in [0, 1]:
            print(f"⚠️ Home direction must be 0 or 1")
            return
        self.write_register(0x0301, direction)

    def save_settings(self):
        """保存設定到Flash"""
        print("💾 保存設定到Flash...")
        self.write_register(0x0300, 1)
        print("⚠️ 保存操作需要1-2秒，期間請勿發送其他命令")

    def test_io_parameters(self, group):
        """測試IO參數（0~3組）"""
        if group not in [0, 1, 2, 3]:
            print(f"⚠️ IO group must be 0, 1, 2, or 3")
            return
        self.write_register(0x0400, group)

    def move_to_position_mm(self, position_mm):
        """移動到指定位置（單位：mm）"""
        position_0_01mm = int(position_mm * 100)  # 轉換為0.01mm單位
        self.set_target_position(position_0_01mm)

    def set_push_length_mm(self, length_mm):
        """設定推壓段長度（單位：mm）"""
        length_0_01mm = int(length_mm * 100)  # 轉換為0.01mm單位
        self.set_push_length(length_0_01mm)

    def move_relative_mm(self, distance_mm):
        """相對移動（單位：mm）"""
        distance_0_01mm = int(distance_mm * 100)  # 轉換為0.01mm單位
        self.set_relative_position(distance_0_01mm)

    def disconnect(self):
        self.client.close()
        print("🔌 Serial connection closed.")