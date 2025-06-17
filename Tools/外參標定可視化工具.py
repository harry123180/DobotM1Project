import customtkinter as ctk
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import tkinter as tk
from tkinter import filedialog, messagebox
import json
import pandas as pd
from datetime import datetime

class CameraCalibrationTool:
    def __init__(self):
        # 設置 CustomTkinter 主題
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        # 初始化主窗口
        self.root = ctk.CTk()
        self.root.title("Camera Calibration Adjuster")
        self.root.geometry("1600x1000")
        
        # 設置中文字體
        try:
            # 嘗試設置系統中文字體
            import platform
            system = platform.system()
            if system == "Darwin":  # macOS
                self.font_family = "PingFang SC"
            elif system == "Windows":
                self.font_family = "Microsoft YaHei"
            else:  # Linux
                self.font_family = "DejaVu Sans"
                
            # 設置matplotlib中文字體
            plt.rcParams['font.sans-serif'] = [self.font_family, 'SimHei', 'Arial Unicode MS']
            plt.rcParams['axes.unicode_minus'] = False  # 解決負號顯示問題
        except:
            self.font_family = "Arial"
        
        # 初始化數據
        self.init_default_data()
        
        # 可視化控制變量
        self.show_image_coords = tk.BooleanVar(value=False)
        self.show_world_coords = tk.BooleanVar(value=True)
        self.show_transformed_coords = tk.BooleanVar(value=True)
        self.show_error_lines = tk.BooleanVar(value=True)
        
        # 創建界面
        self.create_widgets()
        
        # 初始計算和顯示
        self.calculate_transformation()
        
    def init_default_data(self):
        """初始化默認數據"""
        # 默認內參矩陣
        self.K = np.array([
            [5527.91522, 0.0, 1249.56097],
            [0.0, 5523.37409, 997.41524],
            [0.0, 0.0, 1.0]
        ])
        
        # 默認畸變參數
        self.D = np.array([-0.06833483, 0.00056340, 0.00137019, 0.00055740, 4.80949681])
        
        # 默認外參
        self.rvec = np.array([[-2.17796294], [-2.24565035], [0.02621215]])
        self.tvec = np.array([[330.20053861], [48.63793437], [533.5402696]])
        
        # 點位數據
        self.image_coords = np.array([])
        self.world_coords = np.array([])
        self.point_data = []  # 存儲點位數據 [id, image_x, image_y, world_x, world_y]
        
        # 算法選項
        self.estimation_algorithm = tk.StringVar(value="PnP_ITERATIVE")
        
    def create_widgets(self):
        """創建主界面"""
        # 主框架
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 左側控制面板
        left_panel = ctk.CTkFrame(main_frame, width=450)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # 右側可視化面板
        right_panel = ctk.CTkFrame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True)
        
        self.create_control_panel(left_panel)
        self.create_visualization_panel(right_panel)
        
    def create_control_panel(self, parent):
        """創建控制面板"""
        # 標題
        title = ctk.CTkLabel(parent, text="相機參數調整", 
                           font=ctk.CTkFont(family=self.font_family, size=20, weight="bold"))
        title.pack(pady=(10, 20))
        
        # 創建分頁按鈕框架
        tab_frame = ctk.CTkFrame(parent)
        tab_frame.pack(fill="x", padx=10, pady=5)
        
        # 分頁按鈕
        self.tab_buttons = {}
        self.current_tab = "intrinsic"
        
        tab_names = {
            "intrinsic": "內參",
            "extrinsic": "外參", 
            "points": "點位",
            "algorithm": "算法",
            "file": "文件",
            "view": "顯示",
            "help": "說明"
        }
        
        for i, (tab_id, tab_text) in enumerate(tab_names.items()):
            btn = ctk.CTkButton(
                tab_frame, 
                text=tab_text, 
                width=60,
                font=ctk.CTkFont(family=self.font_family, size=11),
                command=lambda tid=tab_id: self.switch_tab(tid)
            )
            btn.grid(row=0, column=i, padx=1, sticky="ew")
            self.tab_buttons[tab_id] = btn
            tab_frame.grid_columnconfigure(i, weight=1)
        
        # 內容框架
        self.content_frame = ctk.CTkScrollableFrame(parent)
        self.content_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 創建所有分頁內容
        self.create_all_tab_contents()
        
        # 顯示默認分頁
        self.switch_tab("intrinsic")
        
    def create_all_tab_contents(self):
        """創建所有分頁內容"""
        # 內參調整內容
        self.intrinsic_content = ctk.CTkFrame(self.content_frame)
        self.create_intrinsic_controls(self.intrinsic_content)
        
        # 外參調整內容
        self.extrinsic_content = ctk.CTkFrame(self.content_frame)
        self.create_extrinsic_controls(self.extrinsic_content)
        
        # 點位數據內容
        self.points_content = ctk.CTkFrame(self.content_frame)
        self.create_points_controls(self.points_content)
        
        # 算法選擇內容
        self.algorithm_content = ctk.CTkFrame(self.content_frame)
        self.create_algorithm_controls(self.algorithm_content)
        
        # 文件操作內容
        self.file_content = ctk.CTkFrame(self.content_frame)
        self.create_file_controls(self.file_content)
        
        # 顯示控制內容
        self.view_content = ctk.CTkFrame(self.content_frame)
        self.create_view_controls(self.view_content)
        
        # 說明頁面內容
        self.help_content = ctk.CTkFrame(self.content_frame)
        self.create_help_controls(self.help_content)
        
        # 存儲所有分頁內容
        self.tab_contents = {
            "intrinsic": self.intrinsic_content,
            "extrinsic": self.extrinsic_content,
            "points": self.points_content,
            "algorithm": self.algorithm_content,
            "file": self.file_content,
            "view": self.view_content,
            "help": self.help_content
        }
    
    def switch_tab(self, tab_id):
        """切換分頁"""
        # 隱藏所有分頁內容
        for content in self.tab_contents.values():
            content.pack_forget()
        
        # 顯示選中的分頁內容
        self.tab_contents[tab_id].pack(fill="both", expand=True, padx=5, pady=5)
        
        # 更新按鈕樣式
        for btn_id, btn in self.tab_buttons.items():
            if btn_id == tab_id:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color=("gray84", "gray25"))
        
        self.current_tab = tab_id
        
    def create_intrinsic_controls(self, parent):
        """創建內參控制面板"""
        # 內參矩陣輸入
        ctk.CTkLabel(parent, text="內參矩陣 K:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(10, 5))
        
        self.intrinsic_entries = {}
        intrinsic_labels = [
            ["fx", "skew", "cx"],
            ["0", "fy", "cy"],
            ["0", "0", "1"]
        ]
        
        for i in range(3):
            row_frame = ctk.CTkFrame(parent)
            row_frame.pack(fill="x", pady=2)
            for j in range(3):
                if intrinsic_labels[i][j] in ["0", "1"]:
                    label = ctk.CTkLabel(row_frame, text=intrinsic_labels[i][j], width=80,
                                       font=ctk.CTkFont(family=self.font_family))
                    label.pack(side="left", padx=2)
                else:
                    entry = ctk.CTkEntry(row_frame, width=80, 
                                       font=ctk.CTkFont(family=self.font_family))
                    entry.pack(side="left", padx=2)
                    entry.insert(0, str(self.K[i, j]))
                    entry.bind("<KeyRelease>", self.on_parameter_change)
                    self.intrinsic_entries[f"K_{i}_{j}"] = entry
        
        # 畸變參數
        ctk.CTkLabel(parent, text="畸變參數 D:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(20, 5))
        
        self.distortion_entries = {}
        distortion_labels = ["k1", "k2", "p1", "p2", "k3"]
        
        for i, label in enumerate(distortion_labels):
            row_frame = ctk.CTkFrame(parent)
            row_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row_frame, text=f"{label}:", width=30,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=2)
            entry = ctk.CTkEntry(row_frame, width=120,
                               font=ctk.CTkFont(family=self.font_family))
            entry.pack(side="left", padx=2)
            entry.insert(0, str(self.D[i]))
            entry.bind("<KeyRelease>", self.on_parameter_change)
            self.distortion_entries[f"D_{i}"] = entry
            
        # 導入內參按鈕
        import_intrinsic_frame = ctk.CTkFrame(parent)
        import_intrinsic_frame.pack(fill="x", pady=20)
        
        ctk.CTkButton(import_intrinsic_frame, text="導入相機內參(.npy)", 
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.import_intrinsic_npy).pack(side="left", padx=5)
        ctk.CTkButton(import_intrinsic_frame, text="導入畸變係數(.npy)",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.import_distortion_npy).pack(side="left", padx=5)
            
    def create_extrinsic_controls(self, parent):
        """創建外參控制面板"""
        # 旋轉向量
        ctk.CTkLabel(parent, text="旋轉向量 rvec:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(10, 5))
        
        self.rvec_entries = {}
        rvec_labels = ["rx", "ry", "rz"]
        
        for i, label in enumerate(rvec_labels):
            row_frame = ctk.CTkFrame(parent)
            row_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row_frame, text=f"{label}:", width=30,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=2)
            entry = ctk.CTkEntry(row_frame, width=120,
                               font=ctk.CTkFont(family=self.font_family))
            entry.pack(side="left", padx=2)
            entry.insert(0, str(self.rvec[i, 0]))
            entry.bind("<KeyRelease>", self.on_parameter_change)
            self.rvec_entries[f"rvec_{i}"] = entry
            
            # 微調按鈕
            btn_frame = ctk.CTkFrame(row_frame)
            btn_frame.pack(side="right", padx=5)
            
            ctk.CTkButton(btn_frame, text="-", width=30, 
                         font=ctk.CTkFont(family=self.font_family),
                         command=lambda idx=i: self.adjust_rvec(idx, -0.01)).pack(side="left", padx=1)
            ctk.CTkButton(btn_frame, text="+", width=30,
                         font=ctk.CTkFont(family=self.font_family),
                         command=lambda idx=i: self.adjust_rvec(idx, 0.01)).pack(side="left", padx=1)
        
        # 平移向量
        ctk.CTkLabel(parent, text="平移向量 tvec:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(20, 5))
        
        self.tvec_entries = {}
        tvec_labels = ["tx", "ty", "tz"]
        
        for i, label in enumerate(tvec_labels):
            row_frame = ctk.CTkFrame(parent)
            row_frame.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row_frame, text=f"{label}:", width=30,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=2)
            entry = ctk.CTkEntry(row_frame, width=120,
                               font=ctk.CTkFont(family=self.font_family))
            entry.pack(side="left", padx=2)
            entry.insert(0, str(self.tvec[i, 0]))
            entry.bind("<KeyRelease>", self.on_parameter_change)
            self.tvec_entries[f"tvec_{i}"] = entry
            
            # 微調按鈕
            btn_frame = ctk.CTkFrame(row_frame)
            btn_frame.pack(side="right", padx=5)
            
            step = 1.0 if i < 2 else 5.0  # x,y用1.0，z用5.0
            ctk.CTkButton(btn_frame, text="-", width=30,
                         font=ctk.CTkFont(family=self.font_family),
                         command=lambda idx=i, s=step: self.adjust_tvec(idx, -s)).pack(side="left", padx=1)
            ctk.CTkButton(btn_frame, text="+", width=30,
                         font=ctk.CTkFont(family=self.font_family),
                         command=lambda idx=i, s=step: self.adjust_tvec(idx, s)).pack(side="left", padx=1)
        
        # 外參操作按鈕
        extrinsic_btn_frame = ctk.CTkFrame(parent)
        extrinsic_btn_frame.pack(fill="x", pady=20)
        
        ctk.CTkButton(extrinsic_btn_frame, text="重置外參", 
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.reset_extrinsic).pack(side="left", padx=5)
        ctk.CTkButton(extrinsic_btn_frame, text="導入外參(.npy)",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.import_extrinsic_npy).pack(side="left", padx=5)
        
        # 新增導出當前外參按鈕
        ctk.CTkButton(extrinsic_btn_frame, text="導出當前外參",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.export_current_extrinsic).pack(side="left", padx=5)
        
    def create_points_controls(self, parent):
        """創建點位數據控制面板"""
        # 添加單個點位
        ctk.CTkLabel(parent, text="添加點位:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(10, 5))
        
        # 點位ID
        id_frame = ctk.CTkFrame(parent)
        id_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(id_frame, text="ID:", width=50,
                    font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=2)
        self.point_id_entry = ctk.CTkEntry(id_frame, width=80,
                                          font=ctk.CTkFont(family=self.font_family))
        self.point_id_entry.pack(side="left", padx=2)
        
        # 圖像座標
        img_frame = ctk.CTkFrame(parent)
        img_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(img_frame, text="圖像座標:", width=80,
                    font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=2)
        self.img_x_entry = ctk.CTkEntry(img_frame, width=60, placeholder_text="x",
                                       font=ctk.CTkFont(family=self.font_family))
        self.img_x_entry.pack(side="left", padx=2)
        self.img_y_entry = ctk.CTkEntry(img_frame, width=60, placeholder_text="y",
                                       font=ctk.CTkFont(family=self.font_family))
        self.img_y_entry.pack(side="left", padx=2)
        
        # 世界座標
        world_frame = ctk.CTkFrame(parent)
        world_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(world_frame, text="世界座標:", width=80,
                    font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=2)
        self.world_x_entry = ctk.CTkEntry(world_frame, width=60, placeholder_text="x",
                                         font=ctk.CTkFont(family=self.font_family))
        self.world_x_entry.pack(side="left", padx=2)
        self.world_y_entry = ctk.CTkEntry(world_frame, width=60, placeholder_text="y",
                                         font=ctk.CTkFont(family=self.font_family))
        self.world_y_entry.pack(side="left", padx=2)
        
        # 添加和清除按鈕
        btn_frame = ctk.CTkFrame(parent)
        btn_frame.pack(fill="x", pady=10)
        ctk.CTkButton(btn_frame, text="添加點位", 
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.add_point).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="清除所有",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.clear_points).pack(side="left", padx=5)
        
        # 點位列表
        ctk.CTkLabel(parent, text="當前點位:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(20, 5))
        
        # 創建表格框架
        table_frame = ctk.CTkFrame(parent)
        table_frame.pack(fill="both", expand=True, pady=5)
        
        # 表格標題
        header_frame = ctk.CTkFrame(table_frame)
        header_frame.pack(fill="x", padx=5, pady=5)
        
        headers = ["ID", "圖像X", "圖像Y", "世界X", "世界Y", "操作"]
        widths = [40, 50, 50, 50, 50, 60]
        
        for header, width in zip(headers, widths):
            ctk.CTkLabel(header_frame, text=header, width=width, 
                        font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(side="left", padx=1)
        
        # 滾動框架用於點位列表
        self.points_scroll_frame = ctk.CTkScrollableFrame(table_frame, height=200)
        self.points_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
    def create_algorithm_controls(self, parent):
        """創建算法選擇控制面板"""
        ctk.CTkLabel(parent, text="外參估算算法:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(10, 5))
        
        # 算法選擇
        algorithm_frame = ctk.CTkFrame(parent)
        algorithm_frame.pack(fill="x", pady=5)
        
        algorithms = [
            ("PnP_ITERATIVE", "PnP迭代法"),
            ("PnP_EPNP", "EPnP算法"),
            ("PnP_P3P", "P3P算法"),
            ("PnP_AP3P", "AP3P算法"),
            ("PnP_IPPE", "IPPE算法"),
            ("PnP_IPPE_SQUARE", "IPPE_SQUARE算法")
        ]
        
        self.algorithm_combo = ctk.CTkComboBox(
            algorithm_frame,
            values=[f"{alg[1]} ({alg[0]})" for alg in algorithms],
            font=ctk.CTkFont(family=self.font_family),
            width=300
        )
        self.algorithm_combo.pack(padx=5, pady=5)
        self.algorithm_combo.set("PnP迭代法 (PnP_ITERATIVE)")
        
        # 算法說明
        algo_desc = ctk.CTkTextbox(parent, height=150, wrap="word",
                                  font=ctk.CTkFont(family=self.font_family, size=11))
        algo_desc.pack(fill="x", pady=10)
        
        algo_text = """
算法說明:

• PnP迭代法: 最常用的方法，通過迭代優化求解，適合大多數情況
• EPnP算法: 效率較高，適用於點數較多的情況  
• P3P算法: 只需3個點，但可能有多解，適合點數少的情況
• AP3P算法: P3P的改進版本，數值穩定性更好
• IPPE算法: 適用於平面物體的姿態估計
• IPPE_SQUARE算法: IPPE的改進版本，適用於正方形標定板

建議：
- 點數>=4時推薦使用PnP迭代法
- 點數較多(>10)時可使用EPnP
- 平面標定時可嘗試IPPE算法
        """
        algo_desc.insert("1.0", algo_text)
        algo_desc.configure(state="disabled")
        
        # 執行按鈕
        execute_frame = ctk.CTkFrame(parent)
        execute_frame.pack(fill="x", pady=20)
        
        ctk.CTkButton(execute_frame, text="計算外參", 
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.estimate_extrinsic).pack(side="left", padx=5)
        ctk.CTkButton(execute_frame, text="導出估算外參",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.export_estimated_extrinsic).pack(side="left", padx=5)
        
        # 結果顯示
        ctk.CTkLabel(parent, text="估算結果:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(20, 5))
        
        self.estimation_result = ctk.CTkTextbox(parent, height=200,
                                               font=ctk.CTkFont(family=self.font_family, size=11))
        self.estimation_result.pack(fill="x", pady=5)
        
    def create_view_controls(self, parent):
        """創建顯示控制面板"""
        ctk.CTkLabel(parent, text="顯示控制:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(10, 5))
        
        # 顯示選項
        view_options = [
            ("show_image_coords", "顯示圖像座標", self.show_image_coords),
            ("show_world_coords", "顯示真實世界座標", self.show_world_coords),
            ("show_transformed_coords", "顯示轉換後座標", self.show_transformed_coords),
            ("show_error_lines", "顯示誤差線", self.show_error_lines)
        ]
        
        for option_id, text, var in view_options:
            checkbox = ctk.CTkCheckBox(
                parent, 
                text=text, 
                variable=var,
                font=ctk.CTkFont(family=self.font_family),
                command=self.update_visualization
            )
            checkbox.pack(anchor="w", pady=5, padx=10)
        
        # 圖表設置
        ctk.CTkLabel(parent, text="圖表設置:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(20, 5))
        
        # 點大小調整
        size_frame = ctk.CTkFrame(parent)
        size_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(size_frame, text="點大小:", font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=5)
        self.point_size_slider = ctk.CTkSlider(size_frame, from_=50, to=200, number_of_steps=15)
        self.point_size_slider.pack(side="right", padx=5, fill="x", expand=True)
        self.point_size_slider.set(100)
        self.point_size_slider.configure(command=self.update_visualization)
        
        # 線寬調整
        width_frame = ctk.CTkFrame(parent)
        width_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(width_frame, text="線寬:", font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=5)
        self.line_width_slider = ctk.CTkSlider(width_frame, from_=0.5, to=3.0, number_of_steps=25)
        self.line_width_slider.pack(side="right", padx=5, fill="x", expand=True)
        self.line_width_slider.set(1.0)
        self.line_width_slider.configure(command=self.update_visualization)
        
        # 刷新按鈕
        ctk.CTkButton(parent, text="刷新圖表", 
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.update_visualization).pack(pady=20)
        
    def create_file_controls(self, parent):
        """創建文件操作控制面板"""
        ctk.CTkLabel(parent, text="文件操作:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(10, 5))
        
        # 導入數據
        import_frame = ctk.CTkFrame(parent)
        import_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(import_frame, text="導入CSV點位", 
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.import_csv).pack(side="left", padx=5)
        ctk.CTkButton(import_frame, text="導入NPY數據",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.import_npy).pack(side="left", padx=5)
        
        # 導出數據
        export_frame = ctk.CTkFrame(parent)
        export_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(export_frame, text="導出參數",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.export_params).pack(side="left", padx=5)
        ctk.CTkButton(export_frame, text="導出點位",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.export_points).pack(side="left", padx=5)
        
        # 批量輸入區域
        ctk.CTkLabel(parent, text="批量輸入 (格式: id,img_x,img_y,world_x,world_y):", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", pady=(20, 5))
        
        self.batch_text = ctk.CTkTextbox(parent, height=150,
                                        font=ctk.CTkFont(family=self.font_family))
        self.batch_text.pack(fill="x", pady=5)
        self.batch_text.insert("1.0", "1,100,200,10.5,20.3\n2,150,250,15.2,25.1\n3,200,300,20.8,30.5")
        
        ctk.CTkButton(parent, text="批量添加點位",
                     font=ctk.CTkFont(family=self.font_family),
                     command=self.batch_add_points).pack(pady=10)
        
    def create_help_controls(self, parent):
        """創建說明頁面"""
        # 創建滾動文本框用於顯示說明
        help_text = ctk.CTkTextbox(parent, height=600, wrap="word",
                                  font=ctk.CTkFont(family="PingFang SC", size=12))
        help_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 插入說明內容
        help_content = """
🎯 相機標定調整工具使用說明

═══════════════════════════════════════════════════════════════

📖 工具概述
────────────────────────────────────────────────────────────────
本工具用於精細調整相機內參和外參矩陣，通過已知的圖像座標點和對應的世界座標點，
實現從相機座標系到世界座標系的精確轉換。特別適用於需要將相機捕獲的二維圖像
座標轉換為三維世界座標的應用場景。

🔧 功能模塊說明
────────────────────────────────────────────────────────────────

📌 1. 內參矩陣 (Intrinsic Matrix)
• fx, fy: 相機焦距（像素單位）
• cx, cy: 主點座標（光軸與像平面交點）
• 畸變係數: k1,k2,k3（徑向畸變），p1,p2（切向畸變）
• 支援導入.npy格式的內參和畸變係數檔案

📌 2. 外參矩陣 (Extrinsic Matrix)
• 旋轉向量 (rvec): 相機座標系相對世界座標系的旋轉
• 平移向量 (tvec): 相機座標系原點在世界座標系中的位置
• 微調按鈕: 點擊 +/- 進行精細調整
• 支援導入算法估算的外參檔案

📌 3. 點位數據 (Point Data)
• 手動添加: 逐個輸入對應點對
• 批量添加: 使用 CSV 格式批量導入
• 格式: id,image_x,image_y,world_x,world_y

📌 4. 算法估算 (Algorithm Estimation)
• 多種PnP算法可選擇
• 自動計算初始外參估值
• 可導出估算結果進行微調

📌 5. 顯示控制 (View Control)
• 可選擇顯示/隱藏不同類型的座標點
• 圖像座標、世界座標、轉換座標獨立控制
• 可調整點大小和線寬

📌 6. 文件操作 (File Operations)
• 導入CSV: 支持多種列名格式
• 導入NPY: 兼容numpy數組格式
• 導出參數: JSON格式保存相機參數
• 導出點位: CSV格式保存點位數據

🧮 數學原理
────────────────────────────────────────────────────────────────

本工具基於針孔相機模型，實現從圖像座標到世界座標的反向投影：

📐 1. 相機模型基礎

內參矩陣 K:
┌                    ┐
│ fx   0   cx        │
│ 0    fy  cy        │  
│ 0    0   1         │
└                    ┘

📐 2. PnP算法原理

PnP (Perspective-n-Point) 問題是計算機視覺中的經典問題，
給定n個3D點和對應的2D投影點，求解相機的姿態（旋轉和平移）。

• PnP_ITERATIVE: 使用Levenberg-Marquardt算法迭代優化
• EPnP: 將問題轉化為線性方程組求解
• P3P: 最少需要3個點，但可能有多解
• AP3P: P3P的改進版本，提高數值穩定性

📐 3. 座標轉換過程

步驟一：圖像座標去畸變
undistorted_uv = undistortPoints(uv, K, D)

步驟二：歸一化座標計算  
[X_norm]   [1 0 0] [u]
[Y_norm] = K⁻¹ × [0 1 0] [v]
[1     ]        [0 0 1] [1]

步驟三：相機座標系計算
由於假設 Z_world = 0（平面假設），可得：
s = -t_z / (R₃ᵀ × [X_norm, Y_norm, 1]ᵀ)

步驟四：世界座標計算
[X_world]       [X_norm]
[Y_world] = R⁻¹([Y_norm] × s - t)
[Z_world]       [1     ]

🎯 操作指南
────────────────────────────────────────────────────────────────

🚀 第一步：準備數據
1. 準備已知的圖像座標點和對應的世界座標點
2. 確保點位數據準確，至少需要4個點位
3. 如有內參標定結果，準備.npy格式的內參檔案

🚀 第二步：導入內參
1. 切換到「內參」頁面
2. 點擊「導入相機內參(.npy)」導入camera_matrix檔案
3. 點擊「導入畸變係數(.npy)」導入dist_coeffs檔案
4. 或手動輸入已知的內參數值

🚀 第三步：輸入點位數據
方法一 - 手動輸入：
• 切換到「點位」頁面
• 在對應欄位輸入點位ID、圖像座標、世界座標
• 點擊「添加點位」

方法二 - 批量輸入：
• 在批量輸入框中按格式輸入：id,img_x,img_y,world_x,world_y
• 每行一個點位
• 點擊「批量添加點位」

🚀 第四步：算法估算外參
1. 切換到「算法」頁面
2. 選擇合適的PnP算法
3. 點擊「計算外參」獲得初始估值
4. 可點擊「導出估算外參」保存結果

🚀 第五步：微調外參
1. 切換到「外參」頁面
2. 可導入剛才估算的外參檔案
3. 使用 +/- 按鈕進行精細調整
4. 觀察右側可視化結果

🚀 第六步：優化顯示
1. 切換到「顯示」頁面
2. 控制顯示/隱藏不同類型的座標點
3. 調整點大小和線寬以獲得最佳視覺效果

⚠️ 注意事項
────────────────────────────────────────────────────────────────
• 本工具假設所有世界座標點都在Z=0平面上
• 點位分布應盡可能均勻覆蓋整個感興趣區域
• 圖像座標和世界座標的對應關係必須準確
• 建議使用高精度的標定點進行測量
• 算法估算後建議進行手動微調

📊 可視化說明
────────────────────────────────────────────────────────────────
• 綠色圓點：圖像座標點（可選顯示）
• 藍色方塊：真實世界座標點
• 橙色三角：經過轉換計算得到的座標點  
• 紅色虛線：兩點間的誤差連線
• 誤差統計：底部顯示轉換精度信息
        """
        
        help_text.insert("1.0", help_content)
        help_text.configure(state="disabled")  # 設為只讀
        
    def create_visualization_panel(self, parent):
        """創建可視化面板"""
        # 創建matplotlib圖形
        self.fig = Figure(figsize=(12, 9), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # 創建畫布
        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        
        # 誤差信息面板
        info_frame = ctk.CTkFrame(parent, height=100)
        info_frame.pack(fill="x", padx=10, pady=(0, 10))
        info_frame.pack_propagate(False)
        
        ctk.CTkLabel(info_frame, text="轉換誤差信息:", 
                    font=ctk.CTkFont(family=self.font_family, weight="bold")).pack(anchor="w", padx=10, pady=5)
        
        self.error_label = ctk.CTkLabel(info_frame, text="", justify="left",
                                       font=ctk.CTkFont(family=self.font_family))
        self.error_label.pack(anchor="w", padx=10, pady=5)
        
    def import_intrinsic_npy(self):
        """導入內參矩陣.npy檔案"""
        file_path = filedialog.askopenfilename(
            title="選擇相機內參檔案 (camera_matrix.npy)",
            filetypes=[("NPY files", "*.npy"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                K = np.load(file_path)
                if K.shape == (3, 3):
                    self.K = K
                    # 更新界面顯示
                    self.intrinsic_entries["K_0_0"].delete(0, "end")
                    self.intrinsic_entries["K_0_0"].insert(0, str(K[0, 0]))
                    self.intrinsic_entries["K_0_2"].delete(0, "end")
                    self.intrinsic_entries["K_0_2"].insert(0, str(K[0, 2]))
                    self.intrinsic_entries["K_1_1"].delete(0, "end")
                    self.intrinsic_entries["K_1_1"].insert(0, str(K[1, 1]))
                    self.intrinsic_entries["K_1_2"].delete(0, "end")
                    self.intrinsic_entries["K_1_2"].insert(0, str(K[1, 2]))
                    
                    self.calculate_transformation()
                    messagebox.showinfo("成功", "內參矩陣導入成功！")
                else:
                    messagebox.showerror("錯誤", "內參矩陣格式不正確，應為3x3矩陣！")
            except Exception as e:
                messagebox.showerror("錯誤", f"導入失敗: {str(e)}")
    
    def import_distortion_npy(self):
        """導入畸變係數.npy檔案"""
        file_path = filedialog.askopenfilename(
            title="選擇畸變係數檔案 (dist_coeffs.npy)",
            filetypes=[("NPY files", "*.npy"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                D = np.load(file_path)
                # 處理不同的畸變係數格式
                if D.shape == (1, 5):
                    D = D.ravel()
                elif D.shape == (5,):
                    pass
                elif D.shape == (5, 1):
                    D = D.ravel()
                else:
                    raise ValueError("畸變係數格式不正確")
                
                self.D = D
                # 更新界面顯示
                for i in range(5):
                    self.distortion_entries[f"D_{i}"].delete(0, "end")
                    self.distortion_entries[f"D_{i}"].insert(0, str(D[i]))
                
                self.calculate_transformation()
                messagebox.showinfo("成功", "畸變係數導入成功！")
            except Exception as e:
                messagebox.showerror("錯誤", f"導入失敗: {str(e)}")
    
    def import_extrinsic_npy(self):
        """導入外參.npy檔案"""
        file_path = filedialog.askopenfilename(
            title="選擇外參檔案 (extrinsic.npy 或包含rvec,tvec的檔案)",
            filetypes=[("NPY files", "*.npy"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                if file_path.endswith('.json'):
                    # JSON格式
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    if 'rotation_vector' in data and 'translation_vector' in data:
                        rvec = np.array(data['rotation_vector'])
                        tvec = np.array(data['translation_vector'])
                    else:
                        raise ValueError("JSON檔案格式不正確")
                else:
                    # NPY格式
                    data = np.load(file_path, allow_pickle=True)
                    
                    if isinstance(data, np.ndarray) and data.shape == ():
                        # 字典格式
                        data = data.item()
                        rvec = data['rvec']
                        tvec = data['tvec']
                    elif isinstance(data, dict):
                        rvec = data['rvec']
                        tvec = data['tvec']
                    else:
                        raise ValueError("NPY檔案格式不正確")
                
                # 確保形狀正確
                if rvec.shape == (3,):
                    rvec = rvec.reshape(3, 1)
                if tvec.shape == (3,):
                    tvec = tvec.reshape(3, 1)
                
                self.rvec = rvec
                self.tvec = tvec
                
                # 更新界面顯示
                for i in range(3):
                    self.rvec_entries[f"rvec_{i}"].delete(0, "end")
                    self.rvec_entries[f"rvec_{i}"].insert(0, str(rvec[i, 0]))
                    self.tvec_entries[f"tvec_{i}"].delete(0, "end")
                    self.tvec_entries[f"tvec_{i}"].insert(0, str(tvec[i, 0]))
                
                self.calculate_transformation()
                messagebox.showinfo("成功", "外參導入成功！")
            except Exception as e:
                messagebox.showerror("錯誤", f"導入失敗: {str(e)}")
    
    def estimate_extrinsic(self):
        """使用選定算法估算外參"""
        if len(self.point_data) < 4:
            messagebox.showwarning("警告", "至少需要4個點位進行外參估算！")
            return
        
        try:
            # 準備數據
            object_points = np.array([[p[3], p[4], 0.0] for p in self.point_data], dtype=np.float32)
            image_points = np.array([[p[1], p[2]] for p in self.point_data], dtype=np.float32)
            
            # 獲取選定的算法
            algo_text = self.algorithm_combo.get()
            if "PnP_ITERATIVE" in algo_text:
                flag = cv2.SOLVEPNP_ITERATIVE
            elif "PnP_EPNP" in algo_text:
                flag = cv2.SOLVEPNP_EPNP
            elif "PnP_P3P" in algo_text:
                flag = cv2.SOLVEPNP_P3P
            elif "PnP_AP3P" in algo_text:
                flag = cv2.SOLVEPNP_AP3P
            elif "PnP_IPPE" in algo_text:
                flag = cv2.SOLVEPNP_IPPE
            elif "PnP_IPPE_SQUARE" in algo_text:
                flag = cv2.SOLVEPNP_IPPE_SQUARE
            else:
                flag = cv2.SOLVEPNP_ITERATIVE
            
            # 執行PnP求解
            success, rvec_est, tvec_est = cv2.solvePnP(
                object_points, image_points, self.K, self.D, flags=flag
            )
            
            if success:
                self.estimated_rvec = rvec_est
                self.estimated_tvec = tvec_est
                
                # 計算重投影誤差
                projected_points, _ = cv2.projectPoints(
                    object_points, rvec_est, tvec_est, self.K, self.D
                )
                projected_points = projected_points.reshape(-1, 2)
                
                errors = []
                for i in range(len(image_points)):
                    error = np.linalg.norm(image_points[i] - projected_points[i])
                    errors.append(error)
                
                mean_error = np.mean(errors)
                max_error = np.max(errors)
                min_error = np.min(errors)
                
                # 顯示結果
                result_text = f"=== {algo_text} 估算結果 ===\n\n"
                result_text += f"旋轉向量 (rvec):\n"
                result_text += f"  rx = {rvec_est[0, 0]:.6f}\n"
                result_text += f"  ry = {rvec_est[1, 0]:.6f}\n"
                result_text += f"  rz = {rvec_est[2, 0]:.6f}\n\n"
                
                result_text += f"平移向量 (tvec):\n"
                result_text += f"  tx = {tvec_est[0, 0]:.6f}\n"
                result_text += f"  ty = {tvec_est[1, 0]:.6f}\n"
                result_text += f"  tz = {tvec_est[2, 0]:.6f}\n\n"
                
                result_text += f"重投影誤差統計:\n"
                result_text += f"  平均誤差: {mean_error:.4f} 像素\n"
                result_text += f"  最大誤差: {max_error:.4f} 像素\n"
                result_text += f"  最小誤差: {min_error:.4f} 像素\n\n"
                
                result_text += f"使用點位數量: {len(object_points)}\n"
                result_text += f"算法類型: {algo_text}\n"
                
                self.estimation_result.delete("1.0", "end")
                self.estimation_result.insert("1.0", result_text)
                
                messagebox.showinfo("成功", f"外參估算完成！\n平均重投影誤差: {mean_error:.4f} 像素")
                
            else:
                messagebox.showerror("錯誤", "外參估算失敗！請檢查點位數據是否正確。")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"估算過程發生錯誤: {str(e)}")
    
    def export_estimated_extrinsic(self):
        """導出估算的外參"""
        if not hasattr(self, 'estimated_rvec') or not hasattr(self, 'estimated_tvec'):
            messagebox.showwarning("警告", "請先執行外參估算！")
            return
        
        # 選擇保存格式
        save_format = messagebox.askyesno("選擇格式", "選擇保存格式:\n是 - NPY格式\n否 - JSON格式")
        
        if save_format:  # NPY格式
            file_path = filedialog.asksaveasfilename(
                title="保存估算外參 (NPY格式)",
                defaultextension=".npy",
                filetypes=[("NPY files", "*.npy"), ("All files", "*.*")]
            )
            
            if file_path:
                try:
                    extrinsic_data = {
                        'rvec': self.estimated_rvec,
                        'tvec': self.estimated_tvec,
                        'algorithm': self.algorithm_combo.get(),
                        'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
                    }
                    np.save(file_path, extrinsic_data)
                    messagebox.showinfo("成功", "估算外參導出成功！(NPY格式)")
                except Exception as e:
                    messagebox.showerror("錯誤", f"導出失敗: {str(e)}")
        else:  # JSON格式
            file_path = filedialog.asksaveasfilename(
                title="保存估算外參 (JSON格式)",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if file_path:
                try:
                    extrinsic_data = {
                        'rotation_vector': self.estimated_rvec.tolist(),
                        'translation_vector': self.estimated_tvec.tolist(),
                        'algorithm': self.algorithm_combo.get(),
                        'timestamp': datetime.now().strftime("%Y%m%d_%H%M%S")
                    }
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(extrinsic_data, f, indent=4, ensure_ascii=False)
                    messagebox.showinfo("成功", "估算外參導出成功！(JSON格式)")
                except Exception as e:
                    messagebox.showerror("錯誤", f"導出失敗: {str(e)}")
    
    def export_current_extrinsic(self):
        """導出當前外參"""
        try:
            # 確保從UI更新當前參數
            self.update_parameters_from_entries()
            
            # 選擇保存格式
            save_format = messagebox.askyesno("選擇格式", "選擇保存格式:\n是 - NPY格式\n否 - JSON格式")
            
            # 生成時間戳記
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if save_format:  # NPY格式
                file_path = filedialog.asksaveasfilename(
                    title="保存當前外參 (NPY格式)",
                    defaultextension=".npy",
                    filetypes=[("NPY files", "*.npy"), ("All files", "*.*")]
                )
                
                if file_path:
                    try:
                        # 如果用戶沒有指定檔名，使用預設檔名
                        if not file_path.endswith('.npy'):
                            file_path = f"extrinsic_{timestamp}.npy"
                        
                        extrinsic_data = {
                            'rvec': self.rvec,
                            'tvec': self.tvec,
                            'algorithm': 'Manual_Adjustment',
                            'timestamp': timestamp
                        }
                        np.save(file_path, extrinsic_data)
                        messagebox.showinfo("成功", "當前外參導出成功！(NPY格式)")
                    except Exception as e:
                        messagebox.showerror("錯誤", f"導出失敗: {str(e)}")
            else:  # JSON格式
                file_path = filedialog.asksaveasfilename(
                    title="保存當前外參 (JSON格式)",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                
                if file_path:
                    try:
                        # 如果用戶沒有指定檔名，使用預設檔名
                        if not file_path.endswith('.json'):
                            file_path = f"extrinsic_{timestamp}.json"
                        
                        extrinsic_data = {
                            'rotation_vector': self.rvec.tolist(),
                            'translation_vector': self.tvec.tolist(),
                            'algorithm': 'Manual_Adjustment',
                            'timestamp': timestamp
                        }
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(extrinsic_data, f, indent=4, ensure_ascii=False)
                        messagebox.showinfo("成功", "當前外參導出成功！(JSON格式)")
                    except Exception as e:
                        messagebox.showerror("錯誤", f"導出失敗: {str(e)}")
                        
        except Exception as e:
            messagebox.showerror("錯誤", f"導出當前外參時發生錯誤: {str(e)}")
    
    def update_visualization(self, *args):
        """更新可視化"""
        self.calculate_transformation()
        
    def add_point(self):
        """添加單個點位"""
        try:
            point_id = int(self.point_id_entry.get())
            img_x = float(self.img_x_entry.get())
            img_y = float(self.img_y_entry.get())
            world_x = float(self.world_x_entry.get())
            world_y = float(self.world_y_entry.get())
            
            # 檢查ID是否已存在
            if any(p[0] == point_id for p in self.point_data):
                messagebox.showwarning("警告", f"點位ID {point_id} 已存在！")
                return
            
            self.point_data.append([point_id, img_x, img_y, world_x, world_y])
            self.update_points_display()
            self.update_coordinate_arrays()
            self.calculate_transformation()
            
            # 清空輸入框
            self.point_id_entry.delete(0, "end")
            self.img_x_entry.delete(0, "end")
            self.img_y_entry.delete(0, "end")
            self.world_x_entry.delete(0, "end")
            self.world_y_entry.delete(0, "end")
            
        except ValueError:
            messagebox.showerror("錯誤", "請輸入有效的數值！")
    
    def batch_add_points(self):
        """批量添加點位"""
        try:
            text_content = self.batch_text.get("1.0", "end-1c")
            lines = text_content.strip().split('\n')
            
            added_count = 0
            for line in lines:
                if line.strip():
                    parts = line.strip().split(',')
                    if len(parts) == 5:
                        point_id = int(parts[0])
                        img_x = float(parts[1])
                        img_y = float(parts[2])
                        world_x = float(parts[3])
                        world_y = float(parts[4])
                        
                        # 檢查ID是否已存在
                        if not any(p[0] == point_id for p in self.point_data):
                            self.point_data.append([point_id, img_x, img_y, world_x, world_y])
                            added_count += 1
            
            if added_count > 0:
                self.update_points_display()
                self.update_coordinate_arrays()
                self.calculate_transformation()
                messagebox.showinfo("成功", f"成功添加 {added_count} 個點位！")
            else:
                messagebox.showwarning("警告", "沒有有效的點位數據被添加！")
                
        except Exception as e:
            messagebox.showerror("錯誤", f"批量添加失敗: {str(e)}")
    
    def clear_points(self):
        """清除所有點位"""
        if messagebox.askyesno("確認", "確定要清除所有點位數據嗎？"):
            self.point_data.clear()
            self.update_points_display()
            self.update_coordinate_arrays()
            self.calculate_transformation()
    
    def delete_point(self, point_id):
        """刪除指定點位"""
        self.point_data = [p for p in self.point_data if p[0] != point_id]
        self.update_points_display()
        self.update_coordinate_arrays()
        self.calculate_transformation()
    
    def update_points_display(self):
        """更新點位顯示"""
        # 清除現有顯示
        for widget in self.points_scroll_frame.winfo_children():
            widget.destroy()
        
        # 顯示每個點位
        for point in sorted(self.point_data, key=lambda x: x[0]):
            point_frame = ctk.CTkFrame(self.points_scroll_frame)
            point_frame.pack(fill="x", pady=1)
            
            # 顯示數據
            ctk.CTkLabel(point_frame, text=str(point[0]), width=40,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=1)
            ctk.CTkLabel(point_frame, text=f"{point[1]:.1f}", width=50,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=1)
            ctk.CTkLabel(point_frame, text=f"{point[2]:.1f}", width=50,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=1)
            ctk.CTkLabel(point_frame, text=f"{point[3]:.1f}", width=50,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=1)
            ctk.CTkLabel(point_frame, text=f"{point[4]:.1f}", width=50,
                        font=ctk.CTkFont(family=self.font_family)).pack(side="left", padx=1)
            
            # 刪除按鈕
            ctk.CTkButton(point_frame, text="刪除", width=60, 
                         font=ctk.CTkFont(family=self.font_family),
                         command=lambda pid=point[0]: self.delete_point(pid)).pack(side="left", padx=1)
    
    def update_coordinate_arrays(self):
        """更新座標數組"""
        if len(self.point_data) > 0:
            sorted_points = sorted(self.point_data, key=lambda x: x[0])
            self.image_coords = np.array([[p[1], p[2]] for p in sorted_points], dtype=np.float32)
            self.world_coords = np.array([[p[3], p[4], 0.0] for p in sorted_points], dtype=np.float32)
        else:
            self.image_coords = np.array([])
            self.world_coords = np.array([])
    
    def adjust_rvec(self, index, delta):
        """微調旋轉向量"""
        current_value = float(self.rvec_entries[f"rvec_{index}"].get())
        new_value = current_value + delta
        self.rvec_entries[f"rvec_{index}"].delete(0, "end")
        self.rvec_entries[f"rvec_{index}"].insert(0, f"{new_value:.6f}")
        self.on_parameter_change()
    
    def adjust_tvec(self, index, delta):
        """微調平移向量"""
        current_value = float(self.tvec_entries[f"tvec_{index}"].get())
        new_value = current_value + delta
        self.tvec_entries[f"tvec_{index}"].delete(0, "end")
        self.tvec_entries[f"tvec_{index}"].insert(0, f"{new_value:.6f}")
        self.on_parameter_change()
    
    def reset_extrinsic(self):
        """重置外參到默認值"""
        default_rvec = np.array([[-2.17796294], [-2.24565035], [0.02621215]])
        default_tvec = np.array([[330.20053861], [48.63793437], [533.5402696]])
        
        for i in range(3):
            self.rvec_entries[f"rvec_{i}"].delete(0, "end")
            self.rvec_entries[f"rvec_{i}"].insert(0, str(default_rvec[i, 0]))
            self.tvec_entries[f"tvec_{i}"].delete(0, "end")
            self.tvec_entries[f"tvec_{i}"].insert(0, str(default_tvec[i, 0]))
        
        self.on_parameter_change()
    
    def on_parameter_change(self, event=None):
        """參數變化時的回調"""
        try:
            self.update_parameters_from_entries()
            self.calculate_transformation()
        except:
            pass  # 輸入不完整時忽略錯誤
    
    def update_parameters_from_entries(self):
        """從輸入框更新參數"""
        # 更新內參矩陣
        self.K[0, 0] = float(self.intrinsic_entries["K_0_0"].get())
        self.K[0, 2] = float(self.intrinsic_entries["K_0_2"].get())
        self.K[1, 1] = float(self.intrinsic_entries["K_1_1"].get())
        self.K[1, 2] = float(self.intrinsic_entries["K_1_2"].get())
        
        # 更新畸變參數
        for i in range(5):
            self.D[i] = float(self.distortion_entries[f"D_{i}"].get())
        
        # 更新外參
        for i in range(3):
            self.rvec[i, 0] = float(self.rvec_entries[f"rvec_{i}"].get())
            self.tvec[i, 0] = float(self.tvec_entries[f"tvec_{i}"].get())
    
    def calculate_transformation(self):
        """計算座標轉換並更新可視化"""
        if len(self.image_coords) == 0:
            self.plot_empty()
            return
        
        try:
            # 計算旋轉矩陣
            R, _ = cv2.Rodrigues(self.rvec)
            
            # 計算反投影世界座標
            transformed_points = []
            for uv in self.image_coords:
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
            if len(self.world_coords) > 0:
                for i in range(len(self.transformed_points)):
                    error = np.linalg.norm(self.world_coords[i, :2] - self.transformed_points[i])
                    errors.append(error)
            
            # 更新可視化
            self.plot_results(errors)
            
        except Exception as e:
            print(f"計算錯誤: {e}")
            self.plot_empty()
    
    def plot_results(self, errors):
        """繪製結果"""
        self.ax.clear()
        
        if len(self.image_coords) == 0:
            self.ax.text(0.5, 0.5, '請添加點位數據', ha='center', va='center', transform=self.ax.transAxes)
            self.canvas.draw()
            return
        
        # 獲取顯示參數
        point_size = self.point_size_slider.get() if hasattr(self, 'point_size_slider') else 100
        line_width = self.line_width_slider.get() if hasattr(self, 'line_width_slider') else 1.0
        
        # 創建顏色映射
        n_points = len(self.image_coords)
        colors = plt.cm.viridis(np.linspace(0, 1, n_points))
        
        # 繪製圖像座標（如果選擇顯示）
        if self.show_image_coords.get():
            # 將圖像座標縮放到合適的範圍進行顯示
            img_coords_scaled = self.image_coords / 10  # 簡單縮放
            self.ax.scatter(img_coords_scaled[:, 0], img_coords_scaled[:, 1],
                           c=colors, s=point_size, marker='o', edgecolor='black', alpha=0.8,
                           label='圖像座標 (縮放)')
        
        # 繪製真實世界座標
        if self.show_world_coords.get() and len(self.world_coords) > 0:
            self.ax.scatter(self.world_coords[:, 0], self.world_coords[:, 1],
                           c=colors, s=point_size, marker='s', edgecolor='black', alpha=0.8,
                           label='真實世界座標')
        
        # 繪製轉換後座標
        if self.show_transformed_coords.get():
            self.ax.scatter(self.transformed_points[:, 0], self.transformed_points[:, 1],
                           c=colors, s=point_size, marker='^', edgecolor='black', alpha=0.8,
                           label='轉換後座標')
        
        # 繪製誤差線
        if self.show_error_lines.get() and len(self.world_coords) > 0 and self.show_world_coords.get() and self.show_transformed_coords.get():
            for i in range(len(self.transformed_points)):
                self.ax.plot([self.world_coords[i, 0], self.transformed_points[i, 0]],
                           [self.world_coords[i, 1], self.transformed_points[i, 1]], 
                           'r--', alpha=0.6, linewidth=line_width)
        
        # 添加點位標籤
        for i, point in enumerate(self.point_data):
            point_id = point[0]
            
            # 圖像座標標籤
            if self.show_image_coords.get():
                img_coords_scaled = self.image_coords[i] / 10
                self.ax.annotate(f'I{point_id}', 
                               (img_coords_scaled[0], img_coords_scaled[1]),
                               xytext=(5, 5), textcoords='offset points', fontsize=8, color='green')
            
            # 世界座標標籤
            if self.show_world_coords.get() and len(self.world_coords) > 0:
                self.ax.annotate(f'W{point_id}', 
                               (self.world_coords[i, 0], self.world_coords[i, 1]),
                               xytext=(5, 5), textcoords='offset points', fontsize=8, color='blue')
            
            # 轉換座標標籤
            if self.show_transformed_coords.get():
                self.ax.annotate(f'T{point_id}', 
                               (self.transformed_points[i, 0], self.transformed_points[i, 1]),
                               xytext=(5, 5), textcoords='offset points', fontsize=8, color='orange')
        
        self.ax.set_title('座標轉換結果對比', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('X (mm)')
        self.ax.set_ylabel('Y (mm)')
        self.ax.legend()
        self.ax.grid(True, alpha=0.3)
        self.ax.axis('equal')
        
        # 更新誤差信息
        if errors:
            mean_error = np.mean(errors)
            max_error = np.max(errors)
            min_error = np.min(errors)
            std_error = np.std(errors)
            error_text = f"平均誤差: {mean_error:.2f} mm | 最大誤差: {max_error:.2f} mm | 最小誤差: {min_error:.2f} mm | 標準差: {std_error:.2f} mm"
            self.error_label.configure(text=error_text)
        else:
            self.error_label.configure(text="無誤差數據")
        
        self.canvas.draw()
    
    def plot_empty(self):
        """繪製空圖表"""
        self.ax.clear()
        self.ax.text(0.5, 0.5, '請添加點位數據\n或檢查參數設置', 
                    ha='center', va='center', transform=self.ax.transAxes,
                    fontsize=12)
        self.ax.set_title('座標轉換結果對比')
        self.canvas.draw()
        self.error_label.configure(text="")
    
    def import_csv(self):
        """導入CSV點位數據"""
        file_path = filedialog.askopenfilename(
            title="選擇CSV文件",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                df = pd.read_csv(file_path)
                
                # 嘗試不同的列名格式
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
                    self.update_coordinate_arrays()
                    self.calculate_transformation()
                    messagebox.showinfo("成功", f"成功導入 {len(df)} 個點位！")
                else:
                    messagebox.showerror("錯誤", "CSV文件格式不正確！\n需要包含: id, image_x, image_y, world_x, world_y")
                    
            except Exception as e:
                messagebox.showerror("錯誤", f"導入失敗: {str(e)}")
    
    def import_npy(self):
        """導入NPY數據"""
        corner_file = filedialog.askopenfilename(
            title="選擇角點數據文件 (corner_points.npy)",
            filetypes=[("NPY files", "*.npy"), ("All files", "*.*")]
        )
        
        if corner_file:
            world_file = filedialog.askopenfilename(
                title="選擇世界座標數據文件 (world_points.npy)",
                filetypes=[("NPY files", "*.npy"), ("All files", "*.*")]
            )
            
            if world_file:
                try:
                    corner_data = np.load(corner_file)  # [id, x, y]
                    world_data = np.load(world_file)    # [id, x, y]
                    
                    # 轉為字典
                    corner_dict = {int(row[0]): row[1:] for row in corner_data}
                    world_dict = {int(row[0]): row[1:] for row in world_data}
                    
                    # 找共同點
                    common_ids = sorted(set(corner_dict.keys()) & set(world_dict.keys()))
                    
                    # 添加點位
                    added_count = 0
                    for point_id in common_ids:
                        if not any(p[0] == point_id for p in self.point_data):
                            self.point_data.append([
                                point_id,
                                float(corner_dict[point_id][0]),
                                float(corner_dict[point_id][1]),
                                float(world_dict[point_id][0]),
                                float(world_dict[point_id][1])
                            ])
                            added_count += 1
                    
                    self.update_points_display()
                    self.update_coordinate_arrays()
                    self.calculate_transformation()
                    messagebox.showinfo("成功", f"成功導入 {added_count} 個點位！")
                    
                except Exception as e:
                    messagebox.showerror("錯誤", f"導入失敗: {str(e)}")
    
    def export_params(self):
        """導出參數"""
        file_path = filedialog.asksaveasfilename(
            title="保存參數文件",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                params = {
                    "intrinsic_matrix": self.K.tolist(),
                    "distortion_coefficients": self.D.tolist(),
                    "rotation_vector": self.rvec.tolist(),
                    "translation_vector": self.tvec.tolist(),
                    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(params, f, indent=4, ensure_ascii=False)
                
                messagebox.showinfo("成功", "參數導出成功！")
                
            except Exception as e:
                messagebox.showerror("錯誤", f"導出失敗: {str(e)}")
    
    def export_points(self):
        """導出點位數據"""
        if not self.point_data:
            messagebox.showwarning("警告", "沒有點位數據可導出！")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="保存點位數據",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                df = pd.DataFrame(self.point_data, 
                                columns=['id', 'image_x', 'image_y', 'world_x', 'world_y'])
                df.to_csv(file_path, index=False)
                messagebox.showinfo("成功", "點位數據導出成功！")
                
            except Exception as e:
                messagebox.showerror("錯誤", f"導出失敗: {str(e)}")
    
    def run(self):
        """運行應用"""
        self.root.mainloop()

# 使用範例
if __name__ == "__main__":
    # 創建並運行應用
    app = CameraCalibrationTool()
    app.run()