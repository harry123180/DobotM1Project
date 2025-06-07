import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from pymodbus.client import ModbusSerialClient
from pymodbus import ModbusException
import threading
import time
from typing import Optional
import serial.tools.list_ports

class XC100Controller:
    def __init__(self):
        # 初始化GUI
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("XC100 滑台控制工具")
        self.root.geometry("800x600")
        
        # Modbus客戶端
        self.client: Optional[ModbusSerialClient] = None
        self.is_connected = False
        self.station_id = 3  # 預設站號改為3
        
        # 狀態變數
        self.action_status = tk.StringVar(value="未連線")
        self.alarm_status = tk.StringVar(value="未連線")
        self.servo_status = tk.StringVar(value="未連線")
        self.current_position = tk.StringVar(value="0")
        
        # 移動量輸入變數
        self.relative_move_var = tk.StringVar(value="0")
        self.absolute_move_var = tk.StringVar(value="0")
        
        # 建立GUI介面
        self.create_widgets()
        
        # 自動掃描COM口
        self.scan_com_ports()
        
        # 啟動狀態監控執行緒
        self.monitoring = False
        self.monitor_thread = None
        
    def create_widgets(self):
        """建立GUI組件"""
        
        # 連線控制區域
        connection_frame = ctk.CTkFrame(self.root)
        connection_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(connection_frame, text="連線設定", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 串列埠設定
        port_frame = ctk.CTkFrame(connection_frame)
        port_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(port_frame, text="串列埠:").pack(side="left", padx=5)
        self.port_combo = ctk.CTkComboBox(port_frame, values=["掃描中..."], width=120)
        self.port_combo.pack(side="left", padx=5)
        
        # 重新掃描按鈕
        self.scan_btn = ctk.CTkButton(port_frame, text="重新掃描", command=self.scan_com_ports, width=80)
        self.scan_btn.pack(side="left", padx=5)
        
        ctk.CTkLabel(port_frame, text="鮑率:").pack(side="left", padx=5)
        self.baudrate_combo = ctk.CTkComboBox(port_frame, values=["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.set("115200")
        self.baudrate_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(port_frame, text="站號:").pack(side="left", padx=5)
        self.station_entry = ctk.CTkEntry(port_frame, placeholder_text="3", width=60)
        self.station_entry.insert(0, "3")
        self.station_entry.pack(side="left", padx=5)
        
        self.connect_btn = ctk.CTkButton(connection_frame, text="連線", command=self.connect_device)
        self.connect_btn.pack(pady=10)
        
        # 狀態顯示區域
        status_frame = ctk.CTkFrame(self.root)
        status_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(status_frame, text="設備狀態", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 狀態資訊網格
        status_grid = ctk.CTkFrame(status_frame)
        status_grid.pack(pady=5, padx=10, fill="x")
        
        # 動作狀態
        ctk.CTkLabel(status_grid, text="動作狀態:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.action_status, fg_color="gray").grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        # 警報狀態
        ctk.CTkLabel(status_grid, text="警報狀態:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.alarm_status, fg_color="gray").grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # 伺服狀態
        ctk.CTkLabel(status_grid, text="伺服狀態:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.servo_status, fg_color="gray").grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        # 目前位置
        ctk.CTkLabel(status_grid, text="目前位置:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.current_position, fg_color="gray").grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        # 控制區域
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        ctk.CTkLabel(control_frame, text="控制指令", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 初始化按鈕
        self.init_btn = ctk.CTkButton(control_frame, text="初始化滑台(原點復歸)", command=self.initialize_device)
        self.init_btn.pack(pady=5)
        
        # 伺服控制
        servo_frame = ctk.CTkFrame(control_frame)
        servo_frame.pack(pady=5, padx=10, fill="x")
        
        self.servo_on_btn = ctk.CTkButton(servo_frame, text="伺服ON", command=self.servo_on, fg_color="green")
        self.servo_on_btn.pack(side="left", padx=5)
        
        self.servo_off_btn = ctk.CTkButton(servo_frame, text="伺服OFF", command=self.servo_off, fg_color="red")
        self.servo_off_btn.pack(side="left", padx=5)
        
        # 移動控制
        move_frame = ctk.CTkFrame(control_frame)
        move_frame.pack(pady=10, padx=10, fill="x")
        
        # 相對移動
        rel_frame = ctk.CTkFrame(move_frame)
        rel_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(rel_frame, text="相對移動:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=5)
        
        rel_input_frame = ctk.CTkFrame(rel_frame)
        rel_input_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(rel_input_frame, text="移動量(0.01mm):").pack(side="left", padx=5)
        rel_entry = ctk.CTkEntry(rel_input_frame, textvariable=self.relative_move_var, placeholder_text="輸入移動量")
        rel_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        self.rel_move_btn = ctk.CTkButton(rel_input_frame, text="執行相對移動", command=self.relative_move)
        self.rel_move_btn.pack(side="right", padx=5)
        
        # 絕對移動
        abs_frame = ctk.CTkFrame(move_frame)
        abs_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(abs_frame, text="絕對移動:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=5)
        
        abs_input_frame = ctk.CTkFrame(abs_frame)
        abs_input_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(abs_input_frame, text="目標位置(0.01mm):").pack(side="left", padx=5)
        abs_entry = ctk.CTkEntry(abs_input_frame, textvariable=self.absolute_move_var, placeholder_text="輸入目標位置")
        abs_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        self.abs_move_btn = ctk.CTkButton(abs_input_frame, text="執行絕對移動", command=self.absolute_move)
        self.abs_move_btn.pack(side="right", padx=5)
        
        # 緊急停止
        self.emergency_stop_btn = ctk.CTkButton(control_frame, text="緊急停止", command=self.emergency_stop, 
                                               fg_color="red", hover_color="darkred", font=ctk.CTkFont(size=16, weight="bold"))
        self.emergency_stop_btn.pack(pady=10)
        
        # 初始狀態下停用控制按鈕
        self.disable_control_buttons()
    
    def scan_com_ports(self):
        """掃描可用的COM口"""
        try:
            # 獲取所有可用的串列埠
            ports = serial.tools.list_ports.comports()
            port_list = []
            
            for port in ports:
                # 格式化顯示：COM口 - 描述
                port_desc = f"{port.device} - {port.description}"
                port_list.append(port_desc)
            
            if not port_list:
                port_list = ["未找到可用的COM口"]
                self.port_combo.configure(values=port_list)
                self.port_combo.set("未找到可用的COM口")
            else:
                self.port_combo.configure(values=port_list)
                # 預設選擇第一個可用的COM口
                self.port_combo.set(port_list[0])
                
        except Exception as e:
            print(f"掃描COM口錯誤: {e}")
            self.port_combo.configure(values=["掃描失敗"])
            self.port_combo.set("掃描失敗")
    
    def get_selected_port(self):
        """從下拉選單中提取COM口名稱"""
        selected = self.port_combo.get()
        if " - " in selected:
            # 提取COM口名稱（例如從 "COM3 - USB Serial Port" 提取 "COM3"）
            return selected.split(" - ")[0]
        return selected
    
    def disable_control_buttons(self):
        """停用控制按鈕"""
        buttons = [self.init_btn, self.servo_on_btn, self.servo_off_btn, 
                  self.rel_move_btn, self.abs_move_btn, self.emergency_stop_btn]
        for btn in buttons:
            btn.configure(state="disabled")
    
    def enable_control_buttons(self):
        """啟用控制按鈕"""
        buttons = [self.init_btn, self.servo_on_btn, self.servo_off_btn, 
                  self.rel_move_btn, self.abs_move_btn, self.emergency_stop_btn]
        for btn in buttons:
            btn.configure(state="normal")
    
    def connect_device(self):
        """連接設備"""
        try:
            if self.is_connected:
                # 斷開連線
                self.disconnect_device()
                return
                
            port = self.get_selected_port()
            if not port or port in ["掃描中...", "未找到可用的COM口", "掃描失敗"]:
                messagebox.showerror("錯誤", "請選擇有效的COM口")
                return
            baudrate = int(self.baudrate_combo.get())
            station = self.station_entry.get()
            
            if station:
                self.station_id = int(station)
            
            # 建立Modbus客戶端 - pymodbus 3.9.2版本（徹底移除strict參數）
            self.client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                timeout=3,
                parity='N',
                stopbits=1,
                bytesize=8
            )
            
            if self.client.connect():
                self.is_connected = True
                self.connect_btn.configure(text="斷開連線", fg_color="red")
                self.enable_control_buttons()
                
                # 啟動狀態監控前先測試連線
                if self.test_connection():
                    self.start_monitoring()
                    messagebox.showinfo("成功", f"已連線到 {port}\n站號: {self.station_id}")
                else:
                    messagebox.showwarning("警告", f"連線到 {port} 但無法與XC100通訊\n請檢查:\n1. 站號設定是否正確\n2. XC100是否開機\n3. 通訊參數設定")
            else:
                messagebox.showerror("錯誤", "連線失敗")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"連線錯誤: {str(e)}")
    
    def disconnect_device(self):
        """斷開設備連線"""
        self.stop_monitoring()
        
        if self.client:
            self.client.close()
            self.client = None
            
        self.is_connected = False
        self.connect_btn.configure(text="連線", fg_color=["#3B8ED0", "#1F6AA5"])
        self.disable_control_buttons()
        
        # 重設狀態顯示
        self.action_status.set("未連線")
        self.alarm_status.set("未連線")
        self.servo_status.set("未連線")
        self.current_position.set("0")
    
    def start_monitoring(self):
        """啟動狀態監控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_status)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止狀態監控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
    
    def monitor_status(self):
        """狀態監控執行緒"""
        consecutive_errors = 0
        max_errors = 3
        
        while self.monitoring and self.is_connected:
            try:
                self.read_status()
                consecutive_errors = 0  # 重設錯誤計數
                time.sleep(1.0)  # 每1秒更新一次，減少通訊負荷
            except Exception as e:
                consecutive_errors += 1
                print(f"監控錯誤 ({consecutive_errors}/{max_errors}): {e}")
                
                if consecutive_errors >= max_errors:
                    print("連續錯誤過多，停止監控")
                    self.disconnect_device()
                    break
                    
                time.sleep(2)  # 錯誤後等待較長時間
    
    def read_status(self):
        """讀取設備狀態"""
        if not self.client or not self.is_connected:
            return
            
        try:
            # 讀取動作狀態 (1000H) - pymodbus 3.9.2正確格式
            result = self.client.read_holding_registers(
                address=0x1000, 
                count=1, 
                slave=self.station_id
            )
            
            if not result.isError():
                action_code = result.registers[0]
                action_texts = {0: "停止", 1: "動作中", 2: "異常停止"}
                self.action_status.set(action_texts.get(action_code, f"未知({action_code})"))
            else:
                print(f"讀取1000H失敗: {result}")
                return
            
            # 讀取警報狀態 (1005H)
            result = self.client.read_holding_registers(
                address=0x1005, 
                count=1, 
                slave=self.station_id
            )
            
            if not result.isError():
                alarm_code = result.registers[0]
                alarm_texts = {
                    0: "無警報", 1: "迴路錯誤", 2: "計數滿", 3: "過速度",
                    4: "增益值調整不良", 5: "過電壓", 6: "初期化異常", 7: "EEPROM異常",
                    8: "主迴路電源電壓不足", 9: "過電流", 10: "回生異常", 11: "緊急停止",
                    12: "馬達斷線", 13: "編碼器斷線", 14: "保護電流值", 15: "電源再投入", 17: "動作逾時"
                }
                self.alarm_status.set(alarm_texts.get(alarm_code, f"未知警報({alarm_code})"))
            
            # 讀取伺服狀態 (100CH)
            result = self.client.read_holding_registers(
                address=0x100C, 
                count=1, 
                slave=self.station_id
            )
            
            if not result.isError():
                servo_code = result.registers[0]
                servo_texts = {0: "伺服OFF", 1: "伺服ON"}
                self.servo_status.set(servo_texts.get(servo_code, f"未知({servo_code})"))
            
            # 讀取目前位置 (1008H-1009H, 2個Word)
            result = self.client.read_holding_registers(
                address=0x1008, 
                count=2, 
                slave=self.station_id
            )
            
            if not result.isError():
                # 組合32位元位置資料
                position = (result.registers[0] << 16) | result.registers[1]
                # 處理有號整數
                if position > 0x7FFFFFFF:
                    position -= 0x100000000
                self.current_position.set(f"{position * 0.01:.2f} mm")
                
        except ModbusException as e:
            print(f"Modbus通訊錯誤: {e}")
            if "No response" in str(e) or "timeout" in str(e).lower():
                print("嘗試重新連線...")
                self.reconnect_device()
        except Exception as e:
            print(f"讀取狀態錯誤: {e}")
            if "No response" in str(e) or "timeout" in str(e).lower():
                print("嘗試重新連線...")
                self.reconnect_device()
    
    def reconnect_device(self):
        """重新連線設備"""
        try:
            if self.client:
                self.client.close()
                time.sleep(1)
                
                # 重新建立連線
                if self.client.connect():
                    print("重新連線成功")
                    return True
                else:
                    print("重新連線失敗")
                    self.disconnect_device()
                    return False
        except Exception as e:
            print(f"重新連線錯誤: {e}")
            self.disconnect_device()
            return False
    
    def test_connection(self):
        """測試連線功能"""
        if not self.client or not self.is_connected:
            return False
            
        try:
            # 嘗試讀取控制器型號 (10E0H) 來測試連線
            result = self.client.read_holding_registers(
                address=0x10E0, 
                count=1, 
                slave=self.station_id
            )
            return not result.isError()
        except (ModbusException, Exception):
            return False

    def write_register(self, address, value):
        """寫入暫存器"""
        if not self.client or not self.is_connected:
            messagebox.showerror("錯誤", "設備未連線")
            return False
            
        try:
            result = self.client.write_register(
                address=address, 
                value=value, 
                slave=self.station_id
            )
            return not result.isError()
        except ModbusException as e:
            messagebox.showerror("錯誤", f"Modbus寫入失敗: {str(e)}")
            return False
        except Exception as e:
            messagebox.showerror("錯誤", f"寫入失敗: {str(e)}")
            return False
    
    def write_registers(self, address, values):
        """寫入多個暫存器"""
        if not self.client or not self.is_connected:
            messagebox.showerror("錯誤", "設備未連線")
            return False
            
        try:
            result = self.client.write_registers(
                address=address, 
                values=values, 
                slave=self.station_id
            )
            return not result.isError()
        except ModbusException as e:
            messagebox.showerror("錯誤", f"Modbus寫入失敗: {str(e)}")
            return False
        except Exception as e:
            messagebox.showerror("錯誤", f"寫入失敗: {str(e)}")
            return False
    
    def initialize_device(self):
        """初始化設備(原點復歸)"""
        if messagebox.askyesno("確認", "確定要執行原點復歸嗎？"):
            # 寫入移動類型 = 3 (ORG 原點復歸) 到 201EH
            if self.write_register(0x201E, 3):
                messagebox.showinfo("成功", "原點復歸指令已發送")
            else:
                messagebox.showerror("錯誤", "原點復歸指令發送失敗")
    
    def servo_on(self):
        """伺服ON"""
        # 寫入伺服控制 = 0 (伺服ON) 到 2011H
        if self.write_register(0x2011, 0):
            messagebox.showinfo("成功", "伺服ON指令已發送")
        else:
            messagebox.showerror("錯誤", "伺服ON指令發送失敗")
    
    def servo_off(self):
        """伺服OFF"""
        # 寫入伺服控制 = 1 (伺服OFF) 到 2011H
        if self.write_register(0x2011, 1):
            messagebox.showinfo("成功", "伺服OFF指令已發送")
        else:
            messagebox.showerror("錯誤", "伺服OFF指令發送失敗")
    
    def relative_move(self):
        """相對移動"""
        try:
            move_amount = float(self.relative_move_var.get())
            # 轉換為脈衝數 (0.01mm單位)
            pulse_amount = int(move_amount * 100)
            
            # 分解為兩個16位元資料 (高位元、低位元)
            high_word = (pulse_amount >> 16) & 0xFFFF
            low_word = pulse_amount & 0xFFFF
            
            # 寫入相對移動量到 2000H-2001H
            if self.write_registers(0x2000, [high_word, low_word]):
                # 寫入移動類型 = 0 (INC 相對位置移動) 到 201EH
                if self.write_register(0x201E, 0):
                    messagebox.showinfo("成功", f"相對移動指令已發送: {move_amount} mm")
                else:
                    messagebox.showerror("錯誤", "移動類型設定失敗")
            else:
                messagebox.showerror("錯誤", "移動量設定失敗")
                
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數值")
    
    def absolute_move(self):
        """絕對移動"""
        try:
            target_position = float(self.absolute_move_var.get())
            # 轉換為脈衝數 (0.01mm單位)
            pulse_position = int(target_position * 100)
            
            # 分解為兩個16位元資料 (高位元、低位元)
            high_word = (pulse_position >> 16) & 0xFFFF
            low_word = pulse_position & 0xFFFF
            
            # 寫入絕對移動量到 2002H-2003H
            if self.write_registers(0x2002, [high_word, low_word]):
                # 寫入移動類型 = 1 (ABS 絕對位置移動) 到 201EH
                if self.write_register(0x201E, 1):
                    messagebox.showinfo("成功", f"絕對移動指令已發送: {target_position} mm")
                else:
                    messagebox.showerror("錯誤", "移動類型設定失敗")
            else:
                messagebox.showerror("錯誤", "目標位置設定失敗")
                
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數值")
    
    def emergency_stop(self):
        """緊急停止"""
        # 寫入移動類型 = 9 (緊急停止) 到 201EH
        if self.write_register(0x201E, 9):
            messagebox.showinfo("成功", "緊急停止指令已發送")
        else:
            messagebox.showerror("錯誤", "緊急停止指令發送失敗")
    
    def run(self):
        """執行應用程式"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """關閉應用程式時的清理"""
        self.disconnect_device()
        self.root.destroy()

if __name__ == "__main__":
    app = XC100Controller()
    app.run()