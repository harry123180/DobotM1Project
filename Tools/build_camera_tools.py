#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相機標定工具自動化建置腳本
用於將內參和外參標定工具打包成可執行檔案
"""

import os
import sys
import shutil
import subprocess
import zipfile
from pathlib import Path

def check_requirements():
    """檢查建置需求"""
    print("🔍 檢查建置環境...")
    
    # 檢查 Python 版本
    if sys.version_info < (3, 7):
        print("❌ 需要 Python 3.7 或更高版本")
        return False
    
    # 檢查必要檔案
    required_files = [
        '內參棋盤格計算可視化工具.py',
        '外參標定可視化工具.py'
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ 缺少必要檔案: {file}")
            return False
    
    print("✅ 建置環境檢查通過")
    return True

def install_dependencies():
    """安裝建置依賴"""
    print("📦 安裝建置依賴...")
    
    dependencies = [
        'pyinstaller>=5.0',
        'customtkinter>=5.0.0',
        'opencv-python>=4.5.0',
        'numpy>=1.20.0',
        'matplotlib>=3.3.0',
        'pillow>=8.0.0',
        'pandas>=1.3.0'
    ]
    
    for dep in dependencies:
        print(f"安裝 {dep}...")
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', dep], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ 安裝 {dep} 失敗")
            print(result.stderr)
            return False
    
    print("✅ 依賴安裝完成")
    return True

def create_directories():
    """創建必要的目錄結構"""
    print("📁 創建目錄結構...")
    
    directories = [
        'build',
        'dist'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    print("✅ 目錄結構創建完成")

def convert_icon():
    """處理圖示檔案（使用 CustomTkinter 預設圖示）"""
    print("🎨 使用 CustomTkinter 預設圖示...")
    print("✅ 圖示設定完成")
    return True

def create_individual_specs():
    """創建個別的 spec 檔案"""
    print("📝 創建 PyInstaller 規格檔案...")
    
    # 內參工具 spec
    intrinsic_spec = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['內參棋盤格計算可視化工具.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'cv2',
        'numpy',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.figure',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'threading',
        'datetime',
        'glob',
        'os'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='相機內參標定工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 使用 CustomTkinter 預設圖示
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='相機內參標定工具'
)
'''
    
    # 外參工具 spec
    extrinsic_spec = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['外參標定可視化工具.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'numpy',
        'cv2',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.cm',
        'matplotlib.colors',
        'matplotlib.backends.backend_tkagg',
        'matplotlib.figure',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'json',
        'pandas',
        'datetime',
        'platform'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='相機外參標定工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None  # 使用 CustomTkinter 預設圖示
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='相機外參標定工具'
)
'''
    
    # 保存 spec 檔案
    with open('intrinsic_tool.spec', 'w', encoding='utf-8') as f:
        f.write(intrinsic_spec)
    
    with open('extrinsic_tool.spec', 'w', encoding='utf-8') as f:
        f.write(extrinsic_spec)
    
    print("✅ PyInstaller 規格檔案創建完成")

def build_tools():
    """建置工具"""
    print("🔨 開始建置可執行檔...")
    
    # 清理舊的建置檔案
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    
    tools = [
        ('intrinsic_tool.spec', '內參標定工具'),
        ('extrinsic_tool.spec', '外參標定工具')
    ]
    
    success_count = 0
    
    for spec_file, tool_name in tools:
        print(f"\n🔧 建置 {tool_name}...")
        
        cmd = [
            sys.executable, '-m', 'PyInstaller',
            '--clean',
            '--noconfirm',
            spec_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ {tool_name} 建置成功")
            success_count += 1
        else:
            print(f"❌ {tool_name} 建置失敗")
            print(result.stderr)
    
    return success_count == len(tools)

def create_launcher():
    """創建啟動器"""
    print("📋 創建工具啟動器...")
    
    launcher_script = '''#!/usr/bin/env python3
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
'''
    
    with open('tool_launcher.py', 'w', encoding='utf-8') as f:
        f.write(launcher_script)
    
    print("✅ 工具啟動器創建完成")

def create_deployment_package():
    """創建部署包"""
    print("📦 創建部署包...")
    
    try:
        # 創建部署目錄
        deploy_dir = "CameraCalibrationTools"
        if os.path.exists(deploy_dir):
            shutil.rmtree(deploy_dir)
        os.makedirs(deploy_dir)
        
        # 複製工具
        if os.path.exists("dist/相機內參標定工具"):
            shutil.copytree("dist/相機內參標定工具", f"{deploy_dir}/相機內參標定工具")
        
        if os.path.exists("dist/相機外參標定工具"):
            shutil.copytree("dist/相機外參標定工具", f"{deploy_dir}/相機外參標定工具")
        
        # 複製啟動器
        if os.path.exists("tool_launcher.py"):
            shutil.copy2("tool_launcher.py", deploy_dir)
        
        # 不需要複製圖示檔案，使用 CustomTkinter 預設圖示
        
        # 創建說明文件
        create_readme(deploy_dir)
        
        # 創建批次檔案
        create_batch_files(deploy_dir)
        
        # 創建壓縮包
        zip_filename = "CameraCalibrationTools_v1.0.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(deploy_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, ".")
                    zipf.write(file_path, arcname)
        
        file_size = os.path.getsize(zip_filename) / (1024 * 1024)  # MB
        print(f"✅ 部署包創建完成: {zip_filename} ({file_size:.1f} MB)")
        
        return True
        
    except Exception as e:
        print(f"❌ 創建部署包失敗: {e}")
        return False

def create_readme(deploy_dir):
    """創建說明文件"""
    readme_content = '''# 相機標定工具套件

## 工具概述

本套件包含兩個相機標定工具：

### 📐 內參標定工具
- **功能**：使用棋盤格圖像計算相機內參矩陣和畸變係數
- **檔案**：相機內參標定工具/相機內參標定工具.exe
- **用途**：相機初次標定，獲得基本參數

### 🎯 外參標定工具  
- **功能**：調整相機外參矩陣，實現圖像座標到世界座標轉換
- **檔案**：相機外參標定工具/相機外參標定工具.exe
- **用途**：精確定位，座標系轉換

## 快速開始

### 方法一：使用啟動器（推薦）
1. 執行 `啟動工具套件.bat`
2. 在啟動器中選擇需要的工具

### 方法二：直接啟動
1. 內參標定：執行 `相機內參標定工具.bat`
2. 外參標定：執行 `相機外參標定工具.bat`

## 使用流程

### 第一步：內參標定
1. 準備棋盤格標定板（建議A4列印）
2. 拍攝10-20張不同角度的棋盤格圖像
3. 啟動內參標定工具
4. 導入圖像並檢測角點
5. 執行標定並導出結果

### 第二步：外參標定
1. 在目標平面設置已知座標的標記點
2. 拍攝包含標記點的圖像
3. 啟動外參標定工具
4. 導入內參標定結果
5. 輸入對應點座標
6. 調整外參矩陣

## 系統需求

- **作業系統**：Windows 10/11 (64-bit)
- **記憶體**：最少 4GB RAM
- **磁碟空間**：500MB 可用空間
- **顯示**：1280x720 或更高解析度

## 檔案格式支援

### 圖像格式
- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)

### 數據格式
- NumPy (.npy) - 相機參數
- JSON (.json) - 參數和設定
- CSV (.csv) - 點位數據

## 故障排除

### 常見問題

1. **工具無法啟動**
   - 確認是否有足夠的記憶體
   - 檢查防毒軟體是否阻擋
   - 嘗試以管理員權限執行

2. **角點檢測失敗**
   - 確認棋盤格圖像清晰
   - 檢查棋盤格尺寸設定
   - 嘗試不同的圖像

3. **座標轉換精度不佳**
   - 增加標定點數量
   - 確認點位對應關係正確
   - 重新檢查內參標定結果

## 技術支援

如遇問題請檢查：
1. 系統需求是否滿足
2. 輸入數據是否正確
3. 工具日誌檔案（如有）

---

© 2024 相機標定工具套件 v1.0
'''
    
    with open(os.path.join(deploy_dir, "README.md"), 'w', encoding='utf-8') as f:
        f.write(readme_content)

def create_batch_files(deploy_dir):
    """創建批次檔案"""
    
    # 啟動器批次檔
    launcher_bat = '''@echo off
title 相機標定工具套件
cd /d "%~dp0"
echo 正在啟動相機標定工具套件...
python tool_launcher.py
if errorlevel 1 (
    echo.
    echo Python 未安裝或啟動失敗，請確認：
    echo 1. 已安裝 Python 3.7+
    echo 2. Python 已添加到系統路徑
    echo.
    pause
)
'''
    
    # 內參工具批次檔
    intrinsic_bat = '''@echo off
title 相機內參標定工具
cd /d "%~dp0\\相機內參標定工具"
echo 正在啟動內參標定工具...
start "" "相機內參標定工具.exe"
'''
    
    # 外參工具批次檔
    extrinsic_bat = '''@echo off
title 相機外參標定工具
cd /d "%~dp0\\相機外參標定工具"
echo 正在啟動外參標定工具...
start "" "相機外參標定工具.exe"
'''
    
    # 保存批次檔案
    with open(os.path.join(deploy_dir, "啟動工具套件.bat"), 'w', encoding='utf-8') as f:
        f.write(launcher_bat)
    
    with open(os.path.join(deploy_dir, "相機內參標定工具.bat"), 'w', encoding='utf-8') as f:
        f.write(intrinsic_bat)
    
    with open(os.path.join(deploy_dir, "相機外參標定工具.bat"), 'w', encoding='utf-8') as f:
        f.write(extrinsic_bat)

def main():
    """主建置流程"""
    print("🚀 相機標定工具建置工具")
    print("=" * 50)
    
    # 檢查環境
    if not check_requirements():
        return False
    
    # 安裝依賴
    if not install_dependencies():
        return False
    
    # 創建目錄
    create_directories()
    
    # 轉換圖示
    convert_icon()
    
    # 創建規格檔案
    create_individual_specs()
    
    # 建置工具
    if not build_tools():
        return False
    
    # 創建啟動器
    create_launcher()
    
    # 創建部署包
    if not create_deployment_package():
        return False
    
    print("\n🎉 建置完成！")
    print("📁 部署目錄: CameraCalibrationTools/")
    print("📦 部署包: CameraCalibrationTools_v1.0.zip")
    print("🌐 使用方式: 解壓縮後執行 啟動工具套件.bat")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n❌ 建置失敗，請檢查錯誤訊息")
        input("按 Enter 鍵退出...")
        sys.exit(1)
    else:
        print("\n✅ 建置成功！")
        input("按 Enter 鍵退出...")
        sys.exit(0)