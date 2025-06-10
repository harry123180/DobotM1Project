import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
import sys
import threading
import time
from datetime import datetime
import numpy as np
from pymodbus.client import ModbusTcpClient

# 添加專案路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dobot_api import DobotApiDashboard, DobotApiMove

class DobotM1Visualizer:
    def __init__(self):
        # 設置CTK主題
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # 創建主窗口
        self.root = ctk.CTk()
        self.root.title("DobotM1 可視化控制工具")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # 初始化變數
        self.dashboard = None
        self.move = None
        self.modbus_client = None
        self.is_connected = False
        self.monitoring = False
        self.sidebar_expanded = True
        
        # 當前位置變數
        self.current_joint = [0, 0, 0, 0]
        self.current_cartesian = [0, 0, 0, 0]
        
        # 設置資料夾路徑
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.points_dir = os.path.join(self.base_dir, "saved_points")
        self.calibration_dir = os.path.join(self.base_dir, "calibration")
        
        # 創建資料夾
        os.makedirs(self.points_dir, exist_ok=True)
        os.makedirs(self.calibration_dir, exist_ok=True)
        
        # 點位列表
        self.saved_points = []
        self.load_points()
        
        # 創建UI
        self.create_ui()
        
        # 載入內外參
        self.load_calibration()
        
        # DI狀態更新定時器
        self.di_update_timer = None
        
    def create_ui(self):
        # 創建主框架
        self.main_frame = ctk.CTkFrame(self.root, fg_color=("gray90", "gray10"))
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 創建側邊欄
        self.create_sidebar()
        
        # 創建內容區域
        self.create_content_area()
        
        # 默認顯示連接頁面
        self.show_connection_page()
        
    def create_sidebar(self):
        # 側邊欄框架
        self.sidebar = ctk.CTkFrame(self.main_frame, width=250, corner_radius=15)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)
        self.sidebar.pack_propagate(False)
        
        # 標題區域
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        self.title_label = ctk.CTkLabel(title_frame, text="DobotM1", 
                                       font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(side="left")
        
        # 收縮按鈕
        self.toggle_btn = ctk.CTkButton(title_frame, text="◀", width=30, height=30,
                                       command=self.toggle_sidebar)
        self.toggle_btn.pack(side="right")
        
        # 導航按鈕
        self.nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.nav_buttons = {}
        nav_items = [
            ("連接", "🔗", self.show_connection_page),
            ("控制/監控", "📊", self.show_control_dashboard_page),
            ("點位管理", "📍", self.show_points_page),
            ("夾爪控制", "🦾", self.show_gripper_page),
            ("視覺檢測", "👁", self.show_vision_page),
            ("IO控制", "🔧", self.show_io_page)
        ]
        
        for i, (text, icon, command) in enumerate(nav_items):
            btn = ctk.CTkButton(self.nav_frame, text=f"{icon} {text}", 
                               height=45, anchor="w", 
                               command=command,
                               fg_color=("gray75", "gray25"),
                               hover_color=("gray65", "gray35"))
            btn.pack(fill="x", pady=5)
            self.nav_buttons[text] = btn
            
    def toggle_sidebar(self):
        if self.sidebar_expanded:
            self.sidebar.configure(width=80)
            self.toggle_btn.configure(text="▶")
            # 隱藏文字，只顯示圖標
            for text, btn in self.nav_buttons.items():
                icon = btn.cget("text").split()[0]
                btn.configure(text=icon)
            self.title_label.configure(text="DM1")
        else:
            self.sidebar.configure(width=250)
            self.toggle_btn.configure(text="◀")
            # 顯示完整文字
            nav_items = [
                ("連接", "🔗"), ("控制/監控", "📊"), 
                ("點位管理", "📍"), ("夾爪控制", "🦾"), ("視覺檢測", "👁"), ("IO控制", "🔧")
            ]
            for (text, icon), btn in zip(nav_items, self.nav_buttons.values()):
                btn.configure(text=f"{icon} {text}")
            self.title_label.configure(text="DobotM1")
        
        self.sidebar_expanded = not self.sidebar_expanded
        
    def create_content_area(self):
        self.content_frame = ctk.CTkFrame(self.main_frame, corner_radius=15)
        self.content_frame.pack(side="right", fill="both", expand=True)
        
    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
            
    def show_connection_page(self):
        self.clear_content()
        self.highlight_nav_button("連接")
        
        # 頁面標題
        title = ctk.CTkLabel(self.content_frame, text="機械臂連接", 
                            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(30, 20))
        
        # 連接設定框架
        settings_frame = ctk.CTkFrame(self.content_frame)
        settings_frame.pack(pady=20, padx=40, fill="x")
        
        # IP設定
        ip_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        ip_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(ip_frame, text="IP地址:", font=ctk.CTkFont(size=16)).pack(side="left")
        self.ip_entry = ctk.CTkEntry(ip_frame, placeholder_text="192.168.1.6", width=200)
        self.ip_entry.pack(side="right")
        self.ip_entry.insert(0, "192.168.1.6")
        
        # 連接狀態
        status_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        status_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(status_frame, text="連接狀態:", font=ctk.CTkFont(size=16)).pack(side="left")
        self.status_label = ctk.CTkLabel(status_frame, text="未連接", 
                                        text_color="red", font=ctk.CTkFont(size=16))
        self.status_label.pack(side="right")
        
        # 連接按鈕
        btn_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        btn_frame.pack(pady=30)
        
        self.connect_btn = ctk.CTkButton(btn_frame, text="連接", width=120, height=40,
                                        font=ctk.CTkFont(size=16),
                                        command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=10)
        
        # Modbus連接檢查
        modbus_frame = ctk.CTkFrame(self.content_frame)
        modbus_frame.pack(pady=20, padx=40, fill="x")
        
        ctk.CTkLabel(modbus_frame, text="模組狀態檢查", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # Gripper狀態
        gripper_frame = ctk.CTkFrame(modbus_frame, fg_color="transparent")
        gripper_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(gripper_frame, text="Gripper模組:", font=ctk.CTkFont(size=14)).pack(side="left")
        self.gripper_status = ctk.CTkLabel(gripper_frame, text="未檢查", 
                                          text_color="orange", font=ctk.CTkFont(size=14))
        self.gripper_status.pack(side="right")
        
        # CCD狀態
        ccd_frame = ctk.CTkFrame(modbus_frame, fg_color="transparent")
        ccd_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(ccd_frame, text="CCD視覺模組:", font=ctk.CTkFont(size=14)).pack(side="left")
        self.ccd_status = ctk.CTkLabel(ccd_frame, text="未檢查", 
                                      text_color="orange", font=ctk.CTkFont(size=14))
        self.ccd_status.pack(side="right")
        
        # 檢查模組按鈕
        check_btn = ctk.CTkButton(modbus_frame, text="檢查模組狀態", 
                                 command=self.check_modules_status)
        check_btn.pack(pady=15)
        
    def show_control_dashboard_page(self):
        """合併JOG控制和監控頁面"""
        self.clear_content()
        self.highlight_nav_button("控制/監控")
        
        # 頁面標題
        title = ctk.CTkLabel(self.content_frame, text="機械臂控制與監控", 
                            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(30, 20))
        
        if not self.is_connected:
            ctk.CTkLabel(self.content_frame, text="請先連接機械臂", 
                        text_color="red", font=ctk.CTkFont(size=18)).pack(expand=True)
            return
            
        # 主容器
        main_container = ctk.CTkFrame(self.content_frame)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 上半部：監控面板
        monitor_frame = ctk.CTkFrame(main_container)
        monitor_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(monitor_frame, text="機械臂狀態監控", 
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        
        # 監控數據區域
        monitor_data_frame = ctk.CTkFrame(monitor_frame)
        monitor_data_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # 左側：關節座標
        left_monitor = ctk.CTkFrame(monitor_data_frame)
        left_monitor.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)
        
        ctk.CTkLabel(left_monitor, text="關節座標 (度)", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.joint_labels = []
        for i in range(4):
            frame = ctk.CTkFrame(left_monitor, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(frame, text=f"J{i+1}:", font=ctk.CTkFont(size=14)).pack(side="left")
            label = ctk.CTkLabel(frame, text="0.00°", font=ctk.CTkFont(size=14, weight="bold"))
            label.pack(side="right")
            self.joint_labels.append(label)
            
        # 右側：笛卡爾座標
        right_monitor = ctk.CTkFrame(monitor_data_frame)
        right_monitor.pack(side="right", fill="both", expand=True, padx=(10, 0), pady=10)
        
        ctk.CTkLabel(right_monitor, text="笛卡爾座標 (mm, 度)", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.cartesian_labels = []
        coords = ["X", "Y", "Z", "R"]
        units = ["mm", "mm", "mm", "°"]
        for i, (coord, unit) in enumerate(zip(coords, units)):
            frame = ctk.CTkFrame(right_monitor, fg_color="transparent")
            frame.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(frame, text=f"{coord}:", font=ctk.CTkFont(size=14)).pack(side="left")
            label = ctk.CTkLabel(frame, text=f"0.00{unit}", font=ctk.CTkFont(size=14, weight="bold"))
            label.pack(side="right")
            self.cartesian_labels.append(label)
        
        # 機械臂狀態
        robot_status_frame = ctk.CTkFrame(monitor_frame)
        robot_status_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.robot_status_label = ctk.CTkLabel(robot_status_frame, text="狀態: 未知", 
                                              font=ctk.CTkFont(size=14))
        self.robot_status_label.pack(pady=10)
        
        # 下半部：JOG控制
        control_frame = ctk.CTkFrame(main_container)
        control_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        
        ctk.CTkLabel(control_frame, text="JOG控制", 
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(15, 10))
        
        # JOG控制區域
        jog_container = ctk.CTkFrame(control_frame)
        jog_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # 左側：關節JOG
        joint_jog_frame = ctk.CTkFrame(jog_container)
        joint_jog_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=15)
        
        ctk.CTkLabel(joint_jog_frame, text="關節座標JOG", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # 關節控制按鈕
        for i in range(4):
            joint_control = ctk.CTkFrame(joint_jog_frame, fg_color="transparent")
            joint_control.pack(fill="x", padx=15, pady=8)
            
            ctk.CTkLabel(joint_control, text=f"J{i+1}:", font=ctk.CTkFont(size=14)).pack(side="left")
            
            btn_frame = ctk.CTkFrame(joint_control, fg_color="transparent")
            btn_frame.pack(side="right")
            
            # 負方向按鈕
            neg_btn = ctk.CTkButton(btn_frame, text="-", width=50, height=35,
                                   command=lambda j=i: self.jog_joint(j, False))
            neg_btn.pack(side="left", padx=3)
            
            # 正方向按鈕
            pos_btn = ctk.CTkButton(btn_frame, text="+", width=50, height=35,
                                   command=lambda j=i: self.jog_joint(j, True))
            pos_btn.pack(side="left", padx=3)
            
        # 右側：笛卡爾JOG
        cart_jog_frame = ctk.CTkFrame(jog_container)
        cart_jog_frame.pack(side="right", fill="both", expand=True, padx=(10, 0), pady=15)
        
        ctk.CTkLabel(cart_jog_frame, text="笛卡爾座標JOG", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # 笛卡爾控制按鈕
        coords = ["X", "Y", "Z", "R"]
        for i, coord in enumerate(coords):
            cart_control = ctk.CTkFrame(cart_jog_frame, fg_color="transparent")
            cart_control.pack(fill="x", padx=15, pady=8)
            
            ctk.CTkLabel(cart_control, text=f"{coord}:", font=ctk.CTkFont(size=14)).pack(side="left")
            
            btn_frame = ctk.CTkFrame(cart_control, fg_color="transparent")
            btn_frame.pack(side="right")
            
            # 負方向按鈕
            neg_btn = ctk.CTkButton(btn_frame, text="-", width=50, height=35,
                                   command=lambda c=coord: self.jog_cartesian(c, False))
            neg_btn.pack(side="left", padx=3)
            
            # 正方向按鈕
            pos_btn = ctk.CTkButton(btn_frame, text="+", width=50, height=35,
                                   command=lambda c=coord: self.jog_cartesian(c, True))
            pos_btn.pack(side="left", padx=3)
            
        # 底部：停止按鈕
        stop_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        stop_frame.pack(pady=10)
        
        stop_btn = ctk.CTkButton(stop_frame, text="停止", width=200, height=50,
                                fg_color="red", hover_color="darkred",
                                font=ctk.CTkFont(size=16, weight="bold"),
                                command=self.stop_jog)
        stop_btn.pack()
        
        # 開始監控
        if not self.monitoring:
            self.start_monitoring()
            
    def show_points_page(self):
        self.clear_content()
        self.highlight_nav_button("點位管理")
        
        # 頁面標題
        title = ctk.CTkLabel(self.content_frame, text="點位管理", 
                            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(30, 20))
        
        # 主框架
        main_frame = ctk.CTkFrame(self.content_frame)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 左側：點位列表
        left_frame = ctk.CTkFrame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)
        
        ctk.CTkLabel(left_frame, text="已保存點位", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # 點位列表框架
        list_frame = ctk.CTkFrame(left_frame)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 滾動框架
        self.points_scrollable = ctk.CTkScrollableFrame(list_frame)
        self.points_scrollable.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.refresh_points_list()
        
        # 右側：點位操作
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="y", padx=(10, 20), pady=20)
        right_frame.configure(width=300)
        right_frame.pack_propagate(False)
        
        ctk.CTkLabel(right_frame, text="點位操作", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # 當前位置顯示
        current_frame = ctk.CTkFrame(right_frame)
        current_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(current_frame, text="當前位置", 
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        self.current_pos_label = ctk.CTkLabel(current_frame, text="未連接", 
                                             font=ctk.CTkFont(size=12))
        self.current_pos_label.pack(pady=5)
        
        # 點位名稱輸入
        name_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        name_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(name_frame, text="點位名稱:", font=ctk.CTkFont(size=14)).pack(anchor="w")
        self.point_name_entry = ctk.CTkEntry(name_frame, placeholder_text="輸入點位名稱")
        self.point_name_entry.pack(fill="x", pady=5)
        
        # 保存當前點位按鈕
        save_btn = ctk.CTkButton(right_frame, text="保存當前點位", 
                                command=self.save_current_point)
        save_btn.pack(fill="x", padx=15, pady=10)
        
        # 導入點位按鈕
        import_btn = ctk.CTkButton(right_frame, text="導入點位檔案", 
                                  command=self.import_points)
        import_btn.pack(fill="x", padx=15, pady=10)
        
        # 導出點位按鈕
        export_btn = ctk.CTkButton(right_frame, text="導出點位檔案", 
                                  command=self.export_points)
        export_btn.pack(fill="x", padx=15, pady=10)
        
    def show_gripper_page(self):
        self.clear_content()
        self.highlight_nav_button("夾爪控制")
        
        # 頁面標題
        title = ctk.CTkLabel(self.content_frame, text="PGC夾爪控制", 
                            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(30, 20))
        
        # 主控制框架
        control_frame = ctk.CTkFrame(self.content_frame)
        control_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 左側：狀態顯示
        status_frame = ctk.CTkFrame(control_frame)
        status_frame.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)
        
        ctk.CTkLabel(status_frame, text="夾爪狀態", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # 連接狀態
        conn_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        conn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(conn_frame, text="連接狀態:", font=ctk.CTkFont(size=14)).pack(side="left")
        self.gripper_conn_label = ctk.CTkLabel(conn_frame, text="未知", 
                                              font=ctk.CTkFont(size=14))
        self.gripper_conn_label.pack(side="right")
        
        # 當前位置
        pos_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        pos_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(pos_frame, text="當前位置:", font=ctk.CTkFont(size=14)).pack(side="left")
        self.gripper_pos_label = ctk.CTkLabel(pos_frame, text="0", 
                                             font=ctk.CTkFont(size=14))
        self.gripper_pos_label.pack(side="right")
        
        # 右側：控制面板
        ctrl_frame = ctk.CTkFrame(control_frame)
        ctrl_frame.pack(side="right", fill="both", expand=True, padx=(10, 20), pady=20)
        
        ctk.CTkLabel(ctrl_frame, text="夾爪控制", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # 力道設定
        force_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        force_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(force_frame, text="力道設定 (20-100):", font=ctk.CTkFont(size=14)).pack(anchor="w")
        self.force_slider = ctk.CTkSlider(force_frame, from_=20, to=100, number_of_steps=80)
        self.force_slider.pack(fill="x", pady=5)
        self.force_slider.set(50)
        
        self.force_value_label = ctk.CTkLabel(force_frame, text="50", font=ctk.CTkFont(size=14))
        self.force_value_label.pack()
        self.force_slider.configure(command=self.update_force_label)
        
        # 位置設定
        pos_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        pos_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(pos_frame, text="位置設定 (0-1000):", font=ctk.CTkFont(size=14)).pack(anchor="w")
        self.position_entry = ctk.CTkEntry(pos_frame, placeholder_text="輸入位置")
        self.position_entry.pack(fill="x", pady=5)
        
        # 開啟位置設定
        open_pos_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        open_pos_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(open_pos_frame, text="開啟位置 (0-1000):", font=ctk.CTkFont(size=14)).pack(anchor="w")
        self.open_position_entry = ctk.CTkEntry(open_pos_frame, placeholder_text="預設開啟位置")
        self.open_position_entry.pack(fill="x", pady=5)
        self.open_position_entry.insert(0, "1000")  # 預設開啟位置
        
        # 關閉位置設定
        close_pos_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        close_pos_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(close_pos_frame, text="關閉位置 (0-1000):", font=ctk.CTkFont(size=14)).pack(anchor="w")
        self.close_position_entry = ctk.CTkEntry(close_pos_frame, placeholder_text="預設關閉位置")
        self.close_position_entry.pack(fill="x", pady=5)
        self.close_position_entry.insert(0, "0")  # 預設關閉位置
        
        # 控制按鈕
        btn_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        # 初始化按鈕
        init_btn = ctk.CTkButton(btn_frame, text="初始化", 
                                command=self.gripper_initialize)
        init_btn.pack(fill="x", pady=5)
        
        # 移動到位置按鈕
        move_btn = ctk.CTkButton(btn_frame, text="移動到位置", 
                                command=self.gripper_move_to_position)
        move_btn.pack(fill="x", pady=5)
        
        # 快速控制按鈕
        quick_frame = ctk.CTkFrame(btn_frame, fg_color="transparent")
        quick_frame.pack(fill="x", pady=10)
        
        open_btn = ctk.CTkButton(quick_frame, text="開啟", 
                                command=self.gripper_open)
        open_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        close_btn = ctk.CTkButton(quick_frame, text="關閉", 
                                 command=self.gripper_close)
        close_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
    def show_vision_page(self):
        self.clear_content()
        self.highlight_nav_button("視覺檢測")
        
        # 頁面標題
        title = ctk.CTkLabel(self.content_frame, text="視覺檢測", 
                            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(30, 20))
        
        # 主框架
        main_frame = ctk.CTkFrame(self.content_frame)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 上方：控制區域
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        # 內外參狀態
        calib_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        calib_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(calib_frame, text="內外參狀態:", font=ctk.CTkFont(size=14)).pack(side="left")
        self.calib_status_label = ctk.CTkLabel(calib_frame, text="未載入", 
                                              text_color="orange", font=ctk.CTkFont(size=14))
        self.calib_status_label.pack(side="right")
        
        # 按鈕區域
        btn_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)
        
        load_calib_btn = ctk.CTkButton(btn_frame, text="載入內外參", 
                                      command=self.load_calibration_file)
        load_calib_btn.pack(side="left", padx=10)
        
        detect_btn = ctk.CTkButton(btn_frame, text="開始視覺檢測", 
                                  command=self.start_vision_detection)
        detect_btn.pack(side="right", padx=10)
        
        # 下方：結果顯示
        result_frame = ctk.CTkFrame(main_frame)
        result_frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        
        ctk.CTkLabel(result_frame, text="檢測結果", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # 結果列表
        self.result_scrollable = ctk.CTkScrollableFrame(result_frame)
        self.result_scrollable.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 初始提示
        ctk.CTkLabel(self.result_scrollable, text="尚未進行檢測", 
                    text_color="gray", font=ctk.CTkFont(size=14)).pack(pady=50)
        
    def show_io_page(self):
        self.clear_content()
        self.highlight_nav_button("IO控制")
        
        # 頁面標題
        title = ctk.CTkLabel(self.content_frame, text="IO控制", 
                            font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=(30, 20))
        
        if not self.is_connected:
            ctk.CTkLabel(self.content_frame, text="請先連接機械臂", 
                        text_color="red", font=ctk.CTkFont(size=18)).pack(expand=True)
            return
        
        # 主框架
        main_frame = ctk.CTkFrame(self.content_frame)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # 左側：DO控制
        do_frame = ctk.CTkFrame(main_frame)
        do_frame.pack(side="left", fill="both", expand=True, padx=(20, 10), pady=20)
        
        ctk.CTkLabel(do_frame, text="數位輸出 (DO)", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # DO控制按鈕 (1-24)
        do_scroll = ctk.CTkScrollableFrame(do_frame)
        do_scroll.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.do_buttons = {}
        for i in range(1, 25):  # DO1-DO24
            do_item = ctk.CTkFrame(do_scroll, fg_color="transparent")
            do_item.pack(fill="x", pady=2)
            
            ctk.CTkLabel(do_item, text=f"DO{i}:", font=ctk.CTkFont(size=12)).pack(side="left")
            
            btn_frame = ctk.CTkFrame(do_item, fg_color="transparent")
            btn_frame.pack(side="right")
            
            on_btn = ctk.CTkButton(btn_frame, text="ON", width=40, height=25,
                                  command=lambda idx=i: self.set_do(idx, True))
            on_btn.pack(side="left", padx=2)
            
            off_btn = ctk.CTkButton(btn_frame, text="OFF", width=40, height=25,
                                   fg_color="gray", hover_color="darkgray",
                                   command=lambda idx=i: self.set_do(idx, False))
            off_btn.pack(side="left", padx=2)
        
        # 右側：DI狀態
        di_frame = ctk.CTkFrame(main_frame)
        di_frame.pack(side="right", fill="both", expand=True, padx=(10, 20), pady=20)
        
        ctk.CTkLabel(di_frame, text="數位輸入 (DI)", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=15)
        
        # DI狀態顯示
        di_scroll = ctk.CTkScrollableFrame(di_frame)
        di_scroll.pack(fill="both", expand=True, padx=15, pady=15)
        
        self.di_labels = {}
        for i in range(1, 25):  # DI1-DI24
            di_item = ctk.CTkFrame(di_scroll, fg_color="transparent")
            di_item.pack(fill="x", pady=2)
            
            ctk.CTkLabel(di_item, text=f"DI{i}:", font=ctk.CTkFont(size=12)).pack(side="left")
            
            status_label = ctk.CTkLabel(di_item, text="LOW", font=ctk.CTkFont(size=12),
                                       text_color="gray")
            status_label.pack(side="right")
            self.di_labels[i] = status_label
            
        # 開始DI狀態更新
        self.start_di_monitoring()
            
    def highlight_nav_button(self, active_text):
        # 重置所有按鈕顏色
        for btn in self.nav_buttons.values():
            btn.configure(fg_color=("gray75", "gray25"))
        
        # 高亮當前按鈕
        if active_text in self.nav_buttons:
            self.nav_buttons[active_text].configure(fg_color=("blue", "blue"))
    
    def toggle_connection(self):
        if not self.is_connected:
            self.connect_robot()
        else:
            self.disconnect_robot()
            
    def connect_robot(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("錯誤", "請輸入IP地址")
            return
            
        try:
            # 連接Dashboard
            self.dashboard = DobotApiDashboard(ip, 29999)
            # 連接Move
            self.move = DobotApiMove(ip, 30003)
            
            # 測試連接
            response = self.dashboard.RobotMode()
            if response and "ErrorID,0" in response:
                self.is_connected = True
                self.status_label.configure(text="已連接", text_color="green")
                self.connect_btn.configure(text="斷開連接")
                
                # 連接Modbus
                self.connect_modbus()
                
                messagebox.showinfo("成功", "機械臂連接成功")
            else:
                raise Exception("連接測試失敗")
                
        except Exception as e:
            messagebox.showerror("連接失敗", f"無法連接到機械臂：{str(e)}")
            self.cleanup_connections()
            
    def disconnect_robot(self):
        self.cleanup_connections()
        self.is_connected = False
        self.monitoring = False
        self.status_label.configure(text="未連接", text_color="red")
        self.connect_btn.configure(text="連接")
        
        # 停止DI監控
        if self.di_update_timer:
            self.root.after_cancel(self.di_update_timer)
            self.di_update_timer = None
            
        messagebox.showinfo("提示", "已斷開連接")
        
    def cleanup_connections(self):
        if self.dashboard:
            self.dashboard.close()
            self.dashboard = None
        if self.move:
            self.move.close()
            self.move = None
        if self.modbus_client:
            self.modbus_client.close()
            self.modbus_client = None
            
    def connect_modbus(self):
        try:
            self.modbus_client = ModbusTcpClient('127.0.0.1', port=502)
            connection_result = self.modbus_client.connect()
            if not connection_result:
                print("Modbus連接失敗")
        except Exception as e:
            print(f"Modbus連接失敗: {e}")
            
    def check_modules_status(self):
        if not self.modbus_client:
            self.connect_modbus()
            
        if self.modbus_client and self.modbus_client.connected:
            # 檢查Gripper模組 (基地址500)
            try:
                result = self.modbus_client.read_holding_registers(500, 1, slave=1)
                if result.isError():
                    self.gripper_status.configure(text="離線", text_color="red")
                else:
                    status = result.registers[0]
                    if status == 1:
                        self.gripper_status.configure(text="在線", text_color="green")
                    else:
                        self.gripper_status.configure(text="異常", text_color="orange")
            except Exception as e:
                print(f"檢查Gripper狀態錯誤: {e}")
                self.gripper_status.configure(text="錯誤", text_color="red")
                
            # 檢查CCD模組 (基地址200)
            try:
                result = self.modbus_client.read_holding_registers(201, 1, slave=1)
                if result.isError():
                    self.ccd_status.configure(text="離線", text_color="red")
                else:
                    status = result.registers[0]
                    if status & 0x1:  # Ready bit
                        self.ccd_status.configure(text="就緒", text_color="green")
                    else:
                        self.ccd_status.configure(text="未就緒", text_color="orange")
            except Exception as e:
                print(f"檢查CCD狀態錯誤: {e}")
                self.ccd_status.configure(text="錯誤", text_color="red")
        else:
            self.gripper_status.configure(text="Modbus未連接", text_color="red")
            self.ccd_status.configure(text="Modbus未連接", text_color="red")
            
    def start_monitoring(self):
        self.monitoring = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()
        
    def monitor_loop(self):
        while self.monitoring and self.is_connected:
            try:
                # 獲取關節角度
                angle_response = self.dashboard.GetAngle()
                if angle_response and "ErrorID,0" in angle_response:
                    # 解析角度數據
                    parts = angle_response.strip().split(',')
                    if len(parts) >= 5:
                        angles = [float(parts[i]) for i in range(1, 5)]
                        self.current_joint = angles
                        
                        # 更新UI
                        self.root.after(0, self.update_joint_display, angles)
                
                # 獲取笛卡爾座標
                pose_response = self.dashboard.GetPose()
                if pose_response and "ErrorID,0" in pose_response:
                    # 解析位置數據
                    parts = pose_response.strip().split(',')
                    if len(parts) >= 5:
                        pose = [float(parts[i]) for i in range(1, 5)]
                        self.current_cartesian = pose
                        
                        # 更新UI
                        self.root.after(0, self.update_cartesian_display, pose)
                
                # 獲取機械臂狀態
                mode_response = self.dashboard.RobotMode()
                if mode_response:
                    self.root.after(0, self.update_robot_status, mode_response)
                    
                time.sleep(0.1)  # 100ms更新間隔
                
            except Exception as e:
                print(f"監控錯誤: {e}")
                time.sleep(1)
                
    def update_joint_display(self, angles):
        for i, angle in enumerate(angles):
            if i < len(self.joint_labels):
                self.joint_labels[i].configure(text=f"{angle:.2f}°")
                
    def update_cartesian_display(self, pose):
        units = ["mm", "mm", "mm", "°"]
        for i, (value, unit) in enumerate(zip(pose, units)):
            if i < len(self.cartesian_labels):
                self.cartesian_labels[i].configure(text=f"{value:.2f}{unit}")
                
    def update_robot_status(self, response):
        # 解析機械臂狀態
        status_map = {
            1: "初始化", 2: "抱閘松開", 3: "未上電", 4: "未使能",
            5: "使能且空閒", 6: "拖拽模式", 7: "運行狀態",
            8: "軌跡錄製", 9: "有未清除報警", 10: "暫停狀態", 11: "點動中"
        }
        
        try:
            parts = response.strip().split(',')
            if len(parts) >= 2:
                mode = int(parts[1])
                status_text = status_map.get(mode, f"未知狀態({mode})")
                self.robot_status_label.configure(text=f"狀態: {status_text}")
        except:
            self.robot_status_label.configure(text="狀態: 解析錯誤")
            
    def jog_joint(self, joint_index, positive):
        if not self.move:
            return
            
        axis_map = [f"J{i+1}+" if positive else f"J{i+1}-" for i in range(4)]
        axis = axis_map[joint_index]
        
        try:
            self.move.MoveJog(axis)
        except Exception as e:
            messagebox.showerror("錯誤", f"關節JOG失敗: {e}")
            
    def jog_cartesian(self, coord, positive):
        if not self.move:
            return
            
        axis = f"{coord}+" if positive else f"{coord}-"
        
        try:
            self.move.MoveJog(axis)
        except Exception as e:
            messagebox.showerror("錯誤", f"笛卡爾JOG失敗: {e}")
            
    def stop_jog(self):
        if not self.move:
            return
            
        try:
            self.move.MoveJog()  # 無參數表示停止
        except Exception as e:
            messagebox.showerror("錯誤", f"停止JOG失敗: {e}")
            
    def save_current_point(self):
        if not self.is_connected:
            messagebox.showerror("錯誤", "請先連接機械臂")
            return
            
        name = self.point_name_entry.get().strip()
        if not name:
            messagebox.showerror("錯誤", "請輸入點位名稱")
            return
            
        # 檢查名稱是否已存在
        if any(point["name"] == name for point in self.saved_points):
            if not messagebox.askyesno("確認", f"點位 '{name}' 已存在，是否覆蓋？"):
                return
            # 移除舊點位
            self.saved_points = [p for p in self.saved_points if p["name"] != name]
            
        # 創建點位數據
        point_data = {
            "name": name,
            "joint": self.current_joint.copy(),
            "cartesian": self.current_cartesian.copy()
        }
        
        self.saved_points.append(point_data)
        self.save_points()
        self.refresh_points_list()
        self.point_name_entry.delete(0, "end")
        
        messagebox.showinfo("成功", f"點位 '{name}' 已保存")
        
    def load_points(self):
        points_file = os.path.join(self.points_dir, "saved_points.json")
        try:
            if os.path.exists(points_file):
                with open(points_file, 'r', encoding='utf-8') as f:
                    self.saved_points = json.load(f)
            else:
                self.saved_points = []
        except Exception as e:
            print(f"載入點位失敗: {e}")
            self.saved_points = []
            
    def save_points(self):
        points_file = os.path.join(self.points_dir, "saved_points.json")
        try:
            with open(points_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_points, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("錯誤", f"保存點位失敗: {e}")
            
    def refresh_points_list(self):
        # 清除現有列表
        for widget in self.points_scrollable.winfo_children():
            widget.destroy()
            
        if not self.saved_points:
            ctk.CTkLabel(self.points_scrollable, text="尚未保存任何點位", 
                        text_color="gray").pack(pady=20)
            return
            
        # 顯示點位列表
        for i, point in enumerate(self.saved_points):
            point_frame = ctk.CTkFrame(self.points_scrollable)
            point_frame.pack(fill="x", padx=5, pady=2)
            
            # 點位資訊
            info_frame = ctk.CTkFrame(point_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            
            # 點位名稱（可編輯）
            name_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            name_frame.pack(fill="x")
            
            name_entry = ctk.CTkEntry(name_frame, width=150)
            name_entry.insert(0, point["name"])
            name_entry.pack(side="left")
            
            update_btn = ctk.CTkButton(name_frame, text="更新", width=60,
                                      command=lambda idx=i, entry=name_entry: self.update_point_name(idx, entry))
            update_btn.pack(side="left", padx=5)
            
            # 座標資訊
            coord_text = f"關節: {[f'{j:.1f}' for j in point['joint']]}\n"
            coord_text += f"笛卡爾: {[f'{c:.1f}' for c in point['cartesian']]}"
            
            coord_label = ctk.CTkLabel(info_frame, text=coord_text, 
                                      font=ctk.CTkFont(size=11), anchor="w")
            coord_label.pack(fill="x", pady=5)
            
            # 操作按鈕
            btn_frame = ctk.CTkFrame(point_frame, fg_color="transparent")
            btn_frame.pack(side="right", padx=10, pady=10)
            
            goto_btn = ctk.CTkButton(btn_frame, text="前往", width=60,
                                    command=lambda idx=i: self.goto_point(idx))
            goto_btn.pack(pady=2)
            
            delete_btn = ctk.CTkButton(btn_frame, text="刪除", width=60,
                                      fg_color="red", hover_color="darkred",
                                      command=lambda idx=i: self.delete_point(idx))
            delete_btn.pack(pady=2)
            
    def update_point_name(self, index, entry):
        new_name = entry.get().strip()
        if not new_name:
            messagebox.showerror("錯誤", "點位名稱不能為空")
            return
            
        # 檢查名稱衝突
        if any(i != index and point["name"] == new_name for i, point in enumerate(self.saved_points)):
            messagebox.showerror("錯誤", "點位名稱已存在")
            return
            
        self.saved_points[index]["name"] = new_name
        self.save_points()
        messagebox.showinfo("成功", "點位名稱已更新")
        
    def goto_point(self, index):
        if not self.move:
            messagebox.showerror("錯誤", "請先連接機械臂")
            return
            
        point = self.saved_points[index]
        
        try:
            # 使用笛卡爾座標移動
            x, y, z, r = point["cartesian"]
            response = self.move.MovJ(x, y, z, r)
            if response and "ErrorID,0" in response:
                messagebox.showinfo("成功", f"正在前往點位 '{point['name']}'")
            else:
                messagebox.showerror("錯誤", "移動指令發送失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"前往點位失敗: {e}")
            
    def delete_point(self, index):
        point = self.saved_points[index]
        if messagebox.askyesno("確認", f"確定要刪除點位 '{point['name']}' 嗎？"):
            self.saved_points.pop(index)
            self.save_points()
            self.refresh_points_list()
            
    def import_points(self):
        file_path = filedialog.askopenfilename(
            title="選擇點位檔案",
            filetypes=[("JSON檔案", "*.json"), ("所有檔案", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_points = json.load(f)
                
                # 驗證格式
                for point in imported_points:
                    if not all(key in point for key in ["name", "joint", "cartesian"]):
                        raise ValueError("點位格式不正確")
                
                # 合併點位
                existing_names = [p["name"] for p in self.saved_points]
                new_points = []
                updated_count = 0
                
                for point in imported_points:
                    if point["name"] in existing_names:
                        if messagebox.askyesno("確認", f"點位 '{point['name']}' 已存在，是否覆蓋？"):
                            # 移除舊點位
                            self.saved_points = [p for p in self.saved_points if p["name"] != point["name"]]
                            new_points.append(point)
                            updated_count += 1
                    else:
                        new_points.append(point)
                
                self.saved_points.extend(new_points)
                self.save_points()
                self.refresh_points_list()
                
                messagebox.showinfo("成功", f"已導入 {len(new_points)} 個點位（更新 {updated_count} 個）")
                
            except Exception as e:
                messagebox.showerror("錯誤", f"導入點位失敗: {e}")
                
    def export_points(self):
        if not self.saved_points:
            messagebox.showwarning("警告", "沒有點位可以導出")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="保存點位檔案",
            defaultextension=".json",
            filetypes=[("JSON檔案", "*.json"), ("所有檔案", "*.*")]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.saved_points, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"已導出 {len(self.saved_points)} 個點位")
            except Exception as e:
                messagebox.showerror("錯誤", f"導出點位失敗: {e}")
                
    def update_force_label(self, value):
        self.force_value_label.configure(text=f"{int(value)}")
        
    def gripper_initialize(self):
        if not self.modbus_client or not self.modbus_client.connected:
            messagebox.showerror("錯誤", "Modbus未連接")
            return
            
        try:
            # PGC夾爪初始化指令 (基地址520, 指令1)
            command_id = int(time.time()) % 65536
            result = self.modbus_client.write_registers(520, [1, 0, 0, command_id], slave=1)
            if not result.isError():
                messagebox.showinfo("成功", "夾爪初始化指令已發送")
            else:
                messagebox.showerror("錯誤", "初始化指令發送失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"夾爪初始化失敗: {e}")
            
    def gripper_move_to_position(self):
        if not self.modbus_client or not self.modbus_client.connected:
            messagebox.showerror("錯誤", "Modbus未連接")
            return
            
        try:
            position_str = self.position_entry.get().strip()
            if not position_str:
                messagebox.showerror("錯誤", "請輸入位置")
                return
                
            position = int(position_str)
            if not 0 <= position <= 1000:
                raise ValueError("位置必須在0-1000範圍內")
                
            # 設定力道
            force = int(self.force_slider.get())
            force_command_id = int(time.time()) % 65536
            self.modbus_client.write_registers(520, [5, force, 0, force_command_id], slave=1)
            time.sleep(0.1)
            
            # 移動到位置指令 (指令3)
            move_command_id = int(time.time()) % 65536
            result = self.modbus_client.write_registers(520, [3, position, 0, move_command_id], slave=1)
            if not result.isError():
                messagebox.showinfo("成功", f"夾爪移動到位置 {position} 指令已發送")
            else:
                messagebox.showerror("錯誤", "移動指令發送失敗")
            
        except ValueError as e:
            messagebox.showerror("錯誤", f"輸入錯誤: {e}")
        except Exception as e:
            messagebox.showerror("錯誤", f"夾爪移動失敗: {e}")
            
    def gripper_open(self):
        if not self.modbus_client or not self.modbus_client.connected:
            messagebox.showerror("錯誤", "Modbus未連接")
            return
            
        try:
            # 獲取開啟位置
            open_pos_str = self.open_position_entry.get().strip()
            if not open_pos_str:
                open_position = 1000  # 預設開啟位置
            else:
                open_position = int(open_pos_str)
                if not 0 <= open_position <= 1000:
                    messagebox.showerror("錯誤", "開啟位置必須在0-1000範圍內")
                    return
            
            # 設定力道
            force = int(self.force_slider.get())
            force_command_id = int(time.time()) % 65536
            self.modbus_client.write_registers(520, [5, force, 0, force_command_id], slave=1)
            time.sleep(0.1)
            
            # 移動到開啟位置
            move_command_id = int(time.time()) % 65536
            result = self.modbus_client.write_registers(520, [3, open_position, 0, move_command_id], slave=1)
            if not result.isError():
                messagebox.showinfo("成功", f"夾爪開啟到位置 {open_position} 指令已發送")
            else:
                messagebox.showerror("錯誤", "開啟指令發送失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"夾爪開啟失敗: {e}")
            
    def gripper_close(self):
        if not self.modbus_client or not self.modbus_client.connected:
            messagebox.showerror("錯誤", "Modbus未連接")
            return
            
        try:
            # 獲取關閉位置
            close_pos_str = self.close_position_entry.get().strip()
            if not close_pos_str:
                close_position = 0  # 預設關閉位置
            else:
                close_position = int(close_pos_str)
                if not 0 <= close_position <= 1000:
                    messagebox.showerror("錯誤", "關閉位置必須在0-1000範圍內")
                    return
            
            # 設定力道
            force = int(self.force_slider.get())
            force_command_id = int(time.time()) % 65536
            self.modbus_client.write_registers(520, [5, force, 0, force_command_id], slave=1)
            time.sleep(0.1)
            
            # 移動到關閉位置
            move_command_id = int(time.time()) % 65536
            result = self.modbus_client.write_registers(520, [3, close_position, 0, move_command_id], slave=1)
            if not result.isError():
                messagebox.showinfo("成功", f"夾爪關閉到位置 {close_position} 指令已發送")
            else:
                messagebox.showerror("錯誤", "關閉指令發送失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"夾爪關閉失敗: {e}")
            
    def load_calibration(self):
        # 檢查內外參檔案
        calib_files = ["camera_matrix.npy", "dist_coeffs.npy", "rvec.npy", "tvec.npy"]
        missing_files = []
        
        for file in calib_files:
            if not os.path.exists(os.path.join(self.calibration_dir, file)):
                missing_files.append(file)
                
        if missing_files:
            print(f"缺少內外參檔案: {missing_files}")
        else:
            print("內外參檔案載入完成")
            
    def load_calibration_file(self):
        dir_path = filedialog.askdirectory(title="選擇內外參資料夾")
        if dir_path:
            try:
                # 複製檔案到calibration目錄
                calib_files = ["camera_matrix.npy", "dist_coeffs.npy", "rvec.npy", "tvec.npy"]
                copied_files = []
                
                for file in calib_files:
                    src = os.path.join(dir_path, file)
                    dst = os.path.join(self.calibration_dir, file)
                    
                    if os.path.exists(src):
                        import shutil
                        shutil.copy2(src, dst)
                        copied_files.append(file)
                
                if copied_files:
                    self.calib_status_label.configure(text="已載入", text_color="green")
                    messagebox.showinfo("成功", f"已載入 {len(copied_files)} 個內外參檔案")
                else:
                    messagebox.showwarning("警告", "未找到任何內外參檔案")
                    
            except Exception as e:
                messagebox.showerror("錯誤", f"載入內外參失敗: {e}")
                
    def start_vision_detection(self):
        if not self.modbus_client or not self.modbus_client.connected:
            messagebox.showerror("錯誤", "Modbus未連接")
            return
            
        try:
            # 發送視覺檢測指令 (基地址200, 指令16)
            result = self.modbus_client.write_register(200, 16, slave=1)
            if not result.isError():
                # 清除結果顯示
                for widget in self.result_scrollable.winfo_children():
                    widget.destroy()
                    
                # 顯示檢測中
                ctk.CTkLabel(self.result_scrollable, text="正在檢測中...", 
                            text_color="blue", font=ctk.CTkFont(size=14)).pack(pady=20)
                
                # 等待檢測結果
                threading.Thread(target=self.wait_vision_result, daemon=True).start()
            else:
                messagebox.showerror("錯誤", "視覺檢測指令發送失敗")
            
        except Exception as e:
            messagebox.showerror("錯誤", f"視覺檢測失敗: {e}")
            
    def wait_vision_result(self):
        """等待視覺檢測結果"""
        try:
            # 等待檢測完成 (最多等待10秒)
            for _ in range(100):
                time.sleep(0.1)
                
                # 檢查狀態寄存器
                result = self.modbus_client.read_holding_registers(201, 1, slave=1)
                if not result.isError():
                    status = result.registers[0]
                    if not (status & 0x2):  # Running bit為0表示完成
                        break
            
            # 讀取檢測結果
            result = self.modbus_client.read_holding_registers(240, 16, slave=1)  # 240-255
            if not result.isError():
                registers = result.registers
                circle_count = registers[0]
                
                # 更新UI顯示結果
                self.root.after(0, self.display_vision_results, circle_count, registers[1:])
            else:
                self.root.after(0, self.display_vision_error, "無法讀取檢測結果")
                
        except Exception as e:
            self.root.after(0, self.display_vision_error, str(e))
            
    def display_vision_results(self, circle_count, data):
        """顯示視覺檢測結果"""
        # 清除檢測中提示
        for widget in self.result_scrollable.winfo_children():
            widget.destroy()
            
        if circle_count == 0:
            ctk.CTkLabel(self.result_scrollable, text="未檢測到任何圓形", 
                        text_color="orange", font=ctk.CTkFont(size=14)).pack(pady=20)
            return
            
        # 顯示檢測到的圓形
        ctk.CTkLabel(self.result_scrollable, text=f"檢測到 {circle_count} 個圓形", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        for i in range(min(circle_count, 5)):
            circle_frame = ctk.CTkFrame(self.result_scrollable)
            circle_frame.pack(fill="x", padx=10, pady=5)
            
            # 獲取圓形數據 (每個圓形3個寄存器: X, Y, R)
            idx = i * 3
            pixel_x = data[idx] if idx < len(data) else 0
            pixel_y = data[idx + 1] if idx + 1 < len(data) else 0
            radius = data[idx + 2] if idx + 2 < len(data) else 0
            
            # 顯示像素座標
            info_text = f"圓形 {i+1}: Pixel_X={pixel_x}, Pixel_Y={pixel_y}, Radius={radius}"
            ctk.CTkLabel(circle_frame, text=info_text, 
                        font=ctk.CTkFont(size=12)).pack(pady=5)
            
            # 如果有內外參，顯示世界座標
            world_coords = self.pixel_to_world(pixel_x, pixel_y)
            if world_coords:
                world_text = f"世界座標: X={world_coords[0]:.2f}mm, Y={world_coords[1]:.2f}mm"
                ctk.CTkLabel(circle_frame, text=world_text, 
                            font=ctk.CTkFont(size=12), text_color="blue").pack()
                
    def display_vision_error(self, error_msg):
        """顯示視覺檢測錯誤"""
        for widget in self.result_scrollable.winfo_children():
            widget.destroy()
            
        ctk.CTkLabel(self.result_scrollable, text=f"檢測失敗: {error_msg}", 
                    text_color="red", font=ctk.CTkFont(size=14)).pack(pady=20)
                    
    def pixel_to_world(self, pixel_x, pixel_y):
        """像素座標轉世界座標"""
        try:
            # 載入內外參
            calib_dir = self.calibration_dir
            camera_matrix = np.load(os.path.join(calib_dir, "camera_matrix.npy"))
            dist_coeffs = np.load(os.path.join(calib_dir, "dist_coeffs.npy"))
            rvec = np.load(os.path.join(calib_dir, "rvec.npy"))
            tvec = np.load(os.path.join(calib_dir, "tvec.npy"))
            
            # 這裡應該進行實際的座標轉換
            # 目前先返回示例數據
            world_x = pixel_x * 0.1  # 示例轉換係數
            world_y = pixel_y * 0.1
            
            return [world_x, world_y]
            
        except Exception as e:
            print(f"座標轉換失敗: {e}")
            return None
            
    def set_do(self, index, state):
        """設置數位輸出"""
        if not self.dashboard:
            messagebox.showerror("錯誤", "請先連接機械臂")
            return
            
        try:
            response = self.dashboard.DO(index, 1 if state else 0)
            if response and "ErrorID,0" in response:
                print(f"DO{index} 設置為 {'ON' if state else 'OFF'}")
            else:
                messagebox.showerror("錯誤", f"DO{index} 設置失敗: {response}")
        except Exception as e:
            messagebox.showerror("錯誤", f"DO{index} 設置失敗: {e}")
            
    def start_di_monitoring(self):
        """開始DI狀態監控"""
        if self.is_connected and self.dashboard:
            self.update_di_status()
            
    def update_di_status(self):
        """更新DI狀態顯示"""
        if not self.dashboard or not self.is_connected:
            return
            
        try:
            for i in range(1, 25):
                response = self.dashboard.DI(i)
                if response and "ErrorID,0" in response:
                    # 解析DI狀態
                    parts = response.strip().split(',')
                    if len(parts) >= 2:
                        state = int(parts[1])
                        if i in self.di_labels:
                            if state:
                                self.di_labels[i].configure(text="HIGH", text_color="green")
                            else:
                                self.di_labels[i].configure(text="LOW", text_color="gray")
                else:
                    if i in self.di_labels:
                        self.di_labels[i].configure(text="ERROR", text_color="red")
        except Exception as e:
            print(f"DI狀態更新失敗: {e}")
            
        # 每2秒更新一次DI狀態
        if self.is_connected:
            self.di_update_timer = self.root.after(2000, self.update_di_status)
            
    def run(self):
        """啟動應用程式"""
        # 更新當前位置顯示
        def update_current_position():
            if hasattr(self, 'current_pos_label') and self.is_connected:
                pos_text = f"關節: {[f'{j:.1f}°' for j in self.current_joint]}\n"
                pos_text += f"笛卡爾: {[f'{c:.1f}' for c in self.current_cartesian[:3]]}mm, {self.current_cartesian[3]:.1f}°"
                self.current_pos_label.configure(text=pos_text)
            
            # 1秒後再次更新
            self.root.after(1000, update_current_position)
            
        # 開始更新循環
        self.root.after(1000, update_current_position)
        
        # 啟動主循環
        self.root.mainloop()
        
    def __del__(self):
        """清理資源"""
        self.monitoring = False
        if self.di_update_timer:
            self.root.after_cancel(self.di_update_timer)
        self.cleanup_connections()


def main():
    """主函數"""
    # 檢查依賴
    try:
        import customtkinter
        import pymodbus
    except ImportError as e:
        print(f"缺少依賴模組: {e}")
        print("請安裝: pip install customtkinter pymodbus")
        return
        
    # 創建並運行應用
    app = DobotM1Visualizer()
    app.run()


if __name__ == "__main__":
    main()
