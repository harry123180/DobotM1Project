from pymodbus.client import ModbusSerialClient
from pymodbus import __version__
print(__version__)

class XC100_Controller:
    def __init__(self, port='COM4', baudrate=115200, parity='N', stopbits=1, unit_id=1):
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
            raise ConnectionError("❌ Could not connect to XC100 controller")

    def write_register(self, address, value):
        """寫入單個寄存器"""
        result = self.client.write_register(address=address, value=value, slave=self.unit_id)
        if result.isError():
            print(f"⚠️ Failed to write {value} to register {address:04X}H (unit {self.unit_id})")
        else:
            print(f"✅ Wrote {value} to register {address:04X}H (unit {self.unit_id})")

    def write_registers(self, address, values):
        """寫入多個寄存器"""
        result = self.client.write_registers(address=address, values=values, slave=self.unit_id)
        if result.isError():
            print(f"⚠️ Failed to write {values} to register {address:04X}H (unit {self.unit_id})")
        else:
            print(f"✅ Wrote {values} to register {address:04X}H (unit {self.unit_id})")

    def read_register(self, address, count=1):
        """讀取寄存器值"""
        result = self.client.read_holding_registers(address=address, count=count, slave=self.unit_id)
        if result.isError():
            print(f"⚠️ Failed to read register {address:04X}H (unit {self.unit_id})")
            return None
        else:
            if count == 1:
                print(f"✅ Read register {address:04X}H: {result.registers[0]} (unit {self.unit_id})")
                return result.registers[0]
            else:
                print(f"✅ Read registers {address:04X}H: {result.registers} (unit {self.unit_id})")
                return result.registers

    def servo_on(self):
        """伺服ON"""
        self.write_register(0x2011, 0)
        print("🔧 伺服ON")

    def servo_off(self):
        """伺服OFF"""
        self.write_register(0x2011, 1)
        print("🔧 伺服OFF")

    def origin_return(self):
        """原點復歸（歸零）"""
        self.write_register(0x201E, 3)  # ORG 原點復歸
        print("🏠 執行原點復歸")

    def set_speed(self, speed_percent):
        """設定速度（1-100%）"""
        if not 1 <= speed_percent <= 100:
            print(f"⚠️ Speed value {speed_percent} out of range (1-100)")
            return
        self.write_register(0x2014, speed_percent)
        print(f"🏃 設定速度: {speed_percent}%")

    def absolute_move(self, position):
        """絕對位置移動"""
        # 設定移動類型為絕對位置移動
        self.write_register(0x201E, 1)  # ABS 絕對位置移動
        
        # 設定目標位置（需要使用32位元，分成兩個16位元寄存器）
        position_high = (position >> 16) & 0xFFFF
        position_low = position & 0xFFFF
        
        self.write_registers(0x2002, [position_high, position_low])
        print(f"📍 絕對移動到位置: {position}")

    def relative_move(self, distance):
        """相對位置移動"""
        # 設定移動類型為相對位置移動
        self.write_register(0x201E, 0)  # INC 相對位置移動
        
        # 設定移動距離（需要使用32位元，分成兩個16位元寄存器）
        # 處理負值
        if distance < 0:
            distance = (1 << 32) + distance  # 轉換為32位無符號整數
            
        distance_high = (distance >> 16) & 0xFFFF
        distance_low = distance & 0xFFFF
        
        self.write_registers(0x2000, [distance_high, distance_low])
        print(f"📍 相對移動距離: {distance}")

    def emergency_stop(self):
        """緊急停止"""
        self.write_register(0x201E, 9)  # 緊急停止
        print("🛑 緊急停止")

    def deceleration_stop(self):
        """減速停止"""
        self.write_register(0x201E, 8)  # 減速停止
        print("🛑 減速停止")

    def get_action_status(self):
        """獲取動作狀態"""
        status = self.read_register(0x1000)
        if status is not None:
            status_dict = {0: "停止", 1: "動作中", 2: "異常停止"}
            print(f"🔍 動作狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_position_status(self):
        """獲取到位狀態"""
        status = self.read_register(0x1001)
        if status is not None:
            status_dict = {
                0: "目前位置尚未到達設定範圍內", 
                1: "目前位置已在目標設定範圍內"
            }
            print(f"🔍 到位狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_current_position(self):
        """獲取當前位置"""
        position_regs = self.read_register(0x1008, 2)  # 讀取2個寄存器
        if position_regs is not None:
            # 合併32位元位置值
            position = (position_regs[0] << 16) | position_regs[1]
            # 處理符號位（如果是負數）
            if position >= (1 << 31):
                position -= (1 << 32)
            print(f"🔍 當前位置: {position}")
            return position
        return None

    def get_servo_status(self):
        """獲取伺服狀態"""
        status = self.read_register(0x100C)
        if status is not None:
            status_dict = {0: "伺服OFF", 1: "伺服ON"}
            print(f"🔍 伺服狀態: {status_dict.get(status, '未知狀態')}")
        return status

    def get_alarm_status(self):
        """獲取警報狀態"""
        status = self.read_register(0x1005)
        if status is not None:
            alarm_dict = {
                0: "無警報",
                1: "Loop error",
                2: "Full Count",
                3: "過速度",
                4: "增益值調整不良",
                5: "過電壓",
                6: "初期化異常",
                7: "EEPROM異常",
                8: "主迴路電源電壓不足",
                9: "過電流",
                10: "回生異常",
                11: "緊急停止",
                12: "馬達斷線",
                13: "編碼器斷線",
                14: "保護電流值",
                15: "電源再投入",
                17: "動作超時"
            }
            print(f"🔍 警報狀態: {alarm_dict.get(status, f'未知警報代碼: {status}')}")
        return status

    def wait_for_completion(self, timeout=30):
        """等待動作完成"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            action_status = self.get_action_status()
            position_status = self.get_position_status()
            
            if action_status == 0 and position_status == 1:  # 停止且到位
                print("✅ 動作完成")
                return True
            elif action_status == 2:  # 異常停止
                print("❌ 動作異常停止")
                self.get_alarm_status()
                return False
                
            time.sleep(0.5)
        
        print("⏰ 等待超時")
        return False

    def disconnect(self):
        """斷開連線"""
        self.client.close()
        print("🔌 Serial connection closed.")