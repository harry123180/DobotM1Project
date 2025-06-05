import customtkinter as ctk
import serial
import serial.tools.list_ports
import struct
import threading
import time
from tkinter import messagebox

# 設定customtkinter外觀
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class ModbusRTU:
    def __init__(self, port, baudrate, bytesize, parity, stopbits, slave_id):
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.slave_id = slave_id
        self.serial_conn = None
        
    def connect(self):
        try:
            # 增加更詳細的錯誤檢查
            if not self.port:
                print("錯誤: 未選擇COM口")
                return False
                
            # 檢查COM口是否存在
            available_ports = [port.device for port in serial.tools.list_ports.comports()]
            if self.port not in available_ports:
                print(f"錯誤: COM口 {self.port} 不存在")
                print(f"可用的COM口: {available_ports}")
                return False
            
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=3  # 增加超時時間到3秒
            )
            
            # 測試連接
            time.sleep(0.1)  # 給串口一些時間初始化
            if not self.serial_conn.is_open:
                print("錯誤: 串口未能成功開啟")
                return False
                
            print(f"連接成功: {self.port} - {self.baudrate}bps - 站號{self.slave_id}")
            
            # 嘗試簡單的通訊測試
            test_result = self.test_communication()
            if test_result:
                print("通訊測試成功")
                return True
            else:
                print("警告: 通訊測試失敗，但串口已連接")
                return True  # 仍然返回True，讓用戶可以手動測試
                
        except serial.SerialException as e:
            print(f"串口錯誤: {e}")
            return False
        except Exception as e:
            print(f"未知連接錯誤: {e}")
            return False
    
    def test_communication(self):
        """測試基本通訊功能"""
        try:
            # 嘗試讀取一個簡單的寄存器
            response = self.send_request(0x03, 126, 1)
            return response is not None and len(response) > 0
        except Exception as e:
            print(f"通訊測試錯誤: {e}")
            return False
    
    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.close()
                print("連接已斷開")
            except Exception as e:
                print(f"斷開連接時發生錯誤: {e}")
    
    def calculate_crc16(self, data):
        """計算CRC-16校驗碼"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def send_request(self, function_code, address, data):
        """發送Modbus請求 - 增加錯誤處理"""
        if not self.serial_conn or not self.serial_conn.is_open:
            print("錯誤: 串口未連接")
            return None
            
        try:
            # 構建請求幀
            frame = bytearray()
            frame.append(self.slave_id)
            frame.append(function_code)
            
            if function_code == 0x03:  # 讀取保持寄存器
                frame.extend(struct.pack('>HH', address, data))
            elif function_code == 0x06:  # 寫入單個寄存器
                frame.extend(struct.pack('>HH', address, data))
            elif function_code == 0x10:  # 寫入多個寄存器
                start_addr, values = data
                frame.extend(struct.pack('>HHB', start_addr, len(values), len(values) * 2))
                for value in values:
                    frame.extend(struct.pack('>H', value))
            
            # 計算並添加CRC
            crc = self.calculate_crc16(frame)
            frame.extend(struct.pack('<H', crc))
            
            # 清空接收緩衝區
            self.serial_conn.reset_input_buffer()
            
            # 發送請求
            bytes_sent = self.serial_conn.write(frame)
            print(f"發送 {bytes_sent} 字節: {' '.join(f'{b:02X}' for b in frame)}")
            
            # 等待回應
            time.sleep(0.3)  # 增加等待時間
            
            # 讀取回應
            response = self.serial_conn.read(256)
            
            if response:
                print(f"接收 {len(response)} 字節: {' '.join(f'{b:02X}' for b in response)}")
                
                # 基本回應驗證
                if len(response) < 3:
                    print("錯誤: 回應長度太短")
                    return None
                    
                if response[0] != self.slave_id:
                    print(f"錯誤: 站號不匹配，期望{self.slave_id}，收到{response[0]}")
                    return None
                    
                return response
            else:
                print("錯誤: 未收到回應")
                return None
                
        except serial.SerialTimeoutException:
            print("錯誤: 通訊超時")
            return None
        except Exception as e:
            print(f"通訊錯誤: {e}")
            return None
    
    def read_holding_registers(self, address, count):
        """讀取保持寄存器 - 增加安全檢查"""
        try:
            response = self.send_request(0x03, address, count)
            if response and len(response) >= 5:
                # 驗證回應
                if response[0] == self.slave_id and response[1] == 0x03:
                    data_len = response[2]
                    if len(response) >= 3 + data_len + 2:  # 檢查數據長度
                        data = response[3:3+data_len]
                        # 解析16位寄存器值
                        values = []
                        for i in range(0, len(data), 2):
                            if i + 1 < len(data):
                                values.append(struct.unpack('>H', data[i:i+2])[0])
                        return values
                    else:
                        print(f"錯誤: 數據長度不足，期望{3+data_len+2}，收到{len(response)}")
                else:
                    print(f"錯誤: 功能碼不匹配，期望03，收到{response[1]:02X}")
            return None
        except Exception as e:
            print(f"讀取寄存器錯誤: {e}")
            return None
    
    def write_single_register(self, address, value):
        """寫入單個寄存器"""
        try:
            response = self.send_request(0x06, address, value)
            return response is not None and len(response) >= 6
        except Exception as e:
            print(f"寫入單個寄存器錯誤: {e}")
            return False
    
    def write_multiple_registers(self, start_address, values):
        """寫入多個寄存器"""
        try:
            response = self.send_request(0x10, start_address, (start_address, values))
            return response is not None and len(response) >= 6
        except Exception as e:
            print(f"寫入多個寄存器錯誤: {e}")
            return False

class ModbusControlApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Modbus RTU 旋轉平台控制工具 - 增強版")
        self.root.geometry("900x750")
        
        # Modbus連接對象
        self.modbus = None
        self.connected = False
        
        # 狀態監控線程控制
        self.monitoring = False
        self.monitor_thread = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # 主框架
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 連接設定區域
        self.setup_connection_frame(main_frame)
        
        # 診斷區域
        self.setup_diagnostic_frame(main_frame)
        
        # 狀態顯示區域
        self.setup_status_frame(main_frame)
        
        # 控制區域
        self.setup_control_frame(main_frame)
    
    def setup_connection_frame(self, parent):
        conn_frame = ctk.CTkFrame(parent)
        conn_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(conn_frame, text="連接設定", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 第一行：COM口和波特率
        row1 = ctk.CTkFrame(conn_frame)
        row1.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(row1, text="COM口:").pack(side="left", padx=5)
        self.com_var = ctk.StringVar()
        self.com_combo = ctk.CTkComboBox(row1, variable=self.com_var, width=100)
        self.com_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(row1, text="掃描", command=self.scan_com_ports, width=60).pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="波特率:").pack(side="left", padx=(20,5))
        self.baud_var = ctk.StringVar(value="115200")
        baud_combo = ctk.CTkComboBox(row1, variable=self.baud_var, 
                                   values=["9600", "19200", "38400", "57600", "115200", "230400"], 
                                   width=100)
        baud_combo.pack(side="left", padx=5)
        
        # 第二行：數據格式和站號
        row2 = ctk.CTkFrame(conn_frame)
        row2.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(row2, text="數據位:").pack(side="left", padx=5)
        self.data_bits_var = ctk.StringVar(value="8")
        data_combo = ctk.CTkComboBox(row2, variable=self.data_bits_var, 
                                   values=["7", "8"], width=60)
        data_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="校驗:").pack(side="left", padx=5)
        self.parity_var = ctk.StringVar(value="None")
        parity_combo = ctk.CTkComboBox(row2, variable=self.parity_var, 
                                     values=["None", "Even", "Odd"], width=80)
        parity_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="停止位:").pack(side="left", padx=5)
        self.stop_bits_var = ctk.StringVar(value="1")
        stop_combo = ctk.CTkComboBox(row2, variable=self.stop_bits_var, 
                                   values=["1", "2"], width=60)
        stop_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="站號:").pack(side="left", padx=(20,5))
        self.slave_id_var = ctk.StringVar(value="1")  # 改為站號1
        slave_entry = ctk.CTkEntry(row2, textvariable=self.slave_id_var, width=60)
        slave_entry.pack(side="left", padx=5)
        
        # 連接按鈕
        btn_frame = ctk.CTkFrame(conn_frame)
        btn_frame.pack(fill="x", padx=5, pady=5)
        
        self.connect_btn = ctk.CTkButton(btn_frame, text="連接", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(btn_frame, text="未連接", text_color="red")
        self.status_label.pack(side="left", padx=10)
        
        # 測試連接按鈕
        ctk.CTkButton(btn_frame, text="測試連接", command=self.test_connection, width=100).pack(side="left", padx=5)
        
        # 初始掃描COM口
        self.scan_com_ports()
    
    def setup_diagnostic_frame(self, parent):
        """新增診斷區域"""
        diag_frame = ctk.CTkFrame(parent)
        diag_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(diag_frame, text="診斷工具", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        btn_row = ctk.CTkFrame(diag_frame)
        btn_row.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkButton(btn_row, text="讀取狀態寄存器127", command=self.test_read_status, width=150).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="讀取控制寄存器125", command=self.test_read_control, width=150).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="寫入測試", command=self.test_write, width=100).pack(side="left", padx=5)
        
        # 診斷結果顯示
        self.diag_text = ctk.CTkTextbox(diag_frame, height=100, width=800)
        self.diag_text.pack(fill="x", padx=5, pady=5)
    
    def setup_status_frame(self, parent):
        status_frame = ctk.CTkFrame(parent)
        status_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(status_frame, text="設備狀態", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 狀態網格
        grid_frame = ctk.CTkFrame(status_frame)
        grid_frame.pack(fill="x", padx=5, pady=5)
        
        # 第一行狀態
        row1 = ctk.CTkFrame(grid_frame)
        row1.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(row1, text="READY:").pack(side="left", padx=5)
        self.ready_label = ctk.CTkLabel(row1, text="--", width=50)
        self.ready_label.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="MOVE:").pack(side="left", padx=(20,5))
        self.move_label = ctk.CTkLabel(row1, text="--", width=50)
        self.move_label.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="IN-POS:").pack(side="left", padx=(20,5))
        self.inpos_label = ctk.CTkLabel(row1, text="--", width=50)
        self.inpos_label.pack(side="left", padx=5)
        
        # 第二行狀態
        row2 = ctk.CTkFrame(grid_frame)
        row2.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(row2, text="HOME-END:").pack(side="left", padx=5)
        self.home_label = ctk.CTkLabel(row2, text="--", width=50)
        self.home_label.pack(side="left", padx=5)
        
        ctk.CTkLabel(row2, text="ALM-A:").pack(side="left", padx=(20,5))
        self.alarm_label = ctk.CTkLabel(row2, text="--", width=50)
        self.alarm_label.pack(side="left", padx=5)
        
        # 當前位置顯示
        pos_frame = ctk.CTkFrame(grid_frame)
        pos_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(pos_frame, text="當前位置:").pack(side="left", padx=5)
        self.position_label = ctk.CTkLabel(pos_frame, text="-- step", font=ctk.CTkFont(size=14))
        self.position_label.pack(side="left", padx=10)
        
        # 自動更新狀態
        auto_frame = ctk.CTkFrame(status_frame)
        auto_frame.pack(fill="x", padx=5, pady=2)
        
        self.auto_update_var = ctk.BooleanVar(value=False)  # 預設關閉自動更新
        auto_check = ctk.CTkCheckBox(auto_frame, text="自動更新狀態", variable=self.auto_update_var,
                                   command=self.toggle_monitoring)
        auto_check.pack(side="left", padx=5)
        
        ctk.CTkButton(auto_frame, text="手動讀取", command=self.read_status).pack(side="left", padx=10)
    
    def setup_control_frame(self, parent):
        control_frame = ctk.CTkFrame(parent)
        control_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(control_frame, text="運轉控制", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 運轉模式選擇
        mode_frame = ctk.CTkFrame(control_frame)
        mode_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(mode_frame, text="運轉模式:").pack(side="left", padx=5)
        self.mode_var = ctk.StringVar(value="相對定位")
        mode_combo = ctk.CTkComboBox(mode_frame, variable=self.mode_var,
                                   values=["絕對定位", "相對定位", "連續運轉"], width=120)
        mode_combo.pack(side="left", padx=5)
        
        # 位置設定
        pos_frame = ctk.CTkFrame(control_frame)
        pos_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(pos_frame, text="目標位置:").pack(side="left", padx=5)
        self.position_var = ctk.StringVar(value="1000")
        pos_entry = ctk.CTkEntry(pos_frame, textvariable=self.position_var, width=100)
        pos_entry.pack(side="left", padx=5)
        ctk.CTkLabel(pos_frame, text="step").pack(side="left", padx=2)
        
        ctk.CTkButton(pos_frame, text="設定位置", command=self.set_position, width=80).pack(side="left", padx=10)
        
        # 速度設定
        speed_frame = ctk.CTkFrame(control_frame)
        speed_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(speed_frame, text="運轉速度:").pack(side="left", padx=5)
        self.speed_var = ctk.StringVar(value="1000")
        speed_entry = ctk.CTkEntry(speed_frame, textvariable=self.speed_var, width=100)
        speed_entry.pack(side="left", padx=5)
        ctk.CTkLabel(speed_frame, text="Hz").pack(side="left", padx=2)
        
        ctk.CTkButton(speed_frame, text="設定速度", command=self.set_speed, width=80).pack(side="left", padx=10)
        
        # 控制按鈕
        btn_frame = ctk.CTkFrame(control_frame)
        btn_frame.pack(fill="x", padx=5, pady=10)
        
        self.start_btn = ctk.CTkButton(btn_frame, text="開始運轉", command=self.start_operation, 
                                     fg_color="green", width=100)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(btn_frame, text="停止運轉", command=self.stop_operation, 
                                    fg_color="red", width=100)
        self.stop_btn.pack(side="left", padx=5)
        
        self.home_btn = ctk.CTkButton(btn_frame, text="原點復歸", command=self.home_operation, width=100)
        self.home_btn.pack(side="left", padx=5)
        
        # 警報復位按鈕
        self.alarm_reset_btn = ctk.CTkButton(btn_frame, text="警報復位", command=self.alarm_reset, 
                                           fg_color="orange", width=100)
        self.alarm_reset_btn.pack(side="left", padx=5)
        
        # 預設位置快捷按鈕
        preset_frame = ctk.CTkFrame(control_frame)
        preset_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(preset_frame, text="快捷位置:").pack(side="left", padx=5)
        
        presets = [("0°", "0"), ("90°", "9000"), ("180°", "18000"), ("270°", "27000"), ("360°", "36000")]
        for name, pos in presets:
            btn = ctk.CTkButton(preset_frame, text=name, width=60,
                              command=lambda p=pos: self.set_preset_position(p))
            btn.pack(side="left", padx=2)
    
    def scan_com_ports(self):
        """掃描可用的COM口"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.com_combo.configure(values=ports)
        if ports:
            self.com_var.set(ports[0])
            self.log_diagnostic(f"找到COM口: {', '.join(ports)}")
        else:
            self.log_diagnostic("未找到可用的COM口")
    
    def log_diagnostic(self, message):
        """記錄診斷訊息"""
        if hasattr(self, 'diag_text'):
            current_time = time.strftime("%H:%M:%S")
            self.diag_text.insert("end", f"[{current_time}] {message}\n")
            self.diag_text.see("end")
    
    def test_connection(self):
        """測試連接但不建立持久連接"""
        try:
            port = self.com_var.get()
            baudrate = int(self.baud_var.get())
            bytesize = int(self.data_bits_var.get())
            
            parity_map = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}
            parity = parity_map[self.parity_var.get()]
            
            stopbits = int(self.stop_bits_var.get())
            slave_id = int(self.slave_id_var.get())
            
            self.log_diagnostic(f"測試連接: {port}, {baudrate}bps, 站號{slave_id}")
            
            # 建立臨時連接
            temp_modbus = ModbusRTU(port, baudrate, bytesize, parity, stopbits, slave_id)
            
            if temp_modbus.connect():
                self.log_diagnostic("✓ 連接測試成功")
                temp_modbus.disconnect()
                messagebox.showinfo("測試結果", "連接測試成功！")
            else:
                self.log_diagnostic("✗ 連接測試失敗")
                messagebox.showerror("測試結果", "連接測試失敗！")
                
        except Exception as e:
            self.log_diagnostic(f"✗ 測試錯誤: {str(e)}")
            messagebox.showerror("測試錯誤", f"測試錯誤: {str(e)}")
    
    def test_read_status(self):
        """測試讀取狀態寄存器127"""
        if not self.connected:
            self.log_diagnostic("請先連接設備")
            return
            
        self.log_diagnostic("測試讀取狀態寄存器127...")
        result = self.modbus.read_holding_registers(127, 1)
        if result:
            status_value = result[0]
            self.log_diagnostic(f"✓ 讀取成功: {result[0]} (0x{result[0]:04X})")
            
            # 解析狀態位（根據您的設備說明）
            ready = (status_value & 0x0020) != 0      # bit 5
            move = (status_value & 0x2000) != 0       # bit 13  
            home = (status_value & 0x0010) != 0       # bit 4
            inpos = (status_value & 0x4000) != 0      # bit 14
            alarm = (status_value & 0x0080) != 0      # bit 7
            
            self.log_diagnostic(f"狀態解析: READY={ready}, MOVE={move}, HOME={home}, IN-POS={inpos}, ALARM={alarm}")
        else:
            self.log_diagnostic("✗ 讀取失敗")
    
    def test_read_control(self):
        """測試讀取控制寄存器125"""
        if not self.connected:
            self.log_diagnostic("請先連接設備")
            return
            
        self.log_diagnostic("測試讀取控制寄存器125...")
        result = self.modbus.read_holding_registers(125, 1)
        if result:
            self.log_diagnostic(f"✓ 讀取成功: {result[0]} (0x{result[0]:04X})")
        else:
            self.log_diagnostic("✗ 讀取失敗")
    
    def test_write(self):
        """測試寫入功能"""
        if not self.connected:
            self.log_diagnostic("請先連接設備")
            return
            
        self.log_diagnostic("測試寫入寄存器125 (值0-停止)...")
        result = self.modbus.write_single_register(125, 0)
        if result:
            self.log_diagnostic("✓ 寫入測試成功")
        else:
            self.log_diagnostic("✗ 寫入測試失敗")
    
    def toggle_connection(self):
        """切換連接狀態"""
        if not self.connected:
            self.connect_device()
        else:
            self.disconnect_device()
    
    def connect_device(self):
        """連接設備"""
        try:
            port = self.com_var.get()
            if not port:
                messagebox.showerror("錯誤", "請選擇COM口！")
                return
                
            baudrate = int(self.baud_var.get())
            bytesize = int(self.data_bits_var.get())
            
            parity_map = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, "Odd": serial.PARITY_ODD}
            parity = parity_map[self.parity_var.get()]
            
            stopbits = int(self.stop_bits_var.get())
            slave_id = int(self.slave_id_var.get())
            
            self.modbus = ModbusRTU(port, baudrate, bytesize, parity, stopbits, slave_id)
            
            if self.modbus.connect():
                self.connected = True
                self.connect_btn.configure(text="斷開連接")
                self.status_label.configure(text="已連接", text_color="green")
                self.log_diagnostic("✓ 設備連接成功")
                
                # 開始監控（如果啟用）
                if self.auto_update_var.get():
                    self.start_monitoring()
                    
                messagebox.showinfo("成功", "設備連接成功！")
            else:
                self.log_diagnostic("✗ 設備連接失敗")
                messagebox.showerror("錯誤", "無法連接到設備！")
                
        except Exception as e:
            self.log_diagnostic(f"✗ 連接錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"連接錯誤: {str(e)}")
    
    def disconnect_device(self):
        """斷開設備連接"""
        if self.modbus:
            self.stop_monitoring()
            self.modbus.disconnect()
            self.modbus = None
            
        self.connected = False
        self.connect_btn.configure(text="連接")
        self.status_label.configure(text="未連接", text_color="red")
        self.log_diagnostic("連接已斷開")
        
        # 清空狀態顯示
        self.clear_status_display()
    
    def toggle_monitoring(self):
        """切換監控狀態"""
        if self.auto_update_var.get() and self.connected:
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def start_monitoring(self):
        """開始狀態監控"""
        if not self.monitoring and self.connected:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_status, daemon=True)
            self.monitor_thread.start()
            self.log_diagnostic("開始狀態監控")
    
    def stop_monitoring(self):
        """停止狀態監控"""
        if self.monitoring:
            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1)
            self.log_diagnostic("停止狀態監控")
    
    def monitor_status(self):
        """監控線程函數"""
        while self.monitoring and self.connected:
            try:
                self.read_status()
                time.sleep(2.0)  # 2秒更新一次
            except Exception as e:
                self.log_diagnostic(f"監控錯誤: {e}")
                time.sleep(3.0)
    
    def read_status(self):
        """讀取設備狀態 - 使用正確的寄存器地址"""
        if not self.connected or not self.modbus:
            self.log_diagnostic("設備未連接")
            return
            
        try:
            # 讀取狀態寄存器127（根據您的Modbus Poll配置）
            status_data = self.modbus.read_holding_registers(127, 1)
            if status_data and len(status_data) >= 1:
                status_word = status_data[0]
                
                # 根據您設備的bit定義解析狀態
                ready = "ON" if (status_word & 0x0020) else "OFF"      # bit5 READY
                move = "ON" if (status_word & 0x2000) else "OFF"       # bit13 MOVE  
                inpos = "ON" if (status_word & 0x4000) else "OFF"      # bit14 IN-POS
                home_end = "ON" if (status_word & 0x0010) else "OFF"   # bit4 HOME-END
                alarm = "ON" if (status_word & 0x0080) else "OFF"      # bit7 ALM-A
                
                # 更新UI顯示
                self.root.after(0, self.update_status_display, ready, move, inpos, home_end, alarm)
                self.log_diagnostic(f"狀態更新: READY={ready}, MOVE={move}, IN-POS={inpos}")
            else:
                self.log_diagnostic("無法讀取狀態數據")
            
            # 暫時註解位置讀取，先確保狀態讀取正常
            # TODO: 需要確認位置寄存器的正確地址
            # pos_data = self.modbus.read_holding_registers(204, 2)
            # if pos_data and len(pos_data) >= 2:
            #     position = (pos_data[0] << 16) | pos_data[1]
            #     if position > 0x7FFFFFFF:
            #         position -= 0x100000000
            #     self.root.after(0, self.update_position_display, position)
            # else:
            #     self.log_diagnostic("無法讀取位置數據")
                
        except Exception as e:
            self.log_diagnostic(f"讀取狀態錯誤: {e}")
    
    def update_status_display(self, ready, move, inpos, home_end, alarm):
        """更新狀態顯示"""
        self.ready_label.configure(text=ready, text_color="green" if ready=="ON" else "gray")
        self.move_label.configure(text=move, text_color="orange" if move=="ON" else "gray")
        self.inpos_label.configure(text=inpos, text_color="green" if inpos=="ON" else "gray")
        self.home_label.configure(text=home_end, text_color="green" if home_end=="ON" else "gray")
        self.alarm_label.configure(text=alarm, text_color="red" if alarm=="ON" else "gray")
    
    def update_position_display(self, position):
        """更新位置顯示"""
        self.position_label.configure(text=f"{position} step")
    
    def clear_status_display(self):
        """清空狀態顯示"""
        for label in [self.ready_label, self.move_label, self.inpos_label, self.home_label, self.alarm_label]:
            label.configure(text="--", text_color="gray")
        self.position_label.configure(text="-- step")
    
    def set_position(self):
        """設定目標位置"""
        if not self.connected:
            messagebox.showwarning("警告", "請先連接設備！")
            return
            
        try:
            position = int(self.position_var.get())
            
            # 根據手冊，運轉資料No.0的位置在地址6210-6211
            high_word = (position >> 16) & 0xFFFF
            low_word = position & 0xFFFF
            
            if self.modbus.write_multiple_registers(6210, [high_word, low_word]):
                self.log_diagnostic(f"✓ 位置設定成功: {position} step")
                messagebox.showinfo("成功", f"位置設定成功: {position} step")
            else:
                self.log_diagnostic("✗ 位置設定失敗")
                messagebox.showerror("錯誤", "位置設定失敗！")
                
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數字！")
        except Exception as e:
            self.log_diagnostic(f"✗ 設定錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"設定錯誤: {str(e)}")
    
    def set_speed(self):
        """設定運轉速度"""
        if not self.connected:
            messagebox.showwarning("警告", "請先連接設備！")
            return
            
        try:
            speed = int(self.speed_var.get())
            
            # 根據手冊，運轉資料No.0的速度在地址6212-6213
            high_word = (speed >> 16) & 0xFFFF
            low_word = speed & 0xFFFF
            
            if self.modbus.write_multiple_registers(6212, [high_word, low_word]):
                self.log_diagnostic(f"✓ 速度設定成功: {speed} Hz")
                messagebox.showinfo("成功", f"速度設定成功: {speed} Hz")
            else:
                self.log_diagnostic("✗ 速度設定失敗")
                messagebox.showerror("錯誤", "速度設定失敗！")
                
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數字！")
        except Exception as e:
            self.log_diagnostic(f"✗ 設定錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"設定錯誤: {str(e)}")
    
    def start_operation(self):
        """開始運轉 - 使用正確的控制寄存器"""
        if not self.connected:
            messagebox.showwarning("警告", "請先連接設備！")
            return
            
        try:
            # 根據您的Modbus Poll顯示，START對應值16
            # 發送START信號到控制寄存器125
            if self.modbus.write_single_register(125, 16):  # 16->start
                self.log_diagnostic("✓ 運轉開始指令已發送 (寫入值16到寄存器125)")
                messagebox.showinfo("成功", "運轉開始指令已發送！")
            else:
                self.log_diagnostic("✗ 運轉開始失敗")
                messagebox.showerror("錯誤", "運轉開始失敗！")
                
        except Exception as e:
            self.log_diagnostic(f"✗ 運轉錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"運轉錯誤: {str(e)}")
    
    def stop_operation(self):
        """停止運轉 - 使用正確的控制寄存器"""
        if not self.connected:
            messagebox.showwarning("警告", "請先連接設備！")
            return
            
        try:
            # 根據您的Modbus Poll顯示，STOP對應值0
            # 發送STOP信號到控制寄存器125
            if self.modbus.write_single_register(125, 0):  # 0->stop
                self.log_diagnostic("✓ 停止指令已發送 (寫入值0到寄存器125)")
                messagebox.showinfo("成功", "停止指令已發送！")
            else:
                self.log_diagnostic("✗ 停止指令發送失敗")
                messagebox.showerror("錯誤", "停止指令發送失敗！")
                
        except Exception as e:
            self.log_diagnostic(f"✗ 停止錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"停止錯誤: {str(e)}")
    
    def home_operation(self):
        """原點復歸"""
        if not self.connected:
            messagebox.showwarning("警告", "請先連接設備！")
            return
            
        try:
            # 發送ZHOME信號 - bit4為ZHOME信號
            if self.modbus.write_single_register(125, 0x0010):
                self.log_diagnostic("✓ 原點復歸指令已發送")
                messagebox.showinfo("成功", "原點復歸指令已發送！")
                # 1秒後自動清除信號
                self.root.after(1000, lambda: self.modbus.write_single_register(125, 0x0000))
            else:
                self.log_diagnostic("✗ 原點復歸指令發送失敗")
                messagebox.showerror("錯誤", "原點復歸指令發送失敗！")
                
        except Exception as e:
            self.log_diagnostic(f"✗ 原點復歸錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"原點復歸錯誤: {str(e)}")
    
    def alarm_reset(self):
        """警報復位"""
        if not self.connected:
            messagebox.showwarning("警告", "請先連接設備！")
            return
            
        try:
            # 發送ALM-RST信號 - bit7為ALM-RST信號
            if self.modbus.write_single_register(125, 0x0080):
                self.log_diagnostic("✓ 警報復位指令已發送")
                messagebox.showinfo("成功", "警報復位指令已發送！")
                # 1秒後自動清除信號
                self.root.after(1000, lambda: self.modbus.write_single_register(125, 0x0000))
            else:
                self.log_diagnostic("✗ 警報復位指令發送失敗")
                messagebox.showerror("錯誤", "警報復位指令發送失敗！")
                
        except Exception as e:
            self.log_diagnostic(f"✗ 警報復位錯誤: {str(e)}")
            messagebox.showerror("錯誤", f"警報復位錯誤: {str(e)}")
    
    def set_preset_position(self, position):
        """設定預設位置"""
        self.position_var.set(position)
        self.set_position()
    
    def run(self):
        """運行應用程序"""
        try:
            self.root.mainloop()
        finally:
            # 確保在退出時斷開連接
            if self.connected:
                self.disconnect_device()

if __name__ == "__main__":
    app = ModbusControlApp()
    app.run()