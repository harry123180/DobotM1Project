import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import os
from datetime import datetime
import serial.tools.list_ports
from pymodbus.client import ModbusSerialClient
from typing import Optional, Dict, Any

# 設定customtkinter外觀
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class ConfigManager:
    """配置管理器"""
    def __init__(self, config_file="xc100_config.json"):
        self.config_file = config_file
        self.default_config = {
            "connection": {
                "baudrate": 19200,
                "unit_id": 2,
                "timeout": 0.2,
                "last_port": ""
            },
            "positions": {
                "position_A": 400,
                "position_B": 2682,
                "custom_positions": {}
            },
            "ui": {
                "appearance_mode": "light",
                "color_theme": "blue",
                "window_geometry": "800x750"
            }
        }
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """載入配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                # 合併默認配置
                config = self.default_config.copy()
                config.update(loaded_config)
                return config
            else:
                return self.default_config.copy()
        except Exception:
            return self.default_config.copy()
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失敗: {e}")
    
    def get(self, key_path: str, default=None):
        """獲取配置值"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, key_path: str, value):
        """設置配置值"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
        self.save_config()

class StatusMonitor:
    """狀態監控器"""
    def __init__(self, parent):
        self.parent = parent
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """開始狀態監控"""
        if not self.monitoring and self.parent.is_connected:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止狀態監控"""
        self.monitoring = False
    
    def _monitor_loop(self):
        """監控循環"""
        while self.monitoring and self.parent.is_connected:
            try:
                # 每3秒檢查一次狀態
                self.parent.check_error_status()
                self.parent.check_servo_status()
                self.parent.check_position_status()
                time.sleep(3)
            except Exception:
                break

class XC100ControlTool:
    def __init__(self):
        # 配置管理器
        self.config_manager = ConfigManager()
        
        # 初始化主窗口
        self.root = ctk.CTk()
        self.root.title("XC100 控制工具 - 進階版")
        geometry = self.config_manager.get("ui.window_geometry", "800x750")
        self.root.geometry(geometry)
        self.root.resizable(True, True)
        
        # 設定外觀
        appearance_mode = self.config_manager.get("ui.appearance_mode", "light")
        ctk.set_appearance_mode(appearance_mode)
        
        # MODBUS連線參數
        self.selected_port = tk.StringVar()
        self.baudrate = self.config_manager.get("connection.baudrate", 19200)
        self.unit_id = self.config_manager.get("connection.unit_id", 2)
        self.timeout = self.config_manager.get("connection.timeout", 0.2)
        self.client: Optional[ModbusSerialClient] = None
        self.is_connected = False
        
        # 位置設定
        self.position_A = self.config_manager.get("positions.position_A", 400)
        self.position_B = self.config_manager.get("positions.position_B", 2682)
        self.custom_positions = self.config_manager.get("positions.custom_positions", {})
        
        # 狀態監控器
        self.status_monitor = StatusMonitor(self)
        
        # 當前位置
        self.current_position = 0
        
        self.setup_ui()
        self.scan_com_ports()
        
        # 恢復上次的COM口選擇
        last_port = self.config_manager.get("connection.last_port", "")
        if last_port:
            try:
                self.selected_port.set(last_port)
            except:
                pass
    
    def setup_ui(self):
        """設置使用者介面"""
        # 建立主要框架
        self.setup_main_frames()
        self.setup_connection_frame()
        self.setup_status_frame()
        self.setup_position_frame()
        self.setup_control_frame()
        self.setup_log_frame()
        self.setup_menu()
    
    def setup_main_frames(self):
        """設置主要框架"""
        # 主標題
        title_label = ctk.CTkLabel(
            self.root, 
            text="XC100 控制工具 - 進階版", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=10)
        
        # 主容器
        main_container = ctk.CTkFrame(self.root)
        main_container.pack(pady=5, padx=10, fill="both", expand=True)
        
        # 左側面板
        self.left_panel = ctk.CTkFrame(main_container, width=400)
        self.left_panel.pack(side="left", fill="both", expand=True, padx=(5, 2.5))
        self.left_panel.pack_propagate(False)
        
        # 右側面板
        self.right_panel = ctk.CTkFrame(main_container, width=380)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(2.5, 5))
        self.right_panel.pack_propagate(False)
    
    def setup_connection_frame(self):
        """設置連線框架"""
        self.connection_frame = ctk.CTkFrame(self.left_panel)
        self.connection_frame.pack(pady=5, padx=10, fill="x")
        
        conn_title = ctk.CTkLabel(
            self.connection_frame, 
            text="🔌 連線設定", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        conn_title.pack(pady=8)
        
        # 連線參數設定區
        settings_frame = ctk.CTkFrame(self.connection_frame)
        settings_frame.pack(pady=5, padx=10, fill="x")
        
        # COM口選擇行
        com_frame = ctk.CTkFrame(settings_frame)
        com_frame.pack(pady=5, fill="x")
        
        ctk.CTkLabel(com_frame, text="COM口:", width=80).pack(side="left", padx=5)
        
        self.com_combobox = ctk.CTkComboBox(
            com_frame,
            variable=self.selected_port,
            width=150,
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
        
        # 連線參數顯示
        params_frame = ctk.CTkFrame(settings_frame)
        params_frame.pack(pady=5, fill="x")
        
        params_text = f"波特率: {self.baudrate} | 從站ID: {self.unit_id} | 超時: {self.timeout}s"
        self.params_label = ctk.CTkLabel(params_frame, text=params_text, font=ctk.CTkFont(size=11))
        self.params_label.pack(pady=5)
        
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
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="red"
        )
        self.connection_status.pack(side="left", padx=15)
    
    def setup_status_frame(self):
        """設置狀態框架"""
        self.status_frame = ctk.CTkFrame(self.left_panel)
        self.status_frame.pack(pady=5, padx=10, fill="x")
        
        status_title = ctk.CTkLabel(
            self.status_frame, 
            text="📊 設備狀態", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        status_title.pack(pady=8)
        
        # 狀態顯示網格
        status_grid = ctk.CTkFrame(self.status_frame)
        status_grid.pack(pady=5, padx=10, fill="x")
        
        # 錯誤狀態
        self.error_status = ctk.CTkLabel(
            status_grid, 
            text="錯誤狀態: 未檢查", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.error_status.pack(pady=3)
        
        # Servo狀態
        self.servo_status = ctk.CTkLabel(
            status_grid, 
            text="Servo狀態: 未檢查", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.servo_status.pack(pady=3)
        
        # 當前位置
        self.position_status = ctk.CTkLabel(
            status_grid, 
            text="當前位置: 未知", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.position_status.pack(pady=3)
        
        # 狀態監控按鈕
        monitor_frame = ctk.CTkFrame(self.status_frame)
        monitor_frame.pack(pady=5, padx=10, fill="x")
        
        self.monitor_button = ctk.CTkButton(
            monitor_frame,
            text="開始監控",
            width=120,
            command=self.toggle_monitoring,
            fg_color="#17a2b8",
            hover_color="#138496",
            state="disabled"
        )
        self.monitor_button.pack(side="left", padx=5)
        
        self.refresh_status_button = ctk.CTkButton(
            monitor_frame,
            text="刷新狀態",
            width=120,
            command=self.refresh_all_status,
            fg_color="#6c757d",
            hover_color="#545b62",
            state="disabled"
        )
        self.refresh_status_button.pack(side="right", padx=5)
    
    def setup_position_frame(self):
        """設置位置設定框架"""
        self.position_frame = ctk.CTkFrame(self.right_panel)
        self.position_frame.pack(pady=5, padx=10, fill="x")
        
        pos_title = ctk.CTkLabel(
            self.position_frame, 
            text="📍 位置管理", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        pos_title.pack(pady=8)
        
        # A點B點設定
        ab_settings = ctk.CTkFrame(self.position_frame)
        ab_settings.pack(pady=5, padx=10, fill="x")
        
        # A點設定
        a_frame = ctk.CTkFrame(ab_settings)
        a_frame.pack(pady=2, fill="x")
        
        ctk.CTkLabel(a_frame, text="A點位置:", width=80).pack(side="left", padx=5)
        self.pos_a_entry = ctk.CTkEntry(a_frame, width=100)
        self.pos_a_entry.pack(side="left", padx=5)
        self.pos_a_entry.insert(0, str(self.position_A))
        
        ctk.CTkButton(
            a_frame, text="更新", width=60,
            command=lambda: self.update_position('A')
        ).pack(side="left", padx=5)
        
        # B點設定
        b_frame = ctk.CTkFrame(ab_settings)
        b_frame.pack(pady=2, fill="x")
        
        ctk.CTkLabel(b_frame, text="B點位置:", width=80).pack(side="left", padx=5)
        self.pos_b_entry = ctk.CTkEntry(b_frame, width=100)
        self.pos_b_entry.pack(side="left", padx=5)
        self.pos_b_entry.insert(0, str(self.position_B))
        
        ctk.CTkButton(
            b_frame, text="更新", width=60,
            command=lambda: self.update_position('B')
        ).pack(side="left", padx=5)
        
        # 自定義位置
        custom_frame = ctk.CTkFrame(self.position_frame)
        custom_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(
            custom_frame, 
            text="自定義位置", 
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(pady=5)
        
        custom_input = ctk.CTkFrame(custom_frame)
        custom_input.pack(pady=2, fill="x")
        
        self.custom_name_entry = ctk.CTkEntry(custom_input, placeholder_text="位置名稱", width=80)
        self.custom_name_entry.pack(side="left", padx=2)
        
        self.custom_pos_entry = ctk.CTkEntry(custom_input, placeholder_text="位置值", width=80)
        self.custom_pos_entry.pack(side="left", padx=2)
        
        ctk.CTkButton(
            custom_input, text="添加", width=60,
            command=self.add_custom_position
        ).pack(side="left", padx=2)
        
        # 自定義位置列表
        self.custom_pos_list = ctk.CTkScrollableFrame(custom_frame, height=80)
        self.custom_pos_list.pack(pady=5, padx=5, fill="x")
        
        self.update_custom_position_list()
    
    def setup_control_frame(self):
        """設置控制框架"""
        control_panel_frame = ctk.CTkFrame(self.right_panel)
        control_panel_frame.pack(pady=5, padx=10, fill="both", expand=True)
        
        control_title = ctk.CTkLabel(
            control_panel_frame, 
            text="🎮 控制面板", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        control_title.pack(pady=8)
        
        # Servo控制
        servo_frame = ctk.CTkFrame(control_panel_frame)
        servo_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(
            servo_frame, 
            text="伺服控制", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        servo_buttons = ctk.CTkFrame(servo_frame)
        servo_buttons.pack(pady=5, fill="x")
        
        self.servo_on_button = ctk.CTkButton(
            servo_buttons,
            text="Servo ON",
            height=35,
            command=self.servo_on_action,
            fg_color="#28a745",
            hover_color="#218838",
            state="disabled"
        )
        self.servo_on_button.pack(side="left", padx=5, expand=True, fill="x")
        
        self.servo_off_button = ctk.CTkButton(
            servo_buttons,
            text="Servo OFF",
            height=35,
            command=self.servo_off_action,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled"
        )
        self.servo_off_button.pack(side="right", padx=5, expand=True, fill="x")
        
        # 移動控制
        move_frame = ctk.CTkFrame(control_panel_frame)
        move_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(
            move_frame, 
            text="移動控制", 
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=5)
        
        # 原點復歸
        self.home_button = ctk.CTkButton(
            move_frame,
            text="🏠 原點復歸",
            height=40,
            command=self.home_action,
            fg_color="#ff6b6b",
            hover_color="#ff5252",
            state="disabled"
        )
        self.home_button.pack(pady=5, fill="x")
        
        # A點B點按鈕
        ab_buttons = ctk.CTkFrame(move_frame)
        ab_buttons.pack(pady=5, fill="x")
        
        self.point_a_button = ctk.CTkButton(
            ab_buttons,
            text=f"A點\n({self.position_A})",
            height=50,
            command=self.move_to_a,
            fg_color="#4dabf7",
            hover_color="#339af0",
            state="disabled"
        )
        self.point_a_button.pack(side="left", padx=5, expand=True, fill="x")
        
        self.point_b_button = ctk.CTkButton(
            ab_buttons,
            text=f"B點\n({self.position_B})",
            height=50,
            command=self.move_to_b,
            fg_color="#51cf66",
            hover_color="#40c057",
            state="disabled"
        )
        self.point_b_button.pack(side="right", padx=5, expand=True, fill="x")
        
        # 緊急停止
        self.emergency_stop_button = ctk.CTkButton(
            move_frame,
            text="🛑 緊急停止",
            height=40,
            command=self.emergency_stop,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled"
        )
        self.emergency_stop_button.pack(pady=5, fill="x")
    
    def setup_log_frame(self):
        """設置日誌框架"""
        log_frame = ctk.CTkFrame(self.left_panel)
        log_frame.pack(pady=5, padx=10, fill="both", expand=True)
        
        log_title = ctk.CTkLabel(
            log_frame, 
            text="📝 操作日誌", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_title.pack(pady=5)
        
        # 日誌文字框
        self.log_text = ctk.CTkTextbox(log_frame, height=200)
        self.log_text.pack(pady=5, padx=10, fill="both", expand=True)
        
        # 日誌控制按鈕
        log_controls = ctk.CTkFrame(log_frame)
        log_controls.pack(pady=5, fill="x")
        
        ctk.CTkButton(
            log_controls,
            text="清除日誌",
            width=100,
            command=self.clear_log,
            fg_color="#6c757d",
            hover_color="#545b62"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            log_controls,
            text="匯出日誌",
            width=100,
            command=self.export_log,
            fg_color="#17a2b8",
            hover_color="#138496"
        ).pack(side="right", padx=5)
    
    def setup_menu(self):
        """設置選單"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # 設定選單
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="設定", menu=settings_menu)
        settings_menu.add_command(label="連線參數", command=self.open_connection_settings)
        settings_menu.add_command(label="外觀設定", command=self.open_appearance_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="重置配置", command=self.reset_config)
        
        # 工具選單
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="寄存器讀寫", command=self.open_register_tool)
        tools_menu.add_command(label="設備診斷", command=self.device_diagnosis)
        
        # 說明選單
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="說明", menu=help_menu)
        help_menu.add_command(label="使用說明", command=self.show_help)
        help_menu.add_command(label="關於", command=self.show_about)
    
    def scan_com_ports(self):
        """掃描可用的COM口"""
        try:
            ports = serial.tools.list_ports.comports()
            port_list = [f"{port.device} ({port.description})" for port in ports]
            
            if port_list:
                self.com_combobox.configure(values=port_list)
                if not self.selected_port.get() or self.selected_port.get() not in port_list:
                    self.selected_port.set(port_list[0])
                self.log_message(f"🔍 掃描到COM口: {len(port_list)}個")
            else:
                self.com_combobox.configure(values=["無可用COM口"])
                self.selected_port.set("無可用COM口")
                self.log_message("⚠️ 未發現可用的COM口")
                
        except Exception as e:
            self.log_message(f"❌ COM口掃描失敗: {e}")
    
    def connect_modbus(self):
        """連線到MODBUS設備"""
        selected = self.selected_port.get()
        if not selected or "無可用COM口" in selected:
            self.log_message("❌ 請選擇有效的COM口")
            return
        
        # 提取COM口名稱
        port_name = selected.split(" (")[0]
        
        def connect_thread():
            try:
                self.log_message(f"🔌 正在連接到 {port_name}...")
                
                self.client = ModbusSerialClient(
                    port=port_name,
                    baudrate=self.baudrate,
                    stopbits=1,
                    parity='N',
                    timeout=self.timeout
                )
                
                if self.client.connect():
                    self.is_connected = True
                    self.root.after(0, self.update_connection_ui, True)
                    self.log_message("✅ MODBUS連線成功")
                    
                    # 保存成功連線的COM口
                    self.config_manager.set("connection.last_port", selected)
                    
                    # 開始狀態監控
                    self.status_monitor.start_monitoring()
                    
                    # 初始狀態檢查
                    time.sleep(0.1)
                    self.refresh_all_status()
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
            self.status_monitor.stop_monitoring()
            
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
            self.connection_status.configure(text="狀態: 已連線", text_color="green")
            self.connect_button.configure(state="disabled")
            self.disconnect_button.configure(state="normal")
            self.com_combobox.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            
            # 啟用控制按鈕
            buttons = [
                self.servo_on_button, self.servo_off_button, self.home_button,
                self.point_a_button, self.point_b_button, self.emergency_stop_button,
                self.monitor_button, self.refresh_status_button
            ]
            for button in buttons:
                button.configure(state="normal")
        else:
            self.connection_status.configure(text="狀態: 未連線", text_color="red")
            self.connect_button.configure(state="normal")
            self.disconnect_button.configure(state="disabled")
            self.com_combobox.configure(state="readonly")
            self.refresh_button.configure(state="normal")
            
            # 禁用控制按鈕
            buttons = [
                self.servo_on_button, self.servo_off_button, self.home_button,
                self.point_a_button, self.point_b_button, self.emergency_stop_button,
                self.monitor_button, self.refresh_status_button
            ]
            for button in buttons:
                button.configure(state="disabled")
            
            # 重置狀態顯示
            self.servo_status.configure(text="Servo狀態: 未檢查", text_color="gray")
            self.error_status.configure(text="錯誤狀態: 未檢查", text_color="gray")
            self.position_status.configure(text="當前位置: 未知", text_color="gray")
            
            if self.status_monitor.monitoring:
                self.monitor_button.configure(text="開始監控")
    
    def log_message(self, message):
        """添加日誌訊息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert("end", log_entry)
        self.log_text.see("end")
        self.root.update()
    
    def clear_log(self):
        """清除日誌"""
        self.log_text.delete("1.0", "end")
        self.log_message("📝 日誌已清除")
    
    def export_log(self):
        """匯出日誌"""
        try:
            from tkinter import filedialog
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文字檔案", "*.txt"), ("所有檔案", "*.*")],
                initialname=f"XC100_Log_{timestamp}.txt"
            )
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get("1.0", "end"))
                self.log_message(f"📄 日誌已匯出到: {filename}")
        except Exception as e:
            self.log_message(f"❌ 匯出日誌失敗: {e}")
    
    def check_servo_status(self):
        """檢查Servo狀態"""
        if not self.is_connected:
            return False
            
        try:
            result = self.client.read_holding_registers(address=0x100C, count=1, slave=self.unit_id)
            
            if result.isError():
                return False
                
            servo_status = result.registers[0]
            
            if servo_status == 1:
                self.servo_status.configure(text="Servo狀態: ON ✅", text_color="green")
                return True
            else:
                self.servo_status.configure(text="Servo狀態: OFF ❌", text_color="red")
                return False
                
        except Exception:
            return False
    
    def check_error_status(self):
        """檢查錯誤狀態"""
        if not self.is_connected:
            return False
            
        try:
            result = self.client.read_holding_registers(address=0x100D, count=1, slave=self.unit_id)
            
            if result.isError():
                return False
                
            error_code = result.registers[0]
            
            if error_code == 0:
                self.error_status.configure(text="錯誤狀態: 正常 ✅", text_color="green")
                return True
            else:
                error_messages = {
                    1: "在動作中接收動作指令", 2: "上下限錯誤", 3: "位置錯誤",
                    4: "格式錯誤", 5: "控制模式錯誤", 6: "斷電重開",
                    7: "初始化未完成", 8: "Servo ON/OFF 錯誤", 9: "LOCK",
                    10: "軟體極限", 11: "參數寫入權限不足", 12: "原點復歸未完成",
                    13: "剎車已解除"
                }
                error_msg = error_messages.get(error_code, f"未知錯誤: {error_code}")
                self.error_status.configure(text=f"錯誤: {error_msg}", text_color="red")
                return False
                
        except Exception:
            return False
    
    def check_position_status(self):
        """檢查當前位置"""
        if not self.is_connected:
            return
            
        try:
            # 讀取當前位置 (假設寄存器地址為1000H-1001H)
            result = self.client.read_holding_registers(address=0x1000, count=2, slave=self.unit_id)
            
            if not result.isError():
                # 組合32位元位置值
                position = (result.registers[0] << 16) | result.registers[1]
                self.current_position = position
                self.position_status.configure(
                    text=f"當前位置: {position}", 
                    text_color="blue"
                )
                
        except Exception:
            pass
    
    def refresh_all_status(self):
        """刷新所有狀態"""
        if self.is_connected:
            self.check_error_status()
            self.check_servo_status()
            self.check_position_status()
            self.log_message("🔄 狀態已刷新")
    
    def toggle_monitoring(self):
        """切換監控狀態"""
        if self.status_monitor.monitoring:
            self.status_monitor.stop_monitoring()
            self.monitor_button.configure(text="開始監控")
            self.log_message("⏹️ 狀態監控已停止")
        else:
            self.status_monitor.start_monitoring()
            self.monitor_button.configure(text="停止監控")
            self.log_message("▶️ 狀態監控已開始")
    
    def update_position(self, point):
        """更新位置設定"""
        try:
            if point == 'A':
                new_pos = int(self.pos_a_entry.get())
                self.position_A = new_pos
                self.point_a_button.configure(text=f"A點\n({new_pos})")
                self.config_manager.set("positions.position_A", new_pos)
            elif point == 'B':
                new_pos = int(self.pos_b_entry.get())
                self.position_B = new_pos
                self.point_b_button.configure(text=f"B點\n({new_pos})")
                self.config_manager.set("positions.position_B", new_pos)
            
            self.log_message(f"📍 {point}點位置已更新為: {new_pos}")
            
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數字")
    
    def add_custom_position(self):
        """添加自定義位置"""
        try:
            name = self.custom_name_entry.get().strip()
            position = int(self.custom_pos_entry.get())
            
            if not name:
                messagebox.showerror("錯誤", "請輸入位置名稱")
                return
            
            self.custom_positions[name] = position
            self.config_manager.set("positions.custom_positions", self.custom_positions)
            
            self.custom_name_entry.delete(0, 'end')
            self.custom_pos_entry.delete(0, 'end')
            
            self.update_custom_position_list()
            self.log_message(f"📍 已添加自定義位置: {name} ({position})")
            
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數字")
    
    def update_custom_position_list(self):
        """更新自定義位置列表"""
        # 清除現有項目
        for widget in self.custom_pos_list.winfo_children():
            widget.destroy()
        
        # 添加自定義位置
        for name, position in self.custom_positions.items():
            pos_frame = ctk.CTkFrame(self.custom_pos_list)
            pos_frame.pack(pady=2, fill="x")
            
            ctk.CTkLabel(pos_frame, text=f"{name}: {position}").pack(side="left", padx=5)
            
            ctk.CTkButton(
                pos_frame, text="移動", width=50,
                command=lambda p=position: self.move_to_custom_position(p)
            ).pack(side="right", padx=2)
            
            ctk.CTkButton(
                pos_frame, text="刪除", width=50,
                command=lambda n=name: self.delete_custom_position(n),
                fg_color="#dc3545", hover_color="#c82333"
            ).pack(side="right", padx=2)
    
    def move_to_custom_position(self, position):
        """移動到自定義位置"""
        def run_move():
            try:
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message(f"📍 開始移動到自定義位置: {position}"))
                
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                if self.write_absolute_position(position) and self.execute_movement(1):
                    self.root.after(0, lambda: self.log_message(f"✅ 移動到自定義位置指令發送完成"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_move, daemon=True).start()
    
    def delete_custom_position(self, name):
        """刪除自定義位置"""
        if messagebox.askyesno("確認", f"確定要刪除位置 '{name}' 嗎？"):
            del self.custom_positions[name]
            self.config_manager.set("positions.custom_positions", self.custom_positions)
            self.update_custom_position_list()
            self.log_message(f"🗑️ 已刪除自定義位置: {name}")
    
    def write_absolute_position(self, position):
        """設定絕對移動位置"""
        try:
            position_high = (position >> 16) & 0xFFFF
            position_low = position & 0xFFFF
            
            result = self.client.write_registers(
                address=0x2002, 
                values=[position_high, position_low], 
                slave=self.unit_id
            )
            
            if result.isError():
                raise Exception("寫入位置失敗")
                
            return True
            
        except Exception as e:
            self.log_message(f"❌ 設定位置失敗: {e}")
            return False
    
    def execute_movement(self, move_type):
        """執行移動指令"""
        try:
            result = self.client.write_register(
                address=0x201E, 
                value=move_type, 
                slave=self.unit_id
            )
            
            if result.isError():
                raise Exception("執行移動指令失敗")
                
            return True
            
        except Exception as e:
            self.log_message(f"❌ 執行移動失敗: {e}")
            return False
    
    def disable_control_buttons(self):
        """禁用控制按鈕"""
        buttons = [
            self.servo_on_button, self.servo_off_button, self.home_button,
            self.point_a_button, self.point_b_button, self.emergency_stop_button
        ]
        for button in buttons:
            button.configure(state="disabled")
    
    def enable_control_buttons(self):
        """啟用控制按鈕"""
        if self.is_connected:
            buttons = [
                self.servo_on_button, self.servo_off_button, self.home_button,
                self.point_a_button, self.point_b_button, self.emergency_stop_button
            ]
            for button in buttons:
                button.configure(state="normal")
    
    def servo_on_action(self):
        """Servo ON動作"""
        def run_servo_on():
            try:
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message("🔧 執行Servo ON..."))
                
                result = self.client.write_register(address=0x2011, value=0, slave=self.unit_id)
                
                if result.isError():
                    self.root.after(0, lambda: self.log_message("❌ Servo ON指令發送失敗"))
                else:
                    self.root.after(0, lambda: self.log_message("✅ Servo ON指令發送完成"))
                    time.sleep(0.1)
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
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message("🔧 執行Servo OFF..."))
                
                result = self.client.write_register(address=0x2011, value=1, slave=self.unit_id)
                
                if result.isError():
                    self.root.after(0, lambda: self.log_message("❌ Servo OFF指令發送失敗"))
                else:
                    self.root.after(0, lambda: self.log_message("✅ Servo OFF指令發送完成"))
                    time.sleep(0.1)
                    self.check_servo_status()
                    
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"❌ Servo OFF操作異常: {e}"))
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_servo_off, daemon=True).start()
    
    def home_action(self):
        """原點復歸動作"""
        def run_home():
            try:
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message("🏠 開始原點復歸操作..."))
                
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                if self.execute_movement(3):
                    self.root.after(0, lambda: self.log_message("✅ 原點復歸指令發送完成"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_home, daemon=True).start()
    
    def move_to_a(self):
        """移動到A點"""
        def run_move_a():
            try:
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message(f"📍 開始移動到A點 ({self.position_A})..."))
                
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                if self.write_absolute_position(self.position_A) and self.execute_movement(1):
                    self.root.after(0, lambda: self.log_message("✅ 移動到A點指令發送完成"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_move_a, daemon=True).start()
    
    def move_to_b(self):
        """移動到B點"""
        def run_move_b():
            try:
                self.root.after(0, self.disable_control_buttons)
                self.root.after(0, lambda: self.log_message(f"📍 開始移動到B點 ({self.position_B})..."))
                
                if not self.check_error_status():
                    self.root.after(0, lambda: self.log_message("❌ 設備狀態異常，操作取消"))
                    return
                
                if self.write_absolute_position(self.position_B) and self.execute_movement(1):
                    self.root.after(0, lambda: self.log_message("✅ 移動到B點指令發送完成"))
                    
            finally:
                self.root.after(0, self.enable_control_buttons)
        
        threading.Thread(target=run_move_b, daemon=True).start()
    
    def emergency_stop(self):
        """緊急停止"""
        try:
            if self.is_connected:
                # 緊急停止指令 (假設寫入特定寄存器)
                result = self.client.write_register(address=0x2020, value=1, slave=self.unit_id)
                if not result.isError():
                    self.log_message("🛑 緊急停止指令已發送")
                else:
                    self.log_message("❌ 緊急停止指令發送失敗")
        except Exception as e:
            self.log_message(f"❌ 緊急停止異常: {e}")
    
    def open_connection_settings(self):
        """打開連線設定對話框"""
        settings_window = ctk.CTkToplevel(self.root)
        settings_window.title("連線參數設定")
        settings_window.geometry("400x300")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 波特率設定
        ctk.CTkLabel(settings_window, text="波特率:").pack(pady=5)
        baudrate_var = tk.StringVar(value=str(self.baudrate))
        baudrate_combo = ctk.CTkComboBox(
            settings_window, 
            values=["9600", "19200", "38400", "57600", "115200"],
            variable=baudrate_var
        )
        baudrate_combo.pack(pady=5)
        
        # 從站ID設定
        ctk.CTkLabel(settings_window, text="從站ID:").pack(pady=5)
        unit_id_var = tk.StringVar(value=str(self.unit_id))
        unit_id_entry = ctk.CTkEntry(settings_window, textvariable=unit_id_var)
        unit_id_entry.pack(pady=5)
        
        # 超時設定
        ctk.CTkLabel(settings_window, text="超時時間(秒):").pack(pady=5)
        timeout_var = tk.StringVar(value=str(self.timeout))
        timeout_entry = ctk.CTkEntry(settings_window, textvariable=timeout_var)
        timeout_entry.pack(pady=5)
        
        def save_settings():
            try:
                self.baudrate = int(baudrate_var.get())
                self.unit_id = int(unit_id_var.get())
                self.timeout = float(timeout_var.get())
                
                self.config_manager.set("connection.baudrate", self.baudrate)
                self.config_manager.set("connection.unit_id", self.unit_id)
                self.config_manager.set("connection.timeout", self.timeout)
                
                # 更新參數顯示
                params_text = f"波特率: {self.baudrate} | 從站ID: {self.unit_id} | 超時: {self.timeout}s"
                self.params_label.configure(text=params_text)
                
                settings_window.destroy()
                messagebox.showinfo("成功", "連線參數已更新")
                
            except ValueError:
                messagebox.showerror("錯誤", "請輸入有效的數值")
        
        ctk.CTkButton(settings_window, text="保存", command=save_settings).pack(pady=20)
    
    def open_appearance_settings(self):
        """打開外觀設定對話框"""
        appearance_window = ctk.CTkToplevel(self.root)
        appearance_window.title("外觀設定")
        appearance_window.geometry("300x200")
        appearance_window.transient(self.root)
        appearance_window.grab_set()
        
        # 外觀模式
        ctk.CTkLabel(appearance_window, text="外觀模式:").pack(pady=10)
        appearance_var = tk.StringVar(value=ctk.get_appearance_mode())
        appearance_combo = ctk.CTkComboBox(
            appearance_window,
            values=["light", "dark", "system"],
            variable=appearance_var
        )
        appearance_combo.pack(pady=5)
        
        # 顏色主題
        ctk.CTkLabel(appearance_window, text="顏色主題:").pack(pady=10)
        theme_var = tk.StringVar(value="blue")
        theme_combo = ctk.CTkComboBox(
            appearance_window,
            values=["blue", "green", "dark-blue"],
            variable=theme_var
        )
        theme_combo.pack(pady=5)
        
        def apply_appearance():
            ctk.set_appearance_mode(appearance_var.get())
            ctk.set_default_color_theme(theme_var.get())
            
            self.config_manager.set("ui.appearance_mode", appearance_var.get())
            self.config_manager.set("ui.color_theme", theme_var.get())
            
            appearance_window.destroy()
            messagebox.showinfo("提示", "外觀設定已應用，重啟程式後完全生效")
        
        ctk.CTkButton(appearance_window, text="應用", command=apply_appearance).pack(pady=20)
    
    def reset_config(self):
        """重置配置"""
        if messagebox.askyesno("確認", "確定要重置所有配置嗎？"):
            try:
                os.remove(self.config_manager.config_file)
                messagebox.showinfo("成功", "配置已重置，請重啟程式")
            except:
                messagebox.showerror("錯誤", "重置配置失敗")
    
    def open_register_tool(self):
        """打開寄存器讀寫工具"""
        messagebox.showinfo("提示", "寄存器讀寫工具功能開發中...")
    
    def device_diagnosis(self):
        """設備診斷"""
        if not self.is_connected:
            messagebox.showwarning("警告", "請先連接設備")
            return
        
        diagnosis_window = ctk.CTkToplevel(self.root)
        diagnosis_window.title("設備診斷")
        diagnosis_window.geometry("500x400")
        diagnosis_window.transient(self.root)
        
        diagnosis_text = ctk.CTkTextbox(diagnosis_window)
        diagnosis_text.pack(pady=10, padx=10, fill="both", expand=True)
        
        diagnosis_text.insert("1.0", "正在進行設備診斷...\n\n")
        
        # 執行診斷
        def run_diagnosis():
            try:
                # 檢查基本狀態
                diagnosis_text.insert("end", "檢查錯誤狀態...\n")
                error_ok = self.check_error_status()
                diagnosis_text.insert("end", f"錯誤狀態: {'正常' if error_ok else '異常'}\n\n")
                
                diagnosis_text.insert("end", "檢查Servo狀態...\n")
                servo_ok = self.check_servo_status()
                diagnosis_text.insert("end", f"Servo狀態: {'ON' if servo_ok else 'OFF'}\n\n")
                
                diagnosis_text.insert("end", "檢查當前位置...\n")
                self.check_position_status()
                diagnosis_text.insert("end", f"當前位置: {self.current_position}\n\n")
                
                # 通訊測試
                diagnosis_text.insert("end", "通訊測試...\n")
                comm_ok = True
                for i in range(5):
                    try:
                        result = self.client.read_holding_registers(address=0x100C, count=1, slave=self.unit_id)
                        if result.isError():
                            comm_ok = False
                            break
                    except:
                        comm_ok = False
                        break
                
                diagnosis_text.insert("end", f"通訊測試: {'通過' if comm_ok else '失敗'}\n\n")
                
                diagnosis_text.insert("end", "診斷完成！\n")
                
            except Exception as e:
                diagnosis_text.insert("end", f"診斷過程中發生錯誤: {e}\n")
        
        threading.Thread(target=run_diagnosis, daemon=True).start()
    
    def show_help(self):
        """顯示使用說明"""
        help_text = """
XC100 控制工具使用說明

1. 連線設定
   - 選擇正確的COM口
   - 點擊"連接"按鈕建立連線
   - 連線成功後會自動檢查設備狀態

2. 狀態監控
   - 點擊"開始監控"自動監控設備狀態
   - 點擊"刷新狀態"手動更新狀態

3. 伺服控制
   - Servo ON: 啟用伺服馬達
   - Servo OFF: 關閉伺服馬達

4. 移動控制
   - 原點復歸: 回到原點位置
   - A點/B點: 移動到預設位置
   - 自定義位置: 可添加和移動到自定義位置

5. 設定選項
   - 連線參數: 修改波特率、從站ID等
   - 外觀設定: 切換淺色/深色模式

6. 安全注意事項
   - 移動前確保設備狀態正常
   - 緊急情況下使用緊急停止按鈕
        """
        
        help_window = ctk.CTkToplevel(self.root)
        help_window.title("使用說明")
        help_window.geometry("600x500")
        help_window.transient(self.root)
        
        help_textbox = ctk.CTkTextbox(help_window)
        help_textbox.pack(pady=10, padx=10, fill="both", expand=True)
        help_textbox.insert("1.0", help_text)
    
    def show_about(self):
        """顯示關於資訊"""
        about_text = """
XC100 控制工具 - 進階版

版本: 2.0
開發日期: 2025年6月

主要功能:
• MODBUS RTU 通訊
• 實時狀態監控  
• 位置控制和管理
• 配置文件保存
• 日誌記錄和匯出
• 設備診斷工具

技術規格:
• Python 3.x
• CustomTkinter GUI框架
• pymodbus 通訊庫
• JSON 配置管理

使用前請確保:
1. 正確連接XC100設備
2. 安裝所需的Python套件
3. 設置正確的通訊參數
        """
        
        messagebox.showinfo("關於", about_text)
    
    def on_closing(self):
        """程式關閉時的處理"""
        # 保存窗口大小
        self.config_manager.set("ui.window_geometry", self.root.geometry())
        
        # 停止監控和斷開連線
        self.status_monitor.stop_monitoring()
        if self.client and self.is_connected:
            self.disconnect_modbus()
        
        self.root.destroy()
    
    def run(self):
        """執行主程式"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 顯示啟動日誌
        self.log_message("🚀 XC100 控制工具啟動")
        self.log_message("📋 配置文件已載入")
        
        self.root.mainloop()

def main():
    """主函數"""
    try:
        app = XC100ControlTool()
        app.run()
    except Exception as e:
        print(f"程式啟動失敗: {e}")
        messagebox.showerror("錯誤", f"程式啟動失敗: {e}")

if __name__ == "__main__":
    main()