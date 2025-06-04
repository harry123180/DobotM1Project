import customtkinter as ctk
import asyncio
import tkinter as tk
from tkinter import messagebox
from pymodbus.client import ModbusSerialClient
import threading
import time
from typing import Optional

class XC100Controller:
    def __init__(self):
        # 初始化GUI
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("XC100 滑台控制工具")
        self.root.geometry("800x600")
        
        # Modbus客户端
        self.client: Optional[ModbusSerialClient] = None
        self.is_connected = False
        self.station_id = 1  # 默认站号，需要根据实际情况调整
        
        # 状态变量
        self.action_status = tk.StringVar(value="未连接")
        self.alarm_status = tk.StringVar(value="未连接")
        self.servo_status = tk.StringVar(value="未连接")
        self.current_position = tk.StringVar(value="0")
        
        # 移动量输入变量
        self.relative_move_var = tk.StringVar(value="0")
        self.absolute_move_var = tk.StringVar(value="0")
        
        # 创建GUI界面
        self.create_widgets()
        
        # 启动状态监控线程
        self.monitoring = False
        self.monitor_thread = None
        
    def create_widgets(self):
        """创建GUI组件"""
        
        # 连接控制区域
        connection_frame = ctk.CTkFrame(self.root)
        connection_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(connection_frame, text="连接设置", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 串口设置
        port_frame = ctk.CTkFrame(connection_frame)
        port_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(port_frame, text="串口:").pack(side="left", padx=5)
        self.port_entry = ctk.CTkEntry(port_frame, placeholder_text="COM1")
        self.port_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(port_frame, text="波特率:").pack(side="left", padx=5)
        self.baudrate_combo = ctk.CTkComboBox(port_frame, values=["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.set("9600")
        self.baudrate_combo.pack(side="left", padx=5)
        
        ctk.CTkLabel(port_frame, text="站号:").pack(side="left", padx=5)
        self.station_entry = ctk.CTkEntry(port_frame, placeholder_text="1", width=60)
        self.station_entry.pack(side="left", padx=5)
        
        self.connect_btn = ctk.CTkButton(connection_frame, text="连接", command=self.connect_device)
        self.connect_btn.pack(pady=10)
        
        # 状态显示区域
        status_frame = ctk.CTkFrame(self.root)
        status_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(status_frame, text="设备状态", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 状态信息网格
        status_grid = ctk.CTkFrame(status_frame)
        status_grid.pack(pady=5, padx=10, fill="x")
        
        # 动作状态
        ctk.CTkLabel(status_grid, text="动作状态:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.action_status, fg_color="gray").grid(row=0, column=1, sticky="w", padx=5, pady=2)
        
        # 警报状态
        ctk.CTkLabel(status_grid, text="警报状态:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.alarm_status, fg_color="gray").grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # 伺服状态
        ctk.CTkLabel(status_grid, text="伺服状态:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.servo_status, fg_color="gray").grid(row=2, column=1, sticky="w", padx=5, pady=2)
        
        # 当前位置
        ctk.CTkLabel(status_grid, text="当前位置:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ctk.CTkLabel(status_grid, textvariable=self.current_position, fg_color="gray").grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        # 控制区域
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        ctk.CTkLabel(control_frame, text="控制命令", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 初始化按钮
        self.init_btn = ctk.CTkButton(control_frame, text="初始化滑台(原点复归)", command=self.initialize_device)
        self.init_btn.pack(pady=5)
        
        # 伺服控制
        servo_frame = ctk.CTkFrame(control_frame)
        servo_frame.pack(pady=5, padx=10, fill="x")
        
        self.servo_on_btn = ctk.CTkButton(servo_frame, text="伺服ON", command=self.servo_on, fg_color="green")
        self.servo_on_btn.pack(side="left", padx=5)
        
        self.servo_off_btn = ctk.CTkButton(servo_frame, text="伺服OFF", command=self.servo_off, fg_color="red")
        self.servo_off_btn.pack(side="left", padx=5)
        
        # 移动控制
        move_frame = ctk.CTkFrame(control_frame)
        move_frame.pack(pady=10, padx=10, fill="x")
        
        # 相对移动
        rel_frame = ctk.CTkFrame(move_frame)
        rel_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(rel_frame, text="相对移动:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=5)
        
        rel_input_frame = ctk.CTkFrame(rel_frame)
        rel_input_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(rel_input_frame, text="移动量(0.01mm):").pack(side="left", padx=5)
        rel_entry = ctk.CTkEntry(rel_input_frame, textvariable=self.relative_move_var, placeholder_text="输入移动量")
        rel_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        self.rel_move_btn = ctk.CTkButton(rel_input_frame, text="执行相对移动", command=self.relative_move)
        self.rel_move_btn.pack(side="right", padx=5)
        
        # 绝对移动
        abs_frame = ctk.CTkFrame(move_frame)
        abs_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(abs_frame, text="绝对移动:", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=5)
        
        abs_input_frame = ctk.CTkFrame(abs_frame)
        abs_input_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(abs_input_frame, text="目标位置(0.01mm):").pack(side="left", padx=5)
        abs_entry = ctk.CTkEntry(abs_input_frame, textvariable=self.absolute_move_var, placeholder_text="输入目标位置")
        abs_entry.pack(side="left", padx=5, fill="x", expand=True)
        
        self.abs_move_btn = ctk.CTkButton(abs_input_frame, text="执行绝对移动", command=self.absolute_move)
        self.abs_move_btn.pack(side="right", padx=5)
        
        # 紧急停止
        self.emergency_stop_btn = ctk.CTkButton(control_frame, text="紧急停止", command=self.emergency_stop, 
                                               fg_color="red", hover_color="darkred", font=ctk.CTkFont(size=16, weight="bold"))
        self.emergency_stop_btn.pack(pady=10)
        
        # 初始状态下禁用控制按钮
        self.disable_control_buttons()
    
    def disable_control_buttons(self):
        """禁用控制按钮"""
        buttons = [self.init_btn, self.servo_on_btn, self.servo_off_btn, 
                  self.rel_move_btn, self.abs_move_btn, self.emergency_stop_btn]
        for btn in buttons:
            btn.configure(state="disabled")
    
    def enable_control_buttons(self):
        """启用控制按钮"""
        buttons = [self.init_btn, self.servo_on_btn, self.servo_off_btn, 
                  self.rel_move_btn, self.abs_move_btn, self.emergency_stop_btn]
        for btn in buttons:
            btn.configure(state="normal")
    
    def connect_device(self):
        """连接设备"""
        try:
            if self.is_connected:
                # 断开连接
                self.disconnect_device()
                return
                
            port = self.port_entry.get() or "COM1"
            baudrate = int(self.baudrate_combo.get())
            station = self.station_entry.get()
            
            if station:
                self.station_id = int(station)
            
            # 创建Modbus客户端，使用RTU模式
            self.client = ModbusSerialClient(
                method='rtu',
                port=port,
                baudrate=baudrate,
                timeout=1,
                parity='N',
                stopbits=1,
                bytesize=8
            )
            
            if self.client.connect():
                self.is_connected = True
                self.connect_btn.configure(text="断开连接", fg_color="red")
                self.enable_control_buttons()
                
                # 启动状态监控
                self.start_monitoring()
                
                messagebox.showinfo("成功", f"已连接到 {port}")
            else:
                messagebox.showerror("错误", "连接失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"连接错误: {str(e)}")
    
    def disconnect_device(self):
        """断开设备连接"""
        self.stop_monitoring()
        
        if self.client:
            self.client.close()
            self.client = None
            
        self.is_connected = False
        self.connect_btn.configure(text="连接", fg_color=["#3B8ED0", "#1F6AA5"])
        self.disable_control_buttons()
        
        # 重置状态显示
        self.action_status.set("未连接")
        self.alarm_status.set("未连接")
        self.servo_status.set("未连接")
        self.current_position.set("0")
    
    def start_monitoring(self):
        """启动状态监控"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_status)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止状态监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)
    
    def monitor_status(self):
        """状态监控线程"""
        while self.monitoring and self.is_connected:
            try:
                self.read_status()
                time.sleep(0.5)  # 每500ms更新一次
            except Exception as e:
                print(f"监控错误: {e}")
                time.sleep(1)
    
    def read_status(self):
        """读取设备状态"""
        if not self.client or not self.is_connected:
            return
            
        try:
            # 读取动作状态 (1000H)
            result = self.client.read_holding_registers(0x1000, 1, unit=self.station_id)
            if not result.isError():
                action_code = result.registers[0]
                action_texts = {0: "停止", 1: "动作中", 2: "异常停止"}
                self.action_status.set(action_texts.get(action_code, f"未知({action_code})"))
            
            # 读取警报状态 (1005H)
            result = self.client.read_holding_registers(0x1005, 1, unit=self.station_id)
            if not result.isError():
                alarm_code = result.registers[0]
                alarm_texts = {
                    0: "无警报", 1: "Loop error", 2: "Full Count", 3: "过速度",
                    4: "增益值调整不良", 5: "过电压", 6: "初期化异常", 7: "EEPROM异常",
                    8: "主回路电源电压不足", 9: "过电流", 10: "回生异常", 11: "紧急停止",
                    12: "马达断线", 13: "编码器断线", 14: "保护电流值", 15: "电源再投入", 17: "动作超时"
                }
                self.alarm_status.set(alarm_texts.get(alarm_code, f"未知警报({alarm_code})"))
            
            # 读取伺服状态 (100CH)
            result = self.client.read_holding_registers(0x100C, 1, unit=self.station_id)
            if not result.isError():
                servo_code = result.registers[0]
                servo_texts = {0: "伺服OFF", 1: "伺服ON"}
                self.servo_status.set(servo_texts.get(servo_code, f"未知({servo_code})"))
            
            # 读取当前位置 (1008H-1009H, 2个Word)
            result = self.client.read_holding_registers(0x1008, 2, unit=self.station_id)
            if not result.isError():
                # 组合32位位置数据
                position = (result.registers[0] << 16) | result.registers[1]
                # 处理有符号整数
                if position > 0x7FFFFFFF:
                    position -= 0x100000000
                self.current_position.set(f"{position * 0.01:.2f} mm")
                
        except Exception as e:
            print(f"读取状态错误: {e}")
    
    def write_register(self, address, value):
        """写入寄存器"""
        if not self.client or not self.is_connected:
            messagebox.showerror("错误", "设备未连接")
            return False
            
        try:
            result = self.client.write_register(address, value, unit=self.station_id)
            return not result.isError()
        except Exception as e:
            messagebox.showerror("错误", f"写入失败: {str(e)}")
            return False
    
    def write_registers(self, address, values):
        """写入多个寄存器"""
        if not self.client or not self.is_connected:
            messagebox.showerror("错误", "设备未连接")
            return False
            
        try:
            result = self.client.write_registers(address, values, unit=self.station_id)
            return not result.isError()
        except Exception as e:
            messagebox.showerror("错误", f"写入失败: {str(e)}")
            return False
    
    def initialize_device(self):
        """初始化设备(原点复归)"""
        if messagebox.askyesno("确认", "确定要执行原点复归吗？"):
            # 写入移动类型 = 3 (ORG 原点复归) 到 201EH
            if self.write_register(0x201E, 3):
                messagebox.showinfo("成功", "原点复归命令已发送")
            else:
                messagebox.showerror("错误", "原点复归命令发送失败")
    
    def servo_on(self):
        """伺服ON"""
        # 写入伺服控制 = 0 (伺服ON) 到 2011H
        if self.write_register(0x2011, 0):
            messagebox.showinfo("成功", "伺服ON命令已发送")
        else:
            messagebox.showerror("错误", "伺服ON命令发送失败")
    
    def servo_off(self):
        """伺服OFF"""
        # 写入伺服控制 = 1 (伺服OFF) 到 2011H
        if self.write_register(0x2011, 1):
            messagebox.showinfo("成功", "伺服OFF命令已发送")
        else:
            messagebox.showerror("错误", "伺服OFF命令发送失败")
    
    def relative_move(self):
        """相对移动"""
        try:
            move_amount = float(self.relative_move_var.get())
            # 转换为脉冲数 (0.01mm单位)
            pulse_amount = int(move_amount * 100)
            
            # 分解为两个16位数据 (高位、低位)
            high_word = (pulse_amount >> 16) & 0xFFFF
            low_word = pulse_amount & 0xFFFF
            
            # 写入相对移动量到 2000H-2001H
            if self.write_registers(0x2000, [high_word, low_word]):
                # 写入移动类型 = 0 (INC 相对位置移动) 到 201EH
                if self.write_register(0x201E, 0):
                    messagebox.showinfo("成功", f"相对移动命令已发送: {move_amount} mm")
                else:
                    messagebox.showerror("错误", "移动类型设置失败")
            else:
                messagebox.showerror("错误", "移动量设置失败")
                
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值")
    
    def absolute_move(self):
        """绝对移动"""
        try:
            target_position = float(self.absolute_move_var.get())
            # 转换为脉冲数 (0.01mm单位)
            pulse_position = int(target_position * 100)
            
            # 分解为两个16位数据 (高位、低位)
            high_word = (pulse_position >> 16) & 0xFFFF
            low_word = pulse_position & 0xFFFF
            
            # 写入绝对移动量到 2002H-2003H
            if self.write_registers(0x2002, [high_word, low_word]):
                # 写入移动类型 = 1 (ABS 绝对位置移动) 到 201EH
                if self.write_register(0x201E, 1):
                    messagebox.showinfo("成功", f"绝对移动命令已发送: {target_position} mm")
                else:
                    messagebox.showerror("错误", "移动类型设置失败")
            else:
                messagebox.showerror("错误", "目标位置设置失败")
                
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值")
    
    def emergency_stop(self):
        """紧急停止"""
        # 写入移动类型 = 9 (紧急停止) 到 201EH
        if self.write_register(0x201E, 9):
            messagebox.showinfo("成功", "紧急停止命令已发送")
        else:
            messagebox.showerror("错误", "紧急停止命令发送失败")
    
    def run(self):
        """运行应用"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """关闭应用时的清理"""
        self.disconnect_device()
        self.root.destroy()

if __name__ == "__main__":
    app = XC100Controller()
    app.run()