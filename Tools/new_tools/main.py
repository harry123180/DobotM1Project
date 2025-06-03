# -*- coding: utf-8 -*-
"""
整合相機標定工具 - Integrated Camera Calibration Tool
包含相機拍照、內參校正、外參計算三大功能模組
"""

import customtkinter as ctk
import cv2
import numpy as np
import os
import glob
import json
import threading
import time
from datetime import datetime
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import pandas as pd
from typing import Optional, List

# 導入相機控制相關模組
try:
    from Camera_API import (
        CameraAPI, CameraInfo, CameraMode, ImageFormat, 
        CameraStatus, CameraParameters, create_camera_api
    )
    CAMERA_AVAILABLE = True
except ImportError:
    print("警告: 無法導入相機模組，相機功能將不可用")
    CAMERA_AVAILABLE = False

# 設定CustomTkinter主題
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class IntegratedCameraCalibrationTool:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("整合相機標定工具 - Integrated Camera Calibration Tool")
        self.root.geometry("1600x1000")
        
        # 初始化相機API
        if CAMERA_AVAILABLE:
            self.camera_api = create_camera_api()
            self.camera_api.set_error_callback(self.on_camera_error)
        else:
            self.camera_api = None
            
        # 相機狀態變數
        self.devices = []
        self.current_device_name = ""
        self.save_directory = ""
        self.capture_count = 0
        
        # 內參校正變數
        self.checkerboard_width = ctk.IntVar(value=17)
        self.checkerboard_height = ctk.IntVar(value=12)
        self.square_size = ctk.DoubleVar(value=1.0)
        self.criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        self.image_paths = []
        self.processed_images = {}
        self.camera_matrix = None
        self.dist_coeffs = None
        self.reprojection_error = None
        self.current_image_index = 0
        
        # 外參計算變數
        self.K = np.array([
            [5527.91522, 0.0, 1249.56097],
            [0.0, 5523.37409, 997.41524],
            [0.0, 0.0, 1.0]
        ])
        self.D = np.array([-0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681])
        self.rvec = np.array([[-2.17796294], [-2.24565035], [0.02621215]])
        self.tvec = np.array([[330.20053861], [48.63793437], [533.5402696]])
        self.point_data = []
        self.transformed_points = np.array([])
        
        # 建立介面
        self.setup_ui()
        
        # 啟動狀態更新
        if CAMERA_AVAILABLE:
            self.start_status_update()
        
        # 視窗關閉事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        """建立主介面"""
        # 主容器
        main_container = ctk.CTkFrame(self.root)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 建立選項卡檢視
        self.tabview = ctk.CTkTabview(main_container)
        self.tabview.pack(fill="both", expand=True)
        
        # 加入三個主要選項卡
        self.camera_tab = self.tabview.add("相機拍照")
        self.intrinsic_tab = self.tabview.add("內參校正")
        self.extrinsic_tab = self.tabview.add("外參計算")
        
        # 設定各個選項卡
        self.setup_camera_tab()
        self.setup_intrinsic_tab()
        self.setup_extrinsic_tab()
    
    def setup_camera_tab(self):
        """設定相機拍照選項卡"""
        if not CAMERA_AVAILABLE:
            warning_label = ctk.CTkLabel(
                self.camera_tab, 
                text="相機模組不可用\n請確保已正確安裝海康威視SDK和相關驅動程式",
                font=ctk.CTkFont(size=16)
            )
            warning_label.pack(expand=True, fill="both")
            return
            
        # 左側控制面板
        left_frame = ctk.CTkFrame(self.camera_tab)
        left_frame.pack(side="left", fill="y", padx=(0, 10), pady=10)
        
        # 右側預覽面板
        right_frame = ctk.CTkFrame(self.camera_tab)
        right_frame.pack(side="right", fill="both", expand=True, pady=10)
        
        # === 左側控制面板內容 ===
        
        # 裝置選擇區域
        device_frame = ctk.CTkFrame(left_frame)
        device_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(device_frame, text="裝置管理", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 裝置清單
        self.device_combo = ctk.CTkComboBox(device_frame, state="readonly", width=300)
        self.device_combo.pack(padx=10, pady=5)
        
        # 裝置操作按鈕
        device_btn_frame = ctk.CTkFrame(device_frame)
        device_btn_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(device_btn_frame, text="重新整理裝置", command=self.refresh_devices).pack(side="left", padx=5)
        ctk.CTkButton(device_btn_frame, text="連線", command=self.connect_camera).pack(side="left", padx=5)
        ctk.CTkButton(device_btn_frame, text="中斷連線", command=self.disconnect_camera).pack(side="left", padx=5)
        
        # 裝置命名
        name_frame = ctk.CTkFrame(device_frame)
        name_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(name_frame, text="裝置名稱:").pack(side="left", padx=5)
        self.device_name_entry = ctk.CTkEntry(name_frame, width=200)
        self.device_name_entry.pack(side="left", padx=5)
        ctk.CTkButton(name_frame, text="儲存", command=self.save_device_name).pack(side="left", padx=5)
        
        # 模式選擇區域
        mode_frame = ctk.CTkFrame(left_frame)
        mode_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(mode_frame, text="工作模式", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        self.camera_mode = ctk.StringVar(value="continuous")
        
        ctk.CTkRadioButton(mode_frame, text="串流模式", variable=self.camera_mode, 
                          value="continuous", command=self.set_camera_mode).pack(anchor="w", padx=10, pady=2)
        ctk.CTkRadioButton(mode_frame, text="觸發模式", variable=self.camera_mode, 
                          value="trigger", command=self.set_camera_mode).pack(anchor="w", padx=10, pady=2)
        
        # 串流控制區域
        stream_frame = ctk.CTkFrame(left_frame)
        stream_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(stream_frame, text="串流控制", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        self.start_stream_btn = ctk.CTkButton(stream_frame, text="開始串流", command=self.start_streaming)
        self.start_stream_btn.pack(fill="x", padx=10, pady=2)
        
        self.stop_stream_btn = ctk.CTkButton(stream_frame, text="停止串流", command=self.stop_streaming)
        self.stop_stream_btn.pack(fill="x", padx=10, pady=2)
        
        # 拍照控制區域
        capture_frame = ctk.CTkFrame(left_frame)
        capture_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(capture_frame, text="拍照控制", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        self.capture_btn = ctk.CTkButton(capture_frame, text="拍照", command=self.capture_image)
        self.capture_btn.pack(fill="x", padx=10, pady=2)
        
        self.set_save_dir_btn = ctk.CTkButton(capture_frame, text="設定儲存目錄", command=self.set_save_directory)
        self.set_save_dir_btn.pack(fill="x", padx=10, pady=2)
        
        # 儲存目錄顯示
        self.save_dir_label = ctk.CTkLabel(capture_frame, text="未設定儲存目錄", wraplength=280)
        self.save_dir_label.pack(padx=10, pady=5)
        
        # 狀態顯示區域
        status_frame = ctk.CTkFrame(left_frame)
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(status_frame, text="狀態資訊", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 連線狀態
        self.connection_status_label = ctk.CTkLabel(status_frame, text="連線狀態: 未連線", 
                                                   text_color="red")
        self.connection_status_label.pack(anchor="w", padx=10, pady=2)
        
        # 掉包狀態
        self.packet_loss_label = ctk.CTkLabel(status_frame, text="掉包狀態: 正常")
        self.packet_loss_label.pack(anchor="w", padx=10, pady=2)
        
        # 拍照計數
        self.capture_count_label = ctk.CTkLabel(status_frame, text="已拍照: 0 張")
        self.capture_count_label.pack(anchor="w", padx=10, pady=2)
        
        # === 右側預覽面板內容 ===
        ctk.CTkLabel(right_frame, text="相機預覽", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # 預覽區域
        self.preview_frame = ctk.CTkFrame(right_frame)
        self.preview_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="請連接相機並開始串流")
        self.preview_label.pack(expand=True, fill="both")
    
    def setup_intrinsic_tab(self):
        """設定內參校正選項卡"""
        # 左側控制面板
        left_frame = ctk.CTkFrame(self.intrinsic_tab)
        left_frame.pack(side="left", fill="y", padx=(0, 10), pady=10)
        
        # 右側顯示面板
        right_frame = ctk.CTkFrame(self.intrinsic_tab)
        right_frame.pack(side="right", fill="both", expand=True, pady=10)
        
        # === 左側控制面板內容 ===
        
        # 棋盤格參數設定
        chess_frame = ctk.CTkFrame(left_frame)
        chess_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(chess_frame, text="棋盤格參數", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 寬度
        width_frame = ctk.CTkFrame(chess_frame)
        width_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(width_frame, text="寬度(格數):").pack(side="left")
        width_entry = ctk.CTkEntry(width_frame, textvariable=self.checkerboard_width, width=80)
        width_entry.pack(side="right", padx=5)
        
        # 高度
        height_frame = ctk.CTkFrame(chess_frame)
        height_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(height_frame, text="高度(格數):").pack(side="left")
        height_entry = ctk.CTkEntry(height_frame, textvariable=self.checkerboard_height, width=80)
        height_entry.pack(side="right", padx=5)
        
        # 格子大小
        size_frame = ctk.CTkFrame(chess_frame)
        size_frame.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(size_frame, text="格子大小(cm):").pack(side="left")
        size_entry = ctk.CTkEntry(size_frame, textvariable=self.square_size, width=80)
        size_entry.pack(side="right", padx=5)
        
        # 影像管理
        image_frame = ctk.CTkFrame(left_frame)
        image_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(image_frame, text="影像管理", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        ctk.CTkButton(image_frame, text="匯入圖片", command=self.import_images).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(image_frame, text="清除所有", command=self.clear_images).pack(fill="x", padx=10, pady=2)
        
        # 影像清單
        self.image_listbox = ctk.CTkScrollableFrame(image_frame, height=200)
        self.image_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 影像導覽
        nav_frame = ctk.CTkFrame(image_frame)
        nav_frame.pack(fill="x", padx=10, pady=5)
        
        self.prev_btn = ctk.CTkButton(nav_frame, text="上一張", command=self.prev_image, width=70)
        self.prev_btn.pack(side="left", padx=2)
        
        self.next_btn = ctk.CTkButton(nav_frame, text="下一張", command=self.next_image, width=70)
        self.next_btn.pack(side="right", padx=2)
        
        self.image_info_label = ctk.CTkLabel(nav_frame, text="0/0")
        self.image_info_label.pack()
        
        # 處理控制
        process_frame = ctk.CTkFrame(left_frame)
        process_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(process_frame, text="處理控制", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        ctk.CTkButton(process_frame, text="檢測角點", command=self.detect_corners).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(process_frame, text="計算內參", command=self.calibrate_camera).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(process_frame, text="匯出內參", command=self.export_intrinsic).pack(fill="x", padx=10, pady=2)
        
        # 結果顯示
        result_frame = ctk.CTkFrame(left_frame)
        result_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(result_frame, text="標定結果", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        self.intrinsic_result_text = ctk.CTkTextbox(result_frame, height=150)
        self.intrinsic_result_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # === 右側顯示面板內容 ===
        ctk.CTkLabel(right_frame, text="影像顯示", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # 影像顯示區域
        self.intrinsic_display_frame = ctk.CTkFrame(right_frame)
        self.intrinsic_display_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.intrinsic_display_label = ctk.CTkLabel(self.intrinsic_display_frame, text="請匯入標定影像")
        self.intrinsic_display_label.pack(expand=True, fill="both")
    
    def setup_extrinsic_tab(self):
        """設定外參計算選項卡"""
        # 左側控制面板
        left_frame = ctk.CTkFrame(self.extrinsic_tab)
        left_frame.pack(side="left", fill="y", padx=(0, 10), pady=10)
        
        # 右側可視化面板
        right_frame = ctk.CTkFrame(self.extrinsic_tab)
        right_frame.pack(side="right", fill="both", expand=True, pady=10)
        
        # === 左側控制面板內容 ===
        
        # 內參匯入
        intrinsic_frame = ctk.CTkFrame(left_frame)
        intrinsic_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(intrinsic_frame, text="內參匯入", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        ctk.CTkButton(intrinsic_frame, text="匯入相機內參", command=self.import_camera_matrix).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(intrinsic_frame, text="匯入畸變係數", command=self.import_distortion).pack(fill="x", padx=10, pady=2)
        
        # 點位資料
        points_frame = ctk.CTkFrame(left_frame)
        points_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(points_frame, text="點位資料", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        # 新增點位
        add_point_frame = ctk.CTkFrame(points_frame)
        add_point_frame.pack(fill="x", padx=10, pady=5)
        
        # 創建網格佈局
        ctk.CTkLabel(add_point_frame, text="ID:").grid(row=0, column=0, padx=2, sticky="w")
        self.point_id_entry = ctk.CTkEntry(add_point_frame, width=50)
        self.point_id_entry.grid(row=0, column=1, padx=2)
        
        ctk.CTkLabel(add_point_frame, text="影像X:").grid(row=1, column=0, padx=2, sticky="w")
        self.img_x_entry = ctk.CTkEntry(add_point_frame, width=50)
        self.img_x_entry.grid(row=1, column=1, padx=2)
        
        ctk.CTkLabel(add_point_frame, text="影像Y:").grid(row=1, column=2, padx=2, sticky="w")
        self.img_y_entry = ctk.CTkEntry(add_point_frame, width=50)
        self.img_y_entry.grid(row=1, column=3, padx=2)
        
        ctk.CTkLabel(add_point_frame, text="世界X:").grid(row=2, column=0, padx=2, sticky="w")
        self.world_x_entry = ctk.CTkEntry(add_point_frame, width=50)
        self.world_x_entry.grid(row=2, column=1, padx=2)
        
        ctk.CTkLabel(add_point_frame, text="世界Y:").grid(row=2, column=2, padx=2, sticky="w")
        self.world_y_entry = ctk.CTkEntry(add_point_frame, width=50)
        self.world_y_entry.grid(row=2, column=3, padx=2)
        
        point_btn_frame = ctk.CTkFrame(points_frame)
        point_btn_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(point_btn_frame, text="新增點位", command=self.add_point).pack(side="left", padx=5)
        ctk.CTkButton(point_btn_frame, text="清除所有", command=self.clear_points).pack(side="left", padx=5)
        ctk.CTkButton(point_btn_frame, text="匯入CSV", command=self.import_points_csv).pack(side="left", padx=5)
        
        # 點位清單
        self.points_listbox = ctk.CTkScrollableFrame(points_frame, height=150)
        self.points_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 外參控制
        extrinsic_control_frame = ctk.CTkFrame(left_frame)
        extrinsic_control_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(extrinsic_control_frame, text="外參計算", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        ctk.CTkButton(extrinsic_control_frame, text="計算外參", command=self.calculate_extrinsic).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(extrinsic_control_frame, text="匯出外參", command=self.export_extrinsic).pack(fill="x", padx=10, pady=2)
        
        # === 右側可視化面板內容 ===
        ctk.CTkLabel(right_frame, text="座標轉換可視化", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # 建立matplotlib圖形
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # 建立畫布
        self.canvas = FigureCanvasTkAgg(self.fig, right_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        
        # 誤差資訊
        self.error_info_label = ctk.CTkLabel(right_frame, text="轉換誤差資訊將在此顯示")
        self.error_info_label.pack(pady=5)
        
        # 初始化空圖表
        self.plot_empty()
    
    # ==================== 相機拍照功能 ====================
    
    def refresh_devices(self):
        """重新整理裝置清單"""
        if not self.camera_api:
            return
            
        try:
            self.devices = self.camera_api.enumerate_devices()
            device_names = [str(device) for device in self.devices]
            
            if device_names:
                self.device_combo.configure(values=device_names)
                self.device_combo.set(device_names[0])
                self.log_message(f"找到 {len(self.devices)} 個裝置")
            else:
                self.device_combo.configure(values=["未找到裝置"])
                self.device_combo.set("未找到裝置")
                self.log_message("未找到可用裝置")
        except Exception as e:
            self.log_message(f"重新整理裝置失敗: {str(e)}")
    
    def connect_camera(self):
        """連接相機"""
        if not self.camera_api or not self.devices:
            messagebox.showwarning("警告", "請先重新整理裝置清單")
            return
            
        try:
            # 獲取目前選中的裝置名稱
            selected_device = self.device_combo.get()
            if not selected_device or selected_device == "未找到裝置":
                messagebox.showwarning("警告", "請選擇一個裝置")
                return
            
            # 找到對應的裝置索引
            device_index = -1
            for i, device in enumerate(self.devices):
                if str(device) == selected_device:
                    device_index = i
                    break
            
            if device_index < 0:
                messagebox.showwarning("警告", "無法找到選中的裝置")
                return
                
            if self.camera_api.connect(device_index):
                # 設定包大小為200
                self.camera_api.set_packet_size(200)
                
                device = self.devices[device_index]
                self.current_device_name = device.device_name
                self.device_name_entry.delete(0, "end")
                self.device_name_entry.insert(0, self.current_device_name)
                
                self.connection_status_label.configure(text="連線狀態: 已連線", text_color="green")
                self.log_message(f"相機連線成功: {device.device_name}")
            else:
                self.log_message("相機連線失敗")
        except Exception as e:
            self.log_message(f"連接相機錯誤: {str(e)}")
    
    def disconnect_camera(self):
        """中斷相機連線"""
        if not self.camera_api:
            return
            
        try:
            if self.camera_api.disconnect():
                self.connection_status_label.configure(text="連線狀態: 未連線", text_color="red")
                self.log_message("相機已中斷連線")
            else:
                self.log_message("中斷相機連線失敗")
        except Exception as e:
            self.log_message(f"中斷相機連線錯誤: {str(e)}")
    
    def save_device_name(self):
        """儲存裝置名稱"""
        self.current_device_name = self.device_name_entry.get()
        self.log_message(f"裝置名稱已儲存: {self.current_device_name}")
    
    def set_camera_mode(self):
        """設定相機模式"""
        if not self.camera_api or not self.camera_api.is_connected():
            return
            
        try:
            mode_str = self.camera_mode.get()
            mode = CameraMode.CONTINUOUS if mode_str == "continuous" else CameraMode.TRIGGER
            
            if self.camera_api.set_mode(mode):
                self.log_message(f"模式切換成功: {'連續模式' if mode == CameraMode.CONTINUOUS else '觸發模式'}")
            else:
                self.log_message("模式切換失敗")
        except Exception as e:
            self.log_message(f"設定模式錯誤: {str(e)}")
    
    def start_streaming(self):
        """開始串流"""
        if not self.camera_api or not self.camera_api.is_connected():
            messagebox.showwarning("警告", "請先連接相機")
            return
            
        try:
            if self.camera_api.start_streaming():
                self.log_message("串流啟動成功")
            else:
                self.log_message("串流啟動失敗")
        except Exception as e:
            self.log_message(f"啟動串流錯誤: {str(e)}")
    
    def stop_streaming(self):
        """停止串流"""
        if not self.camera_api:
            return
            
        try:
            if self.camera_api.stop_streaming():
                self.log_message("串流已停止")
            else:
                self.log_message("停止串流失敗")
        except Exception as e:
            self.log_message(f"停止串流錯誤: {str(e)}")
    
    def capture_image(self):
        """拍照"""
        if not self.camera_api or not self.camera_api.is_streaming():
            messagebox.showwarning("警告", "請先開始串流")
            return
            
        if not self.save_directory:
            self.set_save_directory()
            if not self.save_directory:
                return
                
        try:
            if self.camera_api.save_image(ImageFormat.BMP):
                self.capture_count += 1
                self.capture_count_label.configure(text=f"已拍照: {self.capture_count} 張")
                self.log_message(f"影像儲存成功 - 第 {self.capture_count} 張")
            else:
                self.log_message("影像儲存失敗")
        except Exception as e:
            self.log_message(f"拍照錯誤: {str(e)}")
    
    def set_save_directory(self):
        """設定儲存目錄"""
        directory = filedialog.askdirectory(title="選擇影像儲存目錄")
        if directory:
            self.save_directory = directory
            self.save_dir_label.configure(text=f"儲存目錄: {directory}")
            self.log_message(f"儲存目錄已設定: {directory}")
    
    def start_status_update(self):
        """啟動狀態更新"""
        def update_loop():
            while True:
                try:
                    if self.camera_api and self.camera_api.is_connected():
                        # 更新連線狀態
                        status = self.camera_api.get_status()
                        if status == CameraStatus.STREAMING:
                            self.connection_status_label.configure(text="連線狀態: 串流中", text_color="blue")
                        elif status == CameraStatus.CONNECTED:
                            self.connection_status_label.configure(text="連線狀態: 已連線", text_color="green")
                    
                    time.sleep(1)
                except:
                    break
        
        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
    
    # ==================== 內參校正功能 ====================
    
    def import_images(self):
        """匯入圖片"""
        filetypes = [
            ("影像檔案", "*.jpg *.jpeg *.png *.bmp"),
            ("JPEG檔案", "*.jpg *.jpeg"),
            ("PNG檔案", "*.png"),
            ("BMP檔案", "*.bmp"),
            ("所有檔案", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="選擇標定影像",
            filetypes=filetypes
        )
        
        if files:
            self.image_paths.extend(files)
            self.update_image_list()
            self.update_navigation()
    
    def clear_images(self):
        """清除所有圖片"""
        self.image_paths.clear()
        self.processed_images.clear()
        self.current_image_index = 0
        self.update_image_list()
        self.update_navigation()
        self.intrinsic_display_label.configure(image=None, text="請匯入標定影像")
    
    def update_image_list(self):
        """更新圖片清單"""
        # 清除現有清單
        for widget in self.image_listbox.winfo_children():
            widget.destroy()
        
        # 加入影像項目
        for i, path in enumerate(self.image_paths):
            filename = os.path.basename(path)
            
            # 確定狀態
            if path in self.processed_images:
                if self.processed_images[path]["success"]:
                    status = "✓ 已檢測到角點"
                    color = "green"
                else:
                    status = "✗ 未檢測到角點"
                    color = "red"
            else:
                status = "○ 尚未處理"
                color = "gray"
            
            item_frame = ctk.CTkFrame(self.image_listbox)
            item_frame.pack(fill="x", pady=1)
            
            label = ctk.CTkLabel(item_frame, text=f"{status} {filename}", text_color=color)
            label.pack(side="left", padx=5)
            
            view_btn = ctk.CTkButton(item_frame, text="檢視", width=50,
                                   command=lambda idx=i: self.view_image(idx))
            view_btn.pack(side="right", padx=5)
    
    def update_navigation(self):
        """更新導覽"""
        total = len(self.image_paths)
        current = self.current_image_index + 1 if total > 0 else 0
        self.image_info_label.configure(text=f"{current}/{total}")
        
        self.prev_btn.configure(state="normal" if self.current_image_index > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.current_image_index < total - 1 else "disabled")
    
    def prev_image(self):
        """上一張圖片"""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.view_current_image()
            self.update_navigation()
    
    def next_image(self):
        """下一張圖片"""
        if self.current_image_index < len(self.image_paths) - 1:
            self.current_image_index += 1
            self.view_current_image()
            self.update_navigation()
    
    def view_image(self, index):
        """檢視指定圖片"""
        self.current_image_index = index
        self.view_current_image()
        self.update_navigation()
    
    def view_current_image(self):
        """檢視目前圖片"""
        if not self.image_paths:
            return
            
        path = self.image_paths[self.current_image_index]
        
        try:
            # 讀取影像
            img = cv2.imread(path)
            if img is None:
                messagebox.showerror("錯誤", f"無法讀取影像: {path}")
                return
            
            # 檢查是否已處理
            if path in self.processed_images:
                corners = self.processed_images[path]["corners"]
                success = self.processed_images[path]["success"]
                
                if success and corners is not None:
                    # 繪製角點
                    checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
                    img_with_corners = cv2.drawChessboardCorners(img.copy(), checkerboard, corners, success)
                    img = img_with_corners
            
            # 顯示影像
            self.display_intrinsic_image(img)
            
        except Exception as e:
            messagebox.showerror("錯誤", f"顯示影像時發生錯誤: {str(e)}")
    
    def display_intrinsic_image(self, cv_img):
        """顯示內參標定影像"""
        # 轉換為RGB
        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        
        # 調整大小
        height, width = rgb_img.shape[:2]
        max_width, max_height = 800, 600
        
        if width > max_width or height > max_height:
            scale = min(max_width/width, max_height/height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            rgb_img = cv2.resize(rgb_img, (new_width, new_height))
        
        # 轉換為PIL影像
        pil_img = Image.fromarray(rgb_img)
        photo = ImageTk.PhotoImage(pil_img)
        
        # 顯示影像
        self.intrinsic_display_label.configure(image=photo, text="")
        self.intrinsic_display_label.image = photo  # 保持參考
    
    def detect_corners(self):
        """檢測角點"""
        if not self.image_paths:
            messagebox.showwarning("警告", "請先匯入影像")
            return
        
        def detect_corners_thread():
            checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
            total = len(self.image_paths)
            success_count = 0
            
            for i, path in enumerate(self.image_paths):
                try:
                    img = cv2.imread(path)
                    if img is None:
                        continue
                    
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    
                    # 檢測角點
                    ret, corners = cv2.findChessboardCorners(gray, checkerboard, None)
                    
                    if ret and corners.shape[0] == checkerboard[0] * checkerboard[1]:
                        # 精細化角點
                        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), self.criteria)
                        self.processed_images[path] = {"corners": corners2, "success": True}
                        success_count += 1
                    else:
                        self.processed_images[path] = {"corners": None, "success": False}
                        
                except Exception as e:
                    self.processed_images[path] = {"corners": None, "success": False}
            
            # 更新UI
            self.root.after(0, lambda: [
                self.update_image_list(),
                self.log_message(f"角點檢測完成! 成功: {success_count}/{total}")
            ])
        
        # 在新執行緒中執行
        threading.Thread(target=detect_corners_thread, daemon=True).start()
    
    def calibrate_camera(self):
        """計算內參"""
        if not self.processed_images:
            messagebox.showwarning("警告", "請先檢測角點")
            return
        
        # 收集成功的角點資料
        objpoints = []
        imgpoints = []
        
        checkerboard = (self.checkerboard_width.get(), self.checkerboard_height.get())
        square_size_mm = self.square_size.get() * 10  # 轉換為毫米
        
        # 建立世界座標
        objp = np.zeros((checkerboard[0] * checkerboard[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:checkerboard[0], 0:checkerboard[1]].T.reshape(-1, 2)
        objp *= square_size_mm
        
        for path, data in self.processed_images.items():
            if data["success"] and data["corners"] is not None:
                objpoints.append(objp)
                imgpoints.append(data["corners"])
        
        if len(objpoints) < 3:
            messagebox.showwarning("警告", "至少需要3張成功檢測角點的影像進行標定")
            return
        
        def calibrate_thread():
            try:
                # 取得影像尺寸
                first_image = cv2.imread(self.image_paths[0])
                gray = cv2.cvtColor(first_image, cv2.COLOR_BGR2GRAY)
                image_size = gray.shape[::-1]
                
                # 執行標定
                ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                    objpoints, imgpoints, image_size, None, None
                )
                
                self.camera_matrix = mtx
                self.dist_coeffs = dist
                self.reprojection_error = ret
                
                # 顯示結果
                result_text = f"=== 相機標定結果 ===\n\n"
                result_text += f"使用影像數量: {len(objpoints)}\n"
                result_text += f"重投影誤差: {ret:.4f} 像素\n\n"
                
                result_text += f"相機內參矩陣:\n"
                for row in mtx:
                    result_text += f"  [{row[0]:10.2f} {row[1]:10.2f} {row[2]:10.2f}]\n"
                
                result_text += f"\n畸變係數:\n"
                result_text += f"  {dist.ravel()}\n"
                
                # 更新UI
                self.root.after(0, lambda: [
                    self.intrinsic_result_text.delete("1.0", "end"),
                    self.intrinsic_result_text.insert("1.0", result_text),
                    self.log_message("內參標定完成!")
                ])
                
            except Exception as e:
                self.root.after(0, lambda: [
                    messagebox.showerror("錯誤", f"標定失敗: {str(e)}"),
                    self.log_message(f"標定失敗: {str(e)}")
                ])
        
        # 在新執行緒中執行
        threading.Thread(target=calibrate_thread, daemon=True).start()
    
    def export_intrinsic(self):
        """匯出內參"""
        if self.camera_matrix is None:
            messagebox.showwarning("警告", "請先執行相機標定")
            return
        
        save_dir = filedialog.askdirectory(title="選擇儲存目錄")
        if not save_dir:
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 儲存numpy格式
            np.save(os.path.join(save_dir, f"camera_matrix_{timestamp}.npy"), self.camera_matrix)
            np.save(os.path.join(save_dir, f"dist_coeffs_{timestamp}.npy"), self.dist_coeffs)
            
            # 儲存JSON格式
            calib_data = {
                "camera_matrix": self.camera_matrix.tolist(),
                "distortion_coefficients": self.dist_coeffs.tolist(),
                "reprojection_error": float(self.reprojection_error),
                "checkerboard_size": [self.checkerboard_width.get(), self.checkerboard_height.get()],
                "square_size_cm": self.square_size.get(),
                "timestamp": timestamp,
                "num_images": len([d for d in self.processed_images.values() if d["success"]])
            }
            
            with open(os.path.join(save_dir, f"calibration_data_{timestamp}.json"), 'w') as f:
                json.dump(calib_data, f, indent=2)
            
            messagebox.showinfo("成功", f"標定結果已儲存到:\n{save_dir}")
            self.log_message(f"內參已匯出到: {save_dir}")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗: {str(e)}")
    
    # ==================== 外參計算功能 ====================
    
    def import_camera_matrix(self):
        """匯入相機內參"""
        file_path = filedialog.askopenfilename(
            title="選擇相機內參檔案",
            filetypes=[("NPY檔案", "*.npy"), ("JSON檔案", "*.json"), ("所有檔案", "*.*")]
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    self.K = np.array(data['camera_matrix'])
                else:
                    self.K = np.load(file_path)
                
                if self.K.shape == (3, 3):
                    self.log_message("相機內參匯入成功")
                    self.calculate_transformation()
                else:
                    messagebox.showerror("錯誤", "內參矩陣格式不正確")
            except Exception as e:
                messagebox.showerror("錯誤", f"匯入失敗: {str(e)}")
    
    def import_distortion(self):
        """匯入畸變係數"""
        file_path = filedialog.askopenfilename(
            title="選擇畸變係數檔案",
            filetypes=[("NPY檔案", "*.npy"), ("JSON檔案", "*.json"), ("所有檔案", "*.*")]
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    self.D = np.array(data['distortion_coefficients'])
                else:
                    D = np.load(file_path)
                    if D.shape == (1, 5):
                        D = D.ravel()
                    elif D.shape == (5,):
                        pass
                    elif D.shape == (5, 1):
                        D = D.ravel()
                    self.D = D
                
                self.log_message("畸變係數匯入成功")
                self.calculate_transformation()
            except Exception as e:
                messagebox.showerror("錯誤", f"匯入失敗: {str(e)}")
    
    def add_point(self):
        """新增點位"""
        try:
            point_id = int(self.point_id_entry.get())
            img_x = float(self.img_x_entry.get())
            img_y = float(self.img_y_entry.get())
            world_x = float(self.world_x_entry.get())
            world_y = float(self.world_y_entry.get())
            
            # 檢查ID是否已存在
            if any(p[0] == point_id for p in self.point_data):
                messagebox.showwarning("警告", f"點位ID {point_id} 已存在!")
                return
            
            self.point_data.append([point_id, img_x, img_y, world_x, world_y])
            self.update_points_display()
            self.calculate_transformation()
            
            # 清空輸入框
            for entry in [self.point_id_entry, self.img_x_entry, self.img_y_entry, 
                         self.world_x_entry, self.world_y_entry]:
                entry.delete(0, "end")
            
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數值!")
    
    def clear_points(self):
        """清除所有點位"""
        if messagebox.askyesno("確認", "確定要清除所有點位資料嗎?"):
            self.point_data.clear()
            self.update_points_display()
            self.calculate_transformation()
    
    def import_points_csv(self):
        """匯入CSV點位資料"""
        file_path = filedialog.askopenfilename(
            title="選擇CSV檔案",
            filetypes=[("CSV檔案", "*.csv"), ("所有檔案", "*.*")]
        )
        
        if file_path:
            try:
                df = pd.read_csv(file_path)
                
                # 嘗試不同的欄位名稱格式
                possible_columns = [
                    ['id', 'image_x', 'image_y', 'world_x', 'world_y'],
                    ['ID', 'img_x', 'img_y', 'world_x', 'world_y'],
                    ['point_id', 'pixel_x', 'pixel_y', 'real_x', 'real_y']
                ]
                
                columns_found = None
                for cols in possible_columns:
                    if all(col in df.columns for col in cols):
                        columns_found = cols
                        break
                
                if columns_found:
                    for _, row in df.iterrows():
                        point_id = int(row[columns_found[0]])
                        if not any(p[0] == point_id for p in self.point_data):
                            self.point_data.append([
                                point_id,
                                float(row[columns_found[1]]),
                                float(row[columns_found[2]]),
                                float(row[columns_found[3]]),
                                float(row[columns_found[4]])
                            ])
                    
                    self.update_points_display()
                    self.calculate_transformation()
                    messagebox.showinfo("成功", f"成功匯入 {len(df)} 個點位!")
                else:
                    messagebox.showerror("錯誤", "CSV檔案格式不正確!")
                    
            except Exception as e:
                messagebox.showerror("錯誤", f"匯入失敗: {str(e)}")
    
    def update_points_display(self):
        """更新點位顯示"""
        # 清除現有顯示
        for widget in self.points_listbox.winfo_children():
            widget.destroy()
        
        # 顯示表頭
        header_frame = ctk.CTkFrame(self.points_listbox)
        header_frame.pack(fill="x", pady=1)
        
        headers = ["ID", "影像X", "影像Y", "世界X", "世界Y", "操作"]
        for header in headers:
            ctk.CTkLabel(header_frame, text=header, width=60, 
                        font=ctk.CTkFont(weight="bold")).pack(side="left", padx=2)
        
        # 顯示每個點位
        for point in sorted(self.point_data, key=lambda x: x[0]):
            point_frame = ctk.CTkFrame(self.points_listbox)
            point_frame.pack(fill="x", pady=1)
            
            # 顯示資料
            for i, value in enumerate(point[:5]):
                if i == 0:  # ID
                    text = str(value)
                else:  # 座標值
                    text = f"{value:.1f}"
                ctk.CTkLabel(point_frame, text=text, width=60).pack(side="left", padx=2)
            
            # 刪除按鈕
            ctk.CTkButton(point_frame, text="刪除", width=60,
                         command=lambda pid=point[0]: self.delete_point(pid)).pack(side="left", padx=2)
    
    def delete_point(self, point_id):
        """刪除指定點位"""
        self.point_data = [p for p in self.point_data if p[0] != point_id]
        self.update_points_display()
        self.calculate_transformation()
    
    def calculate_extrinsic(self):
        """計算外參"""
        if len(self.point_data) < 4:
            messagebox.showwarning("警告", "至少需要4個點位進行外參估算!")
            return
        
        try:
            # 準備資料
            object_points = np.array([[p[3], p[4], 0.0] for p in self.point_data], dtype=np.float32)
            image_points = np.array([[p[1], p[2]] for p in self.point_data], dtype=np.float32)
            
            # 執行PnP求解
            success, rvec_est, tvec_est = cv2.solvePnP(
                object_points, image_points, self.K, self.D, flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            if success:
                self.rvec = rvec_est
                self.tvec = tvec_est
                
                self.calculate_transformation()
                self.log_message("外參計算成功!")
                messagebox.showinfo("成功", "外參計算完成!")
            else:
                messagebox.showerror("錯誤", "外參計算失敗!")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"計算過程發生錯誤: {str(e)}")
    
    def calculate_transformation(self):
        """計算座標轉換並更新可視化"""
        if len(self.point_data) == 0:
            self.plot_empty()
            return
        
        try:
            # 取得影像座標
            image_coords = np.array([[p[1], p[2]] for p in self.point_data], dtype=np.float32)
            world_coords = np.array([[p[3], p[4], 0.0] for p in self.point_data], dtype=np.float32)
            
            # 計算旋轉矩陣
            R, _ = cv2.Rodrigues(self.rvec)
            
            # 計算反投影世界座標
            transformed_points = []
            for uv in image_coords:
                # 去畸變
                undistorted_uv = cv2.undistortPoints(
                    uv.reshape(1, 1, 2), self.K, self.D, P=self.K).reshape(-1)
                
                # 轉換到相機座標系
                uv_hom = np.array([undistorted_uv[0], undistorted_uv[1], 1.0])
                cam_coords = np.linalg.inv(self.K) @ uv_hom
                
                # 計算Z=0平面上的點
                s = (0 - self.tvec[2, 0]) / (R[2] @ cam_coords)
                XYZ_cam = s * cam_coords
                
                # 轉換到世界座標系
                world_point = np.linalg.inv(R) @ (XYZ_cam - self.tvec.ravel())
                transformed_points.append(world_point[:2])
            
            self.transformed_points = np.array(transformed_points)
            
            # 計算誤差
            errors = []
            for i in range(len(self.transformed_points)):
                error = np.linalg.norm(world_coords[i, :2] - self.transformed_points[i])
                errors.append(error)
            
            # 更新可視化
            self.plot_results(world_coords, errors)
            
        except Exception as e:
            print(f"計算錯誤: {e}")
            self.plot_empty()
    
    def plot_results(self, world_coords, errors):
        """繪製結果"""
        self.ax.clear()
        
        if len(self.point_data) == 0:
            self.ax.text(0.5, 0.5, '請新增點位資料', ha='center', va='center', transform=self.ax.transAxes)
            self.canvas.draw()
            return
        
        # 建立顏色映射
        n_points = len(self.point_data)
        colors = plt.cm.viridis(np.linspace(0, 1, n_points))
        
        # 繪製真實世界座標
        self.ax.scatter(world_coords[:, 0], world_coords[:, 1],
                       c=colors, s=100, marker='s', edgecolor='black', alpha=0.8,
                       label='真實世界座標')
        
        # 繪製轉換後座標
        self.ax.scatter(self.transformed_points[:, 0], self.transformed_points[:, 1],
                       c=colors, s=100, marker='^', edgecolor='black', alpha=0.8,
                       label='轉換後座標')
        
        # 繪製誤差線
        for i in range(len(self.transformed_points)):
            self.ax.plot([world_coords[i, 0], self.transformed_points[i, 0]],
                        [world_coords[i, 1], self.transformed_points[i, 1]], 
                        'r--', alpha=0.6, linewidth=1)
        
        # 加入點位標籤
        for i, point in enumerate(self.point_data):
            point_id = point[0]
            
            # 世界座標標籤
            self.ax.annotate(f'W{point_id}', 
                           (world_coords[i, 0], world_coords[i, 1]),
                           xytext=(5, 5), textcoords='offset points', fontsize=8, color='blue')
            
            # 轉換座標標籤
            self.ax.annotate(f'T{point_id}', 
                           (self.transformed_points[i, 0], self.transformed_points[i, 1]),
                           xytext=(5, 5), textcoords='offset points', fontsize=8, color='orange')
        
        self.ax.set_title('座標轉換結果對比', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        self.ax.axis('equal')
        
        # 更新誤差資訊
        if errors:
            mean_error = np.mean(errors)
            max_error = np.max(errors)
            min_error = np.min(errors)
            std_error = np.std(errors)
            error_text = f"平均誤差: {mean_error:.2f}mm | 最大誤差: {max_error:.2f}mm | 最小誤差: {min_error:.2f}mm | 標準差: {std_error:.2f}mm"
            self.error_info_label.configure(text=error_text)
        else:
            self.error_info_label.configure(text="無誤差資料")
        
        self.canvas.draw()
    
    def plot_empty(self):
        """繪製空白圖表"""
        self.ax.clear()
        self.ax.text(0.5, 0.5, '請新增點位資料\n或檢查參數設定', 
                    ha='center', va='center', transform=self.ax.transAxes,
                    fontsize=12)
        self.ax.set_title('座標轉換結果對比')
        self.canvas.draw()
        self.error_info_label.configure(text="")
    
    def export_extrinsic(self):
        """匯出外參"""
        file_path = filedialog.asksaveasfilename(
            title="儲存外參",
            defaultextension=".json",
            filetypes=[("JSON檔案", "*.json"), ("NPY檔案", "*.npy"), ("所有檔案", "*.*")]
        )
        
        if file_path:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if file_path.endswith('.json'):
                    # JSON格式
                    extrinsic_data = {
                        "rotation_vector": self.rvec.tolist(),
                        "translation_vector": self.tvec.tolist(),
                        "camera_matrix": self.K.tolist(),
                        "distortion_coefficients": self.D.tolist(),
                        "point_data": self.point_data,
                        "timestamp": timestamp
                    }
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(extrinsic_data, f, indent=4, ensure_ascii=False)
                else:
                    # NPY格式
                    extrinsic_data = {
                        'rvec': self.rvec,
                        'tvec': self.tvec,
                        'camera_matrix': self.K,
                        'distortion_coefficients': self.D,
                        'timestamp': timestamp
                    }
                    np.save(file_path, extrinsic_data)
                
                messagebox.showinfo("成功", "外參匯出成功!")
                self.log_message(f"外參已匯出到: {file_path}")
                
            except Exception as e:
                messagebox.showerror("錯誤", f"匯出失敗: {str(e)}")
    
    # ==================== 通用功能 ====================
    
    def log_message(self, message):
        """記錄日誌訊息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def on_camera_error(self, error_msg):
        """相機錯誤回調"""
        self.log_message(f"相機錯誤: {error_msg}")
    
    def on_closing(self):
        """關閉程式"""
        try:
            if self.camera_api:
                self.camera_api.disconnect()
            self.root.destroy()
        except:
            self.root.destroy()
    
    def run(self):
        """執行應用程式"""
        # 初始化時重新整理裝置
        if CAMERA_AVAILABLE:
            self.root.after(1000, self.refresh_devices)
        
        self.root.mainloop()


def main():
    """主函式"""
    try:
        # 設定matplotlib中文字型
        plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'DejaVu Sans', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
    except:
        pass
    
    # 建立並執行應用程式
    app = IntegratedCameraCalibrationTool()
    app.run()


if __name__ == "__main__":
    main()