#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相機標定工具啟動器
Camera Calibration Tools Launcher
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import sys
from pathlib import Path

class ToolLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("相機標定工具套件 - Camera Calibration Tools")
        self.root.geometry("600x400")
        self.root.resizable(False, False)
        
        # 設置圖示（使用 CustomTkinter 預設圖示）
        # CustomTkinter 有自己的預設圖示，不需要額外設定
        
        self.setup_ui()
        
    def setup_ui(self):
        """設置使用者介面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill="both", expand=True)
        
        # 標題
        title_label = ttk.Label(
            main_frame, 
            text="相機標定工具套件",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        subtitle_label = ttk.Label(
            main_frame, 
            text="Camera Calibration Tools Suite",
            font=("Arial", 12)
        )
        subtitle_label.pack(pady=(0, 30))
        
        # 工具選項框架
        tools_frame = ttk.LabelFrame(main_frame, text="選擇工具", padding="15")
        tools_frame.pack(fill="x", pady=(0, 20))
        
        # 內參標定工具
        intrinsic_frame = ttk.Frame(tools_frame)
        intrinsic_frame.pack(fill="x", pady=5)
        
        ttk.Label(
            intrinsic_frame, 
            text="📐 內參標定工具",
            font=("Arial", 12, "bold")
        ).pack(anchor="w")
        
        ttk.Label(
            intrinsic_frame, 
            text="使用棋盤格圖像計算相機內參矩陣和畸變係數",
            font=("Arial", 10)
        ).pack(anchor="w", padx=(20, 0))
        
        ttk.Button(
            intrinsic_frame,
            text="啟動內參標定工具",
            command=self.launch_intrinsic_tool,
            width=25
        ).pack(anchor="e", pady=5)
        
        # 分隔線
        ttk.Separator(tools_frame, orient="horizontal").pack(fill="x", pady=10)
        
        # 外參標定工具
        extrinsic_frame = ttk.Frame(tools_frame)
        extrinsic_frame.pack(fill="x", pady=5)
        
        ttk.Label(
            extrinsic_frame, 
            text="🎯 外參標定工具",
            font=("Arial", 12, "bold")
        ).pack(anchor="w")
        
        ttk.Label(
            extrinsic_frame, 
            text="調整相機外參矩陣，實現圖像座標到世界座標轉換",
            font=("Arial", 10)
        ).pack(anchor="w", padx=(20, 0))
        
        ttk.Button(
            extrinsic_frame,
            text="啟動外參標定工具",
            command=self.launch_extrinsic_tool,
            width=25
        ).pack(anchor="e", pady=5)
        
        # 說明框架
        info_frame = ttk.LabelFrame(main_frame, text="使用說明", padding="15")
        info_frame.pack(fill="both", expand=True)
        
        info_text = """
使用流程建議：

1. 內參標定：
   • 拍攝多張不同角度的棋盤格圖像（建議10-20張）
   • 使用內參標定工具自動檢測棋盤格角點
   • 計算並導出相機內參矩陣和畸變係數

2. 外參標定：
   • 在目標平面上設置已知世界座標的標記點
   • 拍攝包含這些標記點的圖像
   • 使用外參標定工具匹配圖像座標和世界座標
   • 調整外參矩陣實現準確的座標轉換

注意：建議先完成內參標定，再使用得到的內參進行外參標定。
        """
        
        info_label = ttk.Label(
            info_frame, 
            text=info_text,
            font=("Arial", 9),
            justify="left"
        )
        info_label.pack(anchor="w")
        
        # 底部按鈕框架
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=(20, 0))
        
        ttk.Button(
            bottom_frame,
            text="退出",
            command=self.root.quit,
            width=15
        ).pack(side="right")
        
        ttk.Button(
            bottom_frame,
            text="關於",
            command=self.show_about,
            width=15
        ).pack(side="right", padx=(0, 10))
        
    def launch_intrinsic_tool(self):
        """啟動內參標定工具"""
        tool_path = Path("相機內參標定工具") / "相機內參標定工具.exe"
        if tool_path.exists():
            try:
                subprocess.Popen([str(tool_path)], cwd=tool_path.parent)
                messagebox.showinfo("啟動", "內參標定工具已啟動")
            except Exception as e:
                messagebox.showerror("錯誤", f"啟動失敗: {e}")
        else:
            messagebox.showerror("錯誤", f"找不到工具: {tool_path}")
    
    def launch_extrinsic_tool(self):
        """啟動外參標定工具"""
        tool_path = Path("相機外參標定工具") / "相機外參標定工具.exe"
        if tool_path.exists():
            try:
                subprocess.Popen([str(tool_path)], cwd=tool_path.parent)
                messagebox.showinfo("啟動", "外參標定工具已啟動")
            except Exception as e:
                messagebox.showerror("錯誤", f"啟動失敗: {e}")
        else:
            messagebox.showerror("錯誤", f"找不到工具: {tool_path}")
    
    def show_about(self):
        """顯示關於對話框"""
        about_text = """
相機標定工具套件 v1.0

包含工具：
• 內參標定工具 - 計算相機內參和畸變係數
• 外參標定工具 - 調整外參實現座標轉換

技術特點：
• 支援自動棋盤格角點檢測
• 多種PnP算法可選
• 實時可視化調整
• 完整的數據導入導出功能

開發環境：
• Python + OpenCV + CustomTkinter
• Matplotlib 可視化
• NumPy 數值計算

© 2024 相機標定工具套件
        """
        messagebox.showinfo("關於", about_text)
    
    def run(self):
        """運行應用"""
        self.root.mainloop()

if __name__ == "__main__":
    app = ToolLauncher()
    app.run()
