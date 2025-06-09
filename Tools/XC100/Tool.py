import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import time
import serial.tools.list_ports
from pymodbus.client import ModbusSerialClient

# 設定customtkinter外觀
ctk.set_appearance_mode("light")  # "light" 或 "dark"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"

class XC100ControlTool:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("XC100 控制工具")
        self.root.geometry("700x700")  # 增加視窗高度
        self.root.resizable(False, False)
        
        # MODBUS連線參數
        self.selected_port = tk.StringVar()
        self.baudrate = 115200
        self.unit_id = 2
        self.client = None
        self.is_connected = False
        
        # 位置設定
        self.position_A = 400
        self.position_B = 2682
        
        self.setup_ui()
        self.scan_com_ports()
        
    def setup_ui(self):
        """設置使用者介面"""
        # 主標題
        title_label = ctk.CTkLabel(
            self.root, 
            text="XC100 控制工具", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=15)
        
        # 連線設定框架
        self.connection_frame = ctk.CTkFrame(self.root)
        self.connection_frame.pack(pady=10, padx=20, fill="x")
        
        conn_title = ctk.CTkLabel(
            self.connection_frame, 
            text="連線設定", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        conn_title.pack(pady=5)
        
        # 連線參數設定區
        settings_frame = ctk.CTkFrame(self.connection_frame)
        settings_frame.pack(pady=5, padx=10, fill="x")
        
        # COM口選擇
        com_frame = ctk.CTkFrame(settings_frame)
        com_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(com_frame, text="COM口:", width=80).pack(side="left", padx=5)
        
        self.com_combobox = ctk.CTkComboBox(
            com_frame,
            variable=self.selected_port,
            width=120,
            state="readonly"
        )
        self.com_combobox.pack(side="left", padx=5)
        
        self.refresh_button = ctk.CTkButton(
            com_frame,
            text="🔄",
            width=30,
            command=self.scan_com_ports
        )
        self.refresh_button.pack(side="left", padx=5)
        
        # 其他參數顯示
        params_frame = ctk.CTkFrame(settings_frame)
        params_frame.pack(pady=5, fill="x")
        
        params_text = f"波特率: {self.baudrate} | 資料位: 8 | 停止位: 1 | 校驗位: N | Slave ID: {self.unit_id}"
        ctk.CTkLabel(params_frame, text=params_text, font=ctk.CTkFont(size=12)).pack(pady=5)
        
        # 連線控制按鈕
        control_frame = ctk.CTkFrame(self.connection_frame)
        control_frame.pack(pady=5, padx=10, fill="x")
        
        self.connect_button = ctk.CTkButton(
            control_frame,
            text="連接",
            width=100,
            command=self.connect_modbus,
            fg_color="#28a745",
            hover_color="#218838"
        )
        self.connect_button.pack(side="left", padx=5)
        
        self.disconnect_button = ctk.CTkButton(
            control_frame,
            text="斷開",
            width=100,
            command=self.disconnect_modbus,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled"
        )
        self.disconnect_button.pack(side="left", padx=5)
        
        # 連線狀態
        self.connection_status = ctk.CTkLabel(
            control_frame, 
            text="狀態: 未連線", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="red"
        )
        self.connection_status.pack(side="left", padx=20)
        
        # 狀態監控框架
        self.status_frame = ctk.CTkFrame(self.root)
        self.status_frame.pack(pady=10, padx=20, fill="x")
        
        status_title = ctk.CTkLabel(
            self.status_frame, 
            text="設備狀態", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        status_title.pack(pady=5)
        
        # 錯誤狀態
        self.error_status = ctk.CTkLabel(
            self.status_frame, 
            text="錯誤狀態: 未檢查", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.error_status.pack(pady=5)
        
        # 控制按鈕框架
        control_panel_frame = ctk.CTkFrame(self.root)
        control_panel_frame.pack(pady=15, padx=20, fill="x")
        
        control_title = ctk.CTkLabel(
            control_panel_frame, 
            text="控制面板", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        control_title.pack(pady=10)
        
        # 按鈕容器
        button_container = ctk.CTkFrame(control_panel_frame)
        button_container.pack(pady=10, padx=20, fill="x")
        
        # Servo控制框架
        servo_frame = ctk.CTkFrame(button_container)
        servo_frame.pack(pady=5, fill="x")
        
        servo_title = ctk.CTkLabel(
            servo_frame, 
            text="伺服控制", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        servo_title.pack(pady=3)
        
        servo_buttons_frame = ctk.CTkFrame(servo_frame)
        servo_buttons_frame.pack(pady=3, fill="x")
        
        # Servo ON按鈕
        self.servo_on_button = ctk.CTkButton(
            servo_buttons_frame,
            text="Servo ON",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=35,
            width=100,
            command=self.servo_on_action,
            fg_color="#28a745",
            hover_color="#218838",
            state="disabled"
        )
        self.servo_on_button.pack(side="left", padx=10, expand=True, fill="x")
        
        # Servo OFF按鈕
        self.servo_off_button = ctk.CTkButton(
            servo_buttons_frame,
            text="Servo OFF",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=35,
            width=100,
            command=self.servo_off_action,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled"
        )
        self.servo_off_button.pack(side="right", padx=10, expand=True, fill="x")
        
        # Servo狀態顯示
        self.servo_status = ctk.CTkLabel(
            servo_frame, 
            text="Servo狀態: 未檢查", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.servo_status.pack(pady=2)
        
        # 移動控制框架
        move_frame = ctk.CTkFrame(button_container)
        move_frame.pack(pady=5, fill="x")
        
        move_title = ctk.CTkLabel(
            move_frame, 
            text="移動控制", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        move_title.pack(pady=3)
        
        # 原點復歸按鈕
        self.home_button = ctk.CTkButton(
            move_frame,
            text="原點復歸 (HOME)",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45,
            width=150,
            command=self.home_action,
            fg_color="#ff6b6b",
            hover_color="#ff5252",
            state="disabled"
        )
        self.home_button.pack(pady=3)
        
        # A點B點按鈕框架
        ab_frame = ctk.CTkFrame(button_container)
        ab_frame.pack(pady=5, fill="x")
        
        # A點按鈕
        self.point_a_button = ctk.CTkButton(
            ab_frame,
            text=f"移動到A點\n(位置: {self.position_A})",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=60,
            width=180,
            command=self.move_to_a,
            fg_color="#4dabf7",
            hover_color="#339af0",
            state="disabled"
        )
        self.point_a_button.pack(side="left", padx=10, expand=True, fill="x")
        
        # B點按鈕
        self.point_b_button = ctk.CTkButton(
            ab_frame,
            text=f"移動到B點\n(位置: {self.position_B})",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=60,
            width=180,
            command=self.move_to_b,
            fg_color="#51cf66",
            hover_color="#40c057",
            state="disabled"
        )
        self.point_b_button.pack(side="right", padx=10, expand=True, fill="x")
        
        # 日誌框架
        log_frame = ctk.CTkFrame(self.root)
        log_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        log_title = ctk.CTkLabel(
            log_frame, 
            text="操作日誌", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_title.pack(pady=5)
        
        # 日誌文字框
        self.log_text = ctk.CTkTextbox(log_frame, height=120)  # 減少日誌區域高度
        self.log_text.pack(pady=5, padx=10, fill="both", expand=True)
        
        # 日誌清除按鈕
        clear_button = ctk.CTkButton(
            log_frame,
            text="清除日誌",
            width=100,
            command=self.clear_log,
            fg_color="#6c757d",
            hover_color="#545b62"
        )
        clear_button.pack(pady=5)
        
    def scan_com_ports(self):
        """掃描可用的COM口"""
        try:
            ports = serial.tools.list_ports.comports()
            port_list = [port.device for port in ports]
            
            if port_list:
                self.com_combobox.configure(values=port_list)
                if not self.selected_port.get() or self.selected_port.get() not in port_list:
                    self.selected_port.set(port_list[0])
                self.log_message(f"🔍 掃描到COM口: {', '.join(port_list)}")
            else:
                self.com_combobox.configure(values=["無可用COM口"])
                self.selected_port.set("無可用COM口")
                self.log_message("⚠️ 未發現可用的COM口")
                
        except Exception as e:
            self.log_message(f"❌ COM口掃描失敗: {e}")
    
    def connect_modbus(self):
        """連線到MODBUS設備"""
        if not self.selected_port.get() or self.selected_port.get() == "無可用COM口":
            self.log_message("❌ 請選擇有效的COM口")
            return
            
        def connect_thread():
            try:
                self.log_message(f"🔌 正在連接到 {self.selected_port.get()}...")
                
                self.client = ModbusSerialClient(
                    port=self.selected_port.get(),
                    baudrate=self.baudrate,
                    stopbits=1,
                    parity='N',
                    timeout=0.2
                )
                
                if self.client.connect():
                    self.is_connected = True
                    self.root.after(0, self.update_connection_ui, True)
                    self.log_message("✅ MODBUS連線成功")
                    
                    # 連線成功後立即檢查錯誤狀態和Servo狀態
                    self.check_error_status()
                    self.check_servo_status()
                else:
                    raise Exception("連線失敗")
                    
            except Exception as e:
                self.is_connected = False
                self.root.after(0, self.update_connection_ui, False)
                self.log_message(f"❌ MODBUS連線失敗: {e}")
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def disconnect_modbus(self):
        """斷開MODBUS連線"""
        try:
            if self.client and self.is_connected:
                self.client.close()
                self.is_connected = False
                self.update_connection_ui(False)
                self.log_message("🔌 MODBUS連線已斷開")
            else:
                self.log_message("⚠️ 沒有活動的連線")
        except Exception as e:
            self.log_message(f"❌ 斷開連線時發生錯誤: {e}")
    
    def update_connection_ui(self, connected):
        """更新連線相關的UI狀態"""
        if connected:
            self.connection_status.configure(
                text="狀態: 已連線", 
                text_color="green"
            )
            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="normal")
            self.com_combobox.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            
            # 啟用控制按鈕
            self.servo_on_button.configure(state="normal")
            self.servo_off_button.configure(state="normal")
            self.home_button.configure(state="normal")
            self.point_a_button.configure(state="normal")
            self.point_b_button.configure(state="normal")
        else:
            self.connection_status.configure(
                text="狀態: 未連線", 
                text_color="red"
            )
            self.connect_button.configure(state="normal")
            self.disconnect_button.configure(state="disabled")
            self.com_combobox.configure(state="readonly")
            self.refresh_button.configure(state="normal")
            
            # 禁用控制按鈕
            self.servo_on_button.configure(state="disabled")
            self.servo_off_button.configure(state="disabled")
            self.home_button.configure(state="disabled")
            self.point_a_button.configure(state="disabled")
            self.point_b_button.configure(state="disabled")
            
            # 重置狀態顯示
            self.servo_status.configure(
                text="Servo狀態: 未檢查",
                text_color="gray"
            )
    
    def log_message(self, message):
        """添加日誌訊息"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert("end", log_entry)
        self.log_text.see("end")
        self.root.update()
    
    def clear_log(self):
        """清除日誌"""
        self.log_text.delete("1.0", "end")
        self.log_message("📝 日誌已清除")
    
    def check_servo_status(self):
        """檢查100CH Servo狀態"""
        if not self.is_connected:
            self.log_message("❌ 未連線，無法檢查Servo狀態")
            return False
            
        try:
            # 讀取100CH寄存器
            result = self.client.read_holding_registers(address=0x100C, count=1, slave=self.unit_id)
            
            if result.isError():
                self.log_message("❌ 讀取Servo狀態失敗")
                return False
                
            servo_status = result.registers[0]
            
            if servo_status == 1:
                self.servo_status.configure(
                    text="Servo狀態: ON ✅", 
                    text_color="green"
                )
                self.log_message("✅ Servo狀態: ON")
                return True
            else:
                self.servo_status.configure(
                    text="Servo狀態: OFF ❌", 
                    text_color="red"
                )
                self.log_message("⚠️ Servo狀態: OFF")
                return False
                
        except Exception as e:
            self.log_message(f"❌ 檢查Servo狀態異常: {e}")
            return False
    def check_error_status(self):
        """檢查100DH錯誤狀態"""
        if not self.is_connected:
            self.log_message("❌ 未連線，無法檢查錯誤狀態")
            return False
            
        try:
            # 讀取100DH寄存器
            result = self.client.read_holding_registers(address=0x100D, count=1, slave=self.unit_id)
            
            if result.isError():
                self.log_message("❌ 讀取錯誤狀態失敗")
                return False
                
            error_code = result.registers[0]
            
            if error_code == 0:
                self.error_status.configure(
                    text="錯誤狀態: 正常 ✅", 
                    text_color="green"
                )
                self.log_message("✅ 設備狀態正常")
                return True
            else:
                error_messages = {
                    1: "在動作中接收動作指令",
                    2: "上下限錯誤", 
                    3: "位置錯誤",
                    4: "格式錯誤",
                    5: "控制模式錯誤",
                    6: "斷電重開",
                    7: "初始化未完成",
                    8: "Servo ON/OFF 錯誤",
                    9: "LOCK",
                    10: "軟體極限",
                    11: "參數寫入權限不足",
                    12: "原點復歸未完成",
                    13: "剎車已解除"
                }
                error_msg = error_messages.get(error_code, f"未知錯誤代碼: {error_code}")
                self.error_status.configure(
                    text=f"錯誤狀態: {error_msg} ⚠️", 
                    text_color="red"
                )
                self.log_message(f"⚠️ 設備錯誤: {error_msg}")
                return False
                
        except Exception as e:
            self.log_message(f"❌ 檢查錯誤狀態異常: {e}")
            return False
    
    def write_absolute_position(self, position):
        """設定絕對移動位置"""
        try:
            # 將32位元位置分解為兩個16位元值
            position_high = (position >> 16) & 0xFFFF
            position_low = position & 0xFFFF
            
            # 寫入2002H (ABSamount)
            result = self.client.write_registers(
                address=0x2002, 
                values=[position_high, position_low], 
                slave=self.unit_id
            )
            
            if result.isError():
                raise Exception("寫入位置失敗")
                
            self.log_message(f"📍 設定目標位置: {position}")
            return True
            
        except Exception as e:
            self.log_message(f"❌ 設定位置失敗: {e}")
            return False
    
    def execute_movement(self, move_type):
        """執行移動指令"""
        try:
            # 寫入201EH (MovType)
            result = self.client.write_register(
                address=0x201E, 
                value=move_type, 
                slave=self.unit_id
            )
            
            if result.isError():
                raise Exception("執行移動指令失敗")
                
            move_types = {1: "絕對位置移動", 3: "原點復歸"}
            self.log_message(f"🚀 執行: {move_types.get(move_type, f'移動類型{move_type}')}")
            return True
            
        except Exception as e:
            self.log_message(f"❌ 執行移動失敗: {e}")
            return False
    
    def servo_on_action(self):
        """Servo ON動作"""
        def run_servo_on():
            try:
                start_time = time.time()
                
                # 立即禁用按鈕並更新UI
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message("🔧 執行Servo ON..."))
                
                # 寫入2011H寄存器，值為0 (Servo ON)
                result = self.client.write_register(
                    address=0x2011, 
                    value=0, 
                    slave=self.unit_id
                )
                
                if result.isError():
                    self.root.after(0, lambda: self.log_message("❌ Servo ON指令發送失敗"))
                else:
                    elapsed = (time.time() - start_time) * 1000
                    self.root.after(0, lambda: self.log_message(f"✅ Servo ON指令發送完成 ({elapsed:.1f}ms)"))
                    
                    # 檢查Servo狀態
                    time.sleep(0.1)  # 短暫延遲等待狀態更新
                    self.check_servo_status()
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Servo ON操作異常: {e}"))
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_servo_on, daemon=True).start()
    
    def servo_off_action(self):
        """Servo OFF動作"""
        def run_servo_off():
            try:
                start_time = time.time()
                
                # 立即禁用按鈕並更新UI
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message("🔧 執行Servo OFF..."))
                
                # 寫入2011H寄存器，值為1 (Servo OFF)
                result = self.client.write_register(
                    address=0x2011, 
                    value=1, 
                    slave=self.unit_id
                )
                
                if result.isError():
                    self.root.after(0, lambda: self.log_message("❌ Servo OFF指令發送失敗"))
                else:
                    elapsed = (time.time() - start_time) * 1000
                    self.root.after(0, lambda: self.log_message(f"✅ Servo OFF指令發送完成 ({elapsed:.1f}ms)"))
                    
                    # 檢查Servo狀態
                    time.sleep(0.1)  # 短暫延遲等待狀態更新
                    self.check_servo_status()
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Servo OFF操作異常: {e}"))
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_servo_off, daemon=True).start()
    def disable_control_buttons(self):
        """禁用控制按鈕"""
        self.servo_on_button.configure(state="disabled")
        self.servo_off_button.configure(state="disabled")
        self.home_button.configure(state="disabled")
        self.point_a_button.configure(state="disabled")
        self.point_b_button.configure(state="disabled")
    
    def enable_control_buttons(self):
        """啟用控制按鈕"""
        if self.is_connected:
            self.servo_on_button.configure(state="normal")
            self.servo_off_button.configure(state="normal")
            self.home_button.configure(state="normal")
            self.point_a_button.configure(state="normal")
            self.point_b_button.configure(state="normal")
    
    def home_action(self):
        """原點復歸動作"""
        def run_home():
            try:
                start_time = time.time()
                
                # 立即禁用按鈕並更新UI
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message("🏠 開始原點復歸操作..."))
                
                # 檢查錯誤狀態
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                # 執行原點復歸 (MovType = 3)
                if self.execute_movement(3):
                    elapsed = (time.time() - start_time) * 1000
                    self.root.after(0, lambda: self.log_message(f"✅ 原點復歸指令發送完成 ({elapsed:.1f}ms)"))
                else:
                    self.root.after(0, lambda: self.log_message("❌ 原點復歸指令發送失敗"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        # 在新線程中執行，避免界面凍結
        threading.Thread(target=run_home, daemon=True).start()
    
    def move_to_a(self):
        """移動到A點"""
        def run_move_a():
            try:
                start_time = time.time()
                
                # 立即禁用按鈕並更新UI
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message(f"📍 開始移動到A點操作 (目標位置: {self.position_A})..."))
                
                # 檢查錯誤狀態
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                # 設定絕對位置
                if not self.write_absolute_position(self.position_A):
                    return
                
                # 執行絕對位置移動 (MovType = 1)
                if self.execute_movement(1):
                    elapsed = (time.time() - start_time) * 1000
                    self.root.after(0, lambda: self.log_message(f"✅ 移動到A點指令發送完成 ({elapsed:.1f}ms)"))
                else:
                    self.root.after(0, lambda: self.log_message("❌ 移動到A點指令發送失敗"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_move_a, daemon=True).start()
    
    def move_to_b(self):
        """移動到B點"""
        def run_move_b():
            try:
                start_time = time.time()
                
                # 立即禁用按鈕並更新UI
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message(f"📍 開始移動到B點操作 (目標位置: {self.position_B})..."))
                
                # 檢查錯誤狀態
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                # 設定絕對位置
                if not self.write_absolute_position(self.position_B):
                    return
                
                # 執行絕對位置移動 (MovType = 1) 
                if self.execute_movement(1):
                    elapsed = (time.time() - start_time) * 1000
                    self.root.after(0, lambda: self.log_message(f"✅ 移動到B點指令發送完成 ({elapsed:.1f}ms)"))
                else:
                    self.root.after(0, lambda: self.log_message("❌ 移動到B點指令發送失敗"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_move_b, daemon=True).start()
    
    def on_closing(self):
        """程式關閉時的處理"""
        if self.client and self.is_connected:
            self.disconnect_modbus()
        self.root.destroy()
    
    def run(self):
        """執行主程式"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

def main():
    """主函數"""
    try:
        app = XC100ControlTool()
        app.run()
    except Exception as e:
        print(f"程式啟動失敗: {e}")

if __name__ == "__main__":
    main()