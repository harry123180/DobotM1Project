# -*- coding: utf-8 -*-
"""
Camera UI - 基於Tkinter的相機控制界面
使用Camera_API.py的抽象化API
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
from typing import Optional, List

# 導入自定義API
from Camera_API import (
    CameraAPI, CameraInfo, CameraMode, ImageFormat, 
    CameraStatus, CameraParameters, create_camera_api
)


class CameraUI:
    """相機控制UI主類"""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("相機控制系統 - Camera Control System")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # 初始化相機API
        self.camera_api = create_camera_api()
        self.camera_api.set_error_callback(self.on_error)
        
        # UI狀態變量
        self.devices: List[CameraInfo] = []
        self.current_params = CameraParameters()
        self.status_update_thread = None
        self.status_running = False
        
        # 創建UI
        self.create_widgets()
        self.update_ui_state()
        
        # 設置關閉事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 啟動狀態更新線程
        self.start_status_update()
    
    def create_widgets(self):
        """創建UI組件"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置網格權重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 創建各個功能區域
        self.create_device_section(main_frame, 0)
        self.create_connection_section(main_frame, 1)
        self.create_parameters_section(main_frame, 2)
        self.create_mode_section(main_frame, 3)
        self.create_streaming_section(main_frame, 4)
        self.create_trigger_section(main_frame, 5)
        self.create_image_section(main_frame, 6)
        self.create_status_section(main_frame, 7)
    
    def create_device_section(self, parent, row):
        """創建設備選擇區域"""
        frame = ttk.LabelFrame(parent, text="設備選擇", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 設備列表
        ttk.Label(frame, text="可用設備:").grid(row=0, column=0, sticky=tk.W)
        
        self.device_combo = ttk.Combobox(frame, state="readonly", width=60)
        self.device_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # 刷新按鈕
        ttk.Button(frame, text="刷新設備", 
                  command=self.refresh_devices).grid(row=0, column=2, padx=5)
        
        frame.columnconfigure(1, weight=1)
    
    def create_connection_section(self, parent, row):
        """創建連接控制區域"""
        frame = ttk.LabelFrame(parent, text="連接控制", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 連接按鈕
        self.connect_btn = ttk.Button(frame, text="連接", command=self.connect_device)
        self.connect_btn.grid(row=0, column=0, padx=5)
        
        self.disconnect_btn = ttk.Button(frame, text="斷開", command=self.disconnect_device)
        self.disconnect_btn.grid(row=0, column=1, padx=5)
        
        # 重置連接按鈕
        self.reset_btn = ttk.Button(frame, text="重置連接", command=self.reset_connection)
        self.reset_btn.grid(row=0, column=2, padx=5)
        
        # 包大小設置
        ttk.Label(frame, text="網絡包大小:").grid(row=0, column=3, padx=10)
        self.packet_size_btn = ttk.Button(frame, text="優化包大小", 
                                        command=self.optimize_packet_size)
        self.packet_size_btn.grid(row=0, column=4, padx=5)
    
    def create_parameters_section(self, parent, row):
        """創建參數設置區域"""
        frame = ttk.LabelFrame(parent, text="相機參數", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 曝光時間
        ttk.Label(frame, text="曝光時間(μs):").grid(row=0, column=0, sticky=tk.W)
        self.exposure_var = tk.StringVar(value="10000")
        self.exposure_entry = ttk.Entry(frame, textvariable=self.exposure_var, width=15)
        self.exposure_entry.grid(row=0, column=1, padx=5)
        
        # 增益
        ttk.Label(frame, text="增益:").grid(row=0, column=2, sticky=tk.W, padx=(20,0))
        self.gain_var = tk.StringVar(value="0")
        self.gain_entry = ttk.Entry(frame, textvariable=self.gain_var, width=15)
        self.gain_entry.grid(row=0, column=3, padx=5)
        
        # 幀率
        ttk.Label(frame, text="幀率(fps):").grid(row=1, column=0, sticky=tk.W)
        self.framerate_var = tk.StringVar(value="30")
        self.framerate_entry = ttk.Entry(frame, textvariable=self.framerate_var, width=15)
        self.framerate_entry.grid(row=1, column=1, padx=5)
        
        # 按鈕
        ttk.Button(frame, text="獲取參數", 
                  command=self.get_parameters).grid(row=1, column=2, padx=20)
        ttk.Button(frame, text="設置參數", 
                  command=self.set_parameters).grid(row=1, column=3, padx=5)
    
    def create_mode_section(self, parent, row):
        """創建模式選擇區域"""
        frame = ttk.LabelFrame(parent, text="工作模式", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 模式選擇
        self.mode_var = tk.StringVar(value="continuous")
        
        self.continuous_radio = ttk.Radiobutton(frame, text="連續模式", 
                                              variable=self.mode_var, value="continuous",
                                              command=self.set_mode)
        self.continuous_radio.grid(row=0, column=0, padx=10)
        
        self.trigger_radio = ttk.Radiobutton(frame, text="觸發模式", 
                                           variable=self.mode_var, value="trigger",
                                           command=self.set_mode)
        self.trigger_radio.grid(row=0, column=1, padx=10)
        
        # 模式狀態顯示
        ttk.Label(frame, text="當前模式:").grid(row=0, column=2, padx=(20,5))
        self.mode_status_label = ttk.Label(frame, text="連續模式", foreground="blue")
        self.mode_status_label.grid(row=0, column=3, padx=5)
    
    def create_streaming_section(self, parent, row):
        """創建串流控制區域"""
        frame = ttk.LabelFrame(parent, text="串流控制", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 串流按鈕
        self.start_stream_btn = ttk.Button(frame, text="開始串流", 
                                         command=self.start_streaming)
        self.start_stream_btn.grid(row=0, column=0, padx=5)
        
        self.stop_stream_btn = ttk.Button(frame, text="停止串流", 
                                        command=self.stop_streaming)
        self.stop_stream_btn.grid(row=0, column=1, padx=5)
        
        # 串流狀態
        ttk.Label(frame, text="串流狀態:").grid(row=0, column=2, padx=(20,5))
        self.stream_status_label = ttk.Label(frame, text="已停止", foreground="red")
        self.stream_status_label.grid(row=0, column=3, padx=5)
    
    def create_trigger_section(self, parent, row):
        """創建觸發控制區域"""
        frame = ttk.LabelFrame(parent, text="觸發控制", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 軟觸發按鈕
        self.software_trigger_btn = ttk.Button(frame, text="軟觸發", 
                                             command=self.software_trigger)
        self.software_trigger_btn.grid(row=0, column=0, padx=5)
        
        # 觸發計數
        ttk.Label(frame, text="觸發次數:").grid(row=0, column=1, padx=(20,5))
        self.trigger_count_var = tk.StringVar(value="0")
        self.trigger_count_label = ttk.Label(frame, textvariable=self.trigger_count_var)
        self.trigger_count_label.grid(row=0, column=2, padx=5)
        
        # 重置計數
        ttk.Button(frame, text="重置計數", 
                  command=self.reset_trigger_count).grid(row=0, column=3, padx=5)
        
        self.trigger_count = 0
    
    def create_image_section(self, parent, row):
        """創建圖像保存區域"""
        frame = ttk.LabelFrame(parent, text="圖像保存", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 格式選擇
        ttk.Label(frame, text="圖像格式:").grid(row=0, column=0, sticky=tk.W)
        self.image_format_var = tk.StringVar(value="bmp")
        
        format_frame = ttk.Frame(frame)
        format_frame.grid(row=0, column=1, padx=5)
        
        ttk.Radiobutton(format_frame, text="BMP", variable=self.image_format_var, 
                       value="bmp").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="JPEG", variable=self.image_format_var, 
                       value="jpeg").pack(side=tk.LEFT, padx=(10,0))
        
        # 保存按鈕
        self.save_image_btn = ttk.Button(frame, text="保存圖像", 
                                       command=self.save_image)
        self.save_image_btn.grid(row=0, column=2, padx=20)
        
        # 保存計數
        ttk.Label(frame, text="已保存:").grid(row=0, column=3, padx=5)
        self.save_count_var = tk.StringVar(value="0")
        self.save_count_label = ttk.Label(frame, textvariable=self.save_count_var)
        self.save_count_label.grid(row=0, column=4, padx=5)
        
        self.save_count = 0
    
    def create_status_section(self, parent, row):
        """創建狀態顯示區域"""
        frame = ttk.LabelFrame(parent, text="系統狀態", padding="5")
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 連接狀態
        status_info_frame = ttk.Frame(frame)
        status_info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Label(status_info_frame, text="連接狀態:").grid(row=0, column=0, sticky=tk.W)
        self.connection_status_label = ttk.Label(status_info_frame, text="未連接", 
                                               foreground="red")
        self.connection_status_label.grid(row=0, column=1, padx=10, sticky=tk.W)
        
        ttk.Label(status_info_frame, text="設備信息:").grid(row=0, column=2, padx=(20,5), sticky=tk.W)
        self.device_info_label = ttk.Label(status_info_frame, text="無", foreground="gray")
        self.device_info_label.grid(row=0, column=3, padx=5, sticky=tk.W)
        
        # 日志區域
        ttk.Label(frame, text="系統日志:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=(10,0))
        
        log_frame = ttk.Frame(frame)
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 創建文本區域和滾動條
        self.log_text = tk.Text(log_frame, height=8, width=80, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 清除日志按鈕
        ttk.Button(frame, text="清除日志", 
                  command=self.clear_log).grid(row=3, column=0, pady=5, sticky=tk.W)
        
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(2, weight=1)
        
        # 初始化日志
        self.log_message("系統啟動", "info")
    
    # ========== 事件處理方法 ==========
    
    def refresh_devices(self):
        """刷新設備列表"""
        try:
            self.log_message("正在枚舉設備...", "info")
            self.devices = self.camera_api.enumerate_devices()
            
            # 更新下拉列表
            device_names = [str(device) for device in self.devices]
            self.device_combo['values'] = device_names
            
            if device_names:
                self.device_combo.current(0)
                self.log_message(f"找到 {len(self.devices)} 個設備", "success")
            else:
                self.device_combo.set("")
                self.log_message("未找到可用設備", "warning")
                
        except Exception as e:
            self.log_message(f"枚舉設備失敗: {str(e)}", "error")
    
    def connect_device(self):
        """連接設備"""
        try:
            if not self.devices:
                self.log_message("請先刷新設備列表", "warning")
                return
            
            device_index = self.device_combo.current()
            if device_index < 0:
                self.log_message("請選擇一個設備", "warning")
                return
            
            self.log_message(f"正在連接設備 {device_index}...", "info")
            
            if self.camera_api.connect(device_index):
                device = self.devices[device_index]
                self.log_message(f"設備連接成功: {device.device_name}", "success")
                self.get_parameters()  # 自動獲取參數
            else:
                self.log_message("設備連接失敗", "error")
                
        except Exception as e:
            self.log_message(f"連接設備錯誤: {str(e)}", "error")
    
    def disconnect_device(self):
        """斷開設備"""
        try:
            if self.camera_api.disconnect():
                self.log_message("設備已斷開", "info")
            else:
                self.log_message("斷開設備失敗", "error")
        except Exception as e:
            self.log_message(f"斷開設備錯誤: {str(e)}", "error")
    
    def optimize_packet_size(self):
        """優化網絡包大小"""
        try:
            if self.camera_api.set_packet_size(0):  # 0表示使用最佳大小
                self.log_message("網絡包大小已優化", "success")
            else:
                self.log_message("優化包大小失敗", "error")
        except Exception as e:
            self.log_message(f"優化包大小錯誤: {str(e)}", "error")
    
    def get_parameters(self):
        """獲取相機參數"""
        try:
            params = self.camera_api.get_parameters()
            if params:
                self.exposure_var.set(f"{params.exposure_time:.2f}")
                self.gain_var.set(f"{params.gain:.2f}")
                self.framerate_var.set(f"{params.frame_rate:.2f}")
                self.current_params = params
                self.log_message("參數獲取成功", "success")
            else:
                self.log_message("獲取參數失敗", "error")
        except Exception as e:
            self.log_message(f"獲取參數錯誤: {str(e)}", "error")
    
    def set_parameters(self):
        """設置相機參數"""
        try:
            # 驗證輸入
            try:
                exposure = float(self.exposure_var.get())
                gain = float(self.gain_var.get())
                framerate = float(self.framerate_var.get())
            except ValueError:
                self.log_message("參數格式錯誤，請輸入數字", "error")
                return
            
            # 設置參數
            params = CameraParameters()
            params.exposure_time = exposure
            params.gain = gain
            params.frame_rate = framerate
            
            if self.camera_api.set_parameters(params):
                self.current_params = params
                self.log_message("參數設置成功", "success")
            else:
                self.log_message("參數設置失敗", "error")
                
        except Exception as e:
            self.log_message(f"設置參數錯誤: {str(e)}", "error")
    
    def set_mode(self):
        """設置工作模式"""
        try:
            # 檢查是否已連接
            if not self.camera_api.is_connected():
                self.log_message("請先連接設備", "warning")
                return
            
            mode_str = self.mode_var.get()
            mode = CameraMode.CONTINUOUS if mode_str == "continuous" else CameraMode.TRIGGER
            
            # 記錄當前串流狀態
            was_streaming = self.camera_api.is_streaming()
            
            self.log_message(f"正在切換到{'連續模式' if mode == CameraMode.CONTINUOUS else '觸發模式'}...", "info")
            
            if self.camera_api.set_mode(mode):
                mode_text = "連續模式" if mode == CameraMode.CONTINUOUS else "觸發模式"
                self.log_message(f"模式切換成功: {mode_text}", "success")
                
                # 如果之前在串流但切換後停止了，提示用戶
                if was_streaming and not self.camera_api.is_streaming():
                    self.log_message("模式切換完成，請重新點擊'開始串流'", "info")
                    
            else:
                self.log_message("模式切換失敗", "error")
                # 恢復之前的選擇
                current_mode = self.camera_api.get_mode()
                if current_mode == CameraMode.CONTINUOUS:
                    self.mode_var.set("continuous")
                else:
                    self.mode_var.set("trigger")
                
        except Exception as e:
            self.log_message(f"設置模式錯誤: {str(e)}", "error")
    
    def start_streaming(self):
        """開始串流"""
        try:
            if self.camera_api.start_streaming():
                self.log_message("串流啟動成功", "success")
            else:
                self.log_message("串流啟動失敗", "error")
        except Exception as e:
            self.log_message(f"啟動串流錯誤: {str(e)}", "error")
    
    def stop_streaming(self):
        """停止串流"""
        try:
            if self.camera_api.stop_streaming():
                self.log_message("串流已停止", "info")
            else:
                self.log_message("停止串流失敗", "error")
        except Exception as e:
            self.log_message(f"停止串流錯誤: {str(e)}", "error")
    
    def software_trigger(self):
        """軟觸發"""
        try:
            if self.camera_api.software_trigger():
                self.trigger_count += 1
                self.trigger_count_var.set(str(self.trigger_count))
                self.log_message(f"軟觸發成功 (第 {self.trigger_count} 次)", "success")
            else:
                self.log_message("軟觸發失敗", "error")
        except Exception as e:
            self.log_message(f"軟觸發錯誤: {str(e)}", "error")
    
    def reset_trigger_count(self):
        """重置觸發計數"""
        self.trigger_count = 0
        self.trigger_count_var.set("0")
        self.log_message("觸發計數已重置", "info")
    
    def save_image(self):
        """保存圖像"""
        try:
            format_str = self.image_format_var.get()
            image_format = ImageFormat.BMP if format_str == "bmp" else ImageFormat.JPEG
            
            if self.camera_api.save_image(image_format):
                self.save_count += 1
                self.save_count_var.set(str(self.save_count))
                self.log_message(f"圖像保存成功 ({format_str.upper()}) - 第 {self.save_count} 張", "success")
            else:
                self.log_message("圖像保存失敗", "error")
                
        except Exception as e:
            self.log_message(f"保存圖像錯誤: {str(e)}", "error")
    
    def clear_log(self):
        """清除日志"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("日志已清除", "info")
    
    def reset_connection(self):
        """重置連接"""
        try:
            self.log_message("正在重置連接...", "info")
            
            # 記錄當前設備索引
            current_index = self.device_combo.current()
            
            # 斷開連接
            self.disconnect_device()
            
            # 等待一下
            import time
            time.sleep(1.0)
            
            # 重新連接
            if current_index >= 0:
                self.device_combo.current(current_index)
                self.connect_device()
                
        except Exception as e:
            self.log_message(f"重置連接錯誤: {str(e)}", "error")
    
    # ========== UI狀態更新方法 ==========
    
    def update_ui_state(self):
        """更新UI狀態"""
        status = self.camera_api.get_status()
        is_connected = self.camera_api.is_connected()
        is_streaming = self.camera_api.is_streaming()
        current_mode = self.camera_api.get_mode()
        
        # 更新連接狀態
        if status == CameraStatus.DISCONNECTED:
            self.connection_status_label.config(text="未連接", foreground="red")
            self.device_info_label.config(text="無", foreground="gray")
        elif status == CameraStatus.CONNECTED:
            self.connection_status_label.config(text="已連接", foreground="green")
            device_info = self.camera_api.get_device_info()
            if device_info:
                self.device_info_label.config(text=f"{device_info.device_type}: {device_info.device_name}", 
                                            foreground="blue")
        elif status == CameraStatus.STREAMING:
            self.connection_status_label.config(text="串流中", foreground="blue")
        elif status == CameraStatus.ERROR:
            self.connection_status_label.config(text="錯誤", foreground="red")
        
        # 更新串流狀態
        if is_streaming:
            self.stream_status_label.config(text="運行中", foreground="green")
        else:
            self.stream_status_label.config(text="已停止", foreground="red")
        
        # 更新模式狀態
        mode_text = "連續模式" if current_mode == CameraMode.CONTINUOUS else "觸發模式"
        self.mode_status_label.config(text=mode_text)
        
        # 更新按鈕狀態
        self.connect_btn.config(state="normal" if not is_connected else "disabled")
        self.disconnect_btn.config(state="normal" if is_connected else "disabled")
        self.reset_btn.config(state="normal")  # 重置按鈕始終可用
        self.packet_size_btn.config(state="normal" if is_connected else "disabled")
        
        # 參數控制
        param_state = "normal" if is_connected else "disabled"
        for widget in [self.exposure_entry, self.gain_entry, self.framerate_entry]:
            widget.config(state=param_state)
        
        # 模式控制
        mode_state = "normal" if is_connected else "disabled"
        self.continuous_radio.config(state=mode_state)
        self.trigger_radio.config(state=mode_state)
        
        # 串流控制
        self.start_stream_btn.config(state="normal" if is_connected and not is_streaming else "disabled")
        self.stop_stream_btn.config(state="normal" if is_streaming else "disabled")
        
        # 觸發控制
        trigger_state = "normal" if (is_streaming and current_mode == CameraMode.TRIGGER) else "disabled"
        self.software_trigger_btn.config(state=trigger_state)
        
        # 圖像保存
        save_state = "normal" if is_streaming else "disabled"
        self.save_image_btn.config(state=save_state)
    
    def start_status_update(self):
        """啟動狀態更新線程"""
        self.status_running = True
        self.status_update_thread = threading.Thread(target=self.status_update_loop, daemon=True)
        self.status_update_thread.start()
    
    def status_update_loop(self):
        """狀態更新循環"""
        while self.status_running:
            try:
                self.root.after(0, self.update_ui_state)
                time.sleep(0.5)  # 每500ms更新一次
            except:
                break
    
    # ========== 日志和回調方法 ==========
    
    def log_message(self, message: str, level: str = "info"):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        
        # 設置顏色
        colors = {
            "info": "black",
            "success": "green",
            "warning": "orange",
            "error": "red"
        }
        color = colors.get(level, "black")
        
        # 插入消息
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # 設置顏色
        line_start = self.log_text.index(tk.END + "-2c linestart")
        line_end = self.log_text.index(tk.END + "-2c lineend")
        self.log_text.tag_add(level, line_start, line_end)
        self.log_text.tag_config(level, foreground=color)
        
        # 自動滾動到底部
        self.log_text.see(tk.END)
        
        # 限制日志行數
        lines = int(self.log_text.index(tk.END).split('.')[0])
        if lines > 1000:
            self.log_text.delete("1.0", "100.0")
    
    def on_error(self, error_msg: str):
        """錯誤回調函數"""
        self.root.after(0, lambda: self.log_message(error_msg, "error"))
    
    def on_closing(self):
        """關閉程序"""
        try:
            self.status_running = False
            if self.camera_api:
                self.camera_api.disconnect()
            self.root.destroy()
        except:
            self.root.destroy()


def main():
    """主函數"""
    root = tk.Tk()
    app = CameraUI(root)
    
    # 自動刷新設備列表
    root.after(1000, app.refresh_devices)
    
    root.mainloop()


if __name__ == "__main__":
    main()