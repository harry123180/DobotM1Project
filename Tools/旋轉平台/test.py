import serial
import serial.tools.list_ports
import struct
import time
import sys

class ModbusDiagnostic:
    def __init__(self):
        self.serial_conn = None
        
    def calculate_crc16(self, data):
        """計算CRC-16校驗碼 - 根據手冊實現"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def connect(self, port, baudrate=115200, slave_id=3):
        """建立連接"""
        try:
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity=serial.PARITY_NONE,  # 根據手冊預設為無校驗
                stopbits=1,
                timeout=2
            )
            self.slave_id = slave_id
            print(f"✓ 成功連接到 {port}, 波特率: {baudrate}, 站號: {slave_id}")
            print(f"  數據格式: 8-N-1 (8位數據, 無校驗, 1停止位)")
            return True
        except Exception as e:
            print(f"✗ 連接失敗: {e}")
            return False
    
    def send_raw_frame(self, frame_hex):
        """發送原始幀並接收回應"""
        if not self.serial_conn:
            print("✗ 未建立連接")
            return None
            
        try:
            # 轉換hex字符串為bytes
            frame = bytes.fromhex(frame_hex.replace(' ', ''))
            
            print(f"\n→ 發送: {' '.join(f'{b:02X}' for b in frame)}")
            
            # 清空接收緩衝區
            self.serial_conn.reset_input_buffer()
            
            # 發送幀
            self.serial_conn.write(frame)
            
            # 等待回應
            time.sleep(0.2)
            response = self.serial_conn.read(256)
            
            if response:
                print(f"← 接收: {' '.join(f'{b:02X}' for b in response)}")
                return response
            else:
                print("← 無回應")
                return None
                
        except Exception as e:
            print(f"✗ 通訊錯誤: {e}")
            return None
    
    def build_modbus_frame(self, function_code, data_bytes):
        """構建Modbus幀"""
        frame = bytearray()
        frame.append(self.slave_id)
        frame.append(function_code)
        frame.extend(data_bytes)
        
        # 計算CRC
        crc = self.calculate_crc16(frame)
        frame.extend(struct.pack('<H', crc))  # 小端序
        
        return frame
    
    def test_basic_communication(self):
        """基本通訊測試"""
        print("\n" + "="*50)
        print("基本通訊測試")
        print("="*50)
        
        # 測試1: 診斷功能 (功能碼 08h)
        print("\n1. 診斷測試 (功能碼 08h)")
        print("   發送任意數據並期望相同回應...")
        
        # 根據手冊：副功能碼00h，測試數據1234h
        data = struct.pack('>HH', 0x0000, 0x1234)  # 副功能碼 + 測試數據
        frame = self.build_modbus_frame(0x08, data)
        
        response = self.send_raw_frame(frame.hex())
        
        if response and len(response) >= 8:
            if response[0] == self.slave_id and response[1] == 0x08:
                received_data = struct.unpack('>H', response[4:6])[0]
                if received_data == 0x1234:
                    print("   ✓ 診斷測試成功 - 設備回應正確")
                    return True
                else:
                    print(f"   ✗ 數據不匹配 - 期望: 1234, 收到: {received_data:04X}")
            else:
                print(f"   ✗ 回應格式錯誤 - 站號: {response[0]}, 功能碼: {response[1]:02X}")
        else:
            print("   ✗ 診斷測試失敗 - 無效回應")
            
        return False
    
    def test_read_functions(self):
        """測試讀取功能"""
        print("\n" + "="*50)
        print("讀取功能測試")
        print("="*50)
        
        # 根據手冊中的重要寄存器地址進行測試
        test_addresses = [
            (126, 2, "驅動器輸出狀態"),      # 007Eh - 驅動器輸出狀態
            (124, 2, "驅動器輸入指令"),      # 007Ch - 驅動器輸入指令  
            (48, 2, "群組ID"),              # 0030h - 群組ID
            (88, 2, "直接資料運轉資料No"),   # 0058h - 直接資料運轉
        ]
        
        success_count = 0
        
        for addr, count, desc in test_addresses:
            print(f"\n2. 讀取 {desc} (地址: {addr}, 數量: {count})")
            
            # 功能碼03h: 讀取保持寄存器
            data = struct.pack('>HH', addr, count)
            frame = self.build_modbus_frame(0x03, data)
            
            response = self.send_raw_frame(frame.hex())
            
            if response and len(response) >= 5:
                if response[0] == self.slave_id and response[1] == 0x03:
                    data_len = response[2]
                    if len(response) >= 5 + data_len:
                        # 解析數據
                        values = []
                        for i in range(0, data_len, 2):
                            if i + 1 < data_len:
                                val = struct.unpack('>H', response[3+i:3+i+2])[0]
                                values.append(val)
                        
                        print(f"   ✓ 讀取成功: {[f'{v:04X}h ({v})' for v in values]}")
                        success_count += 1
                    else:
                        print(f"   ✗ 數據長度錯誤 - 期望: {data_len}, 實際: {len(response)-5}")
                elif response[1] & 0x80:  # 異常回應
                    exception_code = response[2]
                    exception_msg = {
                        0x01: "不正確功能碼",
                        0x02: "不正確資料位址", 
                        0x03: "不正確資料",
                        0x04: "伺服器錯誤"
                    }
                    print(f"   ✗ 異常回應: {exception_msg.get(exception_code, f'未知錯誤 {exception_code:02X}')}")
                else:
                    print(f"   ✗ 回應格式錯誤 - 站號: {response[0]}, 功能碼: {response[1]:02X}")
            else:
                print(f"   ✗ 讀取失敗 - 回應長度不足或無回應")
        
        print(f"\n讀取測試結果: {success_count}/{len(test_addresses)} 成功")
        return success_count > 0
    
    def test_write_functions(self):
        """測試寫入功能"""
        print("\n" + "="*50)
        print("寫入功能測試")
        print("="*50)
        
        # 測試寫入群組ID (安全的測試地址)
        print("\n3. 寫入測試 - 群組ID (地址: 48)")
        print("   讀取當前值...")
        
        # 先讀取當前值
        data = struct.pack('>HH', 48, 2)
        frame = self.build_modbus_frame(0x03, data)
        response = self.send_raw_frame(frame.hex())
        
        original_value = None
        if response and len(response) >= 9:
            if response[0] == self.slave_id and response[1] == 0x03:
                original_value = struct.unpack('>HH', response[3:7])
                print(f"   當前群組ID: {original_value[0]:04X}h {original_value[1]:04X}h")
        
        # 測試寫入 (寫入-1表示個別模式)
        print("   嘗試寫入測試值...")
        data = struct.pack('>HH', 48, 0xFFFF)  # 寫入-1 (個別模式)
        frame = self.build_modbus_frame(0x06, data)
        
        response = self.send_raw_frame(frame.hex())
        
        if response and len(response) >= 8:
            if response[0] == self.slave_id and response[1] == 0x06:
                print("   ✓ 寫入成功")
                
                # 驗證寫入
                print("   驗證寫入結果...")
                data = struct.pack('>HH', 48, 2)
                frame = self.build_modbus_frame(0x03, data)
                verify_response = self.send_raw_frame(frame.hex())
                
                if verify_response and len(verify_response) >= 9:
                    new_value = struct.unpack('>HH', verify_response[3:7])
                    print(f"   驗證結果: {new_value[0]:04X}h {new_value[1]:04X}h")
                    
                    if new_value[0] == 0xFFFF:
                        print("   ✓ 寫入驗證成功")
                        return True
                    
        print("   ✗ 寫入測試失敗")
        return False
    
    def test_communication_parameters(self):
        """測試不同通訊參數"""
        print("\n" + "="*50)
        print("通訊參數測試")
        print("="*50)
        
        # 測試不同波特率
        baudrates = [9600, 19200, 38400, 57600, 115200, 230400]
        parities = [
            (serial.PARITY_NONE, "無校驗"),
            (serial.PARITY_EVEN, "偶校驗"),
            (serial.PARITY_ODD, "奇校驗")
        ]
        
        current_port = self.serial_conn.port
        current_slave = self.slave_id
        
        print(f"當前設定 - 波特率: {self.serial_conn.baudrate}, 校驗: 無校驗")
        
        # 測試不同校驗方式
        print("\n測試不同校驗方式...")
        for parity, desc in parities:
            if parity == serial.PARITY_NONE:
                continue
                
            print(f"\n嘗試{desc}...")
            
            # 重新連接
            self.serial_conn.close()
            try:
                self.serial_conn = serial.Serial(
                    port=current_port,
                    baudrate=115200,
                    bytesize=8,
                    parity=parity,
                    stopbits=1,
                    timeout=1
                )
                
                # 簡單診斷測試
                data = struct.pack('>HH', 0x0000, 0x1234)
                frame = self.build_modbus_frame(0x08, data)
                response = self.send_raw_frame(frame.hex())
                
                if response and len(response) >= 8 and response[0] == current_slave:
                    print(f"   ✓ {desc} 通訊成功!")
                else:
                    print(f"   ✗ {desc} 通訊失敗")
                    
            except:
                print(f"   ✗ 無法使用{desc}")
        
        # 測試不同波特率
        print("\n測試不同波特率...")
        for baud in baudrates:
            if baud == 115200:  # 跳過當前波特率
                continue
                
            print(f"\n嘗試波特率 {baud}...")
            
            # 重新連接
            self.serial_conn.close()
            try:
                self.serial_conn = serial.Serial(
                    port=current_port,
                    baudrate=baud,
                    bytesize=8,
                    parity=serial.PARITY_NONE,
                    stopbits=1,
                    timeout=1
                )
                
                # 簡單診斷測試
                data = struct.pack('>HH', 0x0000, 0x1234)
                frame = self.build_modbus_frame(0x08, data)
                response = self.send_raw_frame(frame.hex())
                
                if response and len(response) >= 8 and response[0] == current_slave:
                    print(f"   ✓ 波特率 {baud} 通訊成功!")
                else:
                    print(f"   ✗ 波特率 {baud} 通訊失敗")
                    
            except:
                print(f"   ✗ 無法使用波特率 {baud}")
        
        # 恢復原始連接
        self.serial_conn.close()
        self.connect(current_port, 115200, current_slave)
    
    def full_diagnostic(self):
        """完整診斷流程"""
        print("Modbus RTU 診斷工具")
        print("根據AZ系列驅動器手冊實現")
        print("="*50)
        
        # 基本通訊測試
        comm_ok = self.test_basic_communication()
        
        if comm_ok:
            print("\n✓ 基本通訊正常，繼續進階測試...")
            
            # 讀取功能測試
            read_ok = self.test_read_functions()
            
            # 寫入功能測試  
            write_ok = self.test_write_functions()
            
            # 通訊參數測試
            self.test_communication_parameters()
            
            # 總結
            print("\n" + "="*50)
            print("診斷總結")
            print("="*50)
            print(f"基本通訊: {'✓ 正常' if comm_ok else '✗ 失敗'}")
            print(f"讀取功能: {'✓ 正常' if read_ok else '✗ 失敗'}")
            print(f"寫入功能: {'✓ 正常' if write_ok else '✗ 失敗'}")
            
            if comm_ok and read_ok and write_ok:
                print("\n🎉 所有測試通過！設備通訊正常。")
            else:
                print("\n⚠️  部分測試失敗，請檢查設備設定。")
                
        else:
            print("\n❌ 基本通訊失敗！")
            print("請檢查:")
            print("1. 硬體連接是否正確")
            print("2. COM口是否正確")  
            print("3. 波特率設定是否匹配")
            print("4. 站號是否正確")
            print("5. 數據格式是否為 8-N-1")
            print("6. 設備是否已正確配置Modbus RTU模式")
            print("7. 終端電阻是否正確設定")
    
    def close(self):
        """關閉連接"""
        if self.serial_conn:
            self.serial_conn.close()

def main():
    # 掃描可用COM口
    print("掃描可用COM口...")
    ports = [port.device for port in serial.tools.list_ports.comports()]
    
    if not ports:
        print("未找到可用的COM口!")
        return
    
    print(f"找到COM口: {', '.join(ports)}")
    
    # 選擇COM口
    if len(ports) == 1:
        selected_port = ports[0]
        print(f"自動選擇: {selected_port}")
    else:
        print("\n請選擇COM口:")
        for i, port in enumerate(ports):
            print(f"{i+1}. {port}")
        
        try:
            choice = int(input("輸入編號: ")) - 1
            selected_port = ports[choice]
        except (ValueError, IndexError):
            print("輸入無效，使用第一個COM口")
            selected_port = ports[0]
    
    # 輸入站號
    try:
        slave_id = int(input("輸入站號 (預設3): ") or "3")
    except ValueError:
        slave_id = 3
        print("使用預設站號: 3")
    
    # 開始診斷
    diagnostic = ModbusDiagnostic()
    
    try:
        if diagnostic.connect(selected_port, 115200, slave_id):
            diagnostic.full_diagnostic()
        else:
            print("無法建立連接，診斷終止。")
    finally:
        diagnostic.close()
        
    input("\n按Enter鍵退出...")

if __name__ == "__main__":
    main()