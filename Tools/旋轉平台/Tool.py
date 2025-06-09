import customtkinter as ctk
import serial
import serial.tools.list_ports
import threading
import time
from tkinter import messagebox
import struct

class ModbusRTU:
    def __init__(self):
        self.serial_conn = None
        
    def connect(self, port, baudrate=115200):
        try:
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=1
            )
            return True
        except Exception as e:
            print(f"連接失敗: {e}")
            return False
    
    def disconnect(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
    
    def crc16(self, data):
        """計算CRC-16校驗"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    def write_multiple_registers(self, slave_id, start_addr, values):
        """寫入多個保持寄存器 (功能碼 10h)"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
            
        # 構建請求幀
        register_count = len(values)
        byte_count = register_count * 2
        
        frame = bytearray()
        frame.append(slave_id)           # 從站地址
        frame.append(0x10)               # 功能碼
        frame.extend(start_addr.to_bytes(2, 'big'))  # 起始地址
        frame.extend(register_count.to_bytes(2, 'big'))  # 寄存器數量
        frame.append(byte_count)         # 字節數
        
        # 添加數據
        for value in values:
            frame.extend(value.to_bytes(2, 'big'))
        
        # 計算並添加CRC
        crc = self.crc16(frame)
        frame.extend(crc.to_bytes(2, 'little'))
        
        try:
            self.serial_conn.write(frame)
            response = self.serial_conn.read(8)  # 預期響應長度
            return len(response) >= 8
        except Exception as e:
            print(f"寫入失敗: {e}")
            return False
    
    def write_single_register(self, slave_id, address, value):
        """寫入單個保持寄存器 (功能碼 06h)"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return False
            
        frame = bytearray()
        frame.append(slave_id)           # 從站地址
        frame.append(0x06)               # 功能碼
        frame.extend(address.to_bytes(2, 'big'))    # 寄存器地址
        frame.extend(value.to_bytes(2, 'big'))      # 寄存器值
        
        # 計算並添加CRC
        crc = self.crc16(frame)
        frame.extend(crc.to_bytes(2, 'little'))
        
        try:
            self.serial_conn.write(frame)
            response = self.serial_conn.read(8)  # 預期響應長度
            return len(response) >= 8
        except Exception as e:
            print(f"寫入失敗: {e}")
            return False
    
    def read_holding_registers(self, slave_id, start_addr, count):
        """讀取保持寄存器 (功能碼 03h)"""
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
            
        frame = bytearray()
        frame.append(slave_id)           # 從站地址
        frame.append(0x03)               # 功能碼
        frame.extend(start_addr.to_bytes(2, 'big'))  # 起始地址
        frame.extend(count.to_bytes(2, 'big'))       # 寄存器數量
        
        # 計算並添加CRC
        crc = self.crc16(frame)
        frame.extend(crc.to_bytes(2, 'little'))
        
        try:
            self.serial_conn.write(frame)
            response = self.serial_conn.read(5 + count * 2)  # 響應長度
            
            if len(response) >= 5 and response[1] == 0x03:
                # 解析數據
                byte_count = response[2]
                data = response[3:3+byte_count]
                values = []
                for i in range(0, byte_count, 2):
                    value = struct.unpack('>H', data[i:i+2])[0]
                    values.append(value)
                return values
            return None
        except Exception as e:
            print(f"讀取失敗: {e}")
            return None

class MotorControlApp:
    def __init__(self):
        # 設置主題
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # 主窗口
        self.root = ctk.CTk()
        self.root.title("Modbus RTU 步進馬達控制工具")
        self.root.geometry("600x650")
        
        # Modbus 實例
        self.modbus = ModbusRTU()
        self.slave_id = 1  # 從站地址
        self.is_connected = False
        self.monitoring = False
        
        # 狀態變量
        self.current_position = 0
        self.target_position = 0
        self.motor_status = {"moving": False, "home": False, "ready": False}
        self.previous_moving_status = False  # 追蹤上一次的運動狀態
        self.need_clear_command = False      # 標記是否需要清除指令
        
        self.setup_ui()
        self.scan_com_ports()
        
    def setup_ui(self):
        # 連接區域
        conn_frame = ctk.CTkFrame(self.root)
        conn_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(conn_frame, text="串口連接", font=("Arial", 16, "bold")).pack(pady=5)
        
        port_frame = ctk.CTkFrame(conn_frame)
        port_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(port_frame, text="串口:").pack(side="left", padx=5)
        self.port_var = ctk.StringVar(value="COM5")
        self.port_combo = ctk.CTkComboBox(port_frame, variable=self.port_var)
        self.port_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(port_frame, text="掃描", command=self.scan_com_ports, width=60).pack(side="left", padx=5)
        
        self.connect_btn = ctk.CTkButton(port_frame, text="連接", command=self.toggle_connection, width=80)
        self.connect_btn.pack(side="right", padx=5)
        
        # 初始化設置區域
        init_frame = ctk.CTkFrame(self.root)
        init_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(init_frame, text="馬達初始化", font=("Arial", 16, "bold")).pack(pady=5)
        
        self.init_btn = ctk.CTkButton(init_frame, text="發送初始化參數", command=self.send_init_params)
        self.init_btn.pack(pady=5)
        
        # 控制區域
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        ctk.CTkLabel(control_frame, text="馬達控制", font=("Arial", 16, "bold")).pack(pady=5)
        
        # 位置輸入
        pos_frame = ctk.CTkFrame(control_frame)
        pos_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(pos_frame, text="目標位置:").pack(side="left", padx=5)
        self.position_entry = ctk.CTkEntry(pos_frame, placeholder_text="輸入位置值")
        self.position_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        # 控制按鈕 - 第一排
        btn_frame1 = ctk.CTkFrame(control_frame)
        btn_frame1.pack(pady=5, padx=10, fill="x")
        
        self.move_btn = ctk.CTkButton(btn_frame1, text="移動到位置", command=self.move_to_position, state="disabled")
        self.move_btn.pack(side="left", padx=5)
        
        self.home_btn = ctk.CTkButton(btn_frame1, text="回原點", command=self.go_home, state="disabled")
        self.home_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(btn_frame1, text="緊急停止", command=self.emergency_stop, 
                                     fg_color="red", hover_color="darkred", state="disabled")
        self.stop_btn.pack(side="right", padx=5)
        
        # 控制按鈕 - 第二排（準備和清除指令）
        btn_frame2 = ctk.CTkFrame(control_frame)
        btn_frame2.pack(pady=5, padx=10, fill="x")
        
        self.prepare_btn = ctk.CTkButton(btn_frame2, text="準備", command=self.prepare_motor, state="disabled", 
                                        fg_color="orange", hover_color="darkorange")
        self.prepare_btn.pack(side="left", padx=5)
        
        # 新增的清除指令按鈕
        self.clear_cmd_btn = ctk.CTkButton(btn_frame2, text="清除指令", command=self.manual_clear_command, 
                                          state="disabled", fg_color="purple", hover_color="darkviolet")
        self.clear_cmd_btn.pack(side="left", padx=5)
        
        # 狀態顯示區域
        status_frame = ctk.CTkFrame(self.root)
        status_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(status_frame, text="馬達狀態", font=("Arial", 16, "bold")).pack(pady=5)
        
        status_info_frame = ctk.CTkFrame(status_frame)
        status_info_frame.pack(pady=5, padx=10, fill="x")
        
        # 狀態標籤
        self.status_labels = {}
        status_items = [("連接狀態", "disconnected"), ("運動中", "停止"), ("在原點", "否"), ("準備就緒", "否")]
        
        for i, (label, default) in enumerate(status_items):
            row = i // 2
            col = i % 2
            
            frame = ctk.CTkFrame(status_info_frame)
            frame.grid(row=row, column=col, padx=5, pady=2, sticky="ew")
            
            ctk.CTkLabel(frame, text=f"{label}:").pack(side="left", padx=5)
            status_label = ctk.CTkLabel(frame, text=default, text_color="gray")
            status_label.pack(side="right", padx=5)
            self.status_labels[label] = status_label
        
        status_info_frame.grid_columnconfigure(0, weight=1)
        status_info_frame.grid_columnconfigure(1, weight=1)
        
        # 添加操作日志區域
        log_frame = ctk.CTkFrame(status_frame)
        log_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(log_frame, text="操作日志:", font=("Arial", 12, "bold")).pack(anchor="w", padx=5)
        self.log_text = ctk.CTkTextbox(log_frame, height=60, font=("Consolas", 10))
        self.log_text.pack(fill="x", padx=5, pady=2)
        
        # 開始狀態監控
        self.start_status_monitoring()
    
    def scan_com_ports(self):
        """掃描可用的串口"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo.configure(values=ports if ports else ["COM5"])
        if "COM5" in ports:
            self.port_var.set("COM5")
        elif ports:
            self.port_var.set(ports[0])
    
    def toggle_connection(self):
        """切換連接狀態"""
        if not self.is_connected:
            port = self.port_var.get()
            if self.modbus.connect(port, 115200):
                self.is_connected = True
                self.connect_btn.configure(text="斷開")
                self.enable_controls(True)
                self.status_labels["連接狀態"].configure(text="已連接", text_color="green")
                messagebox.showinfo("成功", f"已連接到 {port}")
            else:
                messagebox.showerror("錯誤", f"無法連接到 {port}")
        else:
            self.modbus.disconnect()
            self.is_connected = False
            self.connect_btn.configure(text="連接")
            self.enable_controls(False)
            self.status_labels["連接狀態"].configure(text="未連接", text_color="red")
    
    def enable_controls(self, enabled):
        """啟用/禁用控制按鈕"""
        state = "normal" if enabled else "disabled"
        self.init_btn.configure(state=state)
        self.move_btn.configure(state=state)
        self.prepare_btn.configure(state=state)
        self.home_btn.configure(state=state)
        self.stop_btn.configure(state=state)
        self.clear_cmd_btn.configure(state=state)  # 新增的清除指令按鈕
    
    def send_init_params(self):
        """發送初始化參數"""
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return
        
        try:
            # 按照你提供的參數設置
            init_values = [
                0,      # 6144: 0
                2,      # 6145: 2
                0,      # 6146: 0
                9000,   # 6147: 9000 (這邊會變)
                0,      # 6148: 0
                5000,   # 6149: 5000
                15,     # 6150: 15
                16960,  # 6151: 16960
                15,     # 6152: 15
                16960,  # 6153: 16960
                0,      # 6154: 0
                1000    # 6155: 1000
            ]
            
            success = self.modbus.write_multiple_registers(self.slave_id, 6144, init_values)
            
            if success:
                messagebox.showinfo("成功", "初始化參數已發送")
                self.log_message("初始化參數已發送完成")
            else:
                messagebox.showerror("錯誤", "發送初始化參數失敗")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"發送失敗: {e}")
    
    def move_to_position(self):
        """移動到指定位置"""
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return
        
        try:
            position = int(self.position_entry.get())
            
            # 檢查是否準備就緒
            if not self.motor_status["ready"]:
                messagebox.showwarning("警告", "馬達未準備就緒，請等待當前動作完成")
                return
            
            # 設置目標位置 (假設位置寄存器在 6147)
            self.modbus.write_single_register(self.slave_id, 6147, position)
            time.sleep(0.1)
            
            # 發送移動指令 (寫入 8 到寄存器 125)
            success = self.modbus.write_single_register(self.slave_id, 125, 8)
            
            if success:
                self.target_position = position
                self.need_clear_command = True  # 標記需要在運動完成後清除指令
                messagebox.showinfo("成功", f"已發送移動指令到位置 {position}")
                self.log_message(f"移動指令已發送到位置 {position}，等待運動完成後自動清除狀態")
            else:
                messagebox.showerror("錯誤", "發送移動指令失敗")
                
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的位置數值")
        except Exception as e:
            messagebox.showerror("錯誤", f"移動失敗: {e}")
    
    def prepare_motor(self):
        """準備馬達 - 清除寄存器125的狀態"""
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return
        
        try:
            # 向寄存器 125 寫入 0 清除指令
            success = self.modbus.write_single_register(self.slave_id, 125, 0)
            
            if success:
                self.need_clear_command = False  # 清除自動清除標記
                messagebox.showinfo("成功", "已手動清除指令狀態")
                self.log_message("手動清除指令狀態完成，馬達已準備好接受新指令")
            else:
                messagebox.showerror("錯誤", "清除指令狀態失敗")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"準備失敗: {e}")
    
    def manual_clear_command(self):
        """手動清除指令 - 新增的獨立功能"""
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return
        
        try:
            # 向寄存器 125 寫入 0 清除指令
            success = self.modbus.write_single_register(self.slave_id, 125, 0)
            
            if success:
                self.need_clear_command = False  # 清除自動清除標記
                messagebox.showinfo("成功", "指令已清除")
                self.log_message("手動執行清除指令操作完成")
            else:
                messagebox.showerror("錯誤", "清除指令失敗")
                self.log_message("手動清除指令操作失敗")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"清除指令失敗: {e}")
            self.log_message(f"清除指令操作異常: {e}")
    
    def go_home(self):
        """回原點"""
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return
        
        try:
            # 檢查是否準備就緒
            if not self.motor_status["ready"]:
                messagebox.showwarning("警告", "馬達未準備就緒，請等待當前動作完成")
                return
            
            # 發送回原點指令 (寫入 16 到寄存器 125)
            success = self.modbus.write_single_register(self.slave_id, 125, 16)
            
            if success:
                self.need_clear_command = True  # 標記需要在運動完成後清除指令
                messagebox.showinfo("成功", "已發送回原點指令")
                self.log_message("回原點指令已發送，等待運動完成後自動清除狀態")
            else:
                messagebox.showerror("錯誤", "發送回原點指令失敗")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"回原點失敗: {e}")
    
    def emergency_stop(self):
        """緊急停止"""
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接串口")
            return
        
        try:
            # 發送緊急停止指令 (寫入 32 到寄存器 125)
            success = self.modbus.write_single_register(self.slave_id, 125, 32)
            
            if success:
                messagebox.showinfo("成功", "已發送緊急停止指令")
                self.log_message("緊急停止指令已發送")
            else:
                messagebox.showerror("錯誤", "發送緊急停止指令失敗")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"緊急停止失敗: {e}")
    
    def read_motor_status(self):
        """讀取馬達狀態"""
        if not self.is_connected:
            return
        
        try:
            # 讀取寄存器 127 的狀態
            result = self.modbus.read_holding_registers(self.slave_id, 127, 1)
            
            if result:
                status_word = result[0]
                
                # 保存上一次的運動狀態
                self.previous_moving_status = self.motor_status["moving"]
                
                # 解析狀態位
                self.motor_status["moving"] = bool(status_word & (1 << 13))  # bit 13: 運動中
                self.motor_status["home"] = bool(status_word & (1 << 4))     # bit 4: 在原點  
                self.motor_status["ready"] = bool(status_word & (1 << 5))    # bit 5: 準備就緒
                
                # 檢查是否從運動中變為停止狀態
                if (self.previous_moving_status and not self.motor_status["moving"] 
                    and self.need_clear_command):
                    # 運動剛剛停止，需要清除指令
                    self.clear_command()
                
                # 更新UI
                self.update_status_display()
                
        except Exception as e:
            print(f"讀取狀態失敗: {e}")
    
    def clear_command(self):
        """清除指令狀態（自動觸發）"""
        try:
            # 向寄存器 125 寫入 0 清除指令
            success = self.modbus.write_single_register(self.slave_id, 125, 0)
            if success:
                self.need_clear_command = False
                self.log_message("運動完成，已自動清除指令狀態，為下一次運動做準備")
            else:
                self.log_message("自動清除指令狀態失敗")
        except Exception as e:
            self.log_message(f"自動清除指令失敗: {e}")
    
    def log_message(self, message):
        """添加日志消息"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # 在主線程中更新UI
        self.root.after(0, lambda: self._update_log(log_entry))
    
    def _update_log(self, log_entry):
        """更新日志顯示"""
        self.log_text.insert("end", log_entry)
        self.log_text.see("end")  # 滾動到最新消息
    
    def update_status_display(self):
        """更新狀態顯示"""
        # 更新運動狀態
        if self.motor_status["moving"]:
            self.status_labels["運動中"].configure(text="是", text_color="orange")
        else:
            self.status_labels["運動中"].configure(text="否", text_color="green")
        
        # 更新原點狀態
        if self.motor_status["home"]:
            self.status_labels["在原點"].configure(text="是", text_color="green")
        else:
            self.status_labels["在原點"].configure(text="否", text_color="gray")
        
        # 更新準備狀態
        if self.motor_status["ready"]:
            self.status_labels["準備就緒"].configure(text="是", text_color="green")
        else:
            self.status_labels["準備就緒"].configure(text="否", text_color="red")
    
    def status_monitoring_thread(self):
        """狀態監控線程"""
        while self.monitoring:
            if self.is_connected:
                self.read_motor_status()
            time.sleep(0.5)  # 每500ms更新一次狀態
    
    def start_status_monitoring(self):
        """開始狀態監控"""
        self.monitoring = True
        thread = threading.Thread(target=self.status_monitoring_thread, daemon=True)
        thread.start()
    
    def run(self):
        """運行應用程序"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """關閉應用程序時的清理工作"""
        self.monitoring = False
        if self.is_connected:
            self.modbus.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    app = MotorControlApp()
    app.run()