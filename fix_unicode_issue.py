#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import socket
import time
import subprocess
import psutil
from pymodbus.client import ModbusTcpClient
import serial.tools.list_ports

class DobotM1Diagnostic:
    """DobotM1專案診斷工具 - 修正版本"""
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        # 修正: 確保專案根目錄正確
        self.project_root = os.path.dirname(self.script_dir)
        
        # 驗證專案根目錄
        if not os.path.basename(self.project_root) == 'DobotM1Project':
            # 如果不在正確位置，嘗試向上查找
            current = os.path.dirname(os.path.abspath(__file__))
            while current and os.path.basename(current) != 'DobotM1Project':
                current = os.path.dirname(current)
            if current:
                self.project_root = current
        
        print(f"檢測到的專案根目錄: {self.project_root}")
        
        # 模組配置
        self.modules = {
            'ModbusTCP_Server': 'ModbusServer/TCPServer.py',
            'CCD1': 'Automation/CCD1/CCD1VisionCode_Enhanced.py',
            'CCD3': 'Automation/CCD3/CCD3AngleDetection.py',
            'Gripper': 'Automation/Gripper/Gripper.py',
            'LED': 'Automation/light/LED_main.py',
            'VP': 'Automation/VP/VP_main.py',
            'XC100': 'Automation/XC100/XCModule.py',
            'Gripper_app': 'Automation/Gripper/Gripper_app.py',
            'LED_app': 'Automation/light/LED_app.py',
            'VP_app': 'Automation/VP/VP_app.py',
            'XC_app': 'Automation/XC100/XCApp.py'
        }
        
        # 端口配置
        self.ports = {
            'ModbusTCP_Server': 502,
            'CCD1': 5051,
            'CCD3': 5052,
            'VP_app': 5053,
            'Gripper_app': 5054,
            'XC_app': 5007,
            'LED_app': 5008
        }
        
        # 配置檔案路徑
        self.configs = {
            'Gripper': 'Automation/Gripper/gripper_config.json',
            'LED': 'Automation/light/led_config.json',
            'VP': 'Automation/VP/vp_config.json',
            'XC100': 'Automation/XC100/xc_module_config.json'
        }
        
        # Modbus基地址
        self.modbus_addresses = {
            'CCD1': 200,
            'VP': 300,
            'Gripper': 500,
            'LED': 600,
            'XC100': 1000
        }
    
    def print_header(self, title):
        """打印標題"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)
    
    def print_section(self, title):
        """打印章節"""
        print(f"\n--- {title} ---")
    
    def check_file_exists(self, relative_path):
        """檢查檔案是否存在"""
        full_path = os.path.join(self.project_root, relative_path)
        return os.path.exists(full_path), full_path
    
    def check_port_status(self, port, timeout=1):
        """檢查端口狀態"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                result = s.connect_ex(('127.0.0.1', port))
                return result == 0
        except Exception:
            return False
    
    def check_process_running(self, script_name):
        """檢查程序是否運行"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if script_name in cmdline and 'python' in cmdline.lower():
                        return True, proc.info['pid']
            return False, None
        except Exception:
            return False, None
    
    def test_modbus_connection(self, port=502, address=200, timeout=3):
        """測試Modbus連接 - 修正PyModbus 3.9.2語法"""
        try:
            client = ModbusTcpClient('127.0.0.1', port=port)
            
            if client.connect():
                print(f"    ✅ ModbusTCP連接成功 (端口 {port})")
                
                # 修正: 使用PyModbus 3.9.2正確語法
                try:
                    result = client.read_holding_registers(address=address, count=1, slave=1)
                    if result.isError():
                        print(f"    ⚠️  寄存器讀取失敗 (地址 {address}): {result}")
                    else:
                        print(f"    ✅ 寄存器讀取成功 (地址 {address}): {result.registers}")
                except Exception as e:
                    print(f"    ⚠️  寄存器讀取異常 (地址 {address}): {e}")
                
                client.close()
                return True
            else:
                print(f"    ❌ ModbusTCP連接失敗 (端口 {port})")
                return False
        except Exception as e:
            print(f"    ❌ ModbusTCP連接異常: {e}")
            return False
    
    def scan_com_ports(self):
        """掃描COM口"""
        try:
            ports = serial.tools.list_ports.comports()
            return [(port.device, port.description) for port in ports]
        except Exception:
            return []
    
    def read_config_file(self, config_path):
        """讀取配置檔案"""
        try:
            full_path = os.path.join(self.project_root, config_path)
            if not os.path.exists(full_path):
                return None, f"配置檔案不存在: {full_path}"
            
            with open(full_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config, None
        except Exception as e:
            return None, f"讀取失敗: {e}"
    
    def check_led_module_connectivity(self):
        """專門檢查LED模組連接狀態"""
        self.print_section("LED模組詳細檢查")
        
        # 1. 檢查LED_main.py是否運行
        is_main_running, main_pid = self.check_process_running('LED_main.py')
        print(f"  LED_main.py: {'✅ 運行中' if is_main_running else '❌ 停止'} {f'(PID: {main_pid})' if main_pid else ''}")
        
        # 2. 檢查LED_app.py是否運行
        is_app_running, app_pid = self.check_process_running('LED_app.py')
        print(f"  LED_app.py: {'✅ 運行中' if is_app_running else '❌ 停止'} {f'(PID: {app_pid})' if app_pid else ''}")
        
        # 3. 檢查端口5008
        port_5008_active = self.check_port_status(5008)
        print(f"  端口5008: {'✅ 監聽中' if port_5008_active else '❌ 未監聽'}")
        
        # 4. 檢查Modbus連接到LED基地址600
        if self.check_port_status(502):
            print(f"  Modbus連接測試 (基地址600):")
            self.test_modbus_connection(502, 600)
        else:
            print(f"  ❌ ModbusTCP服務器未運行，無法測試")
        
        # 5. 檢查LED配置檔案
        led_config_path = os.path.join(self.project_root, 'Automation/light/led_config.json')
        if os.path.exists(led_config_path):
            print(f"  ✅ LED配置檔案存在: {led_config_path}")
            try:
                with open(led_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                tcp_config = config.get('tcp_server', {})
                serial_config = config.get('serial_connection', {})
                print(f"    TCP設定: {tcp_config.get('host')}:{tcp_config.get('port')}")
                print(f"    串口設定: {serial_config.get('port')} @ {serial_config.get('baudrate')}")
            except Exception as e:
                print(f"  ⚠️  配置檔案讀取失敗: {e}")
        else:
            print(f"  ❌ LED配置檔案不存在: {led_config_path}")
        
        # 6. 總結LED模組狀態
        print(f"\n  LED模組狀態總結:")
        if is_main_running and is_app_running and port_5008_active:
            print(f"    ✅ LED模組運行正常")
            print(f"    💡 可訪問Web介面: http://localhost:5008")
        else:
            print(f"    ⚠️  LED模組存在問題:")
            if not is_main_running:
                print(f"      - LED_main.py未運行")
            if not is_app_running:
                print(f"      - LED_app.py未運行")
            if not port_5008_active:
                print(f"      - Web端口5008未開啟")
    
    def generate_startup_script(self):
        """生成啟動腳本"""
        startup_script = f"""@echo off
echo 啟動DobotM1專案模組...
cd /d "{self.project_root}"

echo 1. 啟動ModbusTCP服務器...
start "ModbusTCP Server" python ModbusServer/TCPServer.py

timeout /t 3

echo 2. 啟動LED主模組...
start "LED Main" python Automation/light/LED_main.py

timeout /t 2

echo 3. 啟動LED Web應用...
start "LED App" python Automation/light/LED_app.py

echo 啟動完成！
echo Web介面: http://localhost:5008
pause
"""
        
        script_path = os.path.join(self.script_dir, 'start_led_modules.bat')
        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(startup_script)
            print(f"  ✅ 已生成啟動腳本: {script_path}")
            return script_path
        except Exception as e:
            print(f"  ❌ 生成啟動腳本失敗: {e}")
            return None
    
    def run_diagnosis(self):
        """執行完整診斷"""
        self.print_header("DobotM1專案啟動狀態診斷 - 修正版")
        
        # 1. 環境檢查
        self.print_section("1. 環境檢查")
        print(f"Python版本: {sys.version}")
        print(f"工作目錄: {os.getcwd()}")
        print(f"專案根目錄: {self.project_root}")
        print(f"診斷腳本位置: {self.script_dir}")
        
        # 驗證專案根目錄
        if os.path.basename(self.project_root) != 'DobotM1Project':
            print(f"⚠️  專案根目錄可能不正確")
        else:
            print(f"✅ 專案根目錄正確")
        
        # 2. 檔案存在性檢查
        self.print_section("2. 模組檔案檢查")
        missing_files = []
        existing_files = []
        for name, path in self.modules.items():
            exists, full_path = self.check_file_exists(path)
            status = "✅" if exists else "❌"
            print(f"  {status} {name}: {path}")
            if not exists:
                missing_files.append((name, path, full_path))
            else:
                existing_files.append((name, path))
        
        if missing_files:
            print(f"\n⚠️  缺失檔案: {len(missing_files)}個")
            for name, path, full_path in missing_files:
                print(f"    - {name}: {full_path}")
        
        if existing_files:
            print(f"\n✅ 存在檔案: {len(existing_files)}個")
        
        # 3. 程序運行狀態檢查
        self.print_section("3. 程序運行狀態檢查")
        running_processes = []
        for name, script_path in self.modules.items():
            script_name = os.path.basename(script_path)
            is_running, pid = self.check_process_running(script_name)
            status = "✅ 運行中" if is_running else "❌ 停止"
            pid_info = f" (PID: {pid})" if pid else ""
            print(f"  {status} {name}: {script_name}{pid_info}")
            if is_running:
                running_processes.append((name, pid))
        
        if running_processes:
            print(f"\n✅ 運行中的程序: {len(running_processes)}個")
        
        # 4. 端口狀態檢查
        self.print_section("4. 端口狀態檢查")
        occupied_ports = []
        for name, port in self.ports.items():
            is_occupied = self.check_port_status(port)
            status = "✅ 監聽中" if is_occupied else "❌ 未使用"
            print(f"  {status} {name}: 端口 {port}")
            if is_occupied:
                occupied_ports.append((name, port))
        
        if occupied_ports:
            print(f"\n✅ 監聽中的端口: {len(occupied_ports)}個")
        
        # 5. ModbusTCP服務器檢查
        self.print_section("5. ModbusTCP服務器檢查")
        tcp_server_running = self.check_port_status(502)
        if tcp_server_running:
            print("  ✅ ModbusTCP服務器正在運行 (端口 502)")
            
            # 測試各模組的Modbus連接
            print("\n  測試各模組Modbus基地址:")
            for module, address in self.modbus_addresses.items():
                print(f"    {module} (基地址 {address}):")
                self.test_modbus_connection(502, address)
        else:
            print("  ❌ ModbusTCP服務器未運行")
        
        # 6. LED模組專項檢查
        self.check_led_module_connectivity()
        
        # 7. COM口檢查
        self.print_section("7. COM口檢查")
        com_ports = self.scan_com_ports()
        if com_ports:
            print(f"  可用COM口 ({len(com_ports)}個):")
            for device, description in com_ports:
                print(f"    - {device}: {description}")
        else:
            print("  ❌ 未檢測到COM口")
        
        # 8. 問題分析與建議
        self.print_section("8. 問題分析與建議")
        
        # 檢查啟動腳本路徑問題
        start_script = os.path.join(self.script_dir, 'start.py')
        if os.path.exists(start_script):
            print(f"  啟動腳本分析:")
            print(f"    腳本位置: {start_script}")
            
            # 分析start.py中的專案根目錄設定
            try:
                with open(start_script, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)' in content:
                        print(f"    ⚠️  發現問題: start.py中的PROJECT_ROOT設定可能不正確")
                        print(f"    建議修改: 確保PROJECT_ROOT指向DobotM1Project目錄")
            except Exception as e:
                print(f"    ❌ 無法分析start.py: {e}")
        
        # 生成修正建議
        if missing_files and not existing_files:
            print(f"\n  🔧 修正建議:")
            print(f"    1. 檢查start.py中的專案根目錄路徑設定")
            print(f"    2. 確保start.py在正確的目錄下執行")
            print(f"    3. 當前期望的專案結構:")
            print(f"       {self.project_root}/")
            print(f"       ├── ModbusServer/TCPServer.py")
            print(f"       ├── Automation/light/LED_main.py")
            print(f"       └── start/start.py")
        
        # 生成啟動腳本
        self.print_section("9. 生成啟動腳本")
        startup_script_path = self.generate_startup_script()
        
        self.print_header("診斷完成")

def main():
    """主函數"""
    diagnostic = DobotM1Diagnostic()
    diagnostic.run_diagnosis()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n診斷中斷")
    except Exception as e:
        print(f"\n診斷異常: {e}")
        import traceback
        traceback.print_exc()